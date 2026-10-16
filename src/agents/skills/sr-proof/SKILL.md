---
name: sr-proof
description: Proofread the typeset scoping-review PDF and produce a tracked change list for the author to accept or reject. Use for board node P14.03.
---

# What the skill is about
This is the last read before the human proofread (P14.04). Automated checks (P14.01 numbers,
P14.02 cross-references, numbering, acronyms and spelling) run separately, so this pass looks for
what scripts miss.

# Inputs
- `manuscript/main.pdf` and `manuscript/main.tex`
- `review/proof/auto.md` (P14.02 output), to avoid duplicating its findings

# What to do
Read the whole PDF in order and list every:
- typo, wrong word, or grammar error;
- inconsistent term (the same concept named two ways), inconsistent capitalization or number format;
- sentence a reader would stumble on, with a minimal rewrite;
- caption that does not stand alone;
- table or figure that the text never mentions, or mentions out of order;
- statement in the abstract or conclusion that the Results do not support.

# Output
Write `review/proof/ai.md` as a table: `#`, `page`, `line or location`, `current text`,
`proposed text`, `type` (typo, grammar, consistency, clarity, caption, support). The author
accepts or rejects each row at P14.04.

# Rules
- Do not edit the manuscript. This skill only proposes.
- Do not restyle prose that is correct. Proofreading fixes errors; it does not rewrite voice.
