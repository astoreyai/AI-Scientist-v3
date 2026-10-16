"""Execution ledger for a board: node state comes from recorded events, never from guesses.

`<root>/board_state.jsonl` is append-only. Each line is one event:
  start | done | fail | iterate    (+ option for decisions, approver for gates, outputs -> sha256)
A node is ready when every producer of a required input is done, every producer of an `optional`
input is done or skipped, and its `when` condition holds. It is skipped automatically when its
`when` condition is false, or when the producer of any required input was skipped (so a "stop"
decision halts everything after it).
Loop bodies are reset by an `iterate` event on the loop, bounded by the loop's `bound`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import yaml

from .graph import WHEN

LEDGER = "review/board_state.jsonl"  # relative to the project root that holds review/ and manuscript/


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_events(root: Path) -> list[dict]:
    p = root / LEDGER
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []


def _append(root: Path, event: dict) -> dict:
    (root / LEDGER).parent.mkdir(parents=True, exist_ok=True)
    event = {"utc": _now(), **event}
    with (root / LEDGER).open("a") as f:
        f.write(json.dumps(event) + "\n")
    return event


def iteration(events: list[dict], loop_id: str) -> int:
    return 1 + sum(1 for e in events if e["node"] == loop_id and e["event"] == "iterate")


def _effective(events: list[dict], graph: dict) -> dict[str, dict]:
    """Last event per node, ignoring body-node events from earlier loop iterations."""
    nodes = graph["nodes"]
    last, iters = {}, {}
    for e in events:
        if e["event"] == "iterate":
            iters[e["node"]] = iters.get(e["node"], 1) + 1
            for b in nodes[e["node"]].get("body", []):
                last.pop(b, None)
            last[e["node"]] = {"node": e["node"], "event": "start"}  # an iterating loop stays in progress
            continue
        last[e["node"]] = e
    return last


def options(events: list[dict], graph: dict) -> dict[str, str]:
    return {nid: e["option"] for nid, e in _effective(events, graph).items() if e["event"] == "done" and "option" in e}


def statuses(graph: dict, events: list[dict]) -> dict[str, str]:
    """backlog | ready | doing | done | skipped | failed for every node."""
    nodes = graph["nodes"]
    last = _effective(events, graph)
    chosen = options(events, graph)
    out: dict[str, str] = {}

    def resolve(nid: str) -> str:
        if nid in out:
            return out[nid]
        e = last.get(nid)
        if e:
            out[nid] = {"done": "done", "start": "doing", "fail": "failed"}[e["event"]]
            return out[nid]
        n = nodes[nid]
        parent = n.get("parent")
        if parent and resolve(parent) != "doing":
            out[nid] = "skipped" if out[parent] == "skipped" else "backlog"  # a body runs only inside a started loop
            return out[nid]
        if "when" in n:
            dec, opt = WHEN.match(n["when"]).groups()
            if resolve(dec) == "skipped" or (dec in chosen and chosen[dec] != opt):
                out[nid] = "skipped"
                return out[nid]
            if dec not in chosen:
                out[nid] = "backlog"
                return out[nid]
        inside = set(n.get("body", []))
        optional = set(n.get("optional", []))
        required = {graph["producer"][a] for a in n.get("in", []) if a in graph["producer"] and a not in optional}
        maybe = {graph["producer"][a] for a in optional if a in graph["producer"]} - required
        required -= inside | {parent}
        if any(resolve(p) == "skipped" for p in required):
            out[nid] = "skipped"  # a required input will never exist (e.g. after a "stop" decision)
        elif all(resolve(p) == "done" for p in required) and all(resolve(p) in ("done", "skipped") for p in maybe):
            out[nid] = "ready"
        else:
            out[nid] = "backlog"
        return out[nid]

    for nid in nodes:
        resolve(nid)
    return out


def artifact_path(root: Path, board: dict, artifact: str, it: int) -> Path | None:
    """Filesystem location of an artifact; None for entries inside a shared file ("file#key")."""
    p = board["meta"]["paths"][artifact]
    return None if "#" in p else root / p.replace("{iter}", str(it))


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(path.rglob("*")) if path.is_dir() else [path]:
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()


def mark(root: Path, board: dict, graph: dict, nid: str, event: str, *, option: str | None = None,
         approver: str | None = None, note: str = "") -> dict:
    """Record start/done/fail for a node after checking the node is in a state that allows it."""
    events = read_events(root)
    st = statuses(graph, events)
    n = graph["nodes"][nid]
    allowed = ("ready", "doing", "failed") if event == "start" else ("ready", "doing")  # start on failed = retry
    if event in ("start", "done") and st[nid] not in allowed:
        raise ValueError(f"{nid} is {st[nid]}, not ready")
    rec = {"node": nid, "event": event}
    if note:
        rec["note"] = note
    if event == "done":
        if n["kind"] == "decision":
            if option not in [str(o) for o in n["options"]]:
                raise ValueError(f"{nid} needs --option one of {n['options']}")
            rec["option"] = option
            _record_decision(root, nid, option, note)
        if n["kind"] == "gate":
            if not approver:
                raise ValueError(f"{nid} is a gate: --approver is required ({n['approver']})")
            rec["approver"] = approver
        it = iteration(events, n["parent"]) if n.get("parent") else 1
        outputs = {}
        for a in n["out"]:
            path = artifact_path(root, board, a, it)
            if path is None:
                continue
            if not path.exists():
                raise ValueError(f"{nid}: output '{a}' missing at {path}")
            outputs[a] = _hash(path)
        rec["outputs"] = outputs
        if n.get("parent"):
            rec["iter"] = it
    return _append(root, rec)


def iterate(root: Path, graph: dict, loop_id: str, note: str) -> dict:
    n = graph["nodes"][loop_id]
    events = read_events(root)
    it = iteration(events, loop_id)
    if it >= n["bound"]:
        raise ValueError(f"{loop_id}: bound {n['bound']} reached; raise it deliberately or report the partial result")
    if not note:
        raise ValueError("iterate needs --note with the guard result and progress measure")
    return _append(root, {"node": loop_id, "event": "iterate", "from_iter": it, "note": note})


def _record_decision(root: Path, nid: str, option: str, note: str) -> None:
    p = root / "review" / "decisions.yaml"
    data = yaml.safe_load(p.read_text()) if p.exists() else {}
    data = data or {}
    data[nid] = {"option": option, "note": note, "utc": _now()}
    p.write_text(yaml.safe_dump(data, sort_keys=True))
