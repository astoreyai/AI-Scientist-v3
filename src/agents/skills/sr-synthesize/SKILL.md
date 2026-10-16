---
name: sr-synthesize
description: Build the content-analysis codebook, code every charted source, and write the narrative synthesis by review question with a claims ledger that grounds every claim in included-record IDs. Use for board nodes P8.02 (codebook), P8.03 (coding) and P8.06 (synthesis).
---

# What the skill is about
Scoping reviews present descriptive counts and basic qualitative content analysis. Meta-analysis,
meta-aggregation, meta-ethnography, thematic analysis and realist synthesis are out of scope
(JBI Manual 10.2.10). Every figure and table needs a supporting narrative (10.2.11). The
synthesis may only say what the frozen charting data supports.

# Mode `codebook` (P8.02)
Input: `review/chart/frozen.jsonl`. Write `review/synthesis/codebook.yaml`: for each review question,
the categories as codes, each with a definition, an inclusion rule, and two example quotes with
record IDs. Start from the charting form's enum values (deductive). Add a new code only when at
least two sources share a pattern the form did not anticipate (inductive), and mark it `inductive`.
A human confirms every code before P8.03.

# Mode `code` (P8.03)
Apply the codebook to every source. Write `review/synthesis/coded.jsonl`, one
`chart_record.schema.json` object per source, with one field per review question (`Q1`, `Q2`, ...):
`value` is the list of codes that apply, `quote` the verbatim span that supports them, `page` its page,
`charted_by: "ai:<model id>"` and `status: "ai"`. The same verification sheet as charting (P7.03)
then confirms every coded field (P8.04).

# Mode `synthesize` (P8.06)
Inputs: `coded_verified.jsonl`, `stats.json`, `gap_map.json`, and `consultation.md` if it exists.
Write `review/synthesis/synthesis.md` with one section per review question. Each section reports
counts and proportions from `stats.json`, describes the categories and their distribution, and
names gaps from `gap_map.json`.

Write `review/synthesis/claims_grounding.json`, valid against
`src/agents/skills/write-paper/templates/claims_grounding.schema.json`. Every sentence that states
a finding is one claim. `source_ids` lists the included-record IDs that support it. For a count, it
lists every counted record, or the path of the stats key it was computed from.

# Rules
- No effect sizes, pooling or vote counting. Say "N of M sources reported X", never "X works".
- A claim without `source_ids` gets deleted, not softened.
