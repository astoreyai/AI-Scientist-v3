"""Risk-of-bias rules over the full judgement space; GRADE and SoF on the real BCG meta-analysis."""

import itertools
import statistics

import pytest

from src.systematic_review import appraisal, meta
from tests.systematic_review.test_meta import ROWS, TABLES, V, Y


def all_combinations(tool):
    spec = appraisal.TOOLS[tool]
    for combo in itertools.product(spec["levels"], repeat=len(spec["domains"])):
        yield dict(zip(spec["domains"], combo))


def test_rob2_overall_rule_over_every_combination():
    for j in all_combinations("rob2"):
        got = appraisal.overall("rob2", j)["overall"]
        vals = set(j.values())
        want = "low" if vals == {"low"} else "high" if "high" in vals else "some_concerns"
        assert got == want, j


def test_robins_overall_is_most_severe_domain():
    order = appraisal.TOOLS["robins_i_v2"]["levels"]
    for j in all_combinations("robins_i_v2"):
        assert appraisal.overall("robins_i_v2", j)["overall"] == max(j.values(), key=order.index)


def test_missing_domain_and_assessor_disagreement():
    j = dict.fromkeys(appraisal.TOOLS["rob2"]["domains"], "low")
    del j["missing outcome data"]
    with pytest.raises(ValueError, match="missing domains"):
        appraisal.overall("rob2", j)
    full = dict.fromkeys(appraisal.TOOLS["rob2"]["domains"], "low")
    diff = appraisal.compare_assessors("rob2", {"Aronson 1948": full}, {"Aronson 1948": full | {"missing outcome data": "high"}})
    assert diff == [{"study": "Aronson 1948", "domain": "missing outcome data", "first": "low", "second": "high"}]


def test_grade_requires_reasons_and_floors_at_very_low():
    with pytest.raises(ValueError, match="no reason"):
        appraisal.grade("high", {"inconsistency": 1}, {}, {})
    g = appraisal.grade("high", {"inconsistency": 2, "risk_of_bias": 1, "imprecision": 1}, {},
                        {"inconsistency": "I2 = 92%", "risk_of_bias": "r", "imprecision": "i"})
    assert g["certainty"] == "very_low"


def test_sof_row_from_real_bcg_meta_analysis():
    res = meta.meta(Y, V, "REML", hksj=True)
    control_risk = statistics.median(c / (c + d) for _, _, c, d in TABLES)  # observed control-arm risk across the 13 trials
    a = appraisal.absolute_effect("RR", res["est"], res["ci_lb"], res["ci_ub"], control_risk)
    assert a["intervention_per"] < a["control_per"] and a["difference_ci"][0] < a["difference_ci"][1] < 0
    g = appraisal.grade("high", {"inconsistency": 2}, {}, {"inconsistency": f"I2 = {res['I2']:.0f}%, prediction interval crosses 1"})
    tex = appraisal.sof_table([{"outcome": "Tuberculosis", "absolute": a, "relative": "RR 0.49 (0.33 to 0.73)",
                                "participants": sum(sum(t) for t in TABLES), "studies": len(ROWS), "certainty": g["certainty"]}],
                              "BCG vaccine vs no vaccine", "general population")
    assert "Low" in tex and r"\begin{longtable}" in tex
    with pytest.raises(ValueError, match="1 to 7"):
        appraisal.sof_table([], "x", "y")


def test_prisma_2020_checklist_has_all_items_and_maps_pages():
    from pathlib import Path

    import yaml

    from src.scoping_review import manuscript
    items = yaml.safe_load(Path("src/systematic_review/checklists/prisma_2020.yaml").read_text())["items"]
    assert len(items) == 42 and {i["n"] for i in items} >= {"1", "13d", "24c", "27"}
    aux = r"\newlabel{sec:methods}{{2}{4}{Methods}{section.2}{}}"
    tex, problems = manuscript.checklist("prisma_2020", {i["n"]: "sec:methods" for i in items}, aux)
    assert problems == [] and tex.count(" & 4 \\\\") == 42
