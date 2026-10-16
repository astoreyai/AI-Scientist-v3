"""Forest and funnel plots from a meta-analysis result (board nodes S9.07, S9.08).

Reuses the scoping-review figure settings (validated palette, embedded TrueType fonts).
"""

from __future__ import annotations

import math

import numpy as np

from src.scoping_review.figures import CATEGORICAL, GRID, INK, MUTED, plt  # noqa: F401  (sets rcParams)

RATIO = {"RR": "Risk ratio", "OR": "Odds ratio"}
RATIO_TICKS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]


def _ratio_axis(ax):
    """Log scale with plain tick labels (0.1, 0.5, 1, 2) rather than powers of ten."""
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
    ax.set_xscale("log")
    lo, hi = ax.get_xlim()
    ax.xaxis.set_major_locator(FixedLocator([t for t in RATIO_TICKS if lo <= t <= hi]))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))


def forest(labels: list[str], y, v, res: dict, measure: str, out, favours: tuple[str, str] = ("Favours treatment", "Favours control")):
    """One row per study (square sized by weight, 95% CI), pooled diamond, prediction interval."""
    y, v = np.asarray(y, float), np.asarray(v, float)
    k = len(y)
    ratio = measure in RATIO
    tx = np.exp if ratio else (lambda a: a)
    lo, hi = y - 1.96 * np.sqrt(v), y + 1.96 * np.sqrt(v)
    w = 1 / (v + res.get("tau2", 0.0))
    w = 100 * w / w.sum()
    fig, ax = plt.subplots(figsize=(6.5, 0.28 * k + 1.6))
    rows = np.arange(k, 0, -1) + 1
    for r, yi, a, b, wi in zip(rows, y, lo, hi, w):
        ax.plot([tx(a), tx(b)], [r, r], color=INK, lw=0.8)
        ax.plot(tx(yi), r, "s", color=CATEGORICAL[0], markersize=3 + 6 * math.sqrt(wi / w.max()))
    d = res
    ax.fill([tx(d["ci_lb"]), tx(d["est"]), tx(d["ci_ub"]), tx(d["est"])], [0.5, 0.8, 0.5, 0.2], color=INK)
    if "pi_lb" in d:
        ax.plot([tx(d["pi_lb"]), tx(d["pi_ub"])], [0.5, 0.5], color="#a3a29c", lw=3, zorder=0, solid_capstyle="butt")
    ax.axvline(1 if ratio else 0, color=MUTED, lw=0.6, ls="--")
    if ratio:
        _ratio_axis(ax)
    ax.set_yticks(list(rows) + [0.5], labels + [f"{d['method']} (I² = {d['I2']:.0f}%, τ² = {d['tau2']:.3f})"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel(f"{RATIO.get(measure, measure)} (95% CI); grey bar = 95% prediction interval")
    for x, text, ha in ((0.02, favours[0], "left"), (0.98, favours[1], "right")):
        ax.text(x, -0.13, text, transform=ax.transAxes, ha=ha, fontsize=7, color=MUTED)
    ax.set_ylim(0, k + 2)
    # right-hand column: effect and CI per study, then pooled
    txt = [f"{tx(yi):.2f} [{tx(a):.2f}, {tx(b):.2f}]  {wi:4.1f}%" for yi, a, b, wi in zip(y, lo, hi, w)]
    txt.append(f"{tx(d['est']):.2f} [{tx(d['ci_lb']):.2f}, {tx(d['ci_ub']):.2f}]")
    for r, t in zip(list(rows) + [0.5], txt):
        ax.annotate(t, (1.01, r), xycoords=("axes fraction", "data"), va="center", fontsize=7, color=INK)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def funnel(y, v, res: dict, measure: str, out):
    """Effect against standard error (inverted), with the pooled estimate and 95% pseudo-CI region."""
    y, v = np.asarray(y, float), np.asarray(v, float)
    se = np.sqrt(v)
    ratio = measure in RATIO
    tx = np.exp if ratio else (lambda a: a)
    fig, ax = plt.subplots(figsize=(3.5, 3.0))
    s = np.linspace(0, se.max() * 1.05, 50)
    ax.plot(tx(res["est"] - 1.96 * s), s, color=MUTED, lw=0.7, ls="--")
    ax.plot(tx(res["est"] + 1.96 * s), s, color=MUTED, lw=0.7, ls="--")
    ax.axvline(tx(res["est"]), color=INK, lw=0.8)
    ax.plot(tx(y), se, "o", color=CATEGORICAL[0], markersize=4, markeredgecolor="white", markeredgewidth=0.6)
    ax.invert_yaxis()
    if ratio:
        _ratio_axis(ax)
    ax.set_xlabel(RATIO.get(measure, measure))
    ax.set_ylabel("Standard error")
    ax.yaxis.grid(True, color=GRID, lw=0.5)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


# Status palette from the dataviz reference instance; each cell also carries a letter (color is never alone).
ROB_STYLE = {"low": ("#0ca30c", "+"), "some_concerns": ("#fab219", "?"), "moderate": ("#fab219", "?"),
             "unclear": ("#fab219", "?"), "serious": ("#ec835a", "!"), "high": ("#d03b3b", "x"), "critical": ("#7a1f1f", "x")}


def traffic_light(tool: str, assessments: dict[str, dict], out):
    """robvis-style traffic-light plot: studies by domain plus overall, letter and color per cell."""
    from .appraisal import TOOLS, overall
    domains = TOOLS[tool]["domains"]
    studies = list(assessments)
    cols = domains + ["Overall"]
    fig, ax = plt.subplots(figsize=(0.55 * len(cols) + 2.6, 0.32 * len(studies) + 1.4))
    for i, st in enumerate(studies):
        row = [assessments[st][d] for d in domains] + [overall(tool, assessments[st])["overall"]]
        for j, val in enumerate(row):
            if val is None:
                continue
            color, mark = ROB_STYLE[val]
            ax.scatter(j, i, s=150, color=color, edgecolor="white", linewidth=0.8)
            ax.text(j, i, mark, ha="center", va="center", fontsize=7, fontweight="bold",
                    color=INK if mark == "?" else "white")  # dark on the light yellow for contrast
    ax.set_xticks(range(len(cols)), [f"D{n}" for n in range(1, len(domains) + 1)] + ["Overall"])
    ax.set_yticks(range(len(studies)), studies)
    ax.set_xlim(-0.6, len(cols) - 0.4)
    ax.set_ylim(len(studies) - 0.5, -0.5)
    for s_ in ax.spines.values():
        s_.set_visible(False)
    ax.tick_params(length=0)
    key = "  ".join(f"D{n}: {d}" for n, d in enumerate(domains, 1))
    ax.set_title(key, fontsize=6, color=MUTED, loc="left", wrap=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
