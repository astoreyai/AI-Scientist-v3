"""Run one agent node of a board (`agsci board run`).

The prompt is the node's skill (src/agents/skills/<skill>/SKILL.md) plus the node card: its mode,
the resolved input and output paths, and the rules every agent node shares. The agent runs through
the repo's pinned Headless CLI (`build_agent_command`), inside the agent image by default because
agents run with full tool permissions (README security note). Each run appends one
`ai_ledger_entry` line to `review/ai_ledger.jsonl`, which feeds the AI-use disclosure.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
from pathlib import Path

from . import state
from .graph import SKILLS_DIR

REPO = Path(__file__).parents[2]
IMAGE = "agentic-scientist/agent-cli:latest"
WORK, REPO_MOUNT = "/work", "/repo"


def _sha(p: Path) -> str:
    return state._hash(p) if p.exists() else "missing"


def io_paths(root: Path, board: dict, graph: dict, nid: str, it: int) -> tuple[dict, dict]:
    n = graph["nodes"][nid]
    src = {a: board["meta"]["paths"][a] for a in n.get("in", [])}
    dst = {a: board["meta"]["paths"][a] for a in n["out"]}
    fix = lambda p: p.replace("{iter}", str(it))  # noqa: E731
    return {a: fix(p) for a, p in src.items()}, {a: fix(p) for a, p in dst.items()}


RETROFIT = "review/retrofit.md"  # optional: earlier work on this review that agents should reuse


def build_prompt(board: dict, graph: dict, nid: str, inputs: dict, outputs: dict, it: int,
                 repo: str = REPO_MOUNT, retrofit: bool = False) -> str:
    n = graph["nodes"][nid]
    skill = (SKILLS_DIR / n["skill"] / "SKILL.md").read_text()
    lines = [
        f"# Board node {nid}: {n['title']}",
        f"Research type: {board['meta']['research_type']}. Skill: {n['skill']}. Mode: `{n['mode']}`."
        + (f" Loop iteration: {it}." if n.get("parent") else ""),
        "",
        "Your working directory is the review project root. Paths below are relative to it.",
        f"Repository files (skills, schemas, scripts) are read-only under `{repo}/`; a path that",
        f"starts with `src/` in the skill means `{repo}/src/`.",
        "",
        "## Inputs (read these; do not modify them)",
        *[f"- `{a}`: `{p}`" for a, p in inputs.items()],
        "",
        *(["## Earlier work on this review",
            f"`{RETROFIT}` lists artifacts from an earlier run of this review. Read the ones relevant to this",
            "node and reuse what holds; say in your output what you kept, changed or dropped, and why.", ""]
          if retrofit else []),
        "## Outputs (write exactly these)",
        *[f"- `{a}`: `{p}`" for a, p in outputs.items()],
        "",
        "## Rules for every board node",
        "- Use only the inputs above and sources you actually open. Never invent records, numbers, quotes or citations.",
        "- Write only the outputs above. Do not edit `review/board_state.jsonl`, `review/ai_ledger.jsonl` or `review/decisions.yaml`.",
        "- Any time you record must be the real clock time (`date -u +%FT%TZ`), never a made-up one.",
        "- If an input is missing or the task cannot be done honestly, write nothing and explain why in your final message.",
        "",
        "---",
        "",
        skill,
    ]
    return "\n".join(lines) + "\n"


def command(prompt_file: str, agent: str, model: str | None, native: bool, root: Path, env_file: Path | None) -> list[str]:
    from src.investigation.script_runners import build_agent_command

    inner = build_agent_command(agent, prompt_file, agent_model=model)
    if native:
        return inner
    # The image ships the pinned Headless binary; drop the npx bootstrap the host form uses.
    i = inner.index("npx")
    inner = inner[:i] + ["/usr/local/bin/headless"] + inner[i + 3:]
    cmd = ["docker", "run", "--rm", "--network", "host", "--user", f"{os.getuid()}:{os.getgid()}",
           "-v", f"{root.resolve()}:{WORK}", "-v", f"{REPO}:{REPO_MOUNT}:ro", "-w", WORK]
    if env_file:
        cmd += ["--env-file", str(env_file)]
    return cmd + [IMAGE] + inner


def run(board: dict, graph: dict, root: Path, nid: str, *, agent: str, model: str | None,
        native: bool = False, dry_run: bool = False, env_file: Path | None = None) -> dict:
    n = graph["nodes"][nid]
    if n["exec"] not in ("agent", "ai+human") or "skill" not in n:
        raise ValueError(f"{nid} is a {n['exec']} node: run it as written on its card: {n['run']}")
    events = state.read_events(root)
    st = state.statuses(graph, events)[nid]
    if st not in ("ready", "doing"):
        raise ValueError(f"{nid} is {st}, not ready")
    it = state.iteration(events, n["parent"]) if n.get("parent") else 1
    inputs, outputs = io_paths(root, board, graph, nid, it)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = root / "review" / "agent_runs" / f"{nid}_{it}_{stamp}"
    run_dir, k = base, 1
    while run_dir.exists():  # two runs of one node in the same second
        run_dir, k = base.with_name(f"{base.name}_{k}"), k + 1
    run_dir.mkdir(parents=True)
    prompt = build_prompt(board, graph, nid, inputs, outputs, it, repo=str(REPO) if native else REPO_MOUNT,
                          retrofit=(root / RETROFIT).exists())
    (run_dir / "prompt.md").write_text(prompt)
    prompt_ref = str((run_dir / "prompt.md").resolve()) if native else f"{WORK}/{(run_dir / 'prompt.md').relative_to(root)}"
    cmd = command(prompt_ref, agent, model, native, root, env_file)
    (run_dir / "command.json").write_text(json.dumps(cmd))
    if dry_run:
        return {"node": nid, "prompt": str(run_dir / "prompt.md"), "command": cmd, "dry_run": True}

    in_hashes = {p: _sha(root / p.split("#")[0]) for p in inputs.values()}
    if st == "ready":
        state.mark(root, board, graph, nid, "start")
    with (run_dir / "agent.log").open("w") as log:
        rc = subprocess.run(cmd, cwd=root, stdout=log, stderr=subprocess.STDOUT).returncode
    entry = {"node": nid, "tool": f"headless:{agent}", "model": model or f"{agent} default", "utc": stamp,
             "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(), "inputs": in_hashes,
             "outputs": {p: _sha(root / p.split("#")[0]) for p in outputs.values()}, "human_reviewer": None,
             "exit_code": rc, "run_dir": str(run_dir.relative_to(root))}
    with (root / "review" / "ai_ledger.jsonl").open("a") as f:
        f.write(json.dumps(entry) + "\n")
    if rc != 0:
        state.mark(root, board, graph, nid, "fail", note=f"agent exit {rc}; log {run_dir / 'agent.log'}")
    elif n["exec"] == "agent":
        state.mark(root, board, graph, nid, "done", note=f"agent run {run_dir.name}")
    # ai+human nodes stay in progress: a person reviews the draft and marks the node done.
    return {"node": nid, "exit_code": rc, "run_dir": str(run_dir)}
