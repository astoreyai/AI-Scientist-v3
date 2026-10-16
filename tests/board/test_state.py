"""Ledger and scheduler behaviour on the real scoping-review board."""

import shutil
from pathlib import Path

import pytest

from src.board import state
from src.board.graph import analyze, load

REPO = Path(__file__).parents[2]
BOARD = load(REPO / "src/scoping_review/board.yaml")
GRAPH = analyze(BOARD)[1]
REAL_FILE = REPO / "tests/scoping_review/fixtures/PROVENANCE.md"  # any real file stands in for an output's bytes


def produce(root, nid, it=1):
    """Place the node's output files (copies of a real file) so `done` can hash them."""
    for a in GRAPH["nodes"][nid]["out"]:
        p = state.artifact_path(root, BOARD, a, it)
        if p is None:
            continue
        if BOARD["meta"]["paths"][a].endswith("/"):
            p.mkdir(parents=True, exist_ok=True)
            shutil.copy(REAL_FILE, p / REAL_FILE.name)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REAL_FILE, p)


def done(root, nid, **kw):
    produce(root, nid)
    return state.mark(root, BOARD, GRAPH, nid, "done", **kw)


def ready(root):
    return {n for n, s in state.statuses(GRAPH, state.read_events(root)).items() if s == "ready"}


def test_fresh_board_has_one_ready_card(tmp_path):
    assert ready(tmp_path) == {"P0.01"}


def test_done_requires_outputs_on_disk(tmp_path):
    with pytest.raises(ValueError, match="missing"):
        state.mark(tmp_path, BOARD, GRAPH, "P0.01", "done")
    done(tmp_path, "P0.01")
    assert ready(tmp_path) == {"P0.02"}


def test_stop_decision_halts_the_review(tmp_path):
    done(tmp_path, "P0.01")
    done(tmp_path, "P0.02")
    with pytest.raises(ValueError, match="--option"):
        state.mark(tmp_path, BOARD, GRAPH, "P0.03", "done")
    done(tmp_path, "P0.03", option="stop")
    st = state.statuses(GRAPH, state.read_events(tmp_path))
    assert st["P0.04"] == st["P0.05"] == st["P2.08"] == st["P17.04"] == "skipped"
    assert ready(tmp_path) == set()
    assert (tmp_path / "review/decisions.yaml").read_text().count("stop") == 1


def test_gate_needs_an_approver_and_loop_respects_its_bound(tmp_path):
    for nid in ["P0.01", "P0.02"]:
        done(tmp_path, nid)
    done(tmp_path, "P0.03", option="continue")
    done(tmp_path, "P0.04")
    done(tmp_path, "P0.05", option="scoping")
    with pytest.raises(ValueError, match="approver"):
        done(tmp_path, "P0.06")
    done(tmp_path, "P0.06", approver="lead reviewer")
    done(tmp_path, "P0.07")
    done(tmp_path, "P0.08", option="no")
    for nid in ["P2.01", "P2.02", "P2.03", "P2.04"]:
        done(tmp_path, nid)
    assert "P2.05" in ready(tmp_path) and "P2.05a" not in ready(tmp_path)
    state.mark(tmp_path, BOARD, GRAPH, "P2.05", "start")
    assert "P2.05a" in ready(tmp_path)
    done(tmp_path, "P2.05a")
    assert "P2.05b" in ready(tmp_path)
    state.iterate(tmp_path, GRAPH, "P2.05", note="PRESS: 2 revision items; seeds 8/10")
    assert "P2.05a" in ready(tmp_path), "body resets for iteration 2"
    state.iterate(tmp_path, GRAPH, "P2.05", note="PRESS: 1 revision item; seeds 9/10")
    with pytest.raises(ValueError, match="bound 3"):
        state.iterate(tmp_path, GRAPH, "P2.05", note="third")


def test_run_dry_run_builds_prompt_from_skill_and_resolved_paths(tmp_path):
    from src.board import agent
    done(tmp_path, "P0.01")
    res = agent.run(BOARD, GRAPH, tmp_path, "P0.02", agent="claude", model="claude-opus-5-5", dry_run=True)
    prompt = Path(res["prompt"]).read_text()
    assert "Board node P0.02" in prompt and "`topic_idea`: `review/topic.md`" in prompt
    assert "`prior_reviews`: `review/prior_reviews.json`" in prompt and "name: sr-prior-reviews" in prompt
    cmd = res["command"]
    assert cmd[:3] == ["docker", "run", "--rm"] and agent.IMAGE in cmd and "/usr/local/bin/headless" in cmd
    assert cmd[-2:] == ["--prompt-file", "/work/" + str(Path(res["prompt"]).relative_to(tmp_path))]
    assert not (tmp_path / "review/ai_ledger.jsonl").exists(), "a dry run records nothing"
    with pytest.raises(ValueError, match="not ready"):
        agent.run(BOARD, GRAPH, tmp_path, "P0.04", agent="claude", model=None, dry_run=True)
    with pytest.raises(ValueError, match="human node"):
        agent.run(BOARD, GRAPH, tmp_path, "P0.01", agent="claude", model=None, dry_run=True)


def test_native_prompt_points_at_host_repo_and_lists_retrofit(tmp_path):
    from src.board import agent
    done(tmp_path, "P0.01")
    container = Path(agent.run(BOARD, GRAPH, tmp_path, "P0.02", agent="claude", model=None, dry_run=True)["prompt"]).read_text()
    assert "under `/repo/`" in container and "Earlier work" not in container
    (tmp_path / agent.RETROFIT).write_text("- phase1/research_questions.md\n")
    native = Path(agent.run(BOARD, GRAPH, tmp_path, "P0.02", agent="claude", model=None, native=True, dry_run=True)["prompt"]).read_text()
    assert f"under `{agent.REPO}/`" in native and "/repo/" not in native
    assert "Earlier work on this review" in native and "`review/retrofit.md`" in native


def test_systematic_review_board_is_valid_and_routes_scoping_questions_away(tmp_path):
    sr = load(REPO / "src/systematic_review/board.yaml")
    errs, g = analyze(sr)
    assert errs == [] and g["stats"]["loops"] == 11 and {"S7", "RB", "S9", "GR"} <= {lane["id"] for lane in sr["lanes"]}
    for nid in ("P0.01", "P0.02"):
        for a in g["nodes"][nid]["out"]:
            p = state.artifact_path(tmp_path, sr, a, 1)
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(REAL_FILE, p)
        state.mark(tmp_path, sr, g, nid, "done")
    state.mark(tmp_path, sr, g, "P0.03", "done", option="continue")
    p = state.artifact_path(tmp_path, sr, "pcc_draft", 1)
    shutil.copy(REAL_FILE, p)
    state.mark(tmp_path, sr, g, "P0.04", "done")
    state.mark(tmp_path, sr, g, "P0.05", "done", option="scoping")  # a mapping question belongs on the scoping board
    st = state.statuses(g, state.read_events(tmp_path))
    assert st["P0.06"] == st["S7.02"] == st["GR.03"] == "skipped"
