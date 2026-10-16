"""Pairwise meta-analysis (board nodes in lane S9). Checked against R metafor 3.8.1 on the BCG trials.

Effect sizes are on the analysis scale (log RR, log OR, RD); `exp` the summary for RR and OR.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats


def binary_effect(ai, bi, ci, di, measure: str = "RR", cc: float = 0.5) -> tuple[float, float]:
    """Effect and sampling variance from a 2x2 table (events/non-events in treatment and control).

    A study with a zero cell gets `cc` added to all four cells (metafor's default `to="only0"`);
    a study with no events in either arm is not estimable for RR/OR and raises.
    """
    if measure in ("RR", "OR") and (ai + ci == 0 or bi + di == 0):
        raise ValueError("no events (or no non-events) in both arms: not estimable on the ratio scale")
    if min(ai, bi, ci, di) == 0:
        ai, bi, ci, di = ai + cc, bi + cc, ci + cc, di + cc
    n1, n2 = ai + bi, ci + di
    if measure == "RR":
        return math.log((ai / n1) / (ci / n2)), 1 / ai - 1 / n1 + 1 / ci - 1 / n2
    if measure == "OR":
        return math.log((ai * di) / (bi * ci)), 1 / ai + 1 / bi + 1 / ci + 1 / di
    if measure == "RD":
        p1, p2 = ai / n1, ci / n2
        return p1 - p2, p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2
    raise ValueError(f"unknown measure {measure}")


def smd(m1, sd1, n1, m2, sd2, n2) -> tuple[float, float]:
    """Hedges' g (bias-corrected standardized mean difference) and its variance."""
    sp = math.sqrt(((n1 - 1) * sd1 ** 2 + (n2 - 1) * sd2 ** 2) / (n1 + n2 - 2))
    j = 1 - 3 / (4 * (n1 + n2) - 9)
    g = j * (m1 - m2) / sp
    return g, (n1 + n2) / (n1 * n2) + g ** 2 / (2 * (n1 + n2))


def _fixed(y, v):
    w = 1 / v
    est = np.sum(w * y) / np.sum(w)
    return est, math.sqrt(1 / np.sum(w)), w


def heterogeneity(y, v) -> dict:
    est, _, w = _fixed(y, v)
    q = float(np.sum(w * (y - est) ** 2))
    k = len(y)
    return {"Q": q, "df": k - 1, "Q_p": float(stats.chi2.sf(q, k - 1)), "I2": max(0.0, (q - (k - 1)) / q) * 100 if q > 0 else 0.0}


def tau2_dl(y, v) -> float:
    est, _, w = _fixed(y, v)
    q = np.sum(w * (y - est) ** 2)
    c = np.sum(w) - np.sum(w ** 2) / np.sum(w)
    return max(0.0, float((q - (len(y) - 1)) / c))


def tau2_reml(y, v, tol: float = 1e-10, max_iter: int = 500) -> float:
    """REML by Fisher scoring, started at the DerSimonian-Laird value and truncated at zero."""
    t2 = tau2_dl(y, v)
    for _ in range(max_iter):
        w = 1 / (v + t2)
        mu = np.sum(w * y) / np.sum(w)
        # REML score and information for tau^2
        p_diag = w - w ** 2 / np.sum(w)
        resid = y - mu
        score = 0.5 * (np.sum((w * resid) ** 2) - np.sum(p_diag))
        info = 0.5 * np.sum(p_diag ** 2)
        step = score / info
        new = max(0.0, t2 + step)
        if abs(new - t2) < tol:
            return float(new)
        t2 = new
    raise RuntimeError("REML did not converge")


def meta(y, v, method: str = "REML", hksj: bool = False, level: float = 0.95, pi_dist: str = "t") -> dict:
    """Random-effects (DL or REML) or fixed-effect ('FE') inverse-variance meta-analysis.

    Defaults follow Cochrane Handbook v6.5 ch. 10: REML for tau2; pass hksj=True when tau2 > 0 and
    k > 2. The prediction interval uses t with k-1 df (pi_dist="t"); pi_dist="normal" reproduces
    metafor's default for checking.
    """
    y, v = np.asarray(y, float), np.asarray(v, float)
    k = len(y)
    if k < 2:
        raise ValueError("a meta-analysis needs at least two studies")
    t2 = 0.0 if method == "FE" else {"DL": tau2_dl, "REML": tau2_reml}[method](y, v)
    w = 1 / (v + t2)
    est = float(np.sum(w * y) / np.sum(w))
    se = math.sqrt(1 / np.sum(w))
    alpha = 1 - level
    if hksj and method != "FE":
        # Hartung-Knapp-Sidik-Jonkman: rescale the variance by the weighted residual mean square, t with k-1 df
        q = float(np.sum(w * (y - est) ** 2) / (k - 1))
        se = se * math.sqrt(q)
        crit, df = stats.t.ppf(1 - alpha / 2, k - 1), k - 1
    else:
        crit, df = stats.norm.ppf(1 - alpha / 2), None
    out = {"method": method + ("+HKSJ" if hksj else ""), "k": k, "est": est, "se": se,
           "ci_lb": est - crit * se, "ci_ub": est + crit * se, "tau2": t2, **heterogeneity(y, v)}
    if method != "FE":
        # I2 from tau2 and the typical within-study variance (Higgins & Thompson 2002), as metafor
        # reports it, so I2 follows whichever tau2 estimator was used; it equals the Q-based I2 under DL
        wf = 1 / v
        s2 = (k - 1) * np.sum(wf) / (np.sum(wf) ** 2 - np.sum(wf ** 2))
        out["I2"] = float(100 * t2 / (t2 + s2))
    if df:
        out["df"] = df
    if method != "FE":
        pcrit = stats.t.ppf(1 - alpha / 2, k - 1) if (pi_dist == "t" or hksj) else stats.norm.ppf(1 - alpha / 2)
        out["pi_lb"], out["pi_ub"] = est - pcrit * math.sqrt(se ** 2 + t2), est + pcrit * math.sqrt(se ** 2 + t2)
    return out


def tau2_ci(y, v, level: float = 0.95) -> tuple[float, float]:
    """Q-profile confidence interval for tau2 (Viechtbauer 2007), as Cochrane ch. 10 recommends."""
    y, v = np.asarray(y, float), np.asarray(v, float)
    k = len(y)

    def qgen(t2):
        w = 1 / (v + t2)
        mu = np.sum(w * y) / np.sum(w)
        return float(np.sum(w * (y - mu) ** 2))

    def solve(target):
        if qgen(0.0) < target:
            return 0.0
        lo, hi = 0.0, 1.0
        while qgen(hi) > target:
            hi *= 2
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if qgen(mid) > target else (lo, mid)
        return (lo + hi) / 2

    alpha = 1 - level
    return solve(stats.chi2.ppf(1 - alpha / 2, k - 1)), solve(stats.chi2.ppf(alpha / 2, k - 1))


def mantel_haenszel(tables, measure: str = "RR", level: float = 0.95) -> dict:
    """Fixed-effect Mantel-Haenszel log RR (Greenland-Robins variance) or log OR (Robins-Breslow-
    Greenland variance), with no continuity correction: the Cochrane choice for sparse data."""
    t = np.asarray(tables, float)
    a, b, c, d = t.T
    n1, n2 = a + b, c + d
    n = n1 + n2
    if measure == "RR":
        r, s = a * n2 / n, c * n1 / n
        est = math.log(r.sum() / s.sum())
        var = np.sum((n1 * n2 * (a + c) - a * c * n) / n ** 2) / (r.sum() * s.sum())
    elif measure == "OR":
        r, s = a * d / n, b * c / n
        p_, q_ = (a + d) / n, (b + c) / n
        est = math.log(r.sum() / s.sum())
        var = (np.sum(p_ * r) / (2 * r.sum() ** 2) + np.sum(p_ * s + q_ * r) / (2 * r.sum() * s.sum())
               + np.sum(q_ * s) / (2 * s.sum() ** 2))
    else:
        raise ValueError("Mantel-Haenszel here supports RR and OR")
    se = math.sqrt(var)
    z = stats.norm.ppf(1 - (1 - level) / 2)
    yv = [binary_effect(*row, measure=measure) for row in t]
    yi, vi = np.array([e for e, _ in yv]), np.array([w for _, w in yv])
    return {"method": f"MH-{measure}", "k": len(t), "est": est, "se": se, "ci_lb": est - z * se, "ci_ub": est + z * se,
            "Q": float(np.sum((yi - est) ** 2 / vi))}


def peto(tables, level: float = 0.95) -> dict:
    """Peto one-step log odds ratio: Cochrane's method when events are rare (< 1%)."""
    t = np.asarray(tables, float)
    a, b, c, d = t.T
    n1, n2 = a + b, c + d
    n, m = n1 + n2, a + c
    o_e = a - n1 * m / n
    var = n1 * n2 * m * (n - m) / (n ** 2 * (n - 1))
    est, se = float(o_e.sum() / var.sum()), float(1 / math.sqrt(var.sum()))
    z = stats.norm.ppf(1 - (1 - level) / 2)
    q = float(np.sum(o_e ** 2 / var) - o_e.sum() ** 2 / var.sum())
    return {"method": "Peto-OR", "k": len(t), "est": est, "se": se, "ci_lb": est - z * se, "ci_ub": est + z * se, "Q": q}


def egger(y, v, min_studies: int = 10, measure: str = "RR") -> dict:
    """Egger's regression test for small-study effects: weighted regression of y on its standard
    error, testing the slope (metafor `regtest(model="lm")`). Refuses below `min_studies`, and for
    OR and SMD, where Cochrane (ch. 13) does not recommend the original test."""
    if measure in ("OR", "SMD"):
        raise ValueError(f"the original Egger test is not recommended for {measure} (Cochrane Handbook ch. 13)")
    y, v = np.asarray(y, float), np.asarray(v, float)
    k = len(y)
    if k < min_studies:
        raise ValueError(f"only {k} studies: tests for funnel asymmetry need at least {min_studies}")
    sei = np.sqrt(v)
    x = np.column_stack([np.ones(k), sei])
    w = 1 / v
    xtw = x.T * w
    beta = np.linalg.solve(xtw @ x, xtw @ y)
    resid = y - x @ beta
    sigma2 = float(np.sum(w * resid ** 2) / (k - 2))
    cov = sigma2 * np.linalg.inv(xtw @ x)
    t = float(beta[1] / math.sqrt(cov[1, 1]))
    return {"slope": float(beta[1]), "t": t, "df": k - 2, "p": float(2 * stats.t.sf(abs(t), k - 2))}


def subgroups(y, v, groups: list[str], method: str = "REML", min_per_group: int = 2) -> dict:
    """Cochrane test for subgroup differences: a separate random-effects meta-analysis per subgroup,
    then Cochran's Q across the subgroup estimates (fixed effect, df = groups - 1)."""
    y, v = np.asarray(y, float), np.asarray(v, float)
    res = {}
    for g in sorted(set(groups)):
        idx = [i for i, x in enumerate(groups) if x == g]
        if len(idx) < min_per_group:
            raise ValueError(f"subgroup {g!r} has {len(idx)} studies; need at least {min_per_group}")
        res[g] = meta(y[idx], v[idx], method=method)
    est = np.array([r["est"] for r in res.values()])
    var = np.array([r["se"] ** 2 for r in res.values()])
    het = heterogeneity(est, var)
    return {"groups": res, "Q_between": het["Q"], "df": het["df"], "p": het["Q_p"]}


def leave_one_out(y, v, method: str = "REML") -> list[dict]:
    """The pooled result with each study left out in turn (sensitivity analysis)."""
    y, v = np.asarray(y, float), np.asarray(v, float)
    return [meta(np.delete(y, i), np.delete(v, i), method=method) for i in range(len(y))]
