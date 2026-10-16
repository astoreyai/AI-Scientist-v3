---
name: sr-journals
description: Build a shortlist of journals for a scoping review, each with a requirement profile taken from the journal's live author guidelines. Use for board node P1.01; the profile shape is also what P1.03 writes.
---

# What the skill is about
The target journal sets the reporting checklist, word limits, abstract structure, citation style,
LaTeX template, graphical-abstract and highlights duties, preprint policy and AI-use rules. Choosing
it early (lane P1) lets every later node work to the right limits.

# Inputs
- `review/pcc.md`
- `src/scoping_review/schemas/journal_profile.schema.json`

# What to do
1. List 6 to 10 candidate journals that publish scoping reviews in the topic's field. Find them
   from where comparable scoping reviews were published (OpenAlex query: topic terms plus
   `"scoping review"`, group by venue) and from field-specific evidence-synthesis venues.
2. For each candidate, open the journal's live author guidelines and AI policy pages. Fill every
   field of `journal_profile.schema.json` from those pages. If a page cannot be opened, set the
   field to `null` and add the URL to `unverified`.
3. Score fit on: scope match (0-3), accepts scoping reviews (required), AI policy allows a
   disclosed AI second reviewer (required unless unknown), open-access and APC, typical turnaround.

# Output
Write `review/journal_shortlist.yaml`:
```yaml
generated_utc: "..."
candidates:
  - rank: 1
    profile: {<journal_profile.schema.json object>}
    fit: {scope: 3, notes: "..."}
    unverified: []
excluded: [{name: "...", reason: "AI policy forbids AI screening"}]
```

# Rules
- Every value comes from a page you opened, with `guidelines_url` and `retrieved_utc` filled in.
- Never guess a word limit or a checklist mandate. Unknown is `null` plus an `unverified` URL.
