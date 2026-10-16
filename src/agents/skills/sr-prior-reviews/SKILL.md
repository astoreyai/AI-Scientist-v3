---
name: sr-prior-reviews
description: Find published reviews and registered protocols that already cover a proposed scoping-review topic, so the go/no-go decision (board node P0.03) rests on evidence. Use for board node P0.02.
---

# What the skill is about
Before a scoping review starts, the team must know whether an existing or ongoing review already
answers the same question. This skill searches for reviews and protocols and reports how close
each one is to the proposed topic. It does not make the go/no-go decision; a human does (P0.03).

# Inputs
- `review/topic.md`: the topic paragraph written by the lead reviewer (P0.01).

# What to do
1. Derive 3 to 6 search queries from the topic, each combining the core concept with a review
   filter: `"scoping review" OR "systematic review" OR "mapping review" OR "evidence map" OR
   "literature review" OR survey`.
2. Search, in this order, recording every query string, source and date:
   - OpenAlex and Semantic Scholar (use `src/agents/skills/retrieve-references/scripts/openalex_fetch.py`
     and `s2_fetch.py` with review-type queries),
   - OSF Registries (search `https://api.osf.io/v2/registrations/?filter[title]=<terms>`),
   - JBI Evidence Synthesis, Cochrane Library and Campbell Systematic Reviews (journal search pages),
   - PROSPERO for related systematic reviews (PROSPERO does not register scoping reviews).
3. For every hit, open the abstract (and the protocol for registrations) and judge overlap on each
   PCC element: population, concept, context. Use `same`, `partial` or `different`.
4. Keep only real items you opened. Every item needs a resolvable DOI, registry URL or landing page.

# Output
Write `review/prior_reviews.json`:
```json
{
  "queries": [{"source": "openalex", "query": "...", "run_utc": "...", "hits": 0}],
  "items": [{
    "title": "...", "year": 2025, "type": "scoping review | systematic review | protocol | other",
    "url_or_doi": "...", "registry": "OSF | PROSPERO | journal | none",
    "status": "published | ongoing",
    "overlap": {"population": "same|partial|different", "concept": "...", "context": "..."},
    "differentiation": "one sentence on what the proposed review would add"
  }],
  "summary": "two to four sentences: the closest item and why"
}
```

# Rules
- Never list an item you did not open. An empty `items` list is a valid result.
- Report overlap honestly. Do not frame a near-duplicate as different to keep the project alive.
