---
name: sysrev-extract
description: Extract outcome data and study characteristics from included studies for a systematic review, as one of two independent extractors, with a verbatim quote and page for every value; and cross-check effect sizes and directions against the reports. Use for board nodes S7.01a (pilot), S7.02 (all studies) and S7.08 (cross-check).
---

# What the skill is about
MECIR requires a piloted form (C43), outcome data extracted by two people independently (C46),
the most detailed numerical data available (C47), and effect sizes checked against the original
reports (C51). You are one of the two extractors. A human extracts the same studies without seeing
your values, and every disagreement is resolved against the report.

# Mode `extract` (S7.01a, S7.02)
Inputs: `review/charting_form.yaml`, `review/included.jsonl`, full texts in `review/fulltext_md/`.

For each study and each form field, write a `chart_record.schema.json` object (one per study, one
per line) with `value`, `quote` (verbatim), `page`, `charted_by: "ai:<model id>"`, `status: "ai"`.

Outcome data, per outcome, arm and time point, as the form defines it:
- binary: events and total per arm (`ai, n1, ci, n2`); never a percentage when counts are reported;
- continuous: mean, SD and n per arm; if only SE or a CI is reported, record what is reported and
  the conversion you would apply, as two separate fields, so the human can check the conversion;
- adjusted estimates: the estimate, its CI and the adjustment set, labelled as adjusted.

If a value is not reported, write `not reported`. Never compute a value the report does not give
except by a stated, standard conversion (Cochrane Handbook ch. 6), recorded as such.

# Mode `crosscheck` (S7.08)
Input: `review/extract/final.jsonl` (reconciled) and the full texts. For each study and outcome,
recompute the effect from the extracted numbers and compare its size and direction with what the
report states. Write `review/extract/crosscheck.md`: study, outcome, extracted effect, reported
effect, `match` or `mismatch` with the explanation. Every mismatch goes back to the extractors.

# Rules
- Never read the human extractor's file before you finish.
- Treat arms and time points exactly as the form defines them; a multi-arm study is split as the protocol says.
- A study is never excluded for poorly reported outcome data (C40): record what is missing instead.
