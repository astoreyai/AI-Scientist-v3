# Can AI-Scientist-v3 run a dissertation from a task board?

2026-10-15 · fork `astoreyai/AI-Scientist-v3` @ `2b8aa39` (upstream SakanaAI, Apache-2.0)

## Verdict

**Partly. It can serve as the execution engine for the empirical contribution chapters, inside a
board that a human drives. It cannot carry a dissertation from start to finish, and should not be
built to.**

- **Technical limit.** The engine optimizes a program against a sealed scalar evaluator and writes
  one 8–9 page paper per run.
- **Process limit.** Every degree gate is a human act (committee votes, oral defenses, signatures,
  the AI-use disclosure).
- **Policy limit.** Clarkson publishes no generative-AI policy for theses. Under the policies that
  do exist (UGA, Alabama, FIU), the committee decides what AI use is allowed. So the first card on
  the board is a conversation with the advisor, not code.

The realistic build is a board file plus a thin `agsci board` runner (about 300–500 lines,
estimated). The runner dispatches ready cards to one of three executors: agsci runs, existing
Claude skills, or a human. A card that needs a human blocks until a person clears it.

Evidence tags: **[C]** means confirmed in this repo (file path given) or in a cited source.
**[I]** means inferred, with what would confirm it.

## 1. What a normal CS dissertation looks like

Source: research pass of 2026-10-15. Clarkson CS requirements are at
<https://clarkson.edu/node/10419>.

| Stage | Clarkson CS (sourced) | Evidence/gate | Who clears it |
|---|---|---|---|
| Coursework | 90 credits, at least 36 coursework; 4 foundation courses at B+; 6 semesters of CS707/708 [C] | transcript | registrar |
| Qualifying / candidacy | within 2 years; portfolio + oral before the CS PhD Committee; an advisor must agree to supervise [C] | form, signatures | dept committee |
| Committee | **5 members**, at least 3 from CS, at least 1 from outside the dept, at least 4 Clarkson faculty [C] | roster | dept |
| Proposal + defense | research plan + related work, defended orally; **by the end of year 3** [C] | document, oral | thesis committee |
| IRB | only for human-subjects research [I: 45 CFR 46, not fetched] | approval letter | IRB |
| Research + papers | no publication count is required [C] | papers | advisor |
| Writing | monograph: intro → background → **3–4 contribution chapters** → discussion → conclusion; roughly 100–200 pp [C: one handbook; no CS median found]. The three-paper option exists elsewhere (only 29% of CS at Missouri S&T); Clarkson does not mention it [C] | draft | advisor |
| Final defense | thesis to every member **at least 4 weeks** ahead; 50-min public talk + at least 10 min public Q&A + closed vote; same committee as the proposal [C] | oral, vote | committee |
| Deposit | dean approves; a copy goes to the library [C]. ProQuest: PDF with fonts embedded [C] | final PDF | grad dean |
| Side artifacts | similarity report (iThenticate, required at some schools), reuse permissions for your own IEEE/ACM papers, AI-use disclosure [C, not Clarkson-specific] | appendices | student |

Median US CS time to degree: 5.7 years (NSF SED 2023) [C]. Time limit: 7 years from candidacy at
Clarkson [C].

Caveat: the Clarkson page may not be the current catalog year. Confirm the 5-member rule and the
year-3 proposal deadline with the CS graduate coordinator.

## 2. What AI-Scientist-v3 actually is

- **Unit of work: one run produces one paper.** The fixed phase chain is task_drafting →
  investigation → ablations → final_evaluation → posthoc → paper, with optional review and
  revision [C: `src/pipeline/config.py:55-60`, `docs/pipeline.md`].
- **Input contract.** A `task.md` plus an evaluator that returns `correct` and a finite score.
  Programs are ranked by descending score [C: `examples/circpack/`, `docs/no_winner_studies.md`].
  Drafting a task from a bare brief "is not yet robust" beyond toy tasks [C: README §8].
- **Output.** ICLR or ALife papers of 8–9 body pages, with 25–30 references in the pipeline
  default [C: `configs/venue/*.yaml`, `configs/pipeline_config.yaml`].
- **Strengths worth keeping:**
  - A sealed final evaluation.
  - An evidence audit that binds every manuscript claim to run artifacts [C:
    `src/orchestrator/paper_evidence_audit.py`, 2026 lines].
  - Resume from a run directory.
  - Phase-level degraded/failed status.
  - Review-driven revision.
  - Run Inspector UI.
- **No cross-run or long-horizon state, and no board concept.** grep found nothing for
  kanban/board/issue [C].
- **Agents run with full permissions (`--allow yolo`) inside Docker** [C: README security note].

## 3. Gap matrix

| Dimension | AI-Scientist-v3 | Dissertation needs | Severity | Adaptation |
|---|---|---|---|---|
| Kind of contribution | program optimization with a scalar score | also theory, systems, studies, qualitative work, reviews | **high** | route only scorable empirical questions to agsci; send other cards to other executors |
| Unit / horizon | one paper, hours | 3–4 linked contributions over years | **high** | the board is the long-horizon state; each contribution card owns one or more `run_dir`s |
| Gates | automated (qualification, evidence audit) | human (advisor, committee, orals, dean, IRB) | **blocking** | `human` cards that only a person can mark done; the runner never clears them |
| AI-use permission | n/a | committee authorization + disclosure [C: UGA/UA/FIU] | **blocking** | card 0: get advisor/committee written scope of AI use; log every run as disclosure evidence |
| Literature | Semantic Scholar, 25–30 refs/paper | systematic background chapter, 100+ refs [I] | medium | existing `/systematic-review` skill as executor |
| Document | 8–9 pp venue templates | thesis template, chapter assembly, front matter | medium | add a `thesis` venue + an assembler that rewrites run papers into chapters with shared notation |
| Review | OpenAI reviewer; sends the full manuscript to the cloud [C] | committee review; some schools bar unpublished work in cloud AI [C: Dartmouth] | medium | keep review opt-in; use `/committee-review` and `/matthews` locally; Matthews' real concurrence is the only gate |
| Compute | calls `nvidia-smi` directly; GRPO preset wants 2 GPUs [C] | archimedes has one shared 3090 behind `gpu-run` | medium | wrap launches in `gpu-run`; CPU or 1-GPU presets only |
| Ops | Inspector on :8765 [C] | caius already holds :8765 | low | `agsci inspect start --backend-port 8766` |
| Cost | each run is many agent sessions | tens of runs [I] | medium | budget field per card; the runner refuses past budget |

## 4. Board-driven design (recommended)

**Board = `dissertation/board.yaml` in this repo.** It is the source of truth, versioned with git
and readable by agents and humans.

Example cards:

```yaml
- id: C2.exp1
  lane: contribution-2          # framing | proposal | contribution-N | writing | defense | deposit
  title: "<research question as a measurable claim>"
  executor: agsci               # agsci | skill:<name> | human
  task_dir: dissertation/tasks/c2_exp1   # agsci only: task.md + evaluator
  depends_on: [P.approved]
  gate: advisor                 # who must accept the output
  status: ready                 # backlog | ready | running | review | done | blocked
  runs: []                      # run_dir paths appended by the runner
  budget_usd: 150
- id: P.approved
  executor: human
  title: "Proposal defense passed (committee vote)"
  depends_on: [P.doc, AI.scope]
```

**Runner** (`agsci board next|run|status`):

1. Load the board and pick cards whose dependencies are `done`.
2. For `agsci` cards, call the existing `agsci run` with that card's `task_dir`, append the
   `run_dir`, and move the card to `review`.
3. For `skill:` cards, print the exact command for a Claude session.
4. Never touch `human` cards.

The evidence-audit and run manifests feed the card's review packet.

**Alternatives considered:**

- **GitHub Projects.** Nicer UI, but your `gh` is too old for `gh project`, and the token lacks the
  `project` scope [C]. It also adds a network dependency and is outward-facing. It could be added
  later as a one-way mirror.
- **Obsidian Kanban.** The wiki-worker pattern exists, but markdown card parsing is fragile for
  dependency edges.
- **aira2's DependencyGraph and gates.** Conceptually close, but `01_agent_platforms/aira2` has no
  git repo [C]. Porting it would cost more than the 300-line runner.

**Lane template (one dissertation):**

- **framing:** AI-use scope agreed with the advisor; research questions; committee roster complete
  (5 seats).
- **proposal:** systematic background review; proposal document; mock committee review; the human
  proposal defense.
- **contribution-1..3:** experiment design (`/experiment-design`, with preregistration); agsci runs;
  advisor review; paper submission (human).
- **writing:**
  - Assemble the chapters.
  - Write the intro, discussion and conclusion (human-led).
  - Run the reference and similarity checks.
  - Collect reuse permissions.
  - Write the AI-use disclosure.
- **defense:** send the thesis 4 weeks before the defense (human); slides (`/ted-academic-slide-architect`);
  the defense itself (human).
- **deposit:** corrections; dean approval (human); ProQuest PDF check.

Of about 25 template cards, about 8 are human-only, about 9 are skill-assisted, and about 6–8 are
agsci runs [I: depends on how many contributions are scorable].

## 5. Risks

1. **Integrity and permission (top risk).** "Run a dissertation start to finish" with an
   autonomous agent conflicts with every published thesis AI policy found. The design is defensible
   only as co-discovery, where you own the thesis claim, the agent's role is disclosed and scoped by
   the committee, and the board's run log is the disclosure record. That fits a transparency-focused
   advisor [I: confirm with Matthews].
2. **Scorability.** Questions that do not fit a scalar evaluator get a weak evaluator, which
   produces confident nonsense. Upstream's own task-drafting docs warn about this [C].
3. **Topic.** No dissertation topic is committed (canon, 2026-07-22). The board must stay
   topic-agnostic until the proposal retake defines one.

## 6. Next steps (none started)

1. Ask Matthews what scope of AI use is acceptable.
2. Build `board.yaml` + `agsci board` (one test against a subsample of a real task such as
   `examples/circpack`).
3. Add the `thesis` venue and chapter assembler.
4. Add the `gpu-run` wrapper.
5. Add the Inspector port override.
