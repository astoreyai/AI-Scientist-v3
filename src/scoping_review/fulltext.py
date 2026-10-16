"""Full-text retrieval, PDF conversion and citation chasing (board nodes P6.01, P6.03, P6.08a),
plus the seed-recall test search (P2.05a). `fetch` is injectable so tests replay recorded responses.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.parse
from pathlib import Path
from typing import Callable

from . import records
from .sources import NotFound, _get

Fetch = Callable[[str], bytes]
OPENALEX = "https://api.openalex.org/works"


def safe(rid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", rid)


def openalex_work(rec: dict, fetch: Fetch = _get) -> dict | None:
    """The OpenAlex work for a record, looked up by DOI, PMID or OpenAlex id."""
    if rec.get("doi"):
        key = f"doi:{rec['doi']}"
    elif rec.get("pmid"):
        key = f"pmid:{rec['pmid']}"
    elif rec["id"].startswith("openalex:"):
        key = rec["id"].split(":", 1)[1]
    else:
        return None
    try:
        return json.loads(fetch(f"{OPENALEX}/{urllib.parse.quote(key, safe=':/')}"))
    except NotFound:  # a record OpenAlex does not know; rate limits and outages still raise
        return None


def pdf_url(rec: dict, fetch: Fetch = _get) -> tuple[str | None, str]:
    if rec["id"].startswith("arxiv:"):
        return f"https://arxiv.org/pdf/{rec['id'].split(':', 1)[1]}", "arxiv"
    work = openalex_work(rec, fetch)
    loc = (work or {}).get("best_oa_location") or {}
    return (loc.get("pdf_url"), "openalex_best_oa") if loc.get("pdf_url") else (None, "no open-access pdf")


def fetch_fulltext(recs: list[dict], out: Path, fetch: Fetch = _get) -> list[dict]:
    """Download open-access PDFs; every record gets a log line, missing ones go to the human (P6.02)."""
    out.mkdir(parents=True, exist_ok=True)
    log = []
    for rec in recs:
        url, how = pdf_url(rec, fetch)
        entry = {"record_id": rec["id"], "url": url, "route": how}
        if url:
            try:
                data = fetch(url)
                if data[:4] != b"%PDF":
                    raise ValueError("response is not a PDF (paywall or landing page)")
                (out / f"{safe(rec['id'])}.pdf").write_bytes(data)
                entry["status"] = "retrieved"
            except Exception as e:
                entry.update(status="failed", error=str(e)[:200])
        else:
            entry["status"] = "missing"
        log.append(entry)
    return log


def convert(pdf_dirs: list[Path], out: Path) -> list[str]:
    """PDF -> Markdown with docling when installed (layout-aware), else pdftotext -layout."""
    out.mkdir(parents=True, exist_ok=True)
    docling = shutil.which("docling")
    done = []
    for d in pdf_dirs:
        for pdf in sorted(d.glob("*.pdf")):
            target = out / f"{pdf.stem}.md"
            if docling:
                subprocess.run([docling, "--to", "md", "--output", str(out), str(pdf)], check=True, capture_output=True)
            else:
                text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True, text=True).stdout
                # pdftotext marks page breaks with form feeds; keep page numbers for page-cited quotes
                target.write_text("".join(f"\n\n<!-- page {i} -->\n\n{p}" for i, p in enumerate(text.split("\f"), 1) if p.strip()))
            done.append(target.name)
    return done


def _work_to_record(w: dict) -> dict:
    return records.normalize({"source": "openalex", "openalex": (w.get("id") or "").rsplit("/", 1)[-1],
                              "doi": w.get("doi") or "", "title": w.get("title") or w.get("display_name") or "",
                              "year": str(w.get("publication_year") or "")}, query_id="citation_chasing")


def chase(included: list[dict], fetch: Fetch = _get, forward: bool = True) -> tuple[list[dict], list[str]]:
    """Backward (references) and forward (citing works) candidates for every included source.

    Returns (candidates, unresolved): references OpenAlex no longer resolves (merged or deleted
    works) and included sources it does not know are listed for manual tracing, not dropped.
    """
    found, unresolved = [], []
    for rec in included:
        work = openalex_work(rec, fetch)
        if not work:
            unresolved.append(f"included source not in OpenAlex: {rec['id']}")
            continue
        refs = [r.rsplit("/", 1)[-1] for r in work.get("referenced_works", [])]
        for i in range(0, len(refs), 50):
            q = f"{OPENALEX}?filter=openalex_id:{'|'.join(refs[i:i + 50])}&per-page=50&select=id,doi,title,publication_year"
            batch = json.loads(fetch(q))["results"]
            got = {(w.get("id") or "").rsplit("/", 1)[-1] for w in batch}
            unresolved += [f"reference of {rec['id']} not resolvable: {r}" for r in refs[i:i + 50] if r not in got]
            found += [_work_to_record(w) for w in batch]
        if forward:
            wid = work["id"].rsplit("/", 1)[-1]
            q = f"{OPENALEX}?filter=cites:{wid}&per-page=200&select=id,doi,title,publication_year"
            found += [_work_to_record(w) for w in json.loads(fetch(q))["results"]]
    kept, _ = records.dedup(found)
    return kept, unresolved


def seed_list(seeds_bib: str) -> list[dict]:
    """Seed papers from a .bib: key, normalized DOI and title, raw title, arXiv id."""
    from .bib import entries
    seeds = []
    for key, entry in entries(seeds_bib).items():
        doi = re.search(r"\bdoi\s*=\s*[{\"]([^}\"]+)", entry, re.I)
        title = re.search(r"\btitle\s*=\s*[{\"](.+?)[}\"]\s*,", entry, re.I | re.S)
        ax = re.search(r"(?:\beprint\s*=\s*[{\"]|arxiv\.org/abs/)(\d{4}\.\d{4,5})", entry, re.I)
        raw = " ".join(title.group(1).replace("{", "").replace("}", "").split()) if title else ""
        seeds.append({"key": key, "doi": records.norm_doi(doi.group(1)) if doi else "",
                      "title": records.norm_title(raw) if raw else "", "raw_title": raw, "arxiv": ax.group(1) if ax else ""})
    return seeds


def seed_recall(results: list[dict], seeds_bib: str) -> dict:
    """Which seed papers (from the seed .bib) the test search found, matched by DOI or title."""
    seeds = seed_list(seeds_bib)
    dois = {records.norm_doi(r.get("doi")) for r in results if r.get("doi")}
    titles = {records.norm_title(r.get("title")) for r in results}
    hit = [s["key"] for s in seeds if (s["doi"] and s["doi"] in dois) or (s["title"] and s["title"] in titles)]
    return {"seeds": len(seeds), "found": hit, "missed": [s["key"] for s in seeds if s["key"] not in hit],
            "recall": len(hit) / len(seeds) if seeds else None}


def field_agreement(first: list[dict], second: list[dict]) -> dict:
    """Charting pilot (P7.01b): share of fields where two charters recorded the same value."""
    def norm(v):
        v = v if isinstance(v, list) else [v]
        return sorted(str(x).strip().lower() for x in v)
    b = {r["record_id"]: r for r in second}
    per_field, total, same = {}, 0, 0
    for rec in first:
        other = b.get(rec["record_id"])
        if not other:
            continue
        for field, v in rec["fields"].items():
            w = other["fields"].get(field)
            ok = w is not None and norm(v.get("value")) == norm(w.get("value"))
            per_field.setdefault(field, [0, 0])
            per_field[field][0] += ok
            per_field[field][1] += 1
            total += 1
            same += ok
    return {"agreement": same / total if total else None, "fields_compared": total,
            "by_field": {f: round(a / n, 4) for f, (a, n) in per_field.items()},
            "below": sorted(f for f, (a, n) in per_field.items() if n and a / n < 1)}
