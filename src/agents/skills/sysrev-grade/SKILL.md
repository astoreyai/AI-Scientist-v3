---
name: sysrev-grade
description: Draft GRADE certainty-of-evidence ratings for each Summary of Findings outcome, with a written reason for every downgrade or upgrade, for the review team to confirm. Use for board node GR.01.
---

# What the skill is about
MECIR C74 and C75 require certainty rated per outcome on the five GRADE domains, with every
downgrade or upgrade justified. The team decides; this skill drafts the judgements and their reasons
from the review's own evidence so that each one is checkable.

# Inputs
`review/synthesis/synthesis.md`, `review/rob/overall.json`, `review/synthesis/meta/*.json` and
`egger.json` (when present), `review/extract/final.jsonl`.

# What to do
For each outcome (at most 7, the Summary of Findings outcomes in the protocol):
1. Start at `high` for randomized trials, or for non-randomized studies assessed with ROBINS-I;
   otherwise `low`.
2. Consider each downgrade domain and move 0, 1 or 2 levels:
   - `risk_of_bias`: the share of weight from studies at high risk or with some concerns;
   - `inconsistency`: unexplained heterogeneity (tau2, I2, prediction interval, overlap of CIs);
   - `indirectness`: population, intervention, comparator or outcome differ from the question;
   - `imprecision`: the CI crosses a decision threshold, or the optimal information size is not met;
   - `publication_bias`: small-study effects, or reasons to suspect missing results.
3. Consider upgrades only when no downgrade applies: `large_effect`, `dose_response`,
   `plausible_confounding`.

Write `review/synthesis/grade.json`: per outcome, `start`, `down`, `up` and `reasons` (one sentence
per nonzero move citing the number that drives it), plus `relative`, `participants`, `studies`,
`control_risk` (with its source) and `comment`. `agsci sysrev grade-check` recomputes the certainty
and rejects any move without a reason.

# Rules
- Cite the evidence for each move ("I2 = 92%, prediction interval 0.14 to 1.77 crosses 1"), not a label.
- Do not double count: a risk-of-bias problem already downgraded is not also an inconsistency reason.
