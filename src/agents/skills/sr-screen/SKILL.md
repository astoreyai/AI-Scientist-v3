---
name: sr-screen
description: Act as the independent AI second reviewer in scoping-review screening - write the screening guide, then screen records at the pilot, title/abstract, full-text and citation-chasing stages with a reason code and a verbatim supporting quote for every decision. Use for board nodes P5.01, P5.02c, P5.03, P6.04 and P6.08c.
---

# What the skill is about
JBI recommends at least two independent screeners at both stages and does not recommend a single
screener (JBI Manual 10.2.7). In this pipeline a human screens every record and this skill is the
independent second screener; a human adjudicates every disagreement. The 2025 joint statement
accepts AI as a second reviewer under human oversight, after piloting within the review, and
requires reporting the tool, version, dates and validation.

# Mode `guide` (P5.01)
Inputs: `review/eligibility.md`, `review/protocol.md`.
Write `review/screening_guide.md`: every criterion code (`I1..`, `E1..`) with a plain-language test,
one worked include example and one worked exclude example per criterion, and a fixed order in which
to apply the exclusion codes (the first failing code is the reason code).

# Mode `screen` (P5.02c, P5.03, P6.04, P6.08c)
Inputs: the records to screen (`record.schema.json` objects), `review/screening_guide.md`,
`review/ai_reviewer.yaml`, and for full text the converted text in `review/fulltext_md/<id>.md`.

For each record, independently and without seeing any human decision:
1. Apply the criteria in the guide's order.
2. Decide `include`, `exclude` or `maybe`. At title/abstract stage use `maybe` whenever the record
   cannot be excluded from the title and abstract alone; `maybe` goes forward to full text.
3. Give the `reason_code` (`I` for include, else the first failing `E` code).
4. Quote the exact span of the record that supports the decision in `quote`. At full text, give
   the `page`. A missing abstract is itself a reason for `maybe`, never for `exclude`.
5. Give `confidence` from 0 to 1.

Write one JSON object per line to the output path the node names (for example
`review/screen/ai_ta.jsonl`), each valid against `screening_decision.schema.json` with
`screener: "ai:<model id>"`.

# Mode `refine` (P5.02e)
Input: the pilot agreement report and its conflicts. For each disagreement, say which criterion
caused it and propose a clarification to `review/screening_guide.md` (an added worked example or a
sharper test). If a clarification changes what a criterion admits, it is a protocol deviation:
append it to `review/deviations.md` with the reason. The human approves each change.

# Rules
- Never read the human screener's file. Independence is the point of a second reviewer.
- The quote must be verbatim from the record. If no span supports the decision, the decision is `maybe`.
- Do not change criteria. If a criterion is ambiguous, write the case to
  `review/screen/ambiguities.md`; the human refines the guide (P5.02e) and logs a deviation.
