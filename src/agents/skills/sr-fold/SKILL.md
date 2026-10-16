---
name: sr-fold
description: Fold review findings into a protocol or manuscript one decision at a time, with the author deciding each finding, and record every change so the grounding and reference gates can re-run. Use for board nodes P2.09b, P11.01 (developmental edit), P12.01c and P16.03c.
---

# What the skill is about
In the mays/013 reviews, every fold cycle introduced regressions: overstated methods, a citation
reattributed to the wrong paper, contradictions between old and new text. So this skill folds
narrowly, records each change, and leaves the regression check to the gate that follows
(P11.06, P12.01d, P16.03c's gate run).

# Inputs
- The document being revised (`review/protocol.md` or `manuscript/`).
- A review file: a referee report, a Codex report, a reviewer letter, or for P11.01 a
  reporting-item coverage check against the outline.
- For P16.03c, the author's triage file (`review/journal/response_<n>.yaml`), which marks each
  point `revise` or `rebut`.

# What to do
1. Turn the review into a findings table, `review/folds/<round>/findings.yaml`: `id`, `severity`
   (critical, major, minor), `location`, `finding`, and `proposed_change`.
2. Stop and present the table to the author. Each finding gets `accept`, `reject` (with reason)
   or `modify`. For P16.03c the triage file is that decision.
3. Apply only accepted changes, each as a minimal edit. Record each one in
   `review/folds/<round>/changes.md` with the finding ID, file, before and after text.
4. When a change touches a number or a cited claim, add its claim ID to
   `review/folds/<round>/recheck.txt` so the grounding audit re-checks it.

# Rules
- Never change a number to match a reviewer's expectation. Numbers come only from frozen data.
- Never delete a limitation to satisfy a reviewer. Rebut it instead.
- One finding, one edit. No opportunistic rewrites alongside a fold.
