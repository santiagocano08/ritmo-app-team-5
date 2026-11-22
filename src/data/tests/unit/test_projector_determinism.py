"""T008 — the projection is a pure function of its input (006 FR-002, SC-001)."""
from __future__ import annotations

import ast
import random
from pathlib import Path

from src.data.rules.projector import Action, canonical_json, evaluate, inputs_json, project
from src.data.tests.unit.projector_support import bus, inputs, rate

SOURCE = Path(__file__).resolve().parents[2] / "rules" / "projector.py"
FORBIDDEN_IMPORTS = {"random", "time", "socket", "requests", "httpx", "urllib", "http", "openai", "anthropic"}


def make(order: list[int]):
    buses = [bus("B-103", distance_m=900.0, next_stop_idx=1, occupancy=12),
             bus("B-101", distance_m=100.0, next_stop_idx=1, occupancy=3),
             bus("B-102", distance_m=630.0, next_stop_idx=1),
             bus("B-106", kind="reserve")]
    return inputs([buses[i] for i in order], queues={0: 4, 1: 6, 2: 2}, rates={1: rate(360), 2: rate(90)})


ACTIONS = [Action("hold", "B-101", stop_idx=1, hold_s=60), Action("slow_down", "B-101", stop_idx=1, share=0.2),
           Action("reserve_dispatch", "B-106"), Action("skip_stop", "B-102", stop_idx=1)]


def run(order, actions):
    inp = make(order)
    scored = evaluate(inp, actions)
    return canonical_json({"inputs": inputs_json(inp), "base": project(inp),
                           "ranking": [(s.action, s.projection, s.saving_s) for s in scored]})


def test_two_runs_are_byte_identical() -> None:
    a, b = run([0, 1, 2, 3], ACTIONS), run([0, 1, 2, 3], ACTIONS)
    assert a == b and isinstance(a, bytes)


def test_input_order_does_not_matter() -> None:
    rng = random.Random(7)
    for _ in range(5):
        order = [0, 1, 2, 3]
        rng.shuffle(order)
        actions = list(ACTIONS)
        rng.shuffle(actions)
        # the inputs differ by bus order only; the projections and the ranking must not
        a, b = make(order), make([0, 1, 2, 3])
        assert canonical_json(project(a)) == canonical_json(project(b))
        assert canonical_json([(s.action, s.saving_s) for s in evaluate(a, actions)]) == \
            canonical_json([(s.action, s.saving_s) for s in evaluate(b, ACTIONS)])


def test_module_has_no_randomness_clock_or_network() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported.isdisjoint(FORBIDDEN_IMPORTS), imported & FORBIDDEN_IMPORTS
    calls = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not ({"now", "utcnow", "today", "monotonic", "perf_counter", "random"} & calls)
