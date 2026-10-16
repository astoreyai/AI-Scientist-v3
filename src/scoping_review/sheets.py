"""Spreadsheets for the human cards: screening, adjudication and verification (board nodes
P5.02b, P5.04, P5.06, P6.05, P6.07, P6.08d, P7.03, P8.04).

Export writes a CSV a person fills in with any spreadsheet program; import validates every row and
writes the JSONL the scripts consume. The screening sheet never shows the AI's decision, so the two
screeners stay independent; only the adjudication sheet shows both.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

DECISIONS = {"include", "exclude", "maybe"}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _read(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def export_screen(records: list[dict], out: Path) -> None:
    _write(out, ["record_id", "title", "abstract", "decision", "reason_code", "note"],
           [[r["id"], r.get("title", ""), (r.get("abstract") or "")[:4000], "", "", ""] for r in records])


def import_screen(sheet: Path, stage: str, screener: str, codes: set[str]) -> list[dict]:
    """Validate a filled screening sheet; every row needs a decision and a known reason code."""
    out, errors = [], []
    for i, row in enumerate(_read(sheet), 2):
        d, code = row["decision"].strip().lower(), row["reason_code"].strip()
        if d not in DECISIONS:
            errors.append(f"row {i} ({row['record_id']}): decision {d!r} not in {sorted(DECISIONS)}")
            continue
        if d == "include":
            code = code or "I"
        if code not in codes | {"I"} or (d == "exclude" and code == "I"):
            errors.append(f"row {i} ({row['record_id']}): reason code {code!r} not valid for {d}")
            continue
        out.append({"record_id": row["record_id"], "stage": stage, "screener": screener, "decision": d,
                    "reason_code": code, "decided_utc": _now(), **({"note": row["note"]} if row.get("note") else {})})
    if errors:
        raise ValueError("sheet has invalid rows:\n" + "\n".join(errors))
    return out


def export_adjudicate(conflicts: list[dict], records: dict, out: Path) -> None:
    rows = []
    for c in conflicts:
        a, b = c["first"], c["second"]
        rows.append([c["record_id"], records.get(c["record_id"], {}).get("title", ""), a["screener"], a["decision"],
                     a["reason_code"], a.get("quote", ""), b["screener"], b["decision"], b["reason_code"],
                     b.get("quote", ""), "", ""])
    _write(out, ["record_id", "title", "screener_1", "decision_1", "code_1", "quote_1", "screener_2", "decision_2",
                 "code_2", "quote_2", "final_decision", "final_reason_code"], rows)


def finalize(first: list[dict], second: list[dict], adjudicated: Path | None, stage: str, adjudicator: str,
             codes: set[str]) -> list[dict]:
    """Final decision per record: the agreed decision, or the adjudicator's for every conflict."""
    from .agreement import as_binary
    a = {d["record_id"]: d for d in first if d["stage"] == stage}
    b = {d["record_id"]: d for d in second if d["stage"] == stage}
    if set(a) != set(b):
        raise ValueError(f"screeners did not screen the same records: {sorted(set(a) ^ set(b))[:5]}")
    adj = {}
    if adjudicated:
        for row in _read(adjudicated):
            d, code = row["final_decision"].strip().lower(), row["final_reason_code"].strip() or "I"
            if d not in {"include", "exclude"} or code not in codes | {"I"}:
                raise ValueError(f"adjudication row {row['record_id']}: {d!r}/{code!r} is not a final decision")
            adj[row["record_id"]] = (d, code)
    final, unresolved = [], []
    for rid in sorted(a):
        x, y = as_binary(a[rid]["decision"], stage), as_binary(b[rid]["decision"], stage)
        if rid in adj:
            d, code = adj[rid]
            src = adjudicator
        elif x == y and x != "maybe":
            d, code, src = x, a[rid]["reason_code"] if x == "exclude" else "I", "agreement"
        else:
            unresolved.append(rid)
            continue
        final.append({"record_id": rid, "stage": stage, "screener": src, "decision": d, "reason_code": code,
                      "decided_utc": _now()})
    if unresolved:
        raise ValueError(f"{len(unresolved)} conflicts have no adjudication, e.g. {unresolved[:5]}")
    return final


def export_verify(chart: list[dict], out: Path) -> None:
    rows = [[rec["record_id"], field, v.get("value"), v.get("quote", ""), v.get("page") or "", "", ""]
            for rec in chart for field, v in rec["fields"].items()]
    _write(out, ["record_id", "field", "ai_value", "quote", "page", "verdict", "corrected_value"], rows)


def import_verify(chart: list[dict], sheet: Path, verifier: str) -> list[dict]:
    """Apply a filled verification sheet; every field must be accepted, corrected or not_reported."""
    verdicts = {(r["record_id"], r["field"]): r for r in _read(sheet)}
    out, errors = [], []
    for rec in chart:
        new = {"record_id": rec["record_id"], "form_version": rec["form_version"], "fields": {}}
        for field, v in rec["fields"].items():
            row = verdicts.get((rec["record_id"], field))
            verdict = (row or {}).get("verdict", "").strip().lower()
            f = dict(v, verified_by=verifier)
            if verdict == "accept":
                f["status"] = "verified" if v.get("status") != "not_reported" else "not_reported"
            elif verdict == "correct":
                f.update(value=row["corrected_value"], status="edited")
            elif verdict == "not_reported":
                f.update(value="not reported", quote="", status="not_reported")
            else:
                errors.append(f"{rec['record_id']}/{field}: verdict {verdict!r} (need accept, correct or not_reported)")
            new["fields"][field] = f
        out.append(new)
    if errors:
        raise ValueError(f"{len(errors)} fields are not verified, e.g.:\n" + "\n".join(errors[:10]))
    return out
