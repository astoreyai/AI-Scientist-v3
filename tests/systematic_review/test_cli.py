"""`agsci sysrev` end to end on the BCG trials (real data, checked against metafor)."""

import csv
import json
from pathlib import Path

import pytest

from src.systematic_review import appraisal
from src.systematic_review.cli import main

FIX = Path(__file__).parent / "fixtures"
REF = json.loads((FIX / "bcg_metafor_reference.json").read_text())
EXT = FIX / "bcg_extraction.jsonl"


def run(*args):
    return main([str(a) for a in args])


def test_meta_forest_funnel_subgroups_sensitivity(tmp_path):
    m = tmp_path / "meta_tb.json"
    assert run("meta", "--in", EXT, "--outcome", "tb", "--measure", "RR", "--method", "reml_hksj", "--out", m) == 0
    res = json.loads(m.read_text())
    assert res["k"] == 13 and res["est"] == pytest.approx(REF["REML_HKSJ"]["est"], abs=1e-6)
    assert res["ci_lb"] == pytest.approx(REF["REML_HKSJ"]["ci_lb"], abs=1e-6) and res["method"] == "REML+HKSJ"
    assert run("forest", "--meta", m, "--labels", FIX / "bcg_labels.json", "--out", tmp_path / "f.pdf") == 0
    assert run("funnel-eligible", "--meta", m) == 0
    assert run("funnel", "--meta", m, "--out", tmp_path / "u.pdf", "--egger", tmp_path / "e.json") == 0
    assert json.loads((tmp_path / "e.json").read_text())["tb"]["p"] == pytest.approx(REF["egger"]["p"], abs=1e-8)
    assert run("subgroups", "--meta", m, "--in", EXT, "--by", "allocation", "--out", tmp_path / "s.json") == 0
    assert json.loads((tmp_path / "s.json").read_text())["Q_between"] == pytest.approx(REF["subgroup_alloc"]["Q_between"], rel=1e-6)
    (tmp_path / "rob.json").write_text("{}")
    assert run("sensitivity", "--meta", m, "--rob", tmp_path / "rob.json", "--out", tmp_path / "sens.json") == 0
    sens = json.loads((tmp_path / "sens.json").read_text())
    assert [r["est"] for r in sens["leave_one_out"].values()] == pytest.approx(REF["leave1out"]["est"], abs=1e-6)


def test_sparse_methods_through_cli(tmp_path):
    for method, key in (("mantel_haenszel", "MH_OR"), ("peto", "PETO")):
        out = tmp_path / f"{method}.json"
        assert run("meta", "--in", EXT, "--outcome", "tb", "--measure", "OR", "--method", method, "--out", out) == 0
        assert json.loads(out.read_text())["est"] == pytest.approx(REF[key]["est"], abs=1e-6)
        assert run("funnel-eligible", "--meta", out) == 1, "no original Egger test for OR"


def test_unknown_outcome_fails_cleanly(tmp_path):
    assert run("meta", "--in", EXT, "--outcome", "mortality", "--measure", "RR", "--method", "reml_hksj", "--out", tmp_path / "x") == 1


def test_rob_sheet_import_compare_overall(tmp_path):
    studies = tmp_path / "studies.jsonl"
    studies.write_text("".join(json.dumps({"id": json.loads(line)["record_id"]}) + "\n" for line in EXT.read_text().splitlines()[:3]))
    assert run("rob-sheet", "--tool", "rob2", "--studies", studies, "--out", tmp_path / "s.csv") == 0
    rows = list(csv.DictReader((tmp_path / "s.csv").open()))
    assert len(rows) == 3 * 5
    assert run("rob-import", "--tool", "rob2", "--sheet", tmp_path / "s.csv", "--out", tmp_path / "h.json") == 1, "blank sheet must fail"
    # Every level of the tool once per study: a specification walk, not invented study findings
    levels = appraisal.TOOLS["rob2"]["levels"]
    for i, r in enumerate(rows):
        r.update(judgement=levels[i % 3], quote="see report" if levels[i % 3] != "low" else "", page="1")
    with (tmp_path / "s.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    assert run("rob-import", "--tool", "rob2", "--sheet", tmp_path / "s.csv", "--out", tmp_path / "h.json") == 0
    assert run("rob-compare", "--tool", "rob2", "--a", tmp_path / "h.json", "--b", tmp_path / "h.json", "--out", tmp_path / "c.json") == 0
    assert json.loads((tmp_path / "c.json").read_text()) == []
    assert run("rob-overall", "--tool", "rob2", "--in", tmp_path / "h.json", "--out", tmp_path / "o.json", "--fig", tmp_path / "t.pdf") == 0
    assert set(v["overall"] for v in json.loads((tmp_path / "o.json").read_text()).values()) == {"high"}


def test_grade_check_and_sof(tmp_path):
    m = tmp_path / "meta"
    m.mkdir()
    run("meta", "--in", EXT, "--outcome", "tb", "--measure", "RR", "--method", "reml_hksj", "--out", m / "meta_tb.json")
    rows = list(csv.DictReader((FIX / "bcg_colditz1994.csv").open()))
    cpos, cn = sum(int(r["cpos"]) for r in rows), sum(int(r["cpos"]) + int(r["cneg"]) for r in rows)
    total = sum(int(r[k]) for r in rows for k in ("tpos", "tneg", "cpos", "cneg"))
    g = {"tb": {"start": "high", "down": {"inconsistency": 2}, "reasons": {"inconsistency": "I2 = 92%; prediction interval crosses 1"},
                "participants": total, "control_risk": cpos / cn}}  # pooled control-arm risk across the 13 trials
    (tmp_path / "grade.json").write_text(json.dumps(g))
    assert run("grade-check", "--in", tmp_path / "grade.json") == 0
    assert run("sof", "--grade", tmp_path / "grade.json", "--meta", m, "--comparison", "BCG vs no vaccine",
               "--population", "13 trials", "--out", tmp_path / "sof.tex") == 0
    assert "RR 0.49 (0.33 to 0.73)" in (tmp_path / "sof.tex").read_text()
    g["tb"]["reasons"] = {}
    (tmp_path / "grade.json").write_text(json.dumps(g))
    assert run("grade-check", "--in", tmp_path / "grade.json") == 1


def test_search_lint_on_real_strategy(tmp_path):
    real = Path("tests/scoping_review/fixtures/sr_search_2026-10-16/strategies/pubmed.txt").read_text()
    (tmp_path / "pubmed.txt").write_text(real)
    assert run("search-lint", tmp_path, "--out", tmp_path / "l.json") == 1
    # the recorded 2026-10-16 strategy is free text only, so the controlled-vocabulary rule fires
    assert json.loads((tmp_path / "l.json").read_text())["problems"] == ["pubmed.txt: no controlled vocabulary terms (MECIR C33)"]
    (tmp_path / "pubmed.txt").write_text(real.strip() + " NOT animals")
    run("search-lint", tmp_path, "--out", tmp_path / "l.json")
    assert "pubmed.txt: uses NOT (MECIR C32)" in json.loads((tmp_path / "l.json").read_text())["problems"]
    (tmp_path / "pubmed.txt").write_text("# Filters NOT applied: none\n" + real.strip())
    run("search-lint", tmp_path, "--out", tmp_path / "l.json")
    assert not any("NOT" in p for p in json.loads((tmp_path / "l.json").read_text())["problems"]), "a comment is not the query"
