---
name: sr-submission
description: Prepare scoping-review submission and revision documents - cover letter, suggested and opposed reviewers, highlights, the reviewer response matrix and the response letter. Use for board nodes P15.03, P15.04, P15.05, P16.03a and P16.03d.
---

# Mode `cover-letter` (P15.03)
Inputs: `manuscript/main.pdf`, `review/journal_profile.yaml`, `review/registration.yaml`.
Write `submission/cover_letter.tex`, one page: what the review maps and why it matters to this
journal's readers, the registration DOI, the reporting checklist used, an AI-use sentence pointing
to the declarations, and confirmation that all authors approved. No claims beyond the abstract.

# Mode `reviewers` (P15.04)
Inputs: `manuscript/references.bib`, `review/team.yaml`.
Write `submission/reviewers.yaml` with 4 to 6 suggested reviewers who published on the topic in the
last 5 years. For each, give name, affiliation, a public profile URL, two relevant papers and
`conflict_check` (no co-authorship with any author in the last 5 years and not at an author's
institution, checked on OpenAlex). Add an opposed list only if the author supplies one. A human
confirms every entry.

# Mode `highlights` (P15.05)
Only when the journal profile requires highlights or key points. Write `submission/highlights.txt`
to the journal's count and length limits. Each highlight must be a claim from the claims ledger.

# Mode `response-matrix` (P16.03a)
Input: `review/journal/decision_<n>.md`. Split every reviewer and editor comment into atomic points.
Write `review/journal/response_<n>.yaml`: `id` (R1.3 and so on), `reviewer`, `quote` (verbatim),
`type` (error, request, question, opinion), and `action: null` for the author to set to `revise` or
`rebut` (P16.03b).

# Mode `response-letter` (P16.03d)
Inputs: the triaged matrix and `review/folds/<round>/changes.md`. Write
`review/journal/response_letter_<n>.tex`. For each point, quote it, give the response, and for a
revision give the page and the changed text. Rebuttals are courteous and cite evidence.

# Rules
- Every point in the decision letter appears in the matrix. Missing one is the most common cause
  of a second revision round.
