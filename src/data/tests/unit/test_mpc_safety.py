"""T025 — the final safety guard (006 FR-015 to FR-019, SC-006, SC-007, SC-012; research R14).

A bug in candidate generation must not be able to publish an unsafe row, so the guard is checked on its own.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.data.rules.holds import MAX_HOLD_S
from src.data.rules.mpc import Candidate, Evaluated, guard, is_fresh, rank_candidates
from src.data.rules.mpc_params import MpcParams
from src.data.rules.projector import Action

ROOT = Path(__file__).resolve().parents[4]
STOPS = tuple(f"P-{n}" for n in range(883, 901))
P = MpcParams()


def hold(s: float, bus="B-103"):
    return Evaluated(Candidate(Action("hold", bus, 5, hold_s=s), "C1"), 1000.0, 30.0)


def test_a_hold_above_the_cap_is_dropped_and_ninety_passes() -> None:
    kept, dropped = guard([hold(91), hold(90, "B-104"), hold(MAX_HOLD_S + 0.5, "B-105")], frozenset(), frozenset())
    assert [e.candidate.action.hold_s for e in kept] == [90]
    assert [d[1] for d in dropped] == ["hold_over_cap", "hold_over_cap"]


def test_non_live_targets_are_dropped() -> None:
    kept, dropped = guard([hold(60, "B-101"), hold(60, "B-102"), hold(60, "B-103")],
                          unsafe_buses=frozenset({"B-101"}), sources_down=frozenset({"B-102"}))
    assert [e.candidate.action.bus_id for e in kept] == ["B-103"]
    assert sorted(d[1] for d in dropped) == ["unsafe_target", "unsafe_target"]


def test_the_ranking_applies_the_guard() -> None:
    r = rank_candidates([hold(91)], P, STOPS)
    assert r.picks == []


@pytest.mark.parametrize("age,fresh", [(0.0, True), (15.0, True), (15.1, False), (20.0, False)])
def test_snapshot_age_limit_is_fifteen_seconds(age, fresh) -> None:
    assert is_fresh(age, P) is fresh


def test_freshness_limit_is_a_parameter() -> None:
    assert is_fresh(20.0, MpcParams(freshness_max_s=30)) is True


FORBIDDEN = {"requests", "httpx", "urllib", "urllib3", "http", "socket", "aiohttp", "openai", "anthropic",
             "random", "time", "asyncio", "subprocess"}


@pytest.mark.parametrize("path", ["src/data/rules/mpc.py", "src/data/rules/projector.py",
                                  "src/data/pipeline/recommend.py"])
def test_no_network_client_llm_clock_or_randomness_is_imported(path) -> None:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not (names & FORBIDDEN), names & FORBIDDEN
