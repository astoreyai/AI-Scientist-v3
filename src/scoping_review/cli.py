"""`agsci sr`: script nodes of the scoping-review board.

Each subcommand is one board node (named in its help). Inputs and outputs are files under the
review directory so the board ledger can hash them.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

from . import agreement, bib, fulltext, integrity, manuscript, records, sheets, sources, submission, synthesis


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def cmd_search(args) -> int:
    """P4.01: run every `<source>.txt` strategy file and write raw records plus a PRISMA-S log."""
    out = Path(args.out)
    log = {"searches": [], "not_searched_by_api": "Embase, CINAHL, PsycINFO, Scopus, Web of Science, IEEE Xplore, ACM DL (import exports instead)"}
    failed = 0
    for strategy in sorted(Path(args.strategies).glob("*.txt")):
        name = strategy.stem
        if name not in sources.ADAPTERS:
            continue
        query = strategy.read_text().strip()
        started = _now()
        entry = {"database": name, "interface": "public API", "query": query, "strategy_file": str(strategy),
                 "limits": args.limits or "none", "searched_utc": started, "cap": args.cap,
                 **({"since": args.since} if args.since else {})}
        try:
            raw = sources.ADAPTERS[name](query, args.cap, since=args.since)
            rows = [records.normalize(r, query_id=name, retrieved_utc=started) for r in raw
                    if r.get("doi") or r.get("pmid") or r.get("arxiv") or r.get("openalex") or r.get("s2")]
            entry.update(retrieved=len(raw), kept_with_identifier=len(rows), capped=len(raw) >= args.cap)
            _write_jsonl(out / f"{name}.jsonl", rows)
        except sources.FetchError as e:
            entry.update(error=str(e))
            failed += 1
        log["searches"].append(entry)
        print(f"{name}: {entry.get('retrieved', 'FAILED')}", file=sys.stderr)
    Path(args.log).write_text(json.dumps(log, indent=1))
    return 1 if failed else 0


def cmd_dedup(args) -> int:
    """P4.04 / P6.08b: merge duplicates across every raw file (and an optional existing corpus)."""
    rows = []
    for path in args.inputs:
        p = Path(path)
        rows += [r for f in sorted(p.glob("*.jsonl")) for r in _read_jsonl(f)] if p.is_dir() else _read_jsonl(p)
    against = _read_jsonl(Path(args.against)) if args.against else []
    kept, log = records.dedup(against + rows)
    removed = len(against) + len(rows) - len(kept)
    if args.against:
        old = {r["id"] for r in against}
        kept = [r for r in kept if r["id"] not in old]
    _write_jsonl(Path(args.out), kept)
    Path(args.log).write_text(json.dumps({"input": len(rows), "against": len(against), "kept": len(kept),
                                          "duplicates_removed": removed,
                                          "merges": log}, indent=1))
    print(f"{len(rows)} in, {len(kept)} kept, {len(log)} merges", file=sys.stderr)
    return 0


def cmd_dedup_sample(args) -> int:
    """P4.05: draw merged pairs for the human false-merge check."""
    merges = json.loads(Path(args.log).read_text())["merges"]
    # Every version pair is checked; the random sample covers the remaining merges.
    versions = [m for m in merges if m["reason"] == "version_pair"]
    rest = [m for m in merges if m["reason"] != "version_pair"]
    pick = versions + records.sample(rest, max(0, args.n - len(versions)), args.seed)
    _write_jsonl(Path(args.out), [{**m, "false_merge": None} for m in pick])
    return 0


def cmd_sample(args) -> int:
    """P5.02a: seeded random pilot sample."""
    _write_jsonl(Path(args.out), records.sample(_read_jsonl(Path(args.inp)), args.n, args.seed))
    return 0


def cmd_agreement(args) -> int:
    """P5.02d / P5.05 / P6.06: agreement, kappa and the conflict queue."""
    res = agreement.compare(_read_jsonl(Path(args.a)), _read_jsonl(Path(args.b)), args.stage)
    if args.conflicts:
        _write_jsonl(Path(args.conflicts), res["conflicts"])
    summary = {k: v for k, v in res.items() if k != "conflicts"} | {"n_conflicts": len(res["conflicts"])}
    Path(args.out).write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary), file=sys.stderr)
    return 1 if res["unpaired"] else 0


def cmd_check_stage(args) -> int:
    """P5.07 / P6.09 gate: every record has exactly one final decision; write the included set."""
    recs = {r["id"]: r for r in _read_jsonl(Path(args.records))}
    final = {}
    for d in _read_jsonl(Path(args.decisions)):
        final[d["record_id"]] = d  # adjudication files are ordered; the last word wins
    missing = sorted(set(recs) - set(final))
    unknown = sorted(set(final) - set(recs))
    undecided = sorted(i for i, d in final.items() if d["decision"] == "maybe")
    included = [recs[i] for i in recs if i in final and final[i]["decision"] == "include"]
    reasons = {}
    for d in final.values():
        if d["decision"] == "exclude":
            reasons[d["reason_code"]] = reasons.get(d["reason_code"], 0) + 1
    report = {"stage": args.stage, "records": len(recs), "decided": len(final) - len(unknown), "included": len(included),
              "excluded": sum(reasons.values()), "exclusion_reasons": reasons,
              "missing": missing, "unknown_ids": unknown, "undecided": undecided}
    Path(args.report).write_text(json.dumps(report, indent=1))
    if missing or unknown or undecided:
        print(f"GATE FAILED: missing={len(missing)} unknown={len(unknown)} undecided={len(undecided)}", file=sys.stderr)
        return 1
    _write_jsonl(Path(args.out), included)
    return 0


def cmd_describe(args) -> int:
    """P8.01: counts and proportions per charted field."""
    chart = _read_jsonl(Path(args.inp))
    Path(args.out).write_text(json.dumps(synthesis.describe(chart, args.fields), indent=1, default=str))
    return 0


def cmd_gap_map(args) -> int:
    """P8.05: cross-tabulate two fields; empty cells are gaps."""
    chart = _read_jsonl(Path(args.inp))
    Path(args.out).write_text(json.dumps(synthesis.gap_map(chart, args.rows, args.cols), indent=1, default=str))
    return 0


def cmd_prisma(args) -> int:
    """P6.09: PRISMA 2020 counts; exits 1 if any stage fails to balance."""
    load = lambda p: json.loads(Path(p).read_text())  # noqa: E731
    counts = synthesis.prisma_counts(load(args.search_log), load(args.dedup_log), load(args.ta_report),
                                     load(args.ft_report), args.not_retrieved, load(args.chase_report) if args.chase_report else None)
    Path(args.out).write_text(json.dumps(counts, indent=1))
    for p in counts["balance_problems"]:
        print(f"UNBALANCED: {p}", file=sys.stderr)
    return 1 if counts["balance_problems"] else 0


def cmd_fig(args) -> int:
    """P8.07-P8.11: figures from frozen data only."""
    from . import figures
    if args.kind == "prisma":
        figures.prisma_flow(json.loads(Path(args.inp).read_text()), args.out)
    elif args.kind == "gapmap":
        figures.gap_heatmap(json.loads(Path(args.inp).read_text()), args.out)
    elif args.kind == "timeline":
        figures.timeline(_read_jsonl(Path(args.inp)), args.year_field, args.stack_field, args.out)
    elif args.kind == "bars":
        stats = json.loads(Path(args.inp).read_text())
        figures.category_bars(stats["fields"][args.field]["counts"], args.field.replace("_", " "), stats["n_sources"], args.out)
    return 0


def cmd_table(args) -> int:
    """P8.12: characteristics longtable; columns given as field:Label."""
    from . import figures
    cols = [tuple(c.split(":", 1)) if ":" in c else (c, c.replace("_", " ").capitalize()) for c in args.columns]
    keys = json.loads(Path(args.cite_keys).read_text()) if args.cite_keys else {}
    Path(args.out).write_text(figures.characteristics_table(_read_jsonl(Path(args.inp)), cols, keys))
    return 0


def cmd_freeze(args) -> int:
    """P2.10 / P3.04 / P7.10: hash an artifact into the ledger."""
    e = integrity.freeze(Path(args.path), Path(args.ledger), args.node)
    print(json.dumps(e), file=sys.stderr)
    return 1 if e["event"] == "refreeze_changed" else 0


def cmd_verify_frozen(args) -> int:
    """Gate helper: every frozen artifact still matches its hash."""
    changed = integrity.verify_frozen(Path(args.ledger))
    for a in changed:
        print(f"CHANGED SINCE FREEZE: {a}", file=sys.stderr)
    return 1 if changed else 0


def cmd_search_age(args) -> int:
    """P15.01: exit 1 (decision 'yes') when the oldest search is older than --max-months."""
    on = dt.date.fromisoformat(args.on) if args.on else dt.date.today()
    age = integrity.search_age_months(json.loads(Path(args.log).read_text()), on)
    print(f"search age {age:.1f} months", file=sys.stderr)
    return 1 if age > args.max_months else 0


def cmd_lint(args) -> int:
    """P11.05: house-style lint over .tex files."""
    files = [p for a in args.paths for p in (sorted(Path(a).rglob("*.tex")) if Path(a).is_dir() else [Path(a)])]
    findings = integrity.lint(files)
    for f in findings:
        print(f"{f['file']}:{f['line']}: {f['rule']}: {f['text']}")
    return 1 if findings else 0


def cmd_check_numbers(args) -> int:
    """P14.01: PRISMA counts appear in the typeset text."""
    problems = integrity.check_numbers(integrity.pdf_text(Path(args.pdf)), json.loads(Path(args.counts).read_text()))
    for p in problems:
        print(p, file=sys.stderr)
    return 1 if problems else 0


def cmd_limits(args) -> int:
    """P13.05: counts against the journal profile; exit 1 (decision 'no') when over."""
    import yaml
    profile = yaml.safe_load(Path(args.profile).read_text())
    res = integrity.limits(Path(args.tex), None, profile.get("profile", profile))
    print(json.dumps(res), file=sys.stderr)
    return 1 if res["over"] else 0


def cmd_check_layout(args) -> int:
    """P13.07 helper: every font embedded."""
    missing = integrity.fonts_not_embedded(Path(args.pdf))
    for m in missing:
        print(f"NOT EMBEDDED: {m}", file=sys.stderr)
    return 1 if missing else 0


def cmd_bib(args) -> int:
    """P10.01: BibTeX for every included record with a DOI; records without one are listed."""
    out, keys, missing = [], {}, []
    for rec in _read_jsonl(Path(args.included)):
        if rec.get("doi"):
            out.append(bib.doi_bibtex(rec["doi"]))
            keys[rec["id"]] = bib.cite_key(rec["doi"])
        else:
            missing.append(rec["id"])
    Path(args.out).write_text("\n\n".join(out) + "\n")
    Path(args.keys).write_text(json.dumps(keys, indent=1))
    for m in missing:
        print(f"NO DOI (add BibTeX by hand): {m}", file=sys.stderr)
    return 1 if missing else 0


def cmd_bib_merge(args) -> int:
    """P10.03: merge .bib files, dropping duplicate keys and DOIs."""
    merged, dropped = bib.merge(*(Path(b).read_text() for b in args.bibs))
    Path(args.out).write_text(merged)
    print(f"dropped duplicates: {dropped}", file=sys.stderr)
    return 0


def cmd_retractions(args) -> int:
    """P10.05: Crossref update notices for every DOI in the bibliography."""
    dois = sorted({m.group(1).strip() for m in re.finditer(r"\bdoi\s*=\s*[{\"]([^}\"]+)", Path(args.bib).read_text(), re.I)})
    report = [bib.retraction_status(d) for d in dois]
    Path(args.out).write_text(json.dumps(report, indent=1))
    flagged = [r for r in report if r["notices"]]
    for r in flagged:
        print(f"{r['doi']}: {[n['type'] for n in r['notices']]}", file=sys.stderr)
    return 1 if any(r["retracted"] for r in report) else 0


def _codes(path: str) -> set[str]:
    """Exclusion codes (E1, E2, ...) declared in the eligibility or screening-guide file."""
    return set(re.findall(r"\bE\d+\b", Path(path).read_text()))


def cmd_sheet(args) -> int:
    """Human cards: export a sheet to fill in, or import a filled one (validated)."""
    k = args.kind
    if k == "screen":
        sheets.export_screen(_read_jsonl(Path(args.inp)), Path(args.out))
    elif k == "import-screen":
        _write_jsonl(Path(args.out), sheets.import_screen(Path(args.sheet), args.stage, args.screener, _codes(args.codes_from)))
    elif k == "adjudicate":
        recs = {r["id"]: r for r in _read_jsonl(Path(args.records))}
        sheets.export_adjudicate(_read_jsonl(Path(args.inp)), recs, Path(args.out))
    elif k == "verify":
        sheets.export_verify(_read_jsonl(Path(args.inp)), Path(args.out))
    elif k == "import-verify":
        _write_jsonl(Path(args.out), sheets.import_verify(_read_jsonl(Path(args.inp)), Path(args.sheet), args.verifier))
    return 0


def cmd_finalize(args) -> int:
    """P5.06 / P6.07: agreed decisions plus adjudicated conflicts -> one final decision per record."""
    final = sheets.finalize(_read_jsonl(Path(args.a)), _read_jsonl(Path(args.b)),
                            Path(args.adjudicated) if args.adjudicated else None, args.stage, args.adjudicator,
                            _codes(args.codes_from))
    _write_jsonl(Path(args.out), final)
    return 0


def _report(problems: list[str], out: str | None) -> int:
    if out:
        Path(out).write_text(json.dumps({"problems": problems, "ok": not problems}, indent=1))
    for p in problems:
        print(p, file=sys.stderr)
    return 1 if problems else 0


def cmd_audit_claims(args) -> int:
    """P8.16 / P9.11 / P11.06 / P12.01d: every claim grounded in included sources."""
    claims = json.loads(Path(args.claims).read_text())
    included = {r["record_id"] for r in _read_jsonl(Path(args.data))}
    skeys = manuscript.stats_keys(json.loads(Path(args.stats).read_text())) if args.stats else set()
    tex = manuscript.all_tex(Path(args.tex)) if args.tex else None
    keys = json.loads(Path(args.cite_keys).read_text()) if args.cite_keys else {}
    return _report(manuscript.audit_claims(claims, included, skeys, tex, keys), args.out)


def cmd_assemble(args) -> int:
    """P9.10: draft main.tex from the outline's section order."""
    manuscript.assemble(args.sections, Path(args.out))
    return 0


def cmd_check_refs(args) -> int:
    """P10.07: no dangling citations, no orphans, no retracted sources."""
    retr = json.loads(Path(args.retractions).read_text()) if args.retractions else []
    return _report(manuscript.check_refs(manuscript.all_tex(Path(args.tex)), Path(args.bib).read_text(), retr), args.out)


def cmd_proof_auto(args) -> int:
    """P14.02: automated proof checks (log, doubled words, acronyms, spelling)."""
    root = Path(args.tex)
    words = set(Path(args.wordlist).read_text().split()) if args.wordlist else set()
    found = manuscript.proof_auto((root / "main.log").read_text(errors="replace"), manuscript.all_tex(root), args.lang, words)
    Path(args.out).write_text("\n".join(f"- {f}" for f in found) + "\n")
    print(f"{len(found)} findings for the human proofread (P14.04)", file=sys.stderr)
    return 0  # advisory: the proof gate (P14.06) is the author's sign-off


def cmd_checklist(args) -> int:
    """P14.05: reporting checklist with page numbers from main.aux."""
    import yaml
    tex, problems = manuscript.checklist(args.name, yaml.safe_load(Path(args.map).read_text()), Path(args.aux).read_text())
    out = Path(args.out)
    out.with_suffix(".tex").write_text(tex)
    if not problems:
        subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", out.with_suffix(".tex").name],
                       cwd=out.parent, check=True, capture_output=True)
    return _report(problems, None)


def cmd_fetch_fulltext(args) -> int:
    """P6.01: open-access PDFs; records without one are listed for the human (P6.02)."""
    log = fulltext.fetch_fulltext(_read_jsonl(Path(args.inp)), Path(args.out))
    Path(args.log).write_text(json.dumps(log, indent=1))
    missing = [e for e in log if e["status"] != "retrieved"]
    _write_jsonl(Path(args.out) / "missing.jsonl", missing)
    print(f"{len(log) - len(missing)} retrieved, {len(missing)} for manual retrieval", file=sys.stderr)
    return 0


def cmd_convert(args) -> int:
    """P6.03: PDFs to Markdown with page markers."""
    done = fulltext.convert([Path(d) for d in args.inputs], Path(args.out))
    print(f"{len(done)} converted", file=sys.stderr)
    return 0


def cmd_chase(args) -> int:
    """P6.08a: backward and forward citation candidates of the included sources."""
    found, unresolved = fulltext.chase(_read_jsonl(Path(args.included)), forward=not args.backward_only)
    _write_jsonl(Path(args.out), found)
    Path(args.out).with_suffix(".unresolved.txt").write_text("\n".join(unresolved) + "\n")
    print(f"{len(found)} candidates, {len(unresolved)} unresolved (trace by hand)", file=sys.stderr)
    return 0


def cmd_test_search(args) -> int:
    """P2.05a: run the primary strategy and measure recall of the seed set."""
    strategy = Path(args.strategy)
    lines = [x.strip() for x in strategy.read_text().splitlines() if x.strip() and not x.lstrip().startswith("#")]
    if len(lines) != 1:
        raise SystemExit(f"{strategy}: expected exactly one uncommented query line, found {len(lines)}")
    if args.source == "openalex":  # exact recall at any volume
        res = sources.openalex_seed_recall(lines[0], fulltext.seed_list(Path(args.seeds).read_text()), args.since)
    else:
        raw = sources.ADAPTERS[args.source](lines[0], args.cap, args.since)
        res = fulltext.seed_recall(raw, Path(args.seeds).read_text())
        res |= {"source": args.source, "hits": len(raw), "capped": len(raw) >= args.cap}
    res["strategy"] = str(strategy)
    Path(args.out).write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("hits", "recall", "missed")}), file=sys.stderr)
    return 0


def cmd_chart_agreement(args) -> int:
    """P7.01b: field-level agreement between two charters on the pilot sources."""
    res = fulltext.field_agreement(_read_jsonl(Path(args.a)), _read_jsonl(Path(args.b)))
    Path(args.out).write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("agreement", "fields_compared", "below")}), file=sys.stderr)
    return 0


def cmd_journal_profile(args) -> int:
    """P1.03: the chosen journal's profile, validated against journal_profile.schema.json."""
    import yaml
    prof = submission.journal_profile(yaml.safe_load(Path(args.shortlist).read_text()), yaml.safe_load(Path(args.choice).read_text()))
    Path(args.out).write_text(yaml.safe_dump(prof, sort_keys=False))
    for u in prof["unverified"]:
        print(f"UNVERIFIED (check by hand): {u}", file=sys.stderr)
    return 0


def cmd_template(args) -> int:
    """P1.05: fetch the journal LaTeX template named in the profile."""
    import yaml
    prof = yaml.safe_load(Path(args.profile).read_text())["profile"]
    print("\n".join(submission.fetch_template(prof.get("latex_template_url"), Path(args.out))), file=sys.stderr)
    return 0


def cmd_supplement(args) -> int:
    """P9.09: supplementary files S1-S4."""
    recs = {r["id"]: r for r in _read_jsonl(Path(args.records))}
    made = submission.supplement(Path(args.search_dir), Path(args.charting_form), _read_jsonl(Path(args.included)),
                                 _read_jsonl(Path(args.ft_final)), recs, Path(args.out))
    print(" ".join(made), file=sys.stderr)
    return 0


def cmd_package(args) -> int:
    """P15.09: stage the submission package (review-pending; nothing is sent)."""
    m = submission.package([Path(f) for f in args.files], Path(args.out).expanduser())
    print(f"staged {len(m['files'])} files in {args.out} for review before submission", file=sys.stderr)
    return 0


def cmd_archive(args) -> int:
    """P17.03: hash manifest of the whole review."""
    m = submission.archive(Path(args.root), Path(args.out))
    print(f"{len(m['files'])} files hashed", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="agsci sr", description="Scoping-review script nodes")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search", help="P4.01 run strategies against public APIs")
    p.add_argument("--strategies", required=True, help="dir of <source>.txt files")
    p.add_argument("--out", required=True)
    p.add_argument("--log", required=True)
    p.add_argument("--cap", type=int, default=10000)
    p.add_argument("--limits", default="")
    p.add_argument("--since", default="", help="YYYY-MM-DD: search update, records from this date on (P15.02)")
    p.set_defaults(fn=cmd_search)

    p = sub.add_parser("dedup", help="P4.04 / P6.08b deduplicate records")
    p.add_argument("inputs", nargs="+", help="jsonl files or dirs of jsonl")
    p.add_argument("--against", help="existing corpus; output keeps only records new to it")
    p.add_argument("--out", required=True)
    p.add_argument("--log", required=True)
    p.set_defaults(fn=cmd_dedup)

    p = sub.add_parser("dedup-sample", help="P4.05 merged pairs for the human check")
    p.add_argument("--log", required=True)
    p.add_argument("--n", type=int, default=50)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_dedup_sample)

    p = sub.add_parser("sample", help="P5.02a seeded pilot sample")
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--n", type=int, default=25)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_sample)

    p = sub.add_parser("agreement", help="P5.02d / P5.05 / P6.06 agreement and kappa")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--stage", required=True, choices=["pilot", "ta", "ft", "chase"])
    p.add_argument("--out", required=True)
    p.add_argument("--conflicts")
    p.set_defaults(fn=cmd_agreement)

    p = sub.add_parser("check-stage", help="P5.07 / P6.09 screening-complete gate")
    p.add_argument("stage", choices=["ta", "ft"])
    p.add_argument("--records", required=True)
    p.add_argument("--decisions", required=True, help="final (adjudicated) decisions jsonl")
    p.add_argument("--out", required=True)
    p.add_argument("--report", required=True)
    p.set_defaults(fn=cmd_check_stage)

    p = sub.add_parser("describe", help="P8.01 descriptive statistics")
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--fields", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_describe)

    p = sub.add_parser("gap-map", help="P8.05 evidence gap map")
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--rows", required=True)
    p.add_argument("--cols", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_gap_map)

    p = sub.add_parser("prisma", help="P6.09 PRISMA counts and balance check")
    p.add_argument("--search-log", required=True)
    p.add_argument("--dedup-log", required=True)
    p.add_argument("--ta-report", required=True)
    p.add_argument("--ft-report", required=True)
    p.add_argument("--not-retrieved", type=int, required=True)
    p.add_argument("--chase-report")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_prisma)

    p = sub.add_parser("fig", help="P8.07-P8.11 figures")
    p.add_argument("kind", choices=["prisma", "gapmap", "timeline", "bars"])
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--year-field", default="year")
    p.add_argument("--stack-field", default="")
    p.add_argument("--field", default="")
    p.set_defaults(fn=cmd_fig)

    p = sub.add_parser("table", help="P8.12 characteristics longtable")
    p.add_argument("kind", choices=["characteristics"])
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--columns", nargs="+", required=True, help="field or field:Label")
    p.add_argument("--cite-keys", help="json map record_id -> bibtex key")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_table)

    p = sub.add_parser("freeze", help="P2.10 / P3.04 / P7.10 hash an artifact into the ledger")
    p.add_argument("path")
    p.add_argument("--ledger", required=True)
    p.add_argument("--node", required=True)
    p.set_defaults(fn=cmd_freeze)

    p = sub.add_parser("verify-frozen", help="every frozen artifact still matches its hash")
    p.add_argument("--ledger", required=True)
    p.set_defaults(fn=cmd_verify_frozen)

    p = sub.add_parser("search-age", help="P15.01 exit 1 when the search is stale")
    p.add_argument("--log", required=True)
    p.add_argument("--max-months", type=float, default=12)
    p.add_argument("--on", help="YYYY-MM-DD planned submission date (default today)")
    p.set_defaults(fn=cmd_search_age)

    p = sub.add_parser("lint", help="P11.05 house-style lint")
    p.add_argument("paths", nargs="+")
    p.set_defaults(fn=cmd_lint)

    p = sub.add_parser("check-numbers", help="P14.01 PRISMA counts appear in the PDF text")
    p.add_argument("--pdf", required=True)
    p.add_argument("--counts", required=True)
    p.set_defaults(fn=cmd_check_numbers)

    p = sub.add_parser("limits", help="P13.05 counts vs journal limits")
    p.add_argument("--tex", required=True)
    p.add_argument("--profile", required=True)
    p.set_defaults(fn=cmd_limits)

    p = sub.add_parser("check-layout", help="P13.07 fonts embedded")
    p.add_argument("--pdf", required=True)
    p.set_defaults(fn=cmd_check_layout)

    p = sub.add_parser("bib", help="P10.01 BibTeX for included records via DOI")
    p.add_argument("--included", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--keys", required=True, help="json map record_id -> cite key (feeds `table --cite-keys`)")
    p.set_defaults(fn=cmd_bib)

    p = sub.add_parser("bib-merge", help="P10.03 merge bibliographies")
    p.add_argument("bibs", nargs="+")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_bib_merge)

    p = sub.add_parser("retractions", help="P10.05 Crossref retraction check")
    p.add_argument("--bib", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_retractions)

    p = sub.add_parser("sheet", help="human cards: export or import a screening/adjudication/verification sheet")
    p.add_argument("kind", choices=["screen", "import-screen", "adjudicate", "verify", "import-verify"])
    p.add_argument("--in", dest="inp", help="records (screen), conflicts (adjudicate) or chart jsonl (verify)")
    p.add_argument("--records", help="adjudicate: records jsonl for titles")
    p.add_argument("--sheet", help="import-*: the filled CSV")
    p.add_argument("--stage", choices=["pilot", "ta", "ft", "chase"])
    p.add_argument("--screener", help="import-screen: the human's initials")
    p.add_argument("--verifier", help="import-verify: the human's initials")
    p.add_argument("--codes-from", help="eligibility.md or screening_guide.md declaring E-codes")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_sheet)

    p = sub.add_parser("finalize", help="P5.06 / P6.07 final decision per record")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--adjudicated", help="filled adjudication sheet")
    p.add_argument("--stage", required=True, choices=["pilot", "ta", "ft", "chase"])
    p.add_argument("--adjudicator", required=True)
    p.add_argument("--codes-from", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_finalize)

    p = sub.add_parser("audit-claims", help="P8.16 / P9.11 / P11.06 / P12.01d claim grounding gate")
    p.add_argument("--claims", required=True)
    p.add_argument("--data", required=True, help="frozen chart jsonl (included sources)")
    p.add_argument("--stats", help="stats.json, for stats: source ids")
    p.add_argument("--tex", help="manuscript dir; checks citations against the text")
    p.add_argument("--cite-keys", help="record_id -> cite key map from `agsci sr bib`")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_audit_claims)

    p = sub.add_parser("assemble", help="P9.10 draft main.tex")
    p.add_argument("--sections", nargs="+", required=True, help="section file stems in outline order")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_assemble)

    p = sub.add_parser("check-refs", help="P10.07 reference gate")
    p.add_argument("--tex", required=True, help="manuscript dir")
    p.add_argument("--bib", required=True)
    p.add_argument("--retractions")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_check_refs)

    p = sub.add_parser("proof-auto", help="P14.02 automated proof checks")
    p.add_argument("--tex", required=True, help="manuscript dir with main.log")
    p.add_argument("--lang", default="en_US")
    p.add_argument("--wordlist", help="project terms aspell should accept, whitespace separated")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_proof_auto)

    p = sub.add_parser("checklist", help="P14.05 reporting checklist with page numbers")
    p.add_argument("name", choices=["prisma_scr_2018", "prisma_2020"])
    p.add_argument("--map", required=True, help="reporting_map.yaml: item number -> label or 'na: reason'")
    p.add_argument("--aux", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_checklist)

    p = sub.add_parser("fetch-fulltext", help="P6.01 open-access full texts")
    p.add_argument("--in", dest="inp", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--log", required=True)
    p.set_defaults(fn=cmd_fetch_fulltext)

    p = sub.add_parser("convert", help="P6.03 PDF to Markdown")
    p.add_argument("inputs", nargs="+", help="dirs of PDFs")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_convert)

    p = sub.add_parser("chase", help="P6.08a citation chasing")
    p.add_argument("--included", required=True)
    p.add_argument("--backward-only", action="store_true")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_chase)

    p = sub.add_parser("test-search", help="P2.05a seed recall of the primary strategy")
    p.add_argument("--strategy", required=True)
    p.add_argument("--source", required=True, choices=sorted(sources.ADAPTERS))
    p.add_argument("--seeds", required=True)
    p.add_argument("--cap", type=int, default=2000)
    p.add_argument("--since", default="", help="earliest publication date, YYYY-MM-DD")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_test_search)

    p = sub.add_parser("chart-agreement", help="P7.01b field-level charting agreement")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_chart_agreement)

    p = sub.add_parser("journal-profile", help="P1.03 chosen journal profile")
    p.add_argument("--shortlist", required=True)
    p.add_argument("--choice", required=True, help="yaml: primary: <name>, fallbacks: [<name>, ...]")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_journal_profile)

    p = sub.add_parser("template", help="P1.05 fetch the journal LaTeX template")
    p.add_argument("--profile", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_template)

    p = sub.add_parser("supplement", help="P9.09 supplementary files")
    p.add_argument("--search-dir", required=True)
    p.add_argument("--charting-form", required=True)
    p.add_argument("--included", required=True)
    p.add_argument("--ft-final", required=True)
    p.add_argument("--records", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_supplement)

    p = sub.add_parser("package", help="P15.09 stage the submission package")
    p.add_argument("files", nargs="+")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_package)

    p = sub.add_parser("archive", help="P17.03 archive manifest")
    p.add_argument("--root", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_archive)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)
