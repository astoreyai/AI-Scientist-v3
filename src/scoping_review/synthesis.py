"""Descriptive statistics, evidence gap map and PRISMA counts (board nodes P8.01, P8.05, P6.09).

Scoping reviews report counts and proportions only (JBI Manual 10.2.10); nothing here pools effects.
"""

from __future__ import annotations

from collections import Counter, defaultdict

NOT_REPORTED = "not reported"


def field_values(rec: dict, field: str) -> list:
    """Values of one charted field as a list; list-typed fields count once per value."""
    f = rec["fields"].get(field)
    if f is None or f.get("status") == "not_reported" or f.get("value") in (None, "", NOT_REPORTED):
        return [NOT_REPORTED]
    v = f["value"]
    return list(dict.fromkeys(v)) if isinstance(v, list) else [v]


def describe(chart: list[dict], fields: list[str]) -> dict:
    n = len(chart)
    out = {"n_sources": n, "fields": {}}
    for field in fields:
        counts = Counter(v for rec in chart for v in field_values(rec, field))
        out["fields"][field] = {
            "counts": dict(sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))),
            "proportion_of_sources": {str(k): round(c / n, 4) for k, c in counts.items()} if n else {},
            "record_ids": {str(k): sorted(r["record_id"] for r in chart if k in field_values(r, field)) for k in counts},
        }
    return out


def gap_map(chart: list[dict], rows: str, cols: str) -> dict:
    """Cross-tabulate two fields; empty cells are the evidence gaps."""
    cells = defaultdict(set)
    rvals, cvals = Counter(), Counter()
    for rec in chart:
        for r in field_values(rec, rows):
            rvals[r] += 1
            for c in field_values(rec, cols):
                cells[(r, c)].add(rec["record_id"])
        for c in field_values(rec, cols):
            cvals[c] += 1
    row_order = [k for k, _ in rvals.most_common()]
    col_order = [k for k, _ in cvals.most_common()]
    return {
        "rows_field": rows, "cols_field": cols, "rows": row_order, "cols": col_order,
        "counts": [[len(cells[(r, c)]) for c in col_order] for r in row_order],
        "record_ids": {f"{r}|{c}": sorted(cells[(r, c)]) for r in row_order for c in col_order if cells[(r, c)]},
        "empty_cells": [[r, c] for r in row_order for c in col_order if not cells[(r, c)]],
    }


def prisma_counts(search_log: dict, dedup_log: dict, ta: dict, ft: dict, not_retrieved: int, chase: dict | None) -> dict:
    """Assemble PRISMA 2020 flow numbers and check that every stage balances."""
    by_db = {s["database"]: s.get("kept_with_identifier", 0) for s in search_log["searches"] if "error" not in s}
    identified = sum(by_db.values())
    screened = ta["records"]
    sought = ta["included"]
    assessed = sought - not_retrieved
    counts = {
        "identified_by_database": by_db, "identified": identified,
        "duplicates_removed": dedup_log["duplicates_removed"], "screened": screened,
        "excluded_title_abstract": ta["excluded"], "sought_for_retrieval": sought,
        "not_retrieved": not_retrieved, "assessed_full_text": assessed,
        "excluded_full_text": ft["excluded"], "excluded_full_text_reasons": ft["exclusion_reasons"],
        "identified_by_citation_searching": (chase or {}).get("included", 0),
        "included": ft["included"] + (chase or {}).get("included", 0),
    }
    problems = []
    if identified - counts["duplicates_removed"] != screened:
        problems.append(f"identified {identified} - duplicates {counts['duplicates_removed']} != screened {screened}")
    if screened - ta["excluded"] != sought:
        problems.append(f"screened {screened} - excluded {ta['excluded']} != sought {sought}")
    if ft["records"] != assessed:
        problems.append(f"full-text records {ft['records']} != assessed {assessed}")
    if assessed - ft["excluded"] != ft["included"]:
        problems.append(f"assessed {assessed} - excluded {ft['excluded']} != included {ft['included']}")
    counts["balance_problems"] = problems
    return counts
