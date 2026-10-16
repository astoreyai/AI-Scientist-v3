"""Scoping-review script nodes, tested on real records (see fixtures/PROVENANCE.md)."""

import itertools
import json
from pathlib import Path

import pytest

from src.scoping_review import agreement, cli, records

FIX = Path(__file__).parent / "fixtures"
RAW = FIX / "sr_search_2026-10-16" / "raw"
# aisr_* hold unpublished review decisions and are kept out of git (see PROVENANCE.md)
needs_aisr = pytest.mark.skipif(not (FIX / "aisr_decisions.jsonl").exists(), reason="aisr fixtures not on this host")


def load(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


@pytest.fixture(scope="module")
def search_rows():
    return [r for f in sorted(RAW.glob("*.jsonl")) for r in load(f)]


def test_dedup_leaves_no_shared_identifier(search_rows):
    kept, log = records.dedup(search_rows)
    assert len(kept) < len(search_rows) and log
    for key in ("doi", "pmid"):
        vals = [records.norm_doi(r.get(key)) if key == "doi" else r.get(key) for r in kept]
        vals = [v for v in vals if v]
        assert len(vals) == len(set(vals)), f"two kept records share a {key}"


def test_title_matching_recovers_identifier_duplicates(search_rows):
    truth = {}
    for i, r in enumerate(search_rows):
        for key in (("doi", records.norm_doi(r.get("doi"))), ("pmid", r.get("pmid") or "")):
            if key[1]:
                truth.setdefault(key, set()).add(i)
    pairs = {p for g in truth.values() for p in itertools.combinations(sorted(g), 2)}
    stripped = [{**r, "doi": None, "pmid": None, "id": f"x:{i}"} for i, r in enumerate(search_rows)]
    group = {}
    for rec in records.dedup(stripped)[0]:
        for rid in [rec["id"], *rec.get("merged_ids", [])]:
            group[int(rid[2:])] = rec["id"]
    recall = sum(group[a] == group[b] for a, b in pairs) / len(pairs)
    assert len(pairs) >= 10 and recall >= 0.9  # 18/19 on the 2026-10-16 fixture


def test_same_title_different_doi_is_flagged_as_version_pair(search_rows):
    _, log = records.dedup(search_rows)
    versions = [m for m in log if m["reason"] == "version_pair"]
    assert versions, "the fixture holds preprint/published pairs (e.g. arXiv vs Springer DOI)"
    assert all(m["kept"].startswith("doi:") and m["merged"].startswith("doi:") for m in versions)


def test_kappa_matches_published_worked_example():
    # Wikipedia "Cohen's kappa": 20 yes/yes, 5 yes/no, 10 no/yes, 15 no/no -> p_o 0.7, p_e 0.5, kappa 0.4
    a = ["y"] * 20 + ["y"] * 5 + ["n"] * 10 + ["n"] * 15
    b = ["y"] * 20 + ["n"] * 5 + ["y"] * 10 + ["n"] * 15
    assert agreement.cohen_kappa(a, b) == pytest.approx(0.4)


def test_maybe_counts_as_include_before_full_text():
    assert agreement.as_binary("maybe", "ta") == "include"
    assert agreement.as_binary("maybe", "ft") == "maybe"


@needs_aisr
def test_check_stage_gate_passes_on_complete_real_decisions(tmp_path):
    out, rep = tmp_path / "inc.jsonl", tmp_path / "rep.json"
    rc = cli.main(["check-stage", "ft", "--records", str(FIX / "aisr_records.jsonl"),
                   "--decisions", str(FIX / "aisr_decisions.jsonl"), "--out", str(out), "--report", str(rep)])
    report = json.loads(rep.read_text())
    assert rc == 0 and report["included"] == 139 and report["exclusion_reasons"] == {"E1": 36, "E5": 1}
    assert len(load(out)) == 139


@needs_aisr
def test_check_stage_gate_fails_when_a_decision_is_missing(tmp_path):
    decisions = load(FIX / "aisr_decisions.jsonl")[1:]
    dpath = tmp_path / "d.jsonl"
    dpath.write_text("".join(json.dumps(d) + "\n" for d in decisions))
    rc = cli.main(["check-stage", "ft", "--records", str(FIX / "aisr_records.jsonl"), "--decisions", str(dpath),
                   "--out", str(tmp_path / "inc.jsonl"), "--report", str(tmp_path / "rep.json")])
    assert rc == 1 and not (tmp_path / "inc.jsonl").exists()


@needs_aisr
def test_agreement_cli_pairs_real_decisions_with_themselves(tmp_path):
    d = FIX / "aisr_decisions.jsonl"
    rc = cli.main(["agreement", "--a", str(d), "--b", str(d), "--stage", "ft", "--out", str(tmp_path / "k.json"),
                   "--conflicts", str(tmp_path / "c.jsonl")])
    s = json.loads((tmp_path / "k.json").read_text())
    assert rc == 0 and s["agreement"] == 1.0 and s["kappa"] == pytest.approx(1.0) and s["n_conflicts"] == 0


def test_dedup_sample_puts_every_version_pair_first(tmp_path, search_rows):
    raw = tmp_path / "raw.jsonl"
    raw.write_text("".join(json.dumps(r) + "\n" for r in search_rows))
    cli.main(["dedup", str(raw), "--out", str(tmp_path / "d.jsonl"), "--log", str(tmp_path / "log.json")])
    cli.main(["dedup-sample", "--log", str(tmp_path / "log.json"), "--n", "50", "--out", str(tmp_path / "s.jsonl")])
    picked = load(tmp_path / "s.jsonl")
    versions = [m for m in json.loads((tmp_path / "log.json").read_text())["merges"] if m["reason"] == "version_pair"]
    assert picked[: len(versions)] == [{**m, "false_merge": None} for m in versions]


# ---- synthesis and figures (real charted data: fixtures/aisr_chart.jsonl) ----

from src.scoping_review import figures, synthesis  # noqa: E402

CHART = load(FIX / "aisr_chart.jsonl") if (FIX / "aisr_chart.jsonl").exists() else []


@needs_aisr
def test_describe_counts_match_direct_count():
    stats = synthesis.describe(CHART, ["autonomy_level", "pipeline_stages_covered"])
    direct = sum(1 for r in CHART if r["fields"]["autonomy_level"]["value"] == "Scientist")
    assert stats["n_sources"] == 139 and stats["fields"]["autonomy_level"]["counts"]["Scientist"] == direct
    stages = stats["fields"]["pipeline_stages_covered"]
    assert len(stages["record_ids"]["Writing"]) == stages["counts"]["Writing"]


@needs_aisr
def test_gap_map_cells_hold_the_right_records():
    gm = synthesis.gap_map(CHART, "pipeline_stages_covered", "autonomy_level")
    for (r, c), ids in [(k.split("|"), v) for k, v in gm["record_ids"].items()]:
        for rid in ids:
            rec = next(x for x in CHART if x["record_id"] == rid)
            assert r in synthesis.field_values(rec, "pipeline_stages_covered")
            assert c in synthesis.field_values(rec, "autonomy_level")
    assert sum(map(sum, gm["counts"])) == sum(len(v) for v in gm["record_ids"].values())


@needs_aisr
def test_prisma_balance_flags_mismatched_stages(tmp_path):
    # Identification from the 2026-10-16 search and full-text decisions from a different review:
    # these cannot balance, and the gate must say so.
    cli.main(["dedup", str(RAW), "--out", str(tmp_path / "d.jsonl"), "--log", str(tmp_path / "dlog.json")])
    cli.main(["check-stage", "ft", "--records", str(FIX / "aisr_records.jsonl"), "--decisions",
              str(FIX / "aisr_decisions.jsonl"), "--out", str(tmp_path / "i.jsonl"), "--report", str(tmp_path / "ft.json")])
    rc = cli.main(["prisma", "--search-log", str(RAW.parent / "search_log.json"), "--dedup-log", str(tmp_path / "dlog.json"),
                   "--ta-report", str(tmp_path / "ft.json"), "--ft-report", str(tmp_path / "ft.json"),
                   "--not-retrieved", "0", "--out", str(tmp_path / "p.json")])
    counts = json.loads((tmp_path / "p.json").read_text())
    assert rc == 1 and counts["identified"] == 299 and counts["duplicates_removed"] == 24
    assert any("screened 176" in p for p in counts["balance_problems"])


@needs_aisr
@pytest.mark.parametrize("kind", ["timeline", "gapmap", "bars", "prisma"])
def test_figures_embed_truetype_fonts(tmp_path, kind):
    out = tmp_path / f"{kind}.pdf"
    if kind == "timeline":
        figures.timeline(CHART, "year", "autonomy_level", out)
    elif kind == "gapmap":
        figures.gap_heatmap(synthesis.gap_map(CHART, "pipeline_stages_covered", "autonomy_level"), out)
    elif kind == "bars":
        s = synthesis.describe(CHART, ["evaluation_method"])
        figures.category_bars(s["fields"]["evaluation_method"]["counts"], "evaluation method", 139, out)
    else:
        kept, log = records.dedup([r for f in sorted(RAW.glob("*.jsonl")) for r in load(f)])
        cli.main(["check-stage", "ft", "--records", str(FIX / "aisr_records.jsonl"), "--decisions", str(FIX / "aisr_decisions.jsonl"),
                  "--out", str(tmp_path / "i.jsonl"), "--report", str(tmp_path / "ft.json")])
        ft = json.loads((tmp_path / "ft.json").read_text())
        counts = synthesis.prisma_counts(json.loads((RAW.parent / "search_log.json").read_text()),
                                         {"duplicates_removed": len(log)}, ft, ft, 0, None)
        figures.prisma_flow(counts, out)
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and b"/FontFile2" in data and b"/Subtype /Type3" not in data


@needs_aisr
def test_characteristics_table_escapes_latex():
    tex = figures.characteristics_table(CHART[:5], [("domain", "Domain"), ("paper_type", "Type")], {})
    assert tex.startswith(r"\begin{longtable}") and tex.count(r" \\") == 6
    assert "_" not in tex.replace(r"\_", "")


# ---- references and integrity ----

import datetime as dt  # noqa: E402
import shutil  # noqa: E402

from src.scoping_review import bib, integrity  # noqa: E402

CR = FIX / "crossref_2026-10-16"
WAKEFIELD = "10.1016/s0140-6736(97)11096-0"
WANG = "10.1007/978-3-031-56027-9_25"
HILK = "10.1186/s13643-026-03228-4"


def recorded(url, headers):
    doi = url.split("updates:")[-1].split("&")[0] if "updates:" in url else url.split("doi.org/")[-1]
    stem = doi.replace("/", "_").replace("(", "_").replace(")", "_")
    return (CR / (f"updates_{stem}.json" if "updates:" in url else f"bib_{stem}.bib")).read_bytes()


def test_retraction_detected_from_real_crossref_notice():
    w = bib.retraction_status(WAKEFIELD, fetch=recorded)
    assert w["retracted"] and {n["type"] for n in w["notices"]} == {"retraction", "correction"}
    assert not bib.retraction_status(WANG, fetch=recorded)["retracted"]


def test_doi_bibtex_gets_stable_key_and_merge_drops_duplicate_doi():
    a, b = bib.doi_bibtex(WANG, fetch=recorded), bib.doi_bibtex(HILK, fetch=recorded)
    assert a.startswith("@inbook{doi_10_1007_978_3_031_56027_9_25,")
    merged, dropped = bib.merge(a + "\n" + b, (CR / f"bib_{HILK.replace('/', '_')}.bib").read_text())
    assert len(bib.entries(merged)) == 2 and dropped == ["Hilkenmeier_2026"]


def test_freeze_detects_change_after_freeze(tmp_path):
    art = tmp_path / "protocol.md"
    shutil.copy(FIX / "PROVENANCE.md", art)
    ledger = tmp_path / "ledger.jsonl"
    assert integrity.freeze(art, ledger, "P2.10")["event"] == "freeze"
    assert integrity.verify_frozen(ledger) == []
    art.write_text(art.read_text() + "\nedited after freeze\n")
    assert integrity.verify_frozen(ledger) == [str(art)]
    assert integrity.freeze(art, ledger, "P2.10")["event"] == "refreeze_changed"


def test_search_age_from_real_log():
    log = json.loads((RAW.parent / "search_log.json").read_text())
    assert integrity.search_age_months(log, dt.date(2027, 10, 16)) == pytest.approx(12.0, abs=0.1)


def test_lint_passes_clean_template():
    assert integrity.lint([Path("src/agents/skills/write-paper/templates/iclr/paper.tex")]) == []


REAL_TEX = Path("/mnt/projects/publications/outbox/37_score-without-evidence_IJCB/manuscript/main_blind.tex")


@pytest.mark.skipif(not REAL_TEX.exists(), reason="real manuscript not on this host")
def test_lint_flags_banned_word_in_real_manuscript():
    assert any(f["rule"].startswith("banned word") for f in integrity.lint([REAL_TEX]))


REAL_PDF = Path("/mnt/projects/ai-scientist-review/manuscript/full_manuscript_final.pdf")


@pytest.mark.skipif(not REAL_PDF.exists(), reason="real manuscript not on this host")
def test_check_numbers_on_real_manuscript():
    text = integrity.pdf_text(REAL_PDF)
    stated = {"identified": 551, "screened": 184, "assessed_full_text": 176, "included": 139, "excluded_full_text": 37}
    assert integrity.check_numbers(text, stated) == []
    assert integrity.check_numbers(text, stated | {"included": 1391}) == ["PRISMA count included=1391 does not appear in the text"]


def test_limits_counts_words_and_flags_overrun():
    tex = Path("src/agents/skills/write-paper/templates/iclr/paper.tex")
    res = integrity.limits(tex, None, {"word_limit": 10})
    assert res["counts"]["words"] > 10 and res["over"]["words"] == res["counts"]["words"] - 10
    assert integrity.limits(tex, None, {"word_limit": None})["over"] == {}


@needs_aisr
def test_fonts_embedded_in_generated_figure(tmp_path):
    figures.category_bars({"a": 1}, "x", 1, tmp_path / "f.pdf")
    assert integrity.fonts_not_embedded(tmp_path / "f.pdf") == []


# ---- human sheets (real decisions from fixtures/aisr_decisions.jsonl) ----

import csv  # noqa: E402

from src.scoping_review import sheets  # noqa: E402

CODES = {"E1", "E5"}  # the exclusion codes the real review used


def fill(sheet, values):
    rows = list(csv.DictReader(sheet.open()))
    for r in rows:
        r.update(values[r["record_id"]])
    with sheet.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


@needs_aisr
def test_screen_sheet_round_trip_reproduces_real_decisions(tmp_path):
    recs, decs = load(FIX / "aisr_records.jsonl"), load(FIX / "aisr_decisions.jsonl")
    sheet = tmp_path / "screen.csv"
    sheets.export_screen(recs, sheet)
    assert "decision_1" not in sheet.read_text().splitlines()[0], "screening sheet must not show another screener"
    fill(sheet, {d["record_id"]: {"decision": d["decision"], "reason_code": d["reason_code"]} for d in decs})
    back = sheets.import_screen(sheet, "ft", "AWS", CODES)
    assert [(b["record_id"], b["decision"], b["reason_code"]) for b in back] == \
           [(d["record_id"], d["decision"], d["reason_code"]) for d in decs]


@needs_aisr
def test_screen_sheet_rejects_unknown_reason_code(tmp_path):
    recs = load(FIX / "aisr_records.jsonl")[:3]
    sheet = tmp_path / "s.csv"
    sheets.export_screen(recs, sheet)
    fill(sheet, {r["id"]: {"decision": "exclude", "reason_code": "E9"} for r in recs})
    with pytest.raises(ValueError, match="reason code 'E9'"):
        sheets.import_screen(sheet, "ta", "AWS", CODES)


@needs_aisr
def test_finalize_agreement_and_unresolved_conflict():
    decs = load(FIX / "aisr_decisions.jsonl")
    final = sheets.finalize(decs, decs, None, "ft", "AWS", CODES)
    assert len(final) == 176 and sum(f["decision"] == "include" for f in final) == 139
    flipped = [dict(d, decision="exclude", reason_code="E1") if i == 0 else d for i, d in enumerate(decs)]
    with pytest.raises(ValueError, match="1 conflicts have no adjudication"):
        sheets.finalize(decs, flipped, None, "ft", "AWS", CODES)


@needs_aisr
def test_verify_sheet_requires_a_verdict_for_every_field(tmp_path):
    chart = CHART[:4]
    sheet = tmp_path / "v.csv"
    sheets.export_verify(chart, sheet)
    rows = list(csv.DictReader(sheet.open()))
    fill(sheet, {r["record_id"]: {"verdict": "accept"} for r in rows})
    out = sheets.import_verify(chart, sheet, "AWS")
    assert all(f["verified_by"] == "AWS" and f["status"] in ("verified", "not_reported") for r in out for f in r["fields"].values())
    sheets.export_verify(chart, sheet)
    with pytest.raises(ValueError, match="not verified"):
        sheets.import_verify(chart, sheet, "AWS")


# ---- manuscript gates ----

from src.scoping_review import manuscript  # noqa: E402

P31 = Path("/mnt/projects/publications/outbox/31_world-model-survey_MDPI-Electronics/manuscript")
needs_p31 = pytest.mark.skipif(not (P31 / "main.aux").exists(), reason="paper 31 (a real compiled survey) not on this host")


def derived_claims():
    """Claims computed from the real charted data: 'N sources are <level>' grounded in exactly those records."""
    stats = synthesis.describe(CHART, ["autonomy_level"])
    f = stats["fields"]["autonomy_level"]
    return stats, {"claims": [{"claim": f"{n} of {stats['n_sources']} sources are at the {lvl} level",
                               "source_ids": f["record_ids"][lvl] + [f"stats:fields.autonomy_level.counts.{lvl}"]}
                              for lvl, n in f["counts"].items()]}


@needs_aisr
def test_audit_claims_accepts_grounded_and_rejects_ungrounded():
    stats, claims = derived_claims()
    included = {r["record_id"] for r in CHART}
    assert manuscript.audit_claims(claims, included, manuscript.stats_keys(stats), None, {}) == []
    claims["claims"].append({"claim": "one more", "source_ids": ["arxiv:9999.99999"]})
    claims["claims"].append({"claim": "unsourced", "source_ids": []})
    problems = manuscript.audit_claims(claims, included, manuscript.stats_keys(stats), None, {})
    assert any("not an included source" in p for p in problems) and any("no source_ids" in p for p in problems)


@needs_p31
def test_all_tex_follows_inputs_and_ignores_backups():
    text = manuscript.all_tex(P31)
    assert text.startswith((P31 / "main.tex").read_text(errors="replace")[:200])
    assert (P31 / "main_backup_2026-06-05.tex").read_text(errors="replace") not in text


@needs_p31
def test_check_refs_on_real_survey():
    problems = manuscript.check_refs(manuscript.all_tex(P31), (P31 / "references.bib").read_text(), [])
    assert not any(p.startswith("dangling") for p in problems), problems[:5]


@needs_p31
def test_checklist_pages_come_from_real_aux(tmp_path):
    aux = (P31 / "main.aux").read_text()
    pages = manuscript.page_of_labels(aux)
    assert pages["sec:introduction"] == "1" and pages["sec:background"] == "3"
    labels = [k for k in pages if k.startswith("sec:") and "@" not in k]
    mapping = {n: labels[(n - 1) % len(labels)] for n in range(1, 23)} | {12: "na: not done", 16: "na: not done"}
    tex, problems = manuscript.checklist("prisma_scr_2018", mapping, aux)
    assert problems == [] and tex.count(r"\\") >= 22 and "Identify the report as a scoping review" not in tex
    del mapping[5]
    assert manuscript.checklist("prisma_scr_2018", mapping | {14: "na"}, aux)[1] == [
        "item 5 (Protocol and registration) is not mapped to a label or 'na'",
        "item 14 (Selection of sources of evidence) is required but marked na"]


@needs_p31
def test_proof_auto_on_real_survey_finds_real_faults_without_latex_noise():
    found = manuscript.proof_auto((P31 / "main.log").read_text(errors="replace"), manuscript.all_tex(P31))
    # paper 31 uses LLM and GAN without defining them, and British spellings in a US-English text
    assert "acronym never defined: LLM" in found and "acronym never defined: GAN" in found
    assert "spelling: labelled" in found
    assert "spelling: lcccccccccc" not in found, "tabular column specs are not prose"
    assert "acronym never defined: AND" not in found, "Boolean operators in search strings are not acronyms"
    fewer = manuscript.proof_auto("", manuscript.all_tex(P31), wordlist={"labelled", "LLM"})
    assert "spelling: labelled" not in fewer and "acronym never defined: LLM" not in fewer


# ---- full text, chasing, seed recall (recorded OpenAlex responses, real OA PDF) ----

from src.scoping_review import fulltext  # noqa: E402

OA = FIX / "openalex_2026-10-16"


def replay(url):
    if "/works/doi:" in url:
        return (OA / f"work_{url.split('/works/doi:')[1].replace('/', '_')}.json").read_bytes()
    if "filter=cites:" in url:
        return (OA / f"cites_{url.split('cites:')[1].split('&')[0]}.json").read_bytes()
    if url.endswith(".pdf"):
        return (OA / "hilkenmeier_2026.pdf").read_bytes()
    raise LookupError(url)  # anything unrecorded fails loudly instead of hitting the network


def test_fetch_fulltext_downloads_oa_pdf_and_lists_missing(tmp_path):
    recs = [{"id": "doi:10.1186/s13643-026-03228-4", "doi": "10.1186/s13643-026-03228-4"},
            {"id": "doi:10.1007/978-3-031-56027-9_25", "doi": "10.1007/978-3-031-56027-9_25"}]
    log = fulltext.fetch_fulltext(recs, tmp_path, fetch=replay)
    assert [e["status"] for e in log] == ["retrieved", "missing"]
    assert (tmp_path / "doi_10.1186_s13643-026-03228-4.pdf").read_bytes()[:4] == b"%PDF"


def test_convert_keeps_page_markers(tmp_path, monkeypatch):
    monkeypatch.setattr(fulltext.shutil, "which", lambda _: None)  # exercise the pdftotext path
    pdfs = tmp_path / "pdf"
    pdfs.mkdir()
    shutil.copy(OA / "hilkenmeier_2026.pdf", pdfs / "h.pdf")
    fulltext.convert([pdfs], tmp_path / "md")
    md = (tmp_path / "md" / "h.md").read_text()
    assert md.count("<!-- page ") == 15 and "title-and-abstract screening" in md.replace("-\n", "")


def test_chase_collects_backward_and_forward_candidates():
    rec = {"id": "doi:10.1186/s13643-026-03228-4", "doi": "10.1186/s13643-026-03228-4"}
    work = json.loads((OA / "work_10.1186_s13643-026-03228-4.json").read_text())
    batches = iter(sorted(OA.glob("refs_batch_*.json")))

    def fetch(url):
        return next(batches).read_bytes() if "openalex_id:" in url else replay(url)

    found, unresolved = fulltext.chase([rec], fetch=fetch)
    recorded = [r for f in sorted(OA.glob("refs_batch_*.json")) for r in json.loads(f.read_text())["results"]]
    citing = json.loads((OA / f"cites_{work['id'].rsplit('/', 1)[1]}.json").read_text())["results"]
    # OpenAlex resolved 67 of the 68 referenced ids on 2026-10-16; the missing one must be reported
    assert len(work["referenced_works"]) == 68 and len(recorded) == 67 and len(unresolved) == 1
    assert len(found) == len(records.dedup([fulltext._work_to_record(w) for w in recorded + citing])[0])
    assert all(r["query_id"] == "citation_chasing" and r["title"] for r in found)


def test_seed_recall_on_real_search_results(search_rows):
    seeds = "\n".join((CR / f).read_text() for f in ["bib_10.1007_978-3-031-56027-9_25.bib", "bib_10.1186_s13643-026-03228-4.bib",
                                                     "bib_10.1016_s0140-6736_97_11096-0.bib"])
    res = fulltext.seed_recall(search_rows, seeds)
    assert res["seeds"] == 3 and len(res["found"]) == 2 and res["recall"] == pytest.approx(2 / 3)
    assert res["missed"] == ["Wakefield_1998"]


@needs_aisr
def test_field_agreement_on_real_chart():
    same = fulltext.field_agreement(CHART[:10], CHART[:10])
    assert same["agreement"] == 1.0 and same["below"] == []
    other = [dict(r, fields=dict(r["fields"], domain=dict(r["fields"]["domain"], value="Other"))) for r in CHART[:10]]
    changed = sum(r["fields"]["domain"]["value"] != "Other" for r in CHART[:10])
    res = fulltext.field_agreement(CHART[:10], other)
    assert res["agreement"] == pytest.approx(1 - changed / res["fields_compared"]) and res["below"] == ["domain"]


# ---- journal profile, supplement, package, archive ----

import yaml  # noqa: E402

from src.scoping_review import submission  # noqa: E402

JAIR = yaml.safe_load((FIX / "jair_shortlist_2026-10-16.yaml").read_text())
NAME = "Journal of Artificial Intelligence Research"


def test_journal_profile_from_real_shortlist():
    prof = submission.journal_profile(JAIR, {"primary": NAME, "fallbacks": []})
    assert prof["profile"]["reporting_checklist"] == "none_stated" and len(prof["unverified"]) == 3
    with pytest.raises(ValueError, match="not on the shortlist"):
        submission.journal_profile(JAIR, {"primary": "Nature"})
    broken = yaml.safe_load(yaml.safe_dump(JAIR))
    del broken["candidates"][0]["profile"]["ai_policy"]
    with pytest.raises(ValueError, match="missing required field: ai_policy"):
        submission.journal_profile(broken, {"primary": NAME})


def test_template_refuses_when_profile_has_no_url(tmp_path):
    with pytest.raises(ValueError, match="no latex_template_url"):
        submission.fetch_template(JAIR["candidates"][0]["profile"]["latex_template_url"], tmp_path)


@needs_aisr
def test_supplement_from_real_artifacts(tmp_path):
    form = [{"id": f["field_name"], "label": f["description"], "guidance": f.get("extraction_guidance", "")}
            for f in json.loads(Path("/mnt/projects/ai-scientist-review/phase1/extraction_template.json").read_text())["fields"]] \
        if Path("/mnt/projects/ai-scientist-review/phase1/extraction_template.json").exists() else \
        [{"id": k, "label": k, "guidance": ""} for k in CHART[0]["fields"]]
    (tmp_path / "form.yaml").write_text(yaml.safe_dump(form))
    recs = load(FIX / "aisr_records.jsonl")
    made = submission.supplement(RAW.parent / "strategies", tmp_path / "form.yaml", recs[:5],
                                 load(FIX / "aisr_decisions.jsonl"), {r["id"]: r for r in recs}, tmp_path / "supp")
    assert made == ["S1_search_strategies.tex", "S2_charting_form.tex", "S3_included_sources.tex", "S4_excluded_full_text.tex"]
    s4 = (tmp_path / "supp" / "S4_excluded_full_text.tex").read_text()
    assert s4.count(r" \\") == 1 + 37 and "E5" in s4  # header row + the 37 real exclusions


def test_package_copies_with_manifest_and_never_overwrites(tmp_path):
    files = [FIX / "PROVENANCE.md", OA / "hilkenmeier_2026.pdf"]
    m = submission.package(files, tmp_path / "pkg")
    assert set(m["files"]) == {"PROVENANCE.md", "hilkenmeier_2026.pdf"}
    with pytest.raises(ValueError, match="already holds a package"):
        submission.package(files, tmp_path / "pkg")


@needs_aisr
def test_archive_hashes_review_and_manuscript(tmp_path):
    (tmp_path / "review").mkdir()
    (tmp_path / "manuscript").mkdir()
    shutil.copy(FIX / "aisr_decisions.jsonl", tmp_path / "review" / "board_state.jsonl")
    shutil.copy(OA / "hilkenmeier_2026.pdf", tmp_path / "manuscript" / "main.pdf")
    m = submission.archive(tmp_path, tmp_path / "out" / "manifest.json")
    assert set(m["files"]) == {"review/board_state.jsonl", "manuscript/main.pdf"} and m["ledgers"] == ["review/board_state.jsonl"]
