# 001: A board layer and research-type templates above the fixed pipeline

**Date:** 2026-10-15 · **Status:** accepted

## Context
Upstream AI-Scientist-v3 has one research type. A run takes a `task.md` and a sealed scalar
evaluator through a hard-coded phase tuple (`PIPELINE_PHASES`, `src/pipeline/config.py:60`) and
produces one 8–9 page paper. A scoping review has none of that shape:

- it has no evaluator;
- it has 16 human decisions and 14 gates;
- its loops have unknown iteration counts;
- it runs over months.

Aaron wants each research type driven by a kanban-renderable task graph, starting with the
scoping review and then the systematic review.

## Options
1. **Extend `PIPELINE_PHASES`** with review phases. This reuses the CLI but forces a linear chain,
   with no human cards, decisions or loops.
2. **GitHub Projects as the board.** It has a real UI, but the installed `gh` lacks `gh project`
   and the token lacks the `project` scope. It is also network-bound and outward-facing.
3. **Obsidian Kanban or aira2's DependencyGraph.** Patterns for both exist locally, but Kanban
   markdown is fragile for dependency edges, and `01_agent_platforms/aira2` has no git history.
4. **A `board.yaml` per research type, validated and rendered by a small local engine.** Edges are
   derived from artifacts each node consumes and produces.

## Decision
Option 4 (2026-10-15). Its parts:

- **Edges:** never hand-written. A node depends on whoever produces its `in` artifacts.
- **Node kinds:** task, decision, gate, loop (guard, bound and progress), milestone.
- **Executors:** script, agent, skill, human, ai+human.
- **AI-use ledger:** every agent and ai+human node writes one ledger line per action.
- **Screening:** a human screens all records, an AI is the independent second reviewer, and a
  human adjudicates every conflict (Phase-0 answer Q2).

## Why
Derived edges make every dependency a real data handoff, which the validator can check. Loop
nodes keep the top-level graph a DAG, so readiness is a lookup and failures stay local. We give up
a hosted UI and multi-user sync, and accept building our own renderer of about 300 lines. A
one-way GitHub Projects mirror can be added later without changing the source of truth.

## Consequences
- **Easy:**
  - Adding a research type means writing a YAML template plus skills.
  - The existing pipeline becomes one more type.
  - The board diff in git is the audit trail.
  - The ledger generates the AI-use disclosure.
- **Hard:**
  - Concurrent human edits to `board.yaml` and the state file need git discipline.
  - Conditional inputs (outputs of skipped nodes) are resolved at runtime, not by the validator.
  - The kanban view is static until the Run Inspector gets a board tab (its default port :8765
    collides with caius).
