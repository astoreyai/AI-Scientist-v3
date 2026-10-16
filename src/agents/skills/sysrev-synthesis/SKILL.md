---
name: sysrev-synthesis
description: Write the systematic-review synthesis by outcome from the computed meta-analyses, subgroup, sensitivity and small-study results and the risk-of-bias judgements, with a claims ledger grounding every finding; or, when meta-analysis is not appropriate, a structured synthesis reported with the 9 SWiM items. Use for board nodes S9.10 (swim) and S9.11 (synthesize).
---

# What the skill is about
Every number comes from a computed result file or the frozen extraction. Interpretation rests on
estimates and confidence intervals, never on significance labels (MECIR C72). Heterogeneity is
described, not reduced to a threshold (C63).

# Mode `swim` (S9.10, when board decision S9.01 == no)
Write `review/synthesis/swim.md` covering the 9 SWiM items (Campbell et al., BMJ 2020): how studies
were grouped; the standardised metric and transformation used; the synthesis method (for example,
summarising effect estimates, combining P values, or vote counting based on the direction of effect,
never on statistical significance); the criteria used to prioritise results; how heterogeneity was
investigated; how certainty was assessed; how the data are presented (tables and plots); the
synthesis findings; and the limitations of the synthesis. Name the studies behind every statement.

# Mode `synthesize` (S9.11)
Inputs: `review/synthesis/meta/*.json`, `subgroups/`, `sensitivity/`, `egger.json` (each optional),
`swim.md` if it exists, `review/rob/overall.json`, `review/extract/final.jsonl`.

Write `review/synthesis/synthesis.md`, one section per outcome in the protocol's order:
1. the studies and participants contributing, and their risk of bias;
2. the pooled estimate with its 95% CI and, with 5 or more studies, the 95% prediction interval;
3. heterogeneity (tau2 with its CI, I2) in words;
4. pre-specified subgroup results with the test for subgroup differences, and sensitivity analyses;
5. small-study effects when testable (10 or more studies), else say why not tested.

Write `review/synthesis/claims_grounding.json` (schema
`src/agents/skills/write-paper/templates/claims_grounding.schema.json`): every finding is a claim;
`source_ids` lists the included study IDs, plus `stats:` keys or the result file for computed numbers.

# Rules
- Never round a number differently from the result file, never report an estimate the files do not hold.
- Exponentiate log ratios for the text (RR 0.49, 95% CI 0.33 to 0.73) exactly as computed.
