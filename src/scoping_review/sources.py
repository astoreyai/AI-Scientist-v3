"""Bibliographic source adapters for the scoping-review search (board node P4.01).

Ported from glp1_brca/survivorship/search/multi_source_search.py (PubMed, Europe PMC, OpenAlex,
Semantic Scholar, Crossref) with arXiv added. Each adapter returns raw dicts with the same keys;
`records.normalize` turns them into `record.schema.json` objects. Network failures are reported,
never papered over: an adapter that fails returns what it fetched plus an error string.

Embase, CINAHL, PsycINFO, Scopus, Web of Science, IEEE Xplore and ACM DL need institutional access;
their exports are imported as files (`agsci sr import`), not fetched here.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

TOOL = "agsci-sr"
# Polite-pool contact for OpenAlex/Crossref/NCBI; sent only when the operator sets it.
CONTACT = os.environ.get("AGSCI_CONTACT_EMAIL", "")
# Without a key OpenAlex allows a small free daily budget per IP address (about 100 searches).
OPENALEX_KEY = os.environ.get("OPENALEX_API_KEY", "")
UA = {"User-Agent": f"{TOOL}/1.0" + (f" (mailto:{CONTACT})" if CONTACT else "")}


class FetchError(RuntimeError):
    pass


class NotFound(FetchError):
    pass


def _get(url: str, timeout: int = 60, tries: int = 3) -> bytes:
    if OPENALEX_KEY and url.startswith("https://api.openalex.org/") and "api_key=" not in url:
        url += ("&" if "?" in url else "?") + "api_key=" + urllib.parse.quote(OPENALEX_KEY)
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NotFound(f"not found: {url.split('api_key=')[0][:120]}") from e
            last = e
            # 429/503 are rate limits: honor Retry-After, else back off far longer than for faults
            wait = int(e.headers.get("Retry-After", "0") or 0) if e.code in (429, 503) else 0
            if wait > 300:  # a daily budget, not a burst limit: waiting hours inside a run is a hang
                raise FetchError(f"rate limited for {wait // 3600}h{wait % 3600 // 60:02d}m by {url.split('/')[2]}"
                                 + ("; set OPENALEX_API_KEY" if "openalex" in url and not OPENALEX_KEY else "")) from e
            time.sleep(wait or (15 * (i + 1) if e.code in (429, 503) else 1.5 * (i + 1)))
        except Exception as e:  # network errors of every kind are retried, then surfaced
            last = e
            time.sleep(1.5 * (i + 1))
    raise FetchError(f"GET failed after {tries} tries: {last} ({url.split('api_key=')[0][:120]})")


def _contact(params: dict, key: str) -> dict:
    return {**params, key: CONTACT} if CONTACT else params


def _oa(params: dict) -> dict:
    """OpenAlex query parameters (the API key, when set, is added by _get for every OpenAlex URL)."""
    return _contact(params, "mailto")


def pubmed(query: str, cap: int, since: str = "") -> list[dict]:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    p = _contact({"db": "pubmed", "term": query, "retmode": "json", "retmax": cap, "tool": TOOL}, "email")
    if since:  # Entrez date (when the record entered PubMed)
        p |= {"datetype": "edat", "mindate": since.replace("-", "/"), "maxdate": "3000"}
    ids = json.loads(_get(base + "esearch.fcgi?" + urllib.parse.urlencode(p)))["esearchresult"]["idlist"]
    out = []
    for i in range(0, len(ids), 150):
        p = _contact({"db": "pubmed", "id": ",".join(ids[i:i + 150]), "retmode": "xml", "tool": TOOL}, "email")
        for art in ET.fromstring(_get(base + "efetch.fcgi?" + urllib.parse.urlencode(p), timeout=120)).findall(".//PubmedArticle"):
            out.append({
                "source": "pubmed",
                "pmid": art.findtext(".//PMID") or "",
                "doi": next((x.text for x in art.findall(".//ArticleId") if x.get("IdType") == "doi"), "") or "",
                "title": "".join(art.find(".//ArticleTitle").itertext()) if art.find(".//ArticleTitle") is not None else "",
                "abstract": " ".join("".join(a.itertext()) for a in art.findall(".//Abstract/AbstractText")),
                "year": art.findtext(".//JournalIssue/PubDate/Year") or "",
                "venue": art.findtext(".//Journal/ISOAbbreviation") or "",
                "authors": [f"{a.findtext('LastName')} {a.findtext('Initials') or ''}".strip()
                            for a in art.findall(".//Author") if a.findtext("LastName")],
            })
        time.sleep(0.34)
    return out


def europepmc(query: str, cap: int, since: str = "") -> list[dict]:
    base = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    out, cursor = [], "*"
    if since:
        query = f"({query}) AND FIRST_PDATE:[{since} TO 3000-01-01]"
    while len(out) < cap:
        p = {"query": query, "format": "json", "pageSize": min(1000, cap), "cursorMark": cursor, "resultType": "core"}
        d = json.loads(_get(base + "?" + urllib.parse.urlencode(p), timeout=90))
        res = d.get("resultList", {}).get("result", [])
        if not res:
            break
        for r in res:
            out.append({"source": "europepmc", "pmid": r.get("pmid", "") or "", "doi": r.get("doi", "") or "",
                        "title": r.get("title", "") or "", "abstract": re.sub("<[^>]+>", " ", r.get("abstractText", "") or ""),
                        "year": str(r.get("pubYear", "") or ""), "venue": r.get("journalInfo", {}).get("journal", {}).get("isoabbreviation", "") or "",
                        "authors": [a.get("fullName", "") for a in (r.get("authorList", {}) or {}).get("author", [])]})
        nc = d.get("nextCursorMark")
        if not nc or nc == cursor:
            break
        cursor = nc
        time.sleep(0.3)
    return out[:cap]


def _openalex_abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = {i: w for w, idxs in inv.items() for i in idxs}
    return " ".join(pos[i] for i in sorted(pos))


def openalex(query: str, cap: int, since: str = "") -> list[dict]:
    base = "https://api.openalex.org/works"
    out, cursor = [], "*"
    flt = "title_and_abstract.search:" + query + (f",from_publication_date:{since}" if since else "")
    while len(out) < cap and cursor:
        p = _oa({"filter": flt, "per-page": min(200, cap), "cursor": cursor})
        d = json.loads(_get(base + "?" + urllib.parse.urlencode(p), timeout=90))
        res = d.get("results", [])
        if not res:
            break
        for r in res:
            ids = r.get("ids") or {}
            out.append({"source": "openalex", "openalex": (r.get("id") or "").rsplit("/", 1)[-1],
                        "pmid": (ids.get("pmid") or "").rsplit("/", 1)[-1], "doi": r.get("doi") or "",
                        "title": r.get("title") or "", "abstract": _openalex_abstract(r.get("abstract_inverted_index")),
                        "year": str(r.get("publication_year") or ""),
                        "venue": ((r.get("primary_location") or {}).get("source") or {}).get("display_name", "") or "",
                        "authors": [a["author"]["display_name"] for a in r.get("authorships", []) if a.get("author")]})
        cursor = d.get("meta", {}).get("next_cursor")
        time.sleep(0.25)
    return out[:cap]


def semanticscholar(query: str, cap: int, since: str = "") -> list[dict]:
    base = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    out, token = [], None
    while len(out) < cap:
        params = {"query": query, "fields": "title,abstract,year,externalIds,venue,authors"}
        if since:
            params["publicationDateOrYear"] = f"{since}:"
        if token:
            params["token"] = token
        d = json.loads(_get(base + "?" + urllib.parse.urlencode(params), timeout=90))
        for r in d.get("data") or []:
            ext = r.get("externalIds") or {}
            out.append({"source": "semanticscholar", "s2": r.get("paperId", ""), "pmid": str(ext.get("PubMed", "") or ""),
                        "doi": ext.get("DOI", "") or "", "arxiv": ext.get("ArXiv", "") or "", "title": r.get("title") or "",
                        "abstract": r.get("abstract") or "", "year": str(r.get("year") or ""), "venue": r.get("venue") or "",
                        "authors": [a.get("name", "") for a in r.get("authors") or []]})
        token = d.get("token")
        if not token or not d.get("data"):
            break
        time.sleep(1.1)
    return out[:cap]


def crossref(query: str, cap: int, since: str = "") -> list[dict]:
    base = "https://api.crossref.org/works"
    out, cursor = [], "*"
    while len(out) < cap and cursor:
        p = _contact({"query": query, "rows": min(100, cap), "cursor": cursor}, "mailto")
        if since:
            p["filter"] = f"from-pub-date:{since}"
        msg = json.loads(_get(base + "?" + urllib.parse.urlencode(p), timeout=90)).get("message", {})
        items = msg.get("items", [])
        if not items:
            break
        for r in items:
            parts = (r.get("issued") or {}).get("date-parts") or [[None]]
            out.append({"source": "crossref", "doi": r.get("DOI", ""), "title": " ".join(r.get("title") or []),
                        "abstract": re.sub("<[^>]+>", " ", r.get("abstract", "") or ""), "year": str(parts[0][0] or ""),
                        "venue": " ".join(r.get("container-title") or []),
                        "authors": [f"{a.get('family', '')} {a.get('given', '')}".strip() for a in r.get("author", [])]})
        cursor = msg.get("next-cursor")
        time.sleep(0.3)
    return out[:cap]


def arxiv(query: str, cap: int, since: str = "") -> list[dict]:
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    out, start = [], 0
    if since:
        query = f"({query}) AND submittedDate:[{since.replace('-', '')}0000 TO 300001010000]"
    while len(out) < cap:
        p = {"search_query": query, "start": start, "max_results": min(200, cap - len(out))}
        entries = ET.fromstring(_get("https://export.arxiv.org/api/query?" + urllib.parse.urlencode(p), timeout=90)).findall("a:entry", ns)
        if not entries:
            break
        for e in entries:
            out.append({"source": "arxiv", "arxiv": (e.findtext("a:id", "", ns) or "").rsplit("/abs/", 1)[-1].split("v")[0],
                        "doi": e.findtext("x:doi", "", ns) or "", "title": " ".join((e.findtext("a:title", "", ns) or "").split()),
                        "abstract": " ".join((e.findtext("a:summary", "", ns) or "").split()),
                        "year": (e.findtext("a:published", "", ns) or "")[:4], "venue": "arXiv",
                        "authors": [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)]})
        start += len(entries)
        time.sleep(3.0)  # arXiv API terms: one request every 3 seconds
    return out[:cap]


def _same_title(a: str, b: str) -> bool:
    """True when two titles name the same paper: close overall, or one is the other plus a subtitle."""
    from .records import norm_title
    x, y = norm_title(a), norm_title(b)
    return not x or bool(y) and (x.startswith(y) or y.startswith(x) or difflib.SequenceMatcher(None, x, y).ratio() >= 0.6)


def openalex_seed_recall(query: str, seeds: list[dict], since: str = "") -> dict:
    """Exact seed recall for an OpenAlex strategy at any volume: total hit count, and which seeds the
    query matches, found by membership (seed OpenAlex ids AND the query) rather than in a capped download."""
    from .records import norm_title
    base = "https://api.openalex.org/works?"
    def works(flt: str, per: int = 50) -> dict:
        return json.loads(_get(base + urllib.parse.urlencode(_oa({"filter": flt, "per-page": per, "select": "id,doi,title"})), timeout=90))
    date = f",from_publication_date:{since}" if since else ""
    ids, unresolved = {}, []
    for s in seeds:
        wid = ""
        for doi in [d for d in (s.get("doi"), f"10.48550/arxiv.{s['arxiv']}" if s.get("arxiv") else "") if d]:
            res = works("doi:" + doi, 1)["results"]
            # a DOI that resolves to a different title is a wrong DOI in the seed file, not this paper
            if res and _same_title(s.get("raw_title", ""), res[0].get("title") or ""):
                wid = res[0]["id"].rsplit("/", 1)[-1]
                break
        if not wid and s.get("raw_title"):
            clean = re.sub(r"[,:|]", " ", s["raw_title"])  # filter syntax reserves these
            wid = next((w["id"].rsplit("/", 1)[-1] for w in works("title.search:" + clean, 25)["results"]
                        if norm_title(w.get("title") or "") == s["title"]), "")
        if wid:
            ids[s["key"]] = wid
        else:
            unresolved.append(s["key"])
    total = json.loads(_get(base + urllib.parse.urlencode(_oa({"filter": "title_and_abstract.search:" + query + date, "per-page": 1})), timeout=90))["meta"]["count"]
    hit_ids = set()
    if ids:
        res = works("title_and_abstract.search:" + query + date + ",ids.openalex:" + "|".join(ids.values()), 50)["results"]
        hit_ids = {w["id"].rsplit("/", 1)[-1] for w in res}
    found = [k for k, w in ids.items() if w in hit_ids]
    return {"source": "openalex", "hits": total, "capped": False, "seeds": len(seeds), "found": found,
            "missed": [s["key"] for s in seeds if s["key"] not in found], "not_in_openalex": unresolved,
            "recall": len(found) / len(seeds) if seeds else None, "openalex_ids": ids}


ADAPTERS = {"pubmed": pubmed, "europepmc": europepmc, "openalex": openalex,
            "semanticscholar": semanticscholar, "crossref": crossref, "arxiv": arxiv}
