---
name: sr-question
description: Draft the PCC (population, concept, context) frame, objective, review questions and eligibility criteria for a scoping review. Use for board nodes P0.04 (PCC and questions) and P2.01 (eligibility).
---

# What the skill is about
JBI scoping reviews frame the question with PCC (JBI Manual 10.2.3). One element may be omitted;
PICO or PECO is acceptable only when the review is a precursor to a systematic review. A scoping
review maps evidence, clarifies concepts, examines how research is done or finds gaps (Munn et al.
2018). Questions about effectiveness, feasibility, appropriateness or meaningfulness belong to a
systematic review, so flag any such question for board decision P0.05.

# Mode `pcc` (P0.04)
Inputs: `review/topic.md`, `review/prior_reviews.json`.

Write `review/pcc.md` with these sections:
1. **Population**, **Concept**, **Context**: one short paragraph each, with inclusion boundaries.
2. **Objective**: one sentence that starts "This scoping review will map".
3. **Review questions**: 2 to 5 questions, each tagged with the PCC elements it uses.
4. **Differentiation**: how this review differs from the closest items in `prior_reviews.json`.
5. **Type check**: for each question, `mapping` or `effectiveness-type`. Any `effectiveness-type`
   question must be rewritten as a mapping question or flagged for P0.05.

# Mode `eligibility` (P2.01)
Inputs: `review/pcc.md` (approved at P0.06).

Write `review/eligibility.md` with numbered criteria the screeners will cite as reason codes:
- `I1..In` inclusion criteria, one per PCC element plus source type, language and date range.
- `E1..En` exclusion criteria, each the explicit negation of one inclusion criterion or an
  explicit extra rule (for example, "E7 conference abstract without full text").
- A **source types** line: primary studies, reviews, grey literature, preprints, as the PCC requires.
- A short rationale for every date and language limit.

# Mode `pico` (systematic review board, P0.04)
Write `review/pcc.md` for a systematic review: **Population**, **Intervention** (or Exposure, or Index
test for diagnostic accuracy), **Comparator**, **Outcomes** (primary and secondary, with time
points), and **Study designs** eligible. Objective: one sentence that names the effect, accuracy or
prognostic estimate sought. List up to 7 outcomes for the Summary of Findings table. Flag any
question that only maps evidence: that belongs on the scoping board (decision P0.05).

# Rules
- Every criterion must be decidable from a title and abstract or, if not, be marked `[full-text only]`.
- Use the same terms in the criteria that the questions use.
