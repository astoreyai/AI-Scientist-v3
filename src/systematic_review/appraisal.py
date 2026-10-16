"""Risk of bias, GRADE certainty and the Summary of Findings table (lanes S7, S10).

Tools and rules as sourced in plan/PLAN.md section 6 (MECIR C52-C59, C74-C75; Cochrane Handbook v6.5
chapters 8 and 14; riskofbias.info). ROBINS-I V2 was still a draft on 2025-11-20; its domain list
here follows that draft.
"""

from __future__ import annotations

import math

TOOLS = {
    "rob2": {"levels": ["low", "some_concerns", "high"],
             "domains": ["randomization process", "deviations from intended interventions", "missing outcome data",
                         "measurement of the outcome", "selection of the reported result"]},
    "robins_i_v2": {"levels": ["low", "moderate", "serious", "critical"],
                    "domains": ["confounding", "classification of interventions", "selection of participants",
                                "missing data", "measurement of the outcome", "selection of the reported result"]},
    "quadas2": {"levels": ["low", "unclear", "high"],
                "domains": ["patient selection", "index test", "reference standard", "flow and timing"]},
    "quips": {"levels": ["low", "moderate", "high"],
              "domains": ["study participation", "study attrition", "prognostic factor measurement",
                          "outcome measurement", "study confounding", "statistical analysis and reporting"]},
}


def overall(tool: str, judgements: dict[str, str]) -> dict:
    """Overall risk of bias for one result.

    RoB 2: low only if every domain is low; high if any domain is high; otherwise some concerns,
    flagged for the reviewers to consider high when several domains have some concerns.
    ROBINS-I: the most severe domain judgement. QUADAS-2 and QUIPS have no overall algorithm: the
    domains are reported as they are.
    """
    spec = TOOLS[tool]
    missing = [d for d in spec["domains"] if d not in judgements]
    bad = {d: j for d, j in judgements.items() if j not in spec["levels"]}
    if missing or bad:
        raise ValueError(f"{tool}: missing domains {missing}, invalid judgements {bad}")
    j = [judgements[d] for d in spec["domains"]]
    if tool == "rob2":
        if all(x == "low" for x in j):
            return {"overall": "low"}
        if any(x == "high" for x in j):
            return {"overall": "high"}
        n = j.count("some_concerns")
        return {"overall": "some_concerns", **({"review_for_high": True, "note": f"{n} domains with some concerns"} if n > 1 else {})}
    if tool == "robins_i_v2":
        return {"overall": max(j, key=spec["levels"].index)}
    return {"overall": None, "note": f"{tool} has no overall algorithm; report the domains"}


def compare_assessors(tool: str, first: dict[str, dict], second: dict[str, dict]) -> list[dict]:
    """Domain-level disagreements between two independent assessors (MECIR C53), per study."""
    out = []
    for study in sorted(set(first) | set(second)):
        a, b = first.get(study), second.get(study)
        if a is None or b is None:
            out.append({"study": study, "domain": None, "issue": "assessed by only one reviewer"})
            continue
        for d in TOOLS[tool]["domains"]:
            if a.get(d) != b.get(d):
                out.append({"study": study, "domain": d, "first": a.get(d), "second": b.get(d)})
    return out


GRADE_LEVELS = ["very_low", "low", "moderate", "high"]
DOWN = ["risk_of_bias", "inconsistency", "indirectness", "imprecision", "publication_bias"]
UP = ["large_effect", "dose_response", "plausible_confounding"]


def grade(start: str, down: dict[str, int], up: dict[str, int], reasons: dict[str, str]) -> dict:
    """GRADE certainty for one outcome. Each domain moves 0, 1 or 2 levels and every nonzero move
    needs a written reason (MECIR C75); the result is floored at very low and capped at high."""
    for d, n in {**down, **up}.items():
        if d not in DOWN + UP or n not in (0, 1, 2):
            raise ValueError(f"invalid GRADE move {d}={n}")
        if n and not reasons.get(d, "").strip():
            raise ValueError(f"GRADE: '{d}' moves {n} level(s) but has no reason")
    if start not in ("high", "low"):
        raise ValueError("start is 'high' (randomized trials, or non-randomized assessed with ROBINS-I) or 'low'")
    level = GRADE_LEVELS.index(start) - sum(down.values()) + sum(up.values())
    return {"certainty": GRADE_LEVELS[min(max(level, 0), 3)], "start": start,
            "moves": {k: v for k, v in {**{d: -n for d, n in down.items()}, **up}.items() if v}, "reasons": reasons}


def absolute_effect(measure: str, est: float, lo: float, hi: float, control_risk: float, per: int = 1000) -> dict:
    """Corresponding risk per `per` people from a pooled log RR or log OR and an assumed control risk."""
    def risk(log_eff):
        e = math.exp(log_eff)
        return control_risk * e if measure == "RR" else e * control_risk / (1 - control_risk + e * control_risk)
    if measure not in ("RR", "OR"):
        raise ValueError("absolute effects here need a pooled RR or OR")
    r, rl, rh = (risk(x) for x in (est, lo, hi))
    return {"control_per": round(control_risk * per), "intervention_per": round(r * per),
            "difference_per": round((r - control_risk) * per), "difference_ci": sorted([round((rl - control_risk) * per), round((rh - control_risk) * per)])}


def sof_table(rows: list[dict], comparison: str, population: str) -> str:
    """Summary of Findings table (Cochrane Handbook 14.1.3), at most 7 outcomes."""
    from src.scoping_review.figures import latex_escape as e
    if not 1 <= len(rows) <= 7:
        raise ValueError("a Summary of Findings table holds 1 to 7 outcomes")
    sym = {"high": "High", "moderate": "Moderate", "low": "Low", "very_low": "Very low"}
    lines = [r"\begin{longtable}{p{2.6cm}p{1.6cm}p{2.1cm}p{2.2cm}p{1.8cm}p{1.5cm}p{2.4cm}}",
             rf"\multicolumn{{7}}{{l}}{{\textbf{{{e(comparison)}}} \quad Population: {e(population)}}} \\",
             r"\toprule Outcome & Risk with comparator & Risk with intervention (95\% CI) & Relative effect (95\% CI) & "
             r"Participants (studies) & Certainty & Comments \\ \midrule \endhead"]
    for r in rows:
        a = r["absolute"]
        lines.append(rf"{e(r['outcome'])} & {a['control_per']} per 1000 & {a['intervention_per']} per 1000 "
                     rf"({a['difference_ci'][0]:+d} to {a['difference_ci'][1]:+d}) & {e(r['relative'])} & "
                     rf"{r['participants']} ({r['studies']}) & {sym[r['certainty']]} & {e(r.get('comment', ''))} \\")
    lines += [r"\bottomrule", r"\end{longtable}"]
    return "\n".join(lines) + "\n"
