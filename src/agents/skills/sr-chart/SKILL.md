---
name: sr-chart
description: Chart (extract) data from each included source into the frozen charting form, with a verbatim quote and page for every field, for 100% human verification. Also performs descriptive critical appraisal when the board decision requires it. Use for board nodes P7.01a (pilot), P7.02 (all sources) and P7.05 (appraisal).
---

# What the skill is about
JBI's best practice is two independent extractors, or one extractor with another person reviewing
all or part of the extraction (JBI Manual 10.2.9). JBI also notes that current AI tools have not
shown they can extract to the level many scoping reviews need (10.2.1.4). So this skill extracts and
a human verifies every field against its quote (P7.03). The quote is what makes verification fast
and honest.

# Inputs
- `review/charting_form.yaml` (the pilot version at P7.01a, the final version at P7.02)
- `review/included.json` and the full text in `review/fulltext_md/<record_id>.md`

# What to do
For each source and each form field:
1. Find the passage that answers the field. Copy it verbatim into `quote` and record the `page`.
2. Set `value` in the field's type, choosing from `values` for enums.
3. If the source does not report the field, set `value: "not reported"`, `quote: ""` and
   `status: "not_reported"`. Never infer a value the source does not state.
4. Set `charted_by: "ai:<model id>"`, `verified_by: null` and `status: "ai"`.

Write one `chart_record.schema.json` object per source, one per line, to the node's output path
(`review/chart/pilot/ai.jsonl` at P7.01a, `review/chart/ai.jsonl` at P7.02).

# Mode `appraise` (P7.05, only when board decision P7.04 == yes)
Use the tool named in the protocol. Record each item's rating with its quote. Results are
descriptive only and must not drive recommendations (JBI Manual 10.2.8).

# Rules
- One source per pass. Do not carry values between sources.
- If a field's guidance is ambiguous for a source, record the case in `review/chart/ambiguities.md`
  for the form revision at P7.01c.
