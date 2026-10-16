"""Validate an atomic task graph (board YAML) and render it as a kanban HTML page.

Edges are never written by hand: a node depends on whichever node produces an artifact it
consumes (`in`), so every edge is a real data dependency.

    agsci board check  src/scoping_review/board.yaml
    agsci board render src/scoping_review/board.yaml -o board.html [--root <project>]
    agsci board status|start|done|fail|iterate ... --root <project>   (see src/board/state.py)
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import yaml

KINDS = {"task", "decision", "gate", "loop", "milestone"}
EXECS = {"script", "agent", "skill", "human", "ai+human"}
IMPLS = {"exists", "new", "human"}
STATUSES = ["backlog", "ready", "doing", "done", "skipped", "failed"]
WHEN = re.compile(r"^(\S+) == (\S+)$")
SKILLS_DIR = Path(__file__).parents[1] / "agents" / "skills"


def load(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text())


def analyze(board: dict) -> tuple[list[str], dict]:
    """Return (errors, graph) where graph holds nodes, edges, producer map and stats."""
    errs: list[str] = []
    lanes = [lane["id"] for lane in board["lanes"]]
    givens = set(board["meta"].get("givens", []))
    nodes: dict[str, dict] = {}
    for n in board["nodes"]:
        if n["id"] in nodes:
            errs.append(f"{n['id']}: duplicate id")
        nodes[n["id"]] = n

    producer: dict[str, str] = {}
    for n in nodes.values():
        for a in n.get("out", []):
            if a in producer or a in givens:
                errs.append(f"{n['id']}: artifact '{a}' already produced by {producer.get(a, 'givens')}")
            producer[a] = n["id"]

    for nid, n in nodes.items():
        for key in ("lane", "kind", "title", "exec", "impl", "run"):
            if key not in n:
                errs.append(f"{nid}: missing '{key}'")
        if n.get("lane") not in lanes:
            errs.append(f"{nid}: unknown lane {n.get('lane')}")
        if n.get("kind") not in KINDS:
            errs.append(f"{nid}: bad kind {n.get('kind')}")
        if n.get("exec") not in EXECS:
            errs.append(f"{nid}: bad exec {n.get('exec')}")
        if n.get("impl") not in IMPLS:
            errs.append(f"{nid}: bad impl {n.get('impl')}")
        if not n.get("out"):
            errs.append(f"{nid}: produces nothing (every node needs an output artifact)")
        for a in n.get("optional", []):
            if a not in n.get("in", []):
                errs.append(f"{nid}: optional input '{a}' is not listed in `in`")
        for a in n.get("in", []):
            if a not in producer and a not in givens:
                errs.append(f"{nid}: input '{a}' is produced by no node and is not a given")
        kind = n.get("kind")
        if n.get("exec") == "agent":
            skill = SKILLS_DIR / str(n.get("skill")) / "SKILL.md"
            if not (n.get("skill") and n.get("mode") and skill.exists()):
                errs.append(f"{nid}: agent node needs `skill` (with SKILL.md under {SKILLS_DIR}) and `mode`")
        if kind == "decision" and (len(n.get("options", [])) < 2 or not n.get("criterion")):
            errs.append(f"{nid}: decision needs >=2 options and a criterion")
        if kind == "gate" and not (n.get("criterion") and n.get("approver")):
            errs.append(f"{nid}: gate needs criterion and approver")
        if kind == "loop":
            if not (n.get("guard") and n.get("progress") and isinstance(n.get("bound"), int) and n["bound"] > 0):
                errs.append(f"{nid}: loop needs guard, progress and a positive int bound")
            for b in n.get("body", []):
                if b not in nodes:
                    errs.append(f"{nid}: body node {b} does not exist")
                elif nodes[b].get("parent") != nid:
                    errs.append(f"{nid}: body node {b} must declare parent: {nid}")
            if not n.get("body"):
                errs.append(f"{nid}: loop has no body")
        if "parent" in n and nid not in nodes.get(n["parent"], {}).get("body", []):
            errs.append(f"{nid}: parent {n['parent']} does not list it in body")

    # Body outputs stay inside their loop; the loop node's own `out` is the external interface.
    for nid, n in nodes.items():
        for a in n.get("in", []):
            src = producer.get(a)
            if src and nodes[src].get("parent") and nodes[src]["parent"] != n.get("parent"):
                errs.append(f"{nid}: consumes '{a}' from inside loop {nodes[src]['parent']}")

    paths = board["meta"].get("paths")
    if paths is not None:
        for a in sorted(set(producer) - set(paths)):
            errs.append(f"artifact '{a}' has no entry in meta.paths")
        for a in sorted(set(paths) - set(producer)):
            errs.append(f"meta.paths lists '{a}', which no node produces")

    edges = sorted({(producer[a], nid) for nid, n in nodes.items() for a in n.get("in", []) if a in producer})
    preds: dict[str, set[str]] = defaultdict(set)
    succs: dict[str, set[str]] = defaultdict(set)
    for s, d in edges:
        preds[d].add(s)
        succs[s].add(d)

    # Kahn topological sort over every node; a leftover node means a cycle.
    indeg = {nid: len(preds[nid]) for nid in nodes}
    level = {nid: 0 for nid in nodes}
    queue = [nid for nid, d in indeg.items() if d == 0]
    order = []
    while queue:
        nid = queue.pop()
        order.append(nid)
        for d in succs[nid]:
            level[d] = max(level[d], level[nid] + 1)
            indeg[d] -= 1
            if indeg[d] == 0:
                queue.append(d)
    if len(order) != len(nodes):
        errs.append(f"cycle among: {sorted(set(nodes) - set(order))}")

    ancestors: dict[str, set[str]] = {}
    for nid in order:
        ancestors[nid] = set().union(*[ancestors[p] | {p} for p in preds[nid]]) if preds[nid] else set()
    for nid, n in nodes.items():
        if "when" not in n:
            continue
        m = WHEN.match(n["when"])
        if not m or m.group(1) not in nodes or nodes[m.group(1)].get("kind") != "decision":
            errs.append(f"{nid}: when '{n['when']}' must be '<decision id> == <option>'")
        elif m.group(2) not in nodes[m.group(1)]["options"]:
            errs.append(f"{nid}: option '{m.group(2)}' not in {m.group(1)} options")
        elif nid in ancestors and m.group(1) not in ancestors[nid]:
            errs.append(f"{nid}: decision {m.group(1)} is not upstream of it")

    top = [nid for nid in nodes if "parent" not in nodes[nid]]
    by_level: dict[int, list[str]] = defaultdict(list)
    for nid in top:
        by_level[level[nid]].append(nid)
    stats = {
        "nodes": len(nodes),
        "edges": len(edges),
        "gates": sum(n["kind"] == "gate" for n in nodes.values()),
        "decisions": sum(n["kind"] == "decision" for n in nodes.values()),
        "loops": sum(n["kind"] == "loop" for n in nodes.values()),
        "human": sum(n["exec"] in ("human", "ai+human") for n in nodes.values()),
        "lanes": len(lanes),
        "critical_path_len": (max(level.values()) + 1) if nodes else 0,
        "widest_parallel_group": max((len(v) for v in by_level.values()), default=0),
    }
    graph = {"nodes": nodes, "edges": edges, "preds": preds, "producer": producer, "stats": stats, "givens": givens}
    return errs, graph


def statuses(graph: dict, state: dict) -> dict[str, str]:
    """Explicit state wins; otherwise a node is ready when every predecessor is done."""
    out = {}
    for nid in graph["nodes"]:
        if nid in state:
            out[nid] = state[nid]
        else:
            done = all(state.get(p) == "done" for p in graph["preds"][nid])
            out[nid] = "ready" if done else "backlog"
    return out


CSS = """
:root{--bg:#f7f7f5;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#deddd8;--lane:#efeee9;
--task:#3b6ea5;--decision:#b26b00;--gate:#a8322d;--loop:#6a4c9c;--milestone:#2f7d4f}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161615;--fg:#ecebe6;--muted:#a3a29c;
--card:#21211f;--line:#3a3a37;--lane:#1c1c1a;--task:#7aa7d9;--decision:#e3a446;--gate:#e0706a;--loop:#a98fd6;--milestone:#6cc191}}
:root[data-theme=dark]{--bg:#161615;--fg:#ecebe6;--muted:#a3a29c;--card:#21211f;--line:#3a3a37;--lane:#1c1c1a;
--task:#7aa7d9;--decision:#e3a446;--gate:#e0706a;--loop:#a98fd6;--milestone:#6cc191}
*{box-sizing:border-box}body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.4 system-ui,sans-serif}
h1{font-size:20px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 16px}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}.stat{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px 10px}
.stat b{font-size:16px;margin-right:4px}
.legend{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:16px;color:var(--muted)}
.lane{background:var(--lane);border:1px solid var(--line);border-radius:8px;margin-bottom:12px;padding:8px}
.lane h2{font-size:15px;margin:2px 4px 8px}.lane h2 span{color:var(--muted);font-weight:400}
.cols{display:grid;grid-template-columns:repeat(6,minmax(200px,1fr));gap:8px;overflow-x:auto}
.col h3{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:0 0 6px}
.card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--task);border-radius:6px;padding:6px 8px;margin-bottom:6px}
.card.decision{border-left-color:var(--decision)}.card.gate{border-left-color:var(--gate)}.card.loop{border-left-color:var(--loop)}.card.milestone{border-left-color:var(--milestone)}
.id{font:600 11px ui-monospace,monospace;color:var(--muted)}.t{font-weight:600;margin:2px 0}
.badge{display:inline-block;font-size:10px;border:1px solid var(--line);border-radius:10px;padding:0 6px;margin:2px 2px 0 0;color:var(--muted)}
.k{font-size:12px;color:var(--muted);margin-top:3px}.k code{font-size:11px;word-break:break-all}
details{margin-top:4px}summary{cursor:pointer;font-size:12px;color:var(--muted)}
.body{border-top:1px dashed var(--line);margin-top:4px;padding-top:4px}
.sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:middle}
"""


def card(nid: str, graph: dict) -> str:
    n = graph["nodes"][nid]
    e = html.escape
    deps = sorted(graph["preds"][nid])
    lines = [f'<div class="card {e(n["kind"])}"><div class="id">{e(nid)}</div><div class="t">{e(n["title"])}</div>']
    badges = [n["kind"], n["exec"]] + ([n["impl"]] if n["impl"] != n["exec"] else [])
    lines.append("".join(f'<span class="badge">{e(b)}</span>' for b in badges))
    if n.get("when"):
        lines.append(f'<div class="k">only if <b>{e(n["when"])}</b></div>')
    if n["kind"] == "decision":
        lines.append(f'<div class="k">{e(" / ".join(map(str, n["options"])))} &middot; {e(n["criterion"])}</div>')
    if n["kind"] == "gate":
        lines.append(f'<div class="k">approver: {e(n["approver"])} &middot; {e(n["criterion"])}</div>')
    if n["kind"] == "loop":
        lines.append(f'<div class="k">until {e(n["guard"])} &middot; bound {n["bound"]} &middot; progress: {e(n["progress"])}</div>')
    detail = [f'<div class="k">run: <code>{e(n["run"])}</code></div>']
    if deps:
        detail.append(f'<div class="k">after: {e(", ".join(deps))}</div>')
    detail.append(f'<div class="k">out: {e(", ".join(n["out"]))}</div>')
    if n["kind"] == "loop":
        detail.append('<div class="body">' + "".join(card(b, graph) for b in n["body"]) + "</div>")
    lines.append(f"<details><summary>details</summary>{''.join(detail)}</details></div>")
    return "".join(lines)


def render(board: dict, graph: dict, state: dict) -> str:
    st = {**statuses(graph, {}), **state} if state else statuses(graph, {})
    s = graph["stats"]
    e = html.escape
    out = [f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>{e(board['meta']['title'])}</title><style>{CSS}</style></head><body>",
           f"<h1>{e(board['meta']['title'])}</h1><p class=sub>{e(board['meta'].get('summary', ''))}</p><div class=stats>"]
    for key in ("nodes", "edges", "gates", "decisions", "loops", "human", "critical_path_len", "widest_parallel_group"):
        out.append(f'<div class=stat><b>{s[key]}</b>{e(key.replace("_", " "))}</div>')
    out.append("</div><div class=legend>" + "".join(
        f'<span><span class=sw style="background:var(--{k})"></span>{k}</span>' for k in ("task", "decision", "gate", "loop", "milestone")) + "</div>")
    for lane in board["lanes"]:
        ids = [nid for nid, n in graph["nodes"].items() if n["lane"] == lane["id"] and "parent" not in n]
        out.append(f'<section class=lane><h2>{e(lane["id"])} {e(lane["name"])} <span>&middot; {len(ids)} cards</span></h2><div class=cols>')
        for col in STATUSES:
            out.append(f"<div class=col><h3>{col}</h3>" + "".join(card(i, graph) for i in ids if st[i] == col) + "</div>")
        out.append("</div></section>")
    out.append("</body></html>")
    return "".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="agsci board")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("check", "render", "status"):
        p = sub.add_parser(name)
        p.add_argument("board")
        p.add_argument("--root", help="project root holding review/ (state comes from its ledger)")
        if name == "render":
            p.add_argument("-o", "--out", required=True)
    for name in ("start", "done", "fail"):
        p = sub.add_parser(name)
        p.add_argument("board")
        p.add_argument("node")
        p.add_argument("--root", required=True)
        p.add_argument("--option", help="decision nodes: the chosen option")
        p.add_argument("--approver", help="gate nodes: who approved")
        p.add_argument("--note", default="")
    p = sub.add_parser("run", help="run an agent node through Headless (in the agent image by default)")
    p.add_argument("board")
    p.add_argument("node")
    p.add_argument("--root", required=True)
    p.add_argument("--agent", default="claude")
    p.add_argument("--model")
    p.add_argument("--native", action="store_true", help="run on the host instead of the agent image")
    p.add_argument("--env-file", help="credentials for the agent container (default: <repo>/.env if present)")
    p.add_argument("--dry-run", action="store_true", help="write the prompt and command, run nothing")
    p = sub.add_parser("iterate", help="start the next iteration of a loop node")
    p.add_argument("board")
    p.add_argument("node")
    p.add_argument("--root", required=True)
    p.add_argument("--note", required=True, help="guard result and progress measure of the finished iteration")
    args = ap.parse_args(argv)

    board = load(args.board)
    errs, graph = analyze(board)
    for err in errs:
        print("ERROR", err, file=sys.stderr)
    if errs:
        return 1
    from . import state
    root = Path(args.root) if getattr(args, "root", None) else None
    events = state.read_events(root) if root else []
    if args.cmd == "check":
        print(" ".join(f"{k}={v}" for k, v in graph["stats"].items()))
    elif args.cmd == "render":
        Path(args.out).write_text(render(board, graph, state.statuses(graph, events) if root else {}))
        print(f"wrote {args.out}")
    elif args.cmd == "status":
        st = state.statuses(graph, events)
        counts = {s: sum(v == s for v in st.values()) for s in ("done", "skipped", "doing", "ready", "backlog", "failed")}
        print(" ".join(f"{k}={v}" for k, v in counts.items()))
        for nid, s in st.items():
            if s in ("ready", "doing", "failed"):
                n = graph["nodes"][nid]
                print(f"{s:7} {nid:8} {n['kind']:9} {n['exec']:9} {n['title']}")
    elif args.cmd == "run":
        from . import agent
        env = Path(args.env_file) if args.env_file else (agent.REPO / ".env" if (agent.REPO / ".env").exists() else None)
        try:
            res = agent.run(board, graph, root, args.node, agent=args.agent, model=args.model,
                            native=args.native, dry_run=args.dry_run, env_file=env)
        except ValueError as ex:
            print(f"ERROR {ex}", file=sys.stderr)
            return 1
        print(json.dumps(res))
        return 0 if res.get("dry_run") or res.get("exit_code") == 0 else 1
    elif args.cmd == "iterate":
        try:
            e = state.iterate(root, graph, args.node, args.note)
        except ValueError as ex:
            print(f"ERROR {ex}", file=sys.stderr)
            return 1
        print(json.dumps(e))
    else:
        try:
            e = state.mark(root, board, graph, args.node, args.cmd, option=args.option, approver=args.approver, note=args.note)
        except ValueError as ex:
            print(f"ERROR {ex}", file=sys.stderr)
            return 1
        print(json.dumps(e))
    return 0


if __name__ == "__main__":
    sys.exit(main())
