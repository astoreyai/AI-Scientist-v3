"""Mutation tests for src/board/graph.py, run against the real scoping-review board."""

import copy
from pathlib import Path

import pytest

from src.board.graph import analyze, load, render

BOARD = load(Path(__file__).parents[2] / "src/scoping_review/board.yaml")


def node(board, nid):
    return next(n for n in board["nodes"] if n["id"] == nid)


def errors_after(mutate):
    board = copy.deepcopy(BOARD)
    mutate(board)
    return analyze(board)[0]


def test_real_board_is_clean():
    errs, graph = analyze(BOARD)
    assert errs == []
    assert graph["stats"]["loops"] > 0 and graph["stats"]["gates"] > 0


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda b: node(b, "P0.01")["in"].__setitem__(slice(None), ["published"]) if "in" in node(b, "P0.01")
         else node(b, "P0.01").__setitem__("in", ["published"]), "cycle"),
        (lambda b: node(b, "P0.02").__setitem__("out", ["something_else"]), "produced by no node"),
        (lambda b: node(b, "P2.05").pop("bound"), "positive int bound"),
        (lambda b: node(b, "P4.04")["in"].append("test_run"), "from inside loop"),
        (lambda b: node(b, "P0.04").__setitem__("when", "P15.06 == yes"), "not upstream"),
        (lambda b: node(b, "P0.04").__setitem__("when", "P0.03 == maybe"), "not in P0.03 options"),
        (lambda b: node(b, "P0.06").pop("approver"), "gate needs"),
        (lambda b: node(b, "P1.03").__setitem__("out", ["journal_shortlist"]), "already produced"),
        (lambda b: node(b, "P4.04").__setitem__("optional", ["seed_set"]), "not listed in `in`"),
        (lambda b: b["meta"]["paths"].pop("prior_reviews"), "no entry in meta.paths"),
        (lambda b: node(b, "P0.02").__setitem__("skill", "sr-no-such-skill"), "agent node needs `skill`"),
    ],
)
def test_each_defect_is_caught(mutate, expected):
    assert any(expected in e for e in errors_after(mutate))


def test_render_places_unblocked_nodes_in_ready():
    page = render(BOARD, analyze(BOARD)[1], {})
    assert "Choose the review topic" in page and "<h3>ready</h3>" in page
