"""`agsci sysrev`: script nodes specific to the systematic-review board.

Shared nodes (search, dedup, screening sheets, agreement, PRISMA, references, manuscript gates) use
`agsci sr`. Outcome data in the extraction records follow one convention, so every command reads them
the same way: field `outcome:<id>:<quantity>` with quantities
  binary:      events_t, total_t, events_c, total_c
  continuous:  mean_t, sd_t, n_t, mean_c, sd_c, n_c
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from src.scoping_review.cli import _read_jsonl

from . import appraisal, meta

BINARY = ("events_t", "total_t", "events_c", "total_c")
CONT = ("mean_t", "sd_t", "n_t", "mean_c", "sd_c", "n_c")


def outcome_data(records: list[dict], outcome: str) -> tuple[list[str], list[list[float]], str]:
    """Studies reporting the outcome, their numbers, and whether the data are binary or continuous."""
    studies, rows, kind = [], [], None
    for rec in records:
        f = rec["fields"]
        get = lambda q: f.get(f"outcome:{outcome}:{q}", {}).get("value")  # noqa: E731
        b, c = [get(q) for q in BINARY], [get(q) for q in CONT]
        if all(x not in (None, "not reported") for x in b):
            this, vals = "binary", [float(x) for x in b]
        elif all(x not in (None, "not reported") for x in c):
            this, vals = "continuous", [float(x) for x in c]
        else:
            continue
        if kind and this != kind:
            raise ValueError(f"outcome {outcome} mixes binary and continuous data ({rec['record_id']})")
        kind = this
        studies.append(rec["record_id"])
        rows.append(vals)
    if len(studies) < 2:
        raise ValueError(f"outcome {outcome}: {len(studies)} studies report usable data; a meta-analysis needs 2 or more")
    return studies, rows, kind


def effects(rows, kind: str, measure: str):
    if kind == "binary":
        # (events_t, total_t, events_c, total_c) -> 2x2 (a, b, c, d)
        tables = [[e1, n1 - e1, e2, n2 - e2] for e1, n1, e2, n2 in rows]
        yv = [meta.binary_effect(*t, measure=measure) for t in tables]
        return [a for a, _ in yv], [b for _, b in yv], tables
    if measure == "SMD":
        yv = [meta.smd(*r) for r in rows]
    elif measure == "MD":
        yv = [(m1 - m2, s1 ** 2 / n1 + s2 ** 2 / n2) for m1, s1, n1, m2, s2, n2 in rows]
    else:
        raise ValueError(f"{measure} is not a continuous-outcome measure (use MD or SMD)")
    return [a for a, _ in yv], [b for _, b in yv], None


def cmd_meta(args) -> int:
    """S9.03: pool one outcome with the method chosen at S9.02."""
    studies, rows, kind = outcome_data(_read_jsonl(Path(args.inp)), args.outcome)
    y, v, tables = effects(rows, kind, args.measure)
    if args.method == "reml_hksj":
        dl = meta.meta(y, v, "REML")
        res = meta.meta(y, v, "REML", hksj=dl["tau2"] > 0 and len(y) > 2)  # Cochrane v6.5: HKSJ when tau2 > 0 and k > 2
        res["tau2_ci"] = list(meta.tau2_ci(y, v))
        if len(y) < 5:
            res.pop("pi_lb", None), res.pop("pi_ub", None)  # prediction interval only with about 5 or more studies
    elif args.method == "mantel_haenszel":
        res = meta.mantel_haenszel(tables, args.measure)
    elif args.method == "peto":
        res = meta.peto(tables)
    out = {"outcome": args.outcome, "measure": args.measure, "studies": studies, "y": y, "v": v, "kind": kind, **res}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("k", "est", "ci_lb", "ci_ub")}), file=sys.stderr)
    return 0


def _load_meta(path: str) -> dict:
    return json.loads(Path(path).read_text())


def cmd_forest(args) -> int:
    """S9.04: forest plot for one pooled outcome."""
    from . import plots
    m = _load_meta(args.meta)
    labels = json.loads(Path(args.labels).read_text()) if args.labels else {}
    plots.forest([labels.get(s, s) for s in m["studies"]], m["y"], m["v"], m, m["measure"], args.out)
    return 0


def cmd_funnel_eligible(args) -> int:
    """S9.08: exit 0 (yes) when a small-study test is appropriate."""
    m = _load_meta(args.meta)
    ok = m["k"] >= args.min_studies and m["measure"] not in ("OR", "SMD")
    print(f"k={m['k']} measure={m['measure']}: {'testable' if ok else 'not testable'}", file=sys.stderr)
    return 0 if ok else 1


def cmd_funnel(args) -> int:
    """S9.09: funnel plot and Egger's test."""
    from . import plots
    m = _load_meta(args.meta)
    plots.funnel(m["y"], m["v"], m, m["measure"], args.out)
    res = meta.egger(m["y"], m["v"], measure=m["measure"])
    Path(args.egger).write_text(json.dumps({m["outcome"]: res}, indent=1))
    return 0


def cmd_subgroups(args) -> int:
    """S9.06: Cochrane test for subgroup differences."""
    m = _load_meta(args.meta)
    recs = {r["record_id"]: r for r in _read_jsonl(Path(args.inp))}
    groups = [str(recs[s]["fields"][args.by]["value"]) for s in m["studies"]]
    res = meta.subgroups(m["y"], m["v"], groups)
    Path(args.out).write_text(json.dumps(res, indent=1))
    return 0


def cmd_sensitivity(args) -> int:
    """S9.07: leave-one-out, without high risk-of-bias studies, and fixed vs random effects."""
    m = _load_meta(args.meta)
    rob = json.loads(Path(args.rob).read_text())
    keep = [i for i, s in enumerate(m["studies"]) if rob.get(s, {}).get("overall") not in ("high", "serious", "critical")]
    out = {"leave_one_out": dict(zip(m["studies"], meta.leave_one_out(m["y"], m["v"]))),
           "fixed_effect": meta.meta(m["y"], m["v"], "FE")}
    if 2 <= len(keep) < len(m["studies"]):
        out["excluding_high_risk"] = meta.meta([m["y"][i] for i in keep], [m["v"][i] for i in keep], "REML")
    Path(args.out).write_text(json.dumps(out, indent=1))
    return 0


def cmd_rob_compare(args) -> int:
    """RB.04: domain-level disagreements between the two assessors."""
    first = {s: {d: v["judgement"] for d, v in doms.items()} for s, doms in json.loads(Path(args.a).read_text()).items()}
    second = {s: {d: v["judgement"] for d, v in doms.items()} for s, doms in json.loads(Path(args.b).read_text()).items()}
    diff = appraisal.compare_assessors(args.tool, first, second)
    Path(args.out).write_text(json.dumps(diff, indent=1))
    print(f"{len(diff)} disagreements", file=sys.stderr)
    return 0


def cmd_rob_overall(args) -> int:
    """RB.06: overall judgement per study and the traffic-light figure."""
    from . import plots
    final = json.loads(Path(args.inp).read_text())
    judg = {s: {d: v["judgement"] for d, v in doms.items()} for s, doms in final.items()}
    for s, doms in final.items():
        unsupported = [d for d, v in doms.items() if not v.get("quote") and v["judgement"] != "low"]
        if unsupported:
            raise ValueError(f"{s}: judgements without a supporting quote (MECIR C54): {unsupported}")
    out = {s: appraisal.overall(args.tool, j) for s, j in judg.items()}
    Path(args.out).write_text(json.dumps(out, indent=1))
    plots.traffic_light(args.tool, judg, args.fig)
    return 0


def cmd_rob_sheet(args) -> int:
    """RB.03: a blank assessment sheet (study x domain) for the human assessor."""
    doms = appraisal.TOOLS[args.tool]["domains"]
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["study", "domain", "judgement", "quote", "page"])
        for r in _read_jsonl(Path(args.studies)):
            for d in doms:
                w.writerow([r["id"], d, "", "", ""])
    return 0


def cmd_rob_import(args) -> int:
    """RB.03: read the filled sheet; every cell needs a valid judgement."""
    levels = appraisal.TOOLS[args.tool]["levels"]
    out, bad = {}, []
    with open(args.sheet, newline="") as f:
        for row in csv.DictReader(f):
            j = row["judgement"].strip().lower().replace(" ", "_")
            if j not in levels:
                bad.append(f"{row['study']}/{row['domain']}: {j!r}")
                continue
            out.setdefault(row["study"], {})[row["domain"]] = {"judgement": j, "quote": row["quote"], "page": row["page"] or None}
    if bad:
        raise ValueError(f"invalid judgements (use {levels}): {bad[:10]}")
    Path(args.out).write_text(json.dumps(out, indent=1))
    return 0


def cmd_grade_check(args) -> int:
    """GR.03: recompute every certainty; reject moves without reasons and more than 7 outcomes."""
    g = json.loads(Path(args.inp).read_text())
    if not 1 <= len(g) <= 7:
        raise ValueError(f"{len(g)} outcomes: the Summary of Findings table holds 1 to 7")
    out = {o: appraisal.grade(x["start"], x.get("down", {}), x.get("up", {}), x.get("reasons", {})) for o, x in g.items()}
    print(json.dumps({o: r["certainty"] for o, r in out.items()}), file=sys.stderr)
    return 0


def cmd_sof(args) -> int:
    """GR.02: Summary of Findings table from the GRADE file and the pooled results."""
    g = json.loads(Path(args.grade).read_text())
    rows = []
    for outcome, x in g.items():
        m = _load_meta(Path(args.meta) / f"meta_{outcome}.json")
        cert = appraisal.grade(x["start"], x.get("down", {}), x.get("up", {}), x.get("reasons", {}))["certainty"]
        rows.append({"outcome": outcome, "absolute": appraisal.absolute_effect(m["measure"], m["est"], m["ci_lb"], m["ci_ub"], x["control_risk"]),
                     "relative": f"{m['measure']} {meta.math.exp(m['est']):.2f} ({meta.math.exp(m['ci_lb']):.2f} to {meta.math.exp(m['ci_ub']):.2f})",
                     "participants": x["participants"], "studies": m["k"], "certainty": cert, "comment": x.get("comment", "")})
    Path(args.out).write_text(appraisal.sof_table(rows, args.comparison, args.population))
    return 0


def cmd_search_lint(args) -> int:
    """P2.12: MECIR C32 (no NOT operator) and C33 (controlled vocabulary + free text) checks."""
    problems = []
    for f in sorted(Path(args.dir).glob("*.txt")):
        text = "\n".join(x for x in f.read_text().splitlines() if not x.lstrip().startswith("#"))  # comments are documentation
        if re.search(r"\bNOT\b", text):
            problems.append(f"{f.name}: uses NOT (MECIR C32)")
        if f.stem in ("pubmed", "medline", "embase", "europepmc") and not re.search(r"\[(MeSH|mh|Mesh Terms)\]|/exp|exp |MESH:", text, re.I):
            problems.append(f"{f.name}: no controlled vocabulary terms (MECIR C33)")
    Path(args.out).write_text(json.dumps({"problems": problems, "ok": not problems}, indent=1))
    for p in problems:
        print(p, file=sys.stderr)
    return 1 if problems else 0


def cmd_extract_sheet(args) -> int:
    """S7.03: blank extraction sheet (study x form field); the AI's values are never shown."""
    import yaml
    form = yaml.safe_load(Path(args.form).read_text())
    fields = [f["id"] for f in (form if isinstance(form, list) else form["fields"])]
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["record_id", "field", "value", "quote", "page"])
        for r in _read_jsonl(Path(args.studies)):
            for fld in fields:
                w.writerow([r["id"], fld, "", "", ""])
    return 0


def _sheet_to_records(path: str, who: str) -> list[dict]:
    recs = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if not row["value"].strip():
                raise ValueError(f"{row['record_id']}/{row['field']}: empty value (write 'not reported' if absent)")
            nr = row["value"].strip().lower() == "not reported"
            recs.setdefault(row["record_id"], {"record_id": row["record_id"], "form_version": "sheet", "fields": {}})["fields"][row["field"]] = {
                "value": "not reported" if nr else row["value"].strip(), "quote": row["quote"], "page": row["page"] or None,
                "charted_by": who, "verified_by": None, "status": "not_reported" if nr else "edited"}
    return list(recs.values())


def cmd_extract_import(args) -> int:
    """S7.03: the filled human sheet as extraction records."""
    from src.scoping_review.cli import _write_jsonl
    _write_jsonl(Path(args.out), _sheet_to_records(args.sheet, args.extractor))
    return 0


def cmd_reconcile(args) -> int:
    """S7.05: export every field where the extractions differ; import the resolved sheet as the final set."""
    from src.scoping_review.cli import _write_jsonl
    a = {r["record_id"]: r for r in _read_jsonl(Path(args.a))}
    b = {r["record_id"]: r for r in _read_jsonl(Path(args.b))}
    norm = lambda v: str(v).strip().lower()  # noqa: E731
    if not args.resolved:
        with open(args.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["record_id", "field", "value_1", "quote_1", "value_2", "quote_2", "final_value", "final_quote", "final_page"])
            for rid in sorted(set(a) | set(b)):
                fa, fb = a.get(rid, {}).get("fields", {}), b.get(rid, {}).get("fields", {})
                for fld in sorted(set(fa) | set(fb)):
                    va, vb = fa.get(fld, {}), fb.get(fld, {})
                    if norm(va.get("value")) != norm(vb.get("value")):
                        w.writerow([rid, fld, va.get("value"), va.get("quote", ""), vb.get("value"), vb.get("quote", ""), "", "", ""])
        return 0
    final = {rid: {"record_id": rid, "form_version": a[rid]["form_version"], "fields": dict(a[rid]["fields"])} for rid in a}
    with open(args.resolved, newline="") as f:
        for row in csv.DictReader(f):
            if not row["final_value"].strip():
                raise ValueError(f"{row['record_id']}/{row['field']}: no final value")
            final[row["record_id"]]["fields"][row["field"]] = {"value": row["final_value"].strip(), "quote": row["final_quote"],
                                                               "page": row["final_page"] or None, "status": "verified",
                                                               "verified_by": args.resolver}
    _write_jsonl(Path(args.out), list(final.values()))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="agsci sysrev", description="Systematic-review script nodes")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def p(name, fn, help_, *args):
        sp = sub.add_parser(name, help=help_)
        for a in args:
            flags, kw = (a, {}) if isinstance(a, str) else a
            sp.add_argument(*([flags] if isinstance(flags, str) else flags), **kw)
        sp.set_defaults(fn=fn)

    req = {"required": True}
    p("meta", cmd_meta, "S9.03 pool one outcome", (["--in"], {"dest": "inp", **req}), (["--outcome"], req),
      (["--measure"], {"choices": ["RR", "OR", "RD", "MD", "SMD"], **req}),
      (["--method"], {"choices": ["reml_hksj", "mantel_haenszel", "peto"], **req}), (["--out"], req))
    p("forest", cmd_forest, "S9.04 forest plot", (["--meta"], req), (["--labels"], {}), (["--out"], req))
    p("funnel-eligible", cmd_funnel_eligible, "S9.08 small-study test allowed?", (["--meta"], req),
      (["--min-studies"], {"type": int, "default": 10}))
    p("funnel", cmd_funnel, "S9.09 funnel plot and Egger", (["--meta"], req), (["--out"], req), (["--egger"], req))
    p("subgroups", cmd_subgroups, "S9.06 subgroup differences", (["--meta"], req), (["--in"], {"dest": "inp", **req}),
      (["--by"], req), (["--out"], req))
    p("sensitivity", cmd_sensitivity, "S9.07 sensitivity analyses", (["--meta"], req), (["--rob"], req), (["--out"], req))
    p("rob-sheet", cmd_rob_sheet, "RB.03 blank human sheet", (["--tool"], {"choices": list(appraisal.TOOLS), **req}),
      (["--studies"], req), (["--out"], req))
    p("rob-import", cmd_rob_import, "RB.03 read filled sheet", (["--tool"], {"choices": list(appraisal.TOOLS), **req}),
      (["--sheet"], req), (["--out"], req))
    p("rob-compare", cmd_rob_compare, "RB.04 assessor disagreements", (["--tool"], {"choices": list(appraisal.TOOLS), **req}),
      (["--a"], req), (["--b"], req), (["--out"], req))
    p("rob-overall", cmd_rob_overall, "RB.06 overall + traffic light", (["--tool"], {"choices": list(appraisal.TOOLS), **req}),
      (["--in"], {"dest": "inp", **req}), (["--out"], req), (["--fig"], req))
    p("grade-check", cmd_grade_check, "GR.03 certainty check", (["--in"], {"dest": "inp", **req}))
    p("sof", cmd_sof, "GR.02 Summary of Findings table", (["--grade"], req), (["--meta"], req), (["--comparison"], req),
      (["--population"], req), (["--out"], req))
    p("extract-sheet", cmd_extract_sheet, "S7.03 blank human extraction sheet", (["--form"], req), (["--studies"], req), (["--out"], req))
    p("extract-import", cmd_extract_import, "S7.03 read the filled sheet", (["--sheet"], req), (["--extractor"], req), (["--out"], req))
    p("reconcile", cmd_reconcile, "S7.05 export disagreements, or import the resolved sheet",
      (["--a"], req), (["--b"], req), (["--resolved"], {}), (["--resolver"], {"default": ""}), (["--out"], req))
    p("search-lint", cmd_search_lint, "P2.12 MECIR search rules", "dir", (["--out"], {"default": "review/search/lint.json"}))
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except ValueError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 1
