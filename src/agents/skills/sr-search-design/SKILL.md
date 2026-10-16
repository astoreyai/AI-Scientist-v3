---
name: sr-search-design
description: Build the scoping-review search - concept blocks, a primary search strategy, PRESS 2015 peer review when no librarian is available, revision, and translation to every other source. Use for board nodes P2.02, P2.04, P2.05b (AI branch), P2.05c and P2.11.
---

# What the skill is about
JBI expects an explicit, comprehensive and transparent search aligned with systematic-review
practice (JBI Manual 10.2.6). PRESS peer review happens on the primary strategy before it is
translated to other databases (PRESS 2015, McGowan et al.). The search is reported against the 16
PRISMA-S items, so every decision here must be recorded.

# Mode `terms` (P2.02)
Inputs: `review/pcc.md`, `review/prior_reviews.json`.
Write `review/terms.yaml`: one block per PCC element, each with `free_text` synonyms (with
truncation and spelling variants), `controlled` vocabulary per database where one exists (MeSH,
Emtree, ACM CCS, IEEE thesaurus), and `source` for each term (seed paper, thesaurus, prior review).

# Mode `primary` (P2.04)
Write `review/search/primary.txt` for ONE primary database chosen for the field (MEDLINE/PubMed
for health; Scopus for CS/AI when available, else OpenAlex). Use numbered lines, one concept
block per line, combined with Boolean operators on a final line. Record limits and filters with
a reason for each.

# Mode `press` (P2.05b, only when board decision P0.08 == no)
Review `review/search/primary.txt` against the six PRESS elements: translation of the question;
Boolean and proximity operators; subject headings; text words; spelling, syntax and line numbers;
limits and filters. For each element write `no revision`, `revision suggested` or `revision
required`, with the exact line and a proposed fix. Write `review/search/press.md`. The report is
disclosed in Methods as AI-performed PRESS review.

# Mode `revise` (P2.05c)
Inputs: `review/search/press.md`, `review/search/test_run.json` (hit counts and missed seed
papers). Edit `primary.txt` to fix every `revision required` item and to recover each missed seed
paper. A missed seed reveals a missing synonym; add the synonym rather than the paper's title words.
Append a dated entry to `review/search/changes.md` for every edit.

# Mode `translate` (P2.11)
Translate the PRESS-clean primary strategy to each source in the protocol, one file per source in
`review/search/<source>.txt`, preserving every concept block. Note syntax that cannot be carried
over (proximity, truncation) and the substitute used.

# Mode `seeds` (P2.03)
Input: `review/pcc.md`. Propose 10 to 20 known-relevant sources (landmark papers, papers named in
the prior reviews) as `review/seed_set.bib`, each with a DOI or arXiv id you resolved. The human
confirms every entry; the seed set tests recall, so it must not be built from the search results.

# Mode `grey` (P4.03, only when board decision P4.02 == yes)
Search the grey sources named in the protocol (theses, preprint servers, reports, organisation
websites) with the protocol's fixed screening depth (for example, the first 100 Google Scholar
results in a clean session). Write `review/records/raw/grey.jsonl` as `record.schema.json` objects
with `source` naming the site and a `grey:` id when no DOI exists. Log every query and depth in
`review/search_log.json` under `grey`.

# Mode `registers` (systematic review board, P4.07)
Search ClinicalTrials.gov and the WHO ICTRP separately (MECIR C27) with the review's PICO terms.
Write `review/records/raw/registers.jsonl` as `record.schema.json` objects with `source` set to the
register and a `grey:` id built from the registration number (for example `grey:NCT01234567`). Log
each query, date and hit count in `review/search_log.json` under `registers`.

# Rules
- Never add terms that only match the seed papers' titles; that inflates recall on the test set.
- Do not run the final searches; P4.01 does that after registration.
