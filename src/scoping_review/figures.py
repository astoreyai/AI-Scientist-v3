"""Print figures and tables built only from frozen data (board nodes P8.07 to P8.12).

Palette: the dataviz reference instance (categorical slots in fixed order, blue sequential ramp),
validated with validate_palette.js on 2026-10-16 (all checks pass; contrast WARN on slots 3-5 is
relieved by direct total labels and the legend).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER = "#a3a29c"
SEQUENTIAL = ["#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
SURFACE, INK, MUTED, GRID = "#ffffff", "#0b0b0b", "#52514e", "#e6e5e0"

plt.rcParams.update({
    "pdf.fonttype": 42, "ps.fonttype": 42,  # embed TrueType so journals' font checks pass
    "font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
})


def _fold(counts: dict, keep: int) -> dict:
    """Keep the `keep` largest categories in fixed order; fold the rest into Other."""
    items = sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))
    head = dict(items[:keep])
    rest = sum(c for _, c in items[keep:])
    return head | ({"Other": rest} if rest else {})


def timeline(chart, year_field, stack_field, out, width=3.5):
    """Sources per year, stacked by one categorical field (at most 5 named categories + Other)."""
    from .synthesis import field_values
    years = sorted({y for r in chart for y in field_values(r, year_field) if str(y).isdigit()}, key=int)
    totals = {}
    for r in chart:
        for s in field_values(r, stack_field):
            totals[s] = totals.get(s, 0) + 1
    cats = list(_fold(totals, 5))
    named = set(cats) - {"Other"}
    fig, ax = plt.subplots(figsize=(width, 2.4))
    bottom = [0] * len(years)
    for i, cat in enumerate(cats):
        h = [sum(1 for r in chart if str(y) in map(str, field_values(r, year_field))
                 and ((cat in field_values(r, stack_field)) if cat != "Other" else bool(set(field_values(r, stack_field)) - named)))
             for y in years]
        ax.bar([str(y) for y in years], h, bottom=bottom, width=0.7, color=OTHER if cat == "Other" else CATEGORICAL[i],
               edgecolor=SURFACE, linewidth=1, label=str(cat))
        bottom = [b + x for b, x in zip(bottom, h)]
    for x, t in zip([str(y) for y in years], bottom):
        ax.annotate(str(t), (x, t), ha="center", va="bottom", fontsize=7, color=INK, xytext=(0, 1), textcoords="offset points")
    ax.set_ylabel("Sources")
    ax.yaxis.grid(True, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=6.5, loc="upper left", title=stack_field.replace("_", " "), title_fontsize=6.5)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def category_bars(counts: dict, label: str, n_sources: int, out, width=3.5):
    """Horizontal bars, sorted, single hue, each labelled with its count and share."""
    items = sorted(counts.items(), key=lambda kv: (kv[1], str(kv[0])))
    fig, ax = plt.subplots(figsize=(width, 0.22 * len(items) + 0.6))
    ax.barh([str(k) for k, _ in items], [v for _, v in items], color=CATEGORICAL[0], height=0.65)
    for i, (_, v) in enumerate(items):
        ax.annotate(f"{v} ({100 * v / n_sources:.0f}%)", (v, i), va="center", fontsize=7, color=INK, xytext=(3, 0),
                    textcoords="offset points")
    ax.set_xlabel(f"Sources (n = {n_sources})")
    ax.set_title(label.capitalize(), loc="left", fontsize=8, color=INK)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, max(v for _, v in items) * 1.4)
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def gap_heatmap(gm: dict, out, width=7.0):
    """Evidence gap map: counts per cell on the blue ramp; empty cells stay blank as gaps."""
    import numpy as np
    m = np.array(gm["counts"], dtype=float)
    shown = np.ma.masked_where(m == 0, m)
    fig, ax = plt.subplots(figsize=(width, 0.32 * len(gm["rows"]) + 1.4))
    im = ax.imshow(shown, cmap=ListedColormap(SEQUENTIAL), aspect="auto", vmin=1)
    ax.set_xticks(range(len(gm["cols"])), [str(c) for c in gm["cols"]], rotation=35, ha="right")
    ax.set_yticks(range(len(gm["rows"])), [str(r) for r in gm["rows"]])
    for (i, j), v in np.ndenumerate(m):
        if v:
            ax.text(j, i, int(v), ha="center", va="center", fontsize=6.5, color="#ffffff" if v > m.max() * 0.45 else INK)
    ax.set_xticks([x - 0.5 for x in range(1, len(gm["cols"]))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(gm["rows"]))], minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=2)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xlabel(gm["cols_field"].replace("_", " "))
    ax.set_ylabel(gm["rows_field"].replace("_", " "))
    fig.colorbar(im, ax=ax, shrink=0.6, label="Sources (blank = none: evidence gap)")
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def prisma_flow(c: dict, out):
    """PRISMA 2020-style flow diagram; box heights follow their line counts so text never spills."""
    dbs = "\n".join(f"{k}: {v}" for k, v in c["identified_by_database"].items())
    reasons = "\n".join(f"{k}: {v}" for k, v in sorted(c["excluded_full_text_reasons"].items()))
    rows = [(f"Records identified (n = {c['identified']})\n{dbs}", f"Duplicates removed (n = {c['duplicates_removed']})"),
            (f"Records screened (n = {c['screened']})", f"Excluded at title/abstract (n = {c['excluded_title_abstract']})"),
            (f"Reports sought for retrieval (n = {c['sought_for_retrieval']})", f"Not retrieved (n = {c['not_retrieved']})"),
            (f"Reports assessed for eligibility (n = {c['assessed_full_text']})", f"Excluded at full text (n = {c['excluded_full_text']})\n{reasons}")]
    extra = f"\n(including {c['identified_by_citation_searching']} from citation searching)" if c["identified_by_citation_searching"] else ""
    final = f"Sources included in review (n = {c['included']}){extra}"
    line, pad, gap = 0.16, 0.18, 0.32  # inches
    heights = [max(t.count("\n"), r.count("\n")) * line + line + 2 * pad for t, r in rows]
    final_h = final.count("\n") * line + line + 2 * pad
    total = sum(heights) + final_h + gap * len(rows)
    fig, ax = plt.subplots(figsize=(6.5, total + 0.2))
    ax.set_xlim(0, 6.5)
    ax.set_ylim(0, total + 0.2)
    ax.axis("off")

    def box(x, y, w, h, text, fill="#ffffff"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.06", fc=fill, ec=MUTED, lw=0.8))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7, color=INK, linespacing=1.3)

    def arrow(x1, y1, x2, y2):
        ax.annotate("", (x2, y2), (x1, y1), arrowprops={"arrowstyle": "-|>", "color": MUTED, "lw": 0.8})

    y = total + 0.1
    prev_bottom = None
    for (left, right), h in zip(rows, heights):
        y -= h
        box(0.1, y, 3.0, h, left)
        box(3.6, y, 2.8, h, right)
        arrow(3.1, y + h / 2, 3.6, y + h / 2)
        if prev_bottom is not None:
            arrow(1.6, prev_bottom, 1.6, y + h)
        prev_bottom = y
        y -= gap
    y -= final_h - gap
    y -= gap
    box(0.1, y, 3.0, final_h, final, fill="#f0efec")
    arrow(1.6, prev_bottom, 1.6, y + final_h)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def latex_escape(s) -> str:
    rep = {"&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
           "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "\\": r"\textbackslash{}"}
    return "".join(rep.get(ch, ch) for ch in str(s))


def characteristics_table(chart: list[dict], columns: list[tuple[str, str]], cite_key: dict) -> str:
    """Longtable of included-source characteristics; one row per source, citation in column 1."""
    from .synthesis import field_values
    spec = "p{3.2cm}" + "p{2.4cm}" * len(columns)
    head = " & ".join(["Source"] + [latex_escape(label) for _, label in columns]) + r" \\"
    lines = [r"\begin{longtable}{" + spec + "}", r"\toprule", head, r"\midrule", r"\endhead"]
    for rec in sorted(chart, key=lambda r: str(r["record_id"])):
        cells = [rf"\cite{{{cite_key[rec['record_id']]}}}" if rec["record_id"] in cite_key else latex_escape(rec["record_id"])]
        cells += [latex_escape("; ".join(map(str, field_values(rec, f)))) for f, _ in columns]
        lines.append(" & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{longtable}"]
    return "\n".join(lines) + "\n"
