"""Meta-analysis checked against R metafor 3.8.1 on the 13 BCG trials (Colditz et al. 1994)."""

import csv
import json
from pathlib import Path

import pytest

from src.systematic_review import meta

FIX = Path(__file__).parent / "fixtures"
REF = json.loads((FIX / "bcg_metafor_reference.json").read_text())
ROWS = list(csv.DictReader((FIX / "bcg_colditz1994.csv").open()))
YV = [meta.binary_effect(*(int(r[k]) for k in ("tpos", "tneg", "cpos", "cneg"))) for r in ROWS]
Y, V = [a for a, _ in YV], [b for _, b in YV]


def test_effect_sizes_match_escalc():
    assert Y == pytest.approx(REF["yi"], abs=1e-10) and V == pytest.approx(REF["vi"], abs=1e-10)


@pytest.mark.parametrize("key, method, hksj", [("DL", "DL", False), ("REML", "REML", False),
                                               ("REML_HKSJ", "REML", True), ("FE", "FE", False)])
def test_pooled_results_match_metafor(key, method, hksj):
    got, want = meta.meta(Y, V, method=method, hksj=hksj, pi_dist="normal"), REF[key]
    for field in ("est", "se", "ci_lb", "ci_ub", "tau2", "I2", "QE", "pi_lb", "pi_ub"):
        if field in want:
            # I2 is a percentage driven by tau2; metafor stops REML at its own tolerance (tau2 within ~1e-7)
            tol = {"rel": 1e-6} if field == "I2" else {"abs": 1e-6}
            assert got["Q" if field == "QE" else field] == pytest.approx(want[field], **tol), field


def test_egger_matches_regtest_and_refuses_small_meta():
    e = meta.egger(Y, V)
    assert e["t"] == pytest.approx(REF["egger"]["z"], abs=1e-8) and e["p"] == pytest.approx(REF["egger"]["p"], abs=1e-8)
    with pytest.raises(ValueError, match="at least 10"):
        meta.egger(Y[:9], V[:9])


def test_double_zero_study_is_not_estimable_on_ratio_scale():
    with pytest.raises(ValueError, match="not estimable"):
        meta.binary_effect(0, 50, 0, 50, "RR")
    assert meta.binary_effect(0, 50, 0, 50, "RD")[0] == 0


def test_forest_and_funnel_render_with_embedded_fonts(tmp_path):
    from src.scoping_review.integrity import fonts_not_embedded
    from src.systematic_review import plots
    res = meta.meta(Y, V, "REML", hksj=True)
    plots.forest([f"{r['author']} {r['year']}" for r in ROWS], Y, V, res, "RR", tmp_path / "f.pdf")
    plots.funnel(Y, V, res, "RR", tmp_path / "u.pdf")
    assert fonts_not_embedded(tmp_path / "f.pdf") == [] == fonts_not_embedded(tmp_path / "u.pdf")


TABLES = [[int(r[k]) for k in ("tpos", "tneg", "cpos", "cneg")] for r in ROWS]


@pytest.mark.parametrize("key, fn", [("MH_RR", lambda: meta.mantel_haenszel(TABLES, "RR")),
                                     ("MH_OR", lambda: meta.mantel_haenszel(TABLES, "OR")),
                                     ("PETO", lambda: meta.peto(TABLES))])
def test_sparse_data_methods_match_metafor(key, fn):
    got, want = fn(), REF[key]
    for field in ("est", "se", "ci_lb", "ci_ub", "QE"):
        assert got["Q" if field == "QE" else field] == pytest.approx(want[field], abs=1e-6), field


def test_tau2_qprofile_ci_solves_the_equation_and_matches_confint():
    import numpy as np
    from scipy import stats
    y, v = np.array(Y), np.array(V)

    def q(t2):
        w = 1 / (v + t2)
        return float(np.sum(w * (y - np.sum(w * y) / np.sum(w)) ** 2))

    lo, hi = meta.tau2_ci(Y, V)
    assert q(lo) == pytest.approx(stats.chi2.ppf(0.975, 12), abs=1e-9)
    assert q(hi) == pytest.approx(stats.chi2.ppf(0.025, 12), abs=1e-9)
    # metafor's confint stops uniroot at its default tolerance (~1.2e-4), so agree to that precision
    assert lo == pytest.approx(REF["REML"]["tau2_ci_lb"], abs=1e-4) and hi == pytest.approx(REF["REML"]["tau2_ci_ub"], abs=1e-4)


def test_cochrane_prediction_interval_uses_t_with_k_minus_1():
    from scipy import stats
    r = meta.meta(Y, V, "REML")
    half = stats.t.ppf(0.975, len(Y) - 1) * (r["se"] ** 2 + r["tau2"]) ** 0.5
    assert r["pi_lb"] == pytest.approx(r["est"] - half) and r["pi_ub"] == pytest.approx(r["est"] + half)
    with pytest.raises(ValueError, match="not recommended for OR"):
        meta.egger(Y, V, measure="OR")


def test_subgroup_differences_by_allocation_match_metafor():
    want = REF["subgroup_alloc"]
    got = meta.subgroups(Y, V, [r["alloc"] for r in ROWS])
    # per-subgroup REML fits carry metafor's stopping tolerance, so compare relatively
    assert got["Q_between"] == pytest.approx(want["Q_between"], rel=1e-6) and got["p"] == pytest.approx(want["p"], rel=1e-5)
    for g, w in want["groups"].items():
        assert got["groups"][g]["k"] == w["k"] and got["groups"][g]["est"] == pytest.approx(w["est"], abs=1e-6)


def test_leave_one_out_matches_metafor():
    got = meta.leave_one_out(Y, V)
    assert [r["est"] for r in got] == pytest.approx(REF["leave1out"]["est"], abs=1e-6)
    assert [r["tau2"] for r in got] == pytest.approx(REF["leave1out"]["tau2"], abs=1e-6)
