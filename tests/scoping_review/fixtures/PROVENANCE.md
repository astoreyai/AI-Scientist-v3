# Test fixture provenance (real data only)

| Fixture | What it is | How it was made |
|---|---|---|
| `sr_search_2026-10-16/` | 299 real records from PubMed, Europe PMC, OpenAlex, Semantic Scholar and Crossref (60 per source, 1 Europe PMC record without identifier dropped) | `agsci sr search --strategies sr_search_2026-10-16/strategies --cap 60` on 2026-10-16; queries in `strategies/`, PRISMA-S log in `search_log.json`. arXiv returned HTTP 429 (rate limit) on that run and is absent. |
| `aisr_records.jsonl`, `aisr_decisions.jsonl` | 176 real arXiv records and their real screening decisions | Converted from `/mnt/projects/ai-scientist-review/phase1/screening_merged.json` (Storey, systematic review of LLM research systems, 2026). INCLUDE/EXCLUDE/UNCERTAIN mapped to include/exclude/maybe; exclusion codes kept. Year derived from the arXiv id. |

The Cohen's kappa test uses the published worked example on the Wikipedia "Cohen's kappa" page
(50 proposals; both yes 20, A yes/B no 5, A no/B yes 10, both no 15; kappa = 0.4), not generated data.
| `aisr_chart.jsonl` | 139 real charted sources (9 fields) | Converted from `/mnt/projects/ai-scientist-review/phase1/extraction_database.json` into `chart_record.schema.json`. The source extraction stored no verbatim quotes, so `quote` is empty and `status` is `ai` (or `not_reported` for empty fields). |
| `crossref_2026-10-16/` | Real Crossref `works?filter=updates:<doi>` responses and doi.org BibTeX (content negotiation) for three DOIs: Wakefield et al. 1998 Lancet (retracted 2010, also corrected 2004) and two DOIs from the search fixture | `curl` on 2026-10-16; file names are the DOI with `/()` replaced by `_` |
| `openalex_2026-10-16/` | Real OpenAlex work records (`best_oa_location`, `referenced_works`) for two DOIs, the 68 works Hilkenmeier et al. 2026 references (`refs_batch_*.json`), the works citing it, and that article's open-access PDF (Systematic Reviews 15, CC BY 4.0) | `curl` against api.openalex.org and link.springer.com on 2026-10-16 |
| `jair_shortlist_2026-10-16.yaml` | A real journal requirement profile for JAIR | Recorded by hand from the live submissions page on 2026-10-16; every unstated field is null and listed under `unverified` |
