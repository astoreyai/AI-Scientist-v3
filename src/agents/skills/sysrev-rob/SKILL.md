---
name: sysrev-rob
description: Assess risk of bias of each included result as one of two independent assessors, using the tool chosen at board decision RB.01 (RoB 2, ROBINS-I V2, QUADAS-2 or QUIPS), with a judgement, the signalling-question answers and a verbatim supporting quote for every domain. Use for board node RB.02.
---

# What the skill is about
MECIR requires risk of bias assessed for every result feeding the Summary of Findings table (C52),
in duplicate and independently (C53), with support and the source for each judgement (C54, C55).
RoB 2 takes precedence for randomized trials (C58). You are one assessor; a human is the other, and
disagreements are resolved by consensus.

# Inputs
- The tool from `review/decisions.yaml#RB.01`.
- `review/extract/final.jsonl` (which results feed which synthesis) and the full texts.

# Domains (use these names exactly; `src/systematic_review/appraisal.py` checks them)
- `rob2`: randomization process; deviations from intended interventions; missing outcome data;
  measurement of the outcome; selection of the reported result. Levels: low, some_concerns, high.
- `robins_i_v2` (draft as of 2025-11-20): confounding; classification of interventions; selection of
  participants; missing data; measurement of the outcome; selection of the reported result.
  Levels: low, moderate, serious, critical.
- `quadas2`: patient selection; index test; reference standard; flow and timing (plus applicability
  for the first three). Levels: low, unclear, high.
- `quips`: study participation; study attrition; prognostic factor measurement; outcome measurement;
  study confounding; statistical analysis and reporting. Levels: low, moderate, high.

# What to do
For each study and each assessed result, answer the tool's signalling questions from the report
(and the trial registration or protocol when the report cites one), then give the domain judgement
the tool's algorithm implies. Do not give an overall judgement; `agsci sysrev rob-overall` derives it.

Write `review/rob/ai.json`:
`{"<study id>": {"<domain>": {"judgement": "...", "signalling": {"1.1": "Y", ...}, "quote": "...", "page": 4}}}`

# Rules
- Every judgement other than low needs a quote that shows the problem; a low judgement needs a quote
  that shows the safeguard. No quote means the report is silent: say so and judge as the tool directs.
- Assess the result, not the study's reputation or journal.
- Never read the human assessor's file.
