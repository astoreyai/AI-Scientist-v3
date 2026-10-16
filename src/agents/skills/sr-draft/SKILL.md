---
name: sr-draft
description: Draft scoping-review manuscript sections in the target journal's structure from frozen evidence only - outline, Methods, Results, Introduction, Discussion, Conclusion, structured abstract and title, and declarations. Use for board nodes P9.01 to P9.08.
---

# What the skill is about
Each section is drafted from named artifacts, never from memory. The outline maps PRISMA-ScR items
(Tricco et al. 2018; use the version current at submission) to sections so that the checklist at
P14.05 can cite page numbers.

# Inputs by node
| Node | Section | Reads |
|---|---|---|
| P9.01 | outline | `review/journal_profile.yaml`, reporting standard decision, `synthesis.md` |
| P9.02 | Methods | `protocol.md`, deviations log, `search_log.json` (PRISMA-S), kappa files, `calibration_report`, `ai_reviewer.yaml` |
| P9.03 | Results | `synthesis.md`, `claims_grounding.json`, figures, characteristics table, `prisma_counts.json` |
| P9.04 | Introduction | `pcc.md`, `prior_reviews.json` |
| P9.05 | Discussion | Results draft, `synthesis.md`, `gap_map.json` |
| P9.06 | Conclusion | Discussion draft |
| P9.07 | Abstract and title | Methods, Results and Conclusion drafts, journal abstract structure and word limit |
| P9.08 | Declarations | `ai_reviewer.yaml`, `review/ai_ledger.jsonl`, `team.yaml`, `registration.yaml`, journal profile |

# What to do
0. In mode `outline`, also write `manuscript/reporting_map.yaml`: for each checklist item number,
   the `\label` key you will place where that item is reported (for example `3: sec:rationale`), or
   `"na: <reason>"` for an if-done item that was not done (PRISMA-ScR items 12 and 16). Every drafted
   section must then carry those labels; the checklist (P14.05) reads page numbers from `main.aux`.
1. Write LaTeX for the section to `manuscript/sections/<section>.tex`.
2. **Methods** reports the AI second reviewer: tool, version, dates, which stages, the calibration
   result, kappa at each stage, and how disagreements were adjudicated. It also states the PRESS
   route (librarian or AI) and every protocol deviation with its reason.
3. **Results** opens with the PRISMA flow numbers, exactly as in `prisma_counts.json`. Each figure
   and table gets its own narrative paragraph. Every finding sentence carries the citation keys
   of its `source_ids` from the claims ledger.
4. **Introduction** follows the CARS moves: establish the territory, show the gap (from the prior
   reviews), and state how this review fills it.
5. **Discussion** includes a limitations paragraph covering the sources not searched, language
   limits, records not retrieved, and the AI-screening limits from `ai_reviewer.yaml`.
6. **Abstract** uses the journal's structure and stays within its word limit. The title contains
   "scoping review".
7. **Declarations** covers AI use (from the ledger), data availability (the OSF project in
   `registration.yaml`), CRediT roles, funding, competing interests and registration.

# Rules
- No number may appear that is not in a frozen artifact.
- Keep Aaron's prose rules: no em or en dashes, never the word "falsifiable", and connected
  paragraphs rather than fragment lists.
