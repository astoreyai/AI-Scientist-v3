# Plan: research types for AI-Scientist (scoping review, systematic review)

2026-10-15 · fork `astoreyai/AI-Scientist-v3` @ `2b8aa39`

## L-1 Decision record (frozen)

| # | Decision | Bound answer |
|---|---|---|
| Q1 | Approval gate for AI use | None in the template: "approval doesn't matter for this project" (Aaron, 2026-10-15). Journal AI-disclosure duties still apply, so disclosure stays in P9.08. |
| Q2 | Second screener | An AI second reviewer plus a human adjudicator, piloted and calibrated, with kappa reported. |
| Q3 | Pilot topic | Open. Card P0.01 is a human decision and stays open until Aaron picks a topic. |
| D1 | Board format | `board.yaml` in the repo, validated, rendered and tracked by `src/board/` (`agsci board`). GitHub Projects can be added later as a one-way mirror (the `gh` CLI is too old and its token lacks the `project` scope). |

## 1. Architecture: one board engine, many research types

AI-Scientist today has exactly one research type, which this plan calls `empirical_optimization`. Each run takes a `task.md` and a sealed scalar evaluator, runs a fixed chain of six phases, and produces one paper. The augmentation adds a **board layer** above the existing pipeline. Every research type becomes a graph template that the board layer executes.

```
src/board/                       engine (promoted from plan/board.py)
  schema + validator             data-derived edges, loops with guard/bound/progress, gates, decisions
  ledger                         per-node state + per-iteration loop records (ATG execution ledger)
  scheduler                      ready = all producers done or skipped; dispatch by `exec`
  render                         kanban HTML; Run Inspector gets a board tab later
src/<type>/                      one top-level package per research type (flat, like src/pipeline;
  board.yaml                     the template graph       nested packages break the task-runtime copy)
  cli.py                         `agsci <type-short> <subcommand>`: script nodes
src/agents/skills/<type>-*/      agent nodes (same SKILL.md format as create-idea, write-paper)
configs/journal/*.yaml           journal profiles shared by every type
```

**Executors.** Each node's `exec` decides who acts. `script` nodes run deterministic code. `agent` nodes run a skill through Headless CLI inside the existing Docker image. `skill` nodes are host Claude skills (`/disjoint`, `/ref-bolster`, and so on). `human` cards block until a person marks them done. `ai+human` nodes are drafted by the AI and decided by a person.

**AI-use ledger.** Every `agent` and `ai+human` node appends one line to `review/ai_ledger.jsonl` with the tool, model ID and version, date, prompt hash, input hashes and output hashes. The 2025 joint statement (Cochrane, Campbell, JBI, CEE; Flemyng et al.) requires reporting the tool, version, dates, validation and limits for any AI that makes judgments. The declarations node (P9.08) is generated from this ledger.

**Reuse from the fork (exists today).** Most of the pipeline machinery carries over:

- **Agents:** the Headless CLI agent runner, Docker isolation and the run-directory envelope.
- **Evidence and figures:**
  - `claims_grounding.schema.json`, whose `source_ids` become included-record IDs.
  - `generate-concept-figure`.
- **References:** `retrieve-references` (`s2_fetch.py`, `openalex_fetch.py`).
- **LaTeX validation:** `validate-paper` (`compile_latex.sh`, `validate_tex_refs.py`, `validate_figures.py`).
- **Review and revision:** `review-paper`, plus the review-driven revision patterns in `src/pipeline/revision.py`.

**Reuse from the workspace.** Earlier review projects supply working code:

- **mays/013** (`corpus/`, 584 lines): `harvest_multisource.py`, `build_corpus.py`, `screen_new.py`, `mdtolatex.py`.
- **glp1_brca:** `survivorship/search/multi_source_search.py`.
- **ai-scientist-review:** `phase1/screening_agent.py` and `extraction_template.json`.
- **Host skills:** `/systematic-review`, `/ref-bolster`, `/claim-to-source`, `/disjoint`, `/sciwrite`, `/humanizer`, `/latex-figures`, `/latex-inspect`, `/visual-inspect`, `/scientific-reviewer`, `/committee-review`.

**The existing pipeline as a research type.** `empirical_optimization` gets its own `board.yaml`. Its six phases become `agent` loop nodes, and its outputs feed the same P9–P17 lanes. A dissertation chapter that runs an experiment and a chapter that maps a literature then share one board engine and one manuscript back end.

## 2. Scoping review graph (`src/scoping_review/board.yaml`)

Level history:
- **L0** is one node: a research question in, a published scoping review out.
- **L1** splits that node into 18 lanes.
- **L2** has 167 atomic nodes.

Check: `agsci board check src/scoping_review/board.yaml`, which exits 0 and prints `nodes=167 edges=367 gates=14 decisions=16 loops=11 human=68 critical_path_len=78 widest_parallel_group=6`.

| Lane | Nodes | Gates | Decisions | Loops | Human / AI+human |
|---|---|---|---|---|---|
| P0 Topic and go/no-go | 8 | 1 | 3 | 0 | 6 |
| P1 Journal targeting | 5 | 0 | 2 | 0 | 2 |
| P2 Protocol and search design | 16 | 1 | 0 | 2 | 5 |
| P3 Registration | 4 | 0 | 1 | 0 | 3 |
| P4 Search execution | 6 | 1 | 2 | 0 | 4 |
| P5 Title/abstract screening | 12 | 1 | 0 | 1 | 5 |
| P6 Full-text screening | 13 | 1 | 0 | 1 | 5 |
| P7 Charting | 13 | 1 | 3 | 1 | 10 |
| P8 Synthesis and visualization | 18 | 1 | 1 | 1 | 3 |
| P9 Drafting | 11 | 1 | 0 | 0 | 0 |
| P10 References | 7 | 1 | 0 | 0 | 0 |
| P11 Editing | 6 | 1 | 0 | 0 | 1 |
| P12 Internal review | 6 | 1 | 0 | 1 | 3 |
| P13 Typesetting and layout | 11 | 1 | 1 | 2 | 2 |
| P14 Proofreading | 6 | 1 | 0 | 0 | 2 |
| P15 Submission | 10 | 1 | 2 | 0 | 6 |
| P16 Peer review and revision | 11 | 0 | 1 | 2 | 8 |
| P17 Publication and archiving | 4 | 0 | 0 | 0 | 3 |

**Gates (14).**
- **Scope and protocol:** PCC approved (P0.06); protocol frozen with a hash (P2.10).
- **Screening and data:**
  - Dedup spot-check: 0 false merges in 50 pairs (P4.05).
  - Title/abstract screening complete (P5.07).
  - Included set frozen, with PRISMA counts that balance (P6.09).
  - Charting dataset frozen with 100% of fields human-verified (P7.10).
- **Grounding:**
  - Synthesis grounded and limited to descriptive content analysis (P8.16).
  - Every empirical claim grounded (P9.11).
  - References clean (P10.07).
  - No regressions from editing (P11.06).
- **Sign-off:** all-author approval (P12.02); layout clean (P13.07); proof complete (P14.06); submit (P15.10).

**Yes/no and journal decisions (16).**
- **Go/no-go:**
  - Does an existing review already answer the question (P0.03)?
  - Is a scoping review the right type? Munn 2018 and JBI route effectiveness questions to a systematic review (P0.05).
  - Is a librarian available for PRESS (P0.08)?
- **Journal:**
  - Primary and fallback journals (P1.02).
  - PRISMA-ScR or JBI-only reporting (P1.04).
  - Publish the protocol as well (P3.01)?
- **Search and screening:** grey literature (P4.02); active-learning prioritization with the SAFE stopping rule (P4.06).
- **Charting:**
  - Critical appraisal (P7.04): default no, per JBI 10.2.8.
  - Stakeholder consultation (P7.06): optional under Arksey & O'Malley, required under Levac.
  - Ethics approval for that consultation (P7.07).
- **Presentation:** graphical abstract (P8.13); within journal limits (P13.05).
- **Submission and after:**
  - Search older than 12 months, which triggers an update (P15.01).
  - Preprint (P15.06).
  - Editorial outcome: accept, revise or reject (P16.02). Reject routes to the fallback journal loop P16.04.

**Loops (11), each with a guard, a bound and a progress measure.**
- **Search and screening:**
  - PRESS and seed-recall search refinement on the primary strategy before translation (P2.05).
  - Protocol review (P2.09).
  - Screener calibration to at least 75% agreement on 25 records (P5.02, JBI 10.2.7.1).
  - Citation chasing until a round adds nothing new (P6.08, TARCiS).
- **Charting and figures:** charting pilot on 3 sources per source type (P7.01, JBI 10.2.9.2); figure QA (P8.15).
- **Manuscript:**
  - Adversarial review rounds that re-verify grounding after every fold (P12.01). The mays/013 history shows that folds introduce regressions.
  - Compile until clean (P13.02).
  - Trim to limits (P13.06).
- **Journal:** revision rounds (P16.03); fallback resubmission (P16.04).

**Visualizations, all built by scripts from frozen data only.**
- **Figures:**
  - PRISMA 2020-style flow diagram (P8.07).
  - Sources by year and type (P8.08).
  - Evidence gap map (P8.09).
  - Geographic and venue distribution (P8.10).
  - Category distribution bars (P8.11; an alluvial was dropped as not worth a new dependency).
  - Optional concept figure or graphical abstract (P8.14).
- **Table:** a characteristics longtable (P8.12).
- **Rule:** every visual needs a supporting narrative (JBI 10.2.11).

**Who does the work.** 49 script nodes, 40 agent nodes, 27 AI+human nodes, 41 human nodes and 10 host-skill nodes. 112 nodes need new code (77 distinct `agsci sr` subcommands), 19 reuse existing code and 36 are human-only.

## 3. Build order (ATG of the build itself)

```
B1 promote plan/board.py → src/board (+ ledger, scheduler, state file, agent runner) [done] ── tests: mutation suite already passing (10/10)
B2 agent skills sr-* (12 SKILL.md files) ─────────────────────────────── contract: inputs, outputs, JSON schemas
B3 script modules, built lane by lane in critical-path order:
     search/dedup  → screening (sample, agreement/kappa, screen-ui) → fulltext (fetch, convert)
     → charting (chart-ui, freeze) → synthesis (describe, gap-map, figures, tables)
     → manuscript (assemble, audit-claims, bib, checks, typeset, limits, checklist, package)
   each module: one test on a labelled subsample of a REAL corpus (mays/013 PubMed records,
   mnemos 862-record corpus), never fabricated records
B4 Run Inspector board tab (port override: caius holds :8765)
B5 pilot: Aaron picks the topic (P0.01), board runs end to end
```

B1 has no dependencies. B2 and B3 run in parallel once B1 is done, B4 depends only on B1, and B5 needs all of them.

**Agent skills (B2).** There are 13, one per family of agent nodes:

| Skill | Nodes | Purpose |
|---|---|---|
| sr-prior-reviews | P0.02 | find existing reviews and protocols |
| sr-question | P0.04, P2.01 | PCC, questions, eligibility |
| sr-search-design | P2.02–P2.05c, P2.11 | terms, primary strategy, PRESS, translation |
| sr-journals | P1.01 | shortlist with requirement profiles |
| sr-protocol | P2.06–P2.08 | charting form, AI reviewer spec, protocol |
| sr-screen | P5.01, P5.02c, P5.03, P6.04, P6.08c | the AI second reviewer |
| sr-chart | P7.01a, P7.02, P7.05 | charting with quote and page per field |
| sr-synthesize | P8.02, P8.03, P8.06 | codebook, coding, synthesis and claims ledger |
| sr-draft | P9.01–P9.08 | sections from frozen evidence |
| sr-fold | P2.09b, P11.01, P12.01c, P16.03c | fold review findings, author decides |
| sr-proof | P14.03 | proofread change list |
| sr-submission | P15.03–P15.05, P16.03a, P16.03d | cover letter, reviewers, highlights, response matrix and letter |
| sr-latex | P13.01, P13.02b, P13.06a, P8.15b | typeset, fix compile faults, trim to limits, repair figures |

## 4. Definition of done: scoping review type (status 2026-10-16)

| # | Criterion | Status |
|---|---|---|
| 1 | Board validates, renders and passes its tests | **Done.** `agsci board check` exits 0 (167 nodes, 368 edges). Rendered to `plan/scoping_review.board.html`. 19 board tests cover graph mutations, the ledger, skip and stop propagation, loop bounds and agent dry runs. |
| 2 | Skills exist for every agent node, with input and output contracts | **Done.** 13 `sr-*` skills (plus `sr-latex`) and 3 reused upstream skills. The validator rejects any agent node without one. |
| 3 | Every script node is implemented and tested on real data | **Done for the code** (0 nodes left at `impl: new`). 45 scoping-review tests run on real data: records, decisions, charting, Crossref/OpenAlex responses, an open-access PDF, paper 31, and the JAIR profile. **Not yet run live:** the 49 agent nodes (they need the agent image, credentials and a topic), arXiv search (rate-limited with HTTP 429 on 2026-10-16), and docling conversion (the tests use the `pdftotext` path). |
| 4 | Pilot runs P0 to P15.09 on a chosen topic | **Blocked, need Aaron:** a topic for P0.01, then `docker build` of the agent image and a `.env` with credentials. |

How a review runs:

```
agsci board status src/scoping_review/board.yaml --root <project>        # ready cards
agsci board run    src/scoping_review/board.yaml P0.02 --root <project>  # agent card (Docker by default)
agsci sr <subcommand> ...                                                # script card, as written on the card
agsci board done   src/scoping_review/board.yaml P0.03 --root <project> --option continue
agsci board render src/scoping_review/board.yaml --root <project> -o board.html
```

What the real data exposed during the build (all fixed):
- Records with the same title but two different DOIs (preprint and published versions) are now logged as `version_pair` for the human dedup check.
- OpenAlex no longer resolves 1 of the 68 references of a 2026 paper. Citation chasing now reports such references instead of dropping them.
- The PRISMA balance check flags mismatched stages.
- The proof checks report real undefined acronyms and US/UK spelling mixes in paper 31, without LaTeX noise.

Fixed regressions:
- A nested package broke upstream's task-runtime copy (24 tests). It was flattened to `src/scoping_review`.
- `texcount` silently returned 0 words. It now raises.
- A "stop" decision did not halt downstream cards. Inputs are now explicitly `optional`.

## 5. Systematic review (`src/systematic_review/board.yaml`)

`agsci board check src/systematic_review/board.yaml` exits 0 and prints `nodes=180 edges=420 gates=16 decisions=19 loops=11 human=73 lanes=20 critical_path_len=89`.

The board reuses the scoping lanes for search, screening, writing, typesetting, proofing, submission and revision (P0–P6, P9–P17), with these changes:

| Change | Where | Source |
|---|---|---|
| PICO question; route a mapping question to the scoping board | P0.04, P0.05 | MECIR C1–C13; Munn 2018 |
| PRISMA 2020 (27 items, 42 rows with sub-items) or PRISMA-DTA | P1.04, P14.05 | Page et al. 2021 (checklist parsed from the official PDF) |
| Protocol to PRISMA-P 2015 (17 items); methods fixed in advance | P2.08 | MECIR C19–C23 |
| No NOT operator; controlled vocabulary present | P2.12 (`agsci sysrev search-lint`) | MECIR C32, C33 |
| PROSPERO before extraction when eligible, else OSF | P3.05, P3.02 → S7.02 depends on it | PROSPERO guidance (from Oct 2019) |
| Trial registers searched separately | P4.07 | MECIR C27 |
| **S7 Data extraction:** piloted form, AI and human extract independently, every disagreement reconciled against the report, authors contacted for missing data, effects cross-checked, retractions checked | S7.01–S7.10 | MECIR C40, C43, C46–C51 |
| **RB Risk of bias:** tool chosen by design (RoB 2 / ROBINS-I V2 draft / QUADAS-2 / QUIPS), in duplicate, consensus with a supporting quote per judgement, traffic-light figure | RB.01–RB.07 | MECIR C52–C59; riskofbias.info |
| **S9 Synthesis:** meta-analysis only when appropriate, otherwise SWiM. Pooling: REML random effects, HKSJ when τ² > 0 and k > 2, Peto or Mantel-Haenszel for sparse data. Analyses: forest plots, pre-specified subgroups (at least 10 studies) with a test for subgroup differences, sensitivity analyses, small-study tests only with at least 10 studies and not for OR/SMD | S9.01–S9.16 | MECIR C62–C73; Handbook v6.5 ch. 10, 13; SWiM |
| **GR Certainty:** GRADE per outcome with a reason for every move; Summary of Findings table with at most 7 outcomes | GR.01–GR.03 | MECIR C74–C75; Handbook ch. 14 |

**Statistics checked against R metafor 3.8.1 on the 13 BCG trials (Colditz et al. 1994).** The checks cover:
- **Effect sizes:** RR, OR and RD.
- **Pooling:** DerSimonian-Laird, REML, REML+HKSJ, fixed effect, Mantel-Haenszel RR/OR and Peto OR.
- **Heterogeneity:** I², Q, and the Q-profile τ² interval. Ours solves its equation exactly; metafor's stops at `uniroot` tolerance.
- **Small-study effects:** the Egger test.
- **Further analyses:** the subgroup-differences test and leave-one-out.

All agree with metafor to 1e-6 (relative 1e-6 where metafor's REML stopping tolerance dominates). Prediction intervals follow Cochrane v6.5 (t with k−1 df). `pi_dist="normal"` reproduces metafor's default for checking.

**New code:**
- **Modules:** `src/systematic_review/` with `meta.py`, `appraisal.py` (RoB rules, GRADE, SoF), `plots.py` (forest, funnel, traffic light) and `cli.py` (`agsci sysrev`, 16 subcommands).
- **Skills:** 4 new (`sysrev-extract`, `sysrev-rob`, `sysrev-synthesis`, `sysrev-grade`), plus new modes on `sr-question` (pico), `sr-protocol` (extraction-form, protocol-sr) and `sr-search-design` (registers).
- **Tests:** 28 (27 `tests/systematic_review/` + 1 board-routing test).

**Definition of done (systematic review):**
1. The board validates and renders. **Done.**
2. Every agent node has a skill. **Done.**
3. Every script node is implemented and tested on real data. **Done:** 0 nodes left at `impl: new`. The RoB 2 and ROBINS-I overall rules are checked over every possible combination of domain judgements, because no real per-domain dataset is on disk.
4. Pilot. **Blocked, need Aaron:** a topic, the agent image and credentials, as for the scoping review.

## Sources

The standards behind the gates:

- **JBI Manual for Evidence Synthesis, scoping chapter:** <https://jbi-global.atlassian.net/wiki/spaces/MANUAL/pages/355862497> (10.2.2 protocol, 10.2.6 search, 10.2.7 and 10.2.7.1 selection and pilot, 10.2.8 appraisal, 10.2.9 and 10.2.9.2 extraction, 10.2.10 analysis, 10.2.11 presentation, 10.4 updating).
- **Frameworks:**
  - Arksey & O'Malley 2005 (PMC4491356).
  - Levac et al. 2010 (PMC2954944).
  - Munn et al. 2018, BMC Med Res Methodol 18:143.
- **Search:**
  - PRESS 2015: McGowan et al., J Clin Epidemiol 75:40–6.
  - PRISMA-S: Rethlefsen et al. 2021.
  - TARCiS 2024 (citation searching).
- **Reporting:**
  - PRISMA-ScR: Tricco et al. 2018, Ann Intern Med 169:467.
  - Update in progress: Tricco et al. 2026, J Clin Epidemiol 196:112314.
- **AI and automation:**
  - Joint AI statement: Flemyng et al. 2025, JBI Evid Synth 23(11):2162–6 (PMC12594113), plus RAISE.
  - SAFE stopping: Boetje & van de Schoot 2024, Syst Rev 13:81 (PMC10908130).
- **Search currency:** Cochrane MECIR C37.

Venue rules for BMJ Open, JBI Evidence Synthesis, Systematic Reviews and ACM Computing Surveys could not be fetched (publisher pages blocked automated access). P1.03 records each journal profile from the live author guidelines when a journal is chosen.
