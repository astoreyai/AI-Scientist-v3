"""Record normalization, deduplication and sampling (board nodes P4.04, P4.05, P5.02a, P6.08b)."""

from __future__ import annotations

import difflib
import html
import random
import re
import unicodedata
from collections import defaultdict

FUZZY_RATIO = 0.95  # title similarity for a merge when no identifier is shared


def norm_doi(doi: str | None) -> str:
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", (doi or "").strip().lower())


def norm_title(title: str | None) -> str:
    t = unicodedata.normalize("NFKD", html.unescape(re.sub("<[^>]+>", " ", title or "")))
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def normalize(raw: dict, query_id: str = "", retrieved_utc: str = "") -> dict:
    """Map an adapter dict to a record.schema.json object; id prefers DOI, then PMID, then source ids."""
    doi, pmid = norm_doi(raw.get("doi")), str(raw.get("pmid") or "").strip()
    if doi:
        rid = f"doi:{doi}"
    elif pmid:
        rid = f"pmid:{pmid}"
    elif raw.get("arxiv"):
        rid = f"arxiv:{raw['arxiv']}"
    elif raw.get("openalex"):
        rid = f"openalex:{raw['openalex']}"
    elif raw.get("s2"):
        rid = f"s2:{raw['s2']}"
    else:
        raise ValueError(f"record has no identifier: {raw.get('title', '')[:80]!r}")
    year = str(raw.get("year") or "")
    return {
        "id": rid, "title": " ".join(html.unescape(re.sub("<[^>]+>", " ", raw.get("title") or "")).split()),
        "authors": raw.get("authors") or [], "year": int(year) if year.isdigit() else year,
        "venue": raw.get("venue") or raw.get("journal") or "", "doi": doi or None,
        "pmid": pmid or None, "abstract": raw.get("abstract") or None, "source": raw.get("source", ""),
        "query_id": query_id, "retrieved_utc": retrieved_utc,
    }


def dedup(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Merge duplicates by shared DOI, shared PMID, or near-identical title in the same year.

    Returns (kept records, merge log). Records keep input order; the first of a group survives and
    absorbs the others' ids in `merged_ids` and any missing abstract, so nothing is lost.
    """
    parent = list(range(len(records)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    log = []

    def union(i, j, reason):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)
            log.append({"kept": records[min(ri, rj)]["id"], "merged": records[max(ri, rj)]["id"], "reason": reason})

    for key, reason in (("doi", "doi"), ("pmid", "pmid")):
        first = {}
        for i, r in enumerate(records):
            k = norm_doi(r.get(key)) if key == "doi" else str(r.get(key) or "")
            if k:
                union(first.setdefault(k, i), i, reason)

    # Titles: block on (year, first 3 title words) to keep the fuzzy pass near-linear.
    blocks = defaultdict(list)
    titles = [norm_title(r.get("title")) for r in records]
    for i, t in enumerate(titles):
        if t:
            blocks[(str(records[i].get("year", "")), " ".join(t.split()[:3]))].append(i)
    for members in blocks.values():
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                i, j = members[a], members[b]
                di, dj = norm_doi(records[i].get("doi")), norm_doi(records[j].get("doi"))
                # Same title, two different DOIs = preprint/published or article/supplement:
                # merged as one work but logged separately so the P4.05 human check sees it.
                version = bool(di and dj and di != dj)
                if titles[i] == titles[j]:
                    union(i, j, "version_pair" if version else "title_exact")
                elif difflib.SequenceMatcher(None, titles[i], titles[j]).ratio() >= FUZZY_RATIO:
                    union(i, j, "version_pair" if version else "title_fuzzy")

    groups = defaultdict(list)
    for i in range(len(records)):
        groups[find(i)].append(i)
    kept = []
    for root in sorted(groups):
        rec = dict(records[root])
        others = [records[i] for i in groups[root] if i != root]
        if others:
            rec["merged_ids"] = sorted({o["id"] for o in others} - {rec["id"]})
            rec["abstract"] = rec.get("abstract") or next((o["abstract"] for o in others if o.get("abstract")), None)
            rec["sources"] = sorted({rec.get("source", "")} | {o.get("source", "") for o in others})
        kept.append(rec)
    return kept, log


def sample(records: list[dict], n: int, seed: int) -> list[dict]:
    """Seeded simple random sample, so a pilot draw is reproducible from the board ledger."""
    return random.Random(seed).sample(records, min(n, len(records)))
