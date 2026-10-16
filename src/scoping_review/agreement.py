"""Screener agreement, Cohen's kappa and conflict queues (board nodes P5.02d, P5.05, P6.06)."""

from __future__ import annotations

from collections import Counter


def as_binary(decision: str, stage: str) -> str:
    """At title/abstract stages `maybe` moves a record forward, so it counts as include."""
    if decision == "maybe":
        return "include" if stage in ("pilot", "ta", "chase") else "maybe"
    return decision


def cohen_kappa(a: list[str], b: list[str]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("kappa needs two equal-length, non-empty rating lists")
    n = len(a)
    p_o = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    p_e = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    if p_e == 1:
        return 1.0  # both raters used one identical category throughout
    return (p_o - p_e) / (1 - p_e)


def compare(first: list[dict], second: list[dict], stage: str) -> dict:
    """Pair two screeners' decisions by record_id and report agreement, kappa and conflicts."""
    da = {d["record_id"]: d for d in first if d["stage"] == stage}
    db = {d["record_id"]: d for d in second if d["stage"] == stage}
    missing = sorted(set(da) ^ set(db))
    ids = sorted(set(da) & set(db))
    a = [as_binary(da[i]["decision"], stage) for i in ids]
    b = [as_binary(db[i]["decision"], stage) for i in ids]
    conflicts = [{"record_id": i, "first": da[i], "second": db[i]} for i, x, y in zip(ids, a, b) if x != y]
    return {
        "stage": stage, "n": len(ids), "agreement": sum(x == y for x, y in zip(a, b)) / len(ids) if ids else None,
        "kappa": cohen_kappa(a, b) if ids else None, "conflicts": conflicts, "unpaired": missing,
    }
