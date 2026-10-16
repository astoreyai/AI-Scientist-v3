---
name: sr-protocol
description: Draft the scoping-review charting form, the AI second-reviewer specification and the a priori protocol in the JBI structure. Use for board nodes P2.06 (charting form), P2.07 (AI reviewer spec) and P2.08 (protocol).
---

# What the skill is about
JBI requires an a priori protocol, and every later deviation must be reported with a reason
(JBI Manual 10.2.2). Protocol items follow Peters et al. 2022 (JBI Evid Synth 20(4):953-68).
Scoping reviews register on OSF Registries (Generalized Systematic Review Registration) because
PROSPERO does not accept them.

# Mode `charting-form` (P2.06)
Inputs: `review/pcc.md`, `review/eligibility.md`.
Write `review/charting_form.yaml`, a list of fields. Each field has `id`, `label`, `question`
(the review question it serves), `type` (`text`, `enum`, `number`, `year`, `list`), `values` for
enums (always including `not reported`), and a one-line `guidance` with a worked example. Include
the standard descriptors: author, year, country, source type, study design, population, setting,
and one or more fields per review question. Use a named framework such as PROGRESS-Plus for any
equity fields.

# Mode `ai-reviewer` (P2.07)
Write `review/ai_reviewer.yaml`, which the board's screening and charting nodes read:
- `model`: exact model ID and version; `temperature`; `run_dates` (filled at run time).
- `tasks`: which nodes the AI acts on (P5.02c, P5.03, P6.04, P6.08c, P7.01a, P7.02).
- `prompt_files`: paths to the prompt templates, versioned.
- `decision_rule`: when uncertain, the AI answers `maybe`, which counts as `include` for conflict
  purposes, so uncertainty never silently excludes a record.
- `calibration`: the pilot procedure (P5.02) and the threshold it must meet.
- `limits`: known failure modes to disclose (non-English records, missing abstracts).
This content feeds the AI-use disclosure required by the 2025 joint statement (Flemyng et al.):
tool, version, dates, validation and limits.

# Mode `protocol` (P2.08)
Write `review/protocol.md` with these sections: title (contains "scoping review"); review team;
background and differentiation; objective and questions; PCC and eligibility (from
`eligibility.md`); sources and search (strategy from `review/search/`, PRESS outcome, grey-literature
plan with fixed screening depth); selection (two independent screeners, the human and the AI second
reviewer, a human adjudicator, the 25-record pilot at >= 75% agreement, kappa reporting); charting
(form, pilot, AI charting with 100% human verification); critical appraisal (not planned, per JBI
10.2.8, unless a funder requires it); consultation (state Arksey and O'Malley or Levac); analysis and
presentation (descriptive counts and basic content analysis only, figures and tables planned);
reporting (PRISMA-ScR); deviations policy; AI-use statement; registration.

# Mode `revise-form` (P7.01c)
Input: the charting pilot agreement report. For every field below the agreement threshold, rewrite
its `guidance` and worked example, split it if it mixes two questions, or add an enum value the
sources actually use. Record each change in `review/chart/form_changes.md`.

# Mode `extraction-form` (systematic review board, P2.06)
As `charting-form`, plus outcome-data fields per outcome, arm and time point: events and totals for
binary outcomes; mean, SD and n for continuous outcomes; adjusted estimates with CI and adjustment
set; and the fields the risk-of-bias tool needs (allocation, blinding, attrition, analysis).

# Mode `protocol-sr` (systematic review board, P2.08)
Write `review/protocol.md` covering the 17 PRISMA-P 2015 items, with the methods fixed in advance as
MECIR C19-C23 require: search (C19); risk-of-bias tool and process (C20); synthesis: effect
measures, model (REML random effects, HKSJ when tau2 > 0 and k > 2), heterogeneity assessment,
sparse-data methods (C21); a short list of pre-specified effect modifiers, each with a rationale
(C22); and the GRADE and Summary of Findings plan with at most 7 outcomes (C23). State that an AI
is one of the two independent reviewers for screening, extraction and risk of bias, how it was
calibrated, and that humans resolve every disagreement. Registration: PROSPERO when eligible,
before data extraction starts; otherwise OSF.

# Rules
- The protocol is frozen at P2.10. Do not edit it after that; deviations go to the deviations log.
