---
name: sr-latex
description: Typeset a scoping-review manuscript in the target journal's class, fix compile errors from the log, trim to the journal's limits with the author approving every cut, and repair figure scripts after a figure audit. Use for board nodes P13.01 (typeset), P13.02b (fix), P13.06a (trim) and P8.15b (figures).
---

# What the skill is about
The manuscript sections and figures already exist and are grounded. This skill changes layout,
never content: it applies the journal's class and citation style, places floats, and fixes LaTeX
faults. Every number and claim stays exactly as the grounding audit approved it.

# Mode `typeset` (P13.01)
Inputs: `manuscript/` (sections, figures, tables, `references.bib`), `review/journal_profile.yaml`.
1. Build `manuscript/main.tex` on the journal class from `manuscript/` (fetched at P1.05), with
   `\input{sections/...}` in the order of the outline.
2. Apply the journal's citation style (`.bst` or `biblatex` style named in the profile).
3. Place each figure and table near its first mention. Use `longtable` (landscape pages via
   `pdflscape` when wider than the text block) for the characteristics table.
4. Move the supplementary files listed in the outline into `manuscript/supplement/`.

# Mode `fix` (P13.02b)
Input: `manuscript/main.log` from the last compile. Fix, in order: errors, undefined references and
citations, overfull boxes over 1pt, and a `.bbl` that drops URLs or DOIs (some `.bst` files silently
drop `url` for `@inproceedings`; add the DOI through `note` if so). One fault, one minimal edit.
Write each fix to `review/layout/fixes.md` with the log line it resolves.

# Mode `trim` (P13.06a)
Inputs: the limits report and the journal profile. Propose cuts as a table in
`review/layout/trim_proposal.md`: the passage, its word count, and where it goes (supplement or
deleted). Prefer moving detail to the supplement over deleting it. Apply only the rows the author
marks `accept`. Never cut a limitation, a PRISMA number, or a reported deviation.

# Mode `figures` (P8.15b)
Input: the figure audit. Fix the figure by changing the options of `agsci sr fig ...` (size, label
rotation, legend placement) and regenerating. Never edit a PDF by hand and never change the data
the figure reads.

# Rules
- Do not touch `review/` data files, `claims_grounding.json` or `references.bib` entries.
- Keep Aaron's prose rules if any text must move: no em or en dashes, never "falsifiable".
