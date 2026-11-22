"""T002 — the decision model's parameters (006 FR-010, FR-018; data-model M1).

`MpcParams` is a frozen dataclass whose defaults equal the `config.decision_model` defaults; the projector and
the candidate rules read every number from it, never from a literal.
"""
from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from src.data.rules.mpc_params import MpcParams
from src.data.tests.unit.projector_support import bus, inputs, with_params

RULES = Path(__file__).resolve().parents[2] / "rules"
FORBIDDEN_LITERALS = {90, 900, 300, 120, 15}

M1_DEFAULTS = {
    "scoring_window_s": 1800,
    "horizon_s": 600,
    "step_s": 5,
    "capacity": 40,
    "threshold_s_per_rider": 15,
    "top_n": 3,
    "reserve_ready_s": 120,
    "reserve_cost_s": 900,
    "slow_duration_s": 300,
    "slow_shares": (0.10, 0.20),
    "hold_options_s": (30, 60, 90),
    "adjust_options_s": (-120, -60, 60, 120),
    "skip_reach_stops": 4,
    "queue_trigger_riders": 20,
    "proposal_ttl_s": 120,
    "rest_s": 300,
    "freshness_max_s": 15,
    "rate_window_s": 1800,
    "train_share": 0.80,
    "walk_mean_s": 120,
    "model_version": "1.0.0",
}


def test_defaults_equal_data_model_m1() -> None:
    params = MpcParams()
    for name, expected in M1_DEFAULTS.items():
        assert getattr(params, name) == expected, name
    assert {f.name for f in dataclasses.fields(MpcParams)} == set(M1_DEFAULTS)


def test_params_are_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        MpcParams().capacity = 50  # type: ignore[misc]


def test_changing_one_field_changes_the_projection() -> None:
    from src.data.rules.projector import project

    # A bus at 630 m of the first segment, 37 s from stop 1; a 7 s grid moves 37 s -> 42 s.
    b = bus(distance_m=630.0, next_stop_idx=1)
    base = project(inputs([b]))
    other = project(inputs([b], params=with_params(step_s=7)))
    assert base.departures != other.departures


@pytest.mark.parametrize("name", ["projector.py", "mpc.py"])
def test_no_model_literal_in_the_rules(name: str) -> None:
    """FR-010: 90, 900, 300, 120 and 15 live only in `mpc_params.py` (and `MAX_HOLD_S` is reused)."""
    path = RULES / name
    if name == "mpc.py" and not path.exists():
        pytest.skip("rules/mpc.py is built in phase 2")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits = [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
            and not isinstance(n.value, bool) and n.value in FORBIDDEN_LITERALS]
    assert hits == [], f"{name} has model literals: {hits}"


def test_projector_file_is_scanned() -> None:
    assert (RULES / "projector.py").exists()
