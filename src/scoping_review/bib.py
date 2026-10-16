"""References for included sources (board nodes P10.01, P10.03, P10.05).

`fetch` is injectable so tests replay recorded Crossref / doi.org responses.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Callable

from .records import norm_doi
from .sources import UA, _get

Fetch = Callable[[str, dict], bytes]


def http_fetch(url: str, headers: dict) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers={**UA, **headers}), timeout=60) as r:
        return r.read()


def doi_bibtex(doi: str, fetch: Fetch = http_fetch) -> str:
    """BibTeX from doi.org content negotiation; the key is rewritten to a stable form."""
    bib = fetch(f"https://doi.org/{urllib.parse.quote(doi, safe='/()')}", {"Accept": "application/x-bibtex"}).decode().strip()
    if not bib.startswith("@"):
        raise ValueError(f"doi.org returned no BibTeX for {doi}")
    return re.sub(r"^@(\w+)\{[^,]*,", lambda m: f"@{m.group(1)}{{{cite_key(doi)},", bib, count=1)


def cite_key(doi: str) -> str:
    return "doi_" + re.sub(r"[^a-z0-9]+", "_", norm_doi(doi)).strip("_")


def entries(bibtex: str) -> dict[str, str]:
    """Split a .bib text into {key: entry}; good enough for the well-formed output of doi.org."""
    out = {}
    for m in re.finditer(r"@\w+\{([^,]+),", bibtex):
        start = m.start()
        depth, i = 0, bibtex.index("{", start)
        for i in range(i, len(bibtex)):
            depth += {"{": 1, "}": -1}.get(bibtex[i], 0)
            if depth == 0:
                break
        out[m.group(1).strip()] = bibtex[start:i + 1]
    return out


def merge(*bibs: str) -> tuple[str, list[str]]:
    """Merge .bib texts; duplicate keys or duplicate DOIs keep the first entry and are reported."""
    seen_keys, seen_dois, kept, dropped = set(), set(), [], []
    for bib in bibs:
        for key, entry in entries(bib).items():
            m = re.search(r"\bdoi\s*=\s*[{\"]([^}\"]+)", entry, re.I)
            doi = norm_doi(m.group(1)) if m else ""
            if key in seen_keys or (doi and doi in seen_dois):
                dropped.append(key)
                continue
            seen_keys.add(key)
            if doi:
                seen_dois.add(doi)
            kept.append(entry)
    return "\n\n".join(kept) + "\n", dropped


def retraction_status(doi: str, fetch: Fetch | None = None) -> dict:
    """Crossref notices that update this DOI (retraction, correction, expression of concern)."""
    url = f"https://api.crossref.org/works?filter=updates:{norm_doi(doi)}&rows=20"
    raw = fetch(url, {}) if fetch else _get(url)
    notices = []
    for item in json.loads(raw)["message"]["items"]:
        for u in item.get("update-to", []):
            if norm_doi(u.get("DOI")) == norm_doi(doi):
                notices.append({"type": u.get("type"), "notice_doi": item["DOI"]})
    return {"doi": norm_doi(doi), "retracted": any(n["type"] == "retraction" for n in notices), "notices": notices}
