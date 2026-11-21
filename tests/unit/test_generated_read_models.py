"""T009 — generated read models import and round-trip the `normal` fixtures (Principle II, R9)."""
from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NAMES = ["source_status", "corridor_now", "decision_inputs", "incident"]


def _model_root(module):
    """The schema's top-level model is the class named <Title>V100 in the generated module."""
    models = [v for v in vars(module).values()
              if isinstance(v, type) and v.__module__ == module.__name__ and v.__name__.endswith("V100")]
    assert len(models) == 1, "expected exactly one top-level <Title>V100 model"
    return models[0]


@pytest.mark.parametrize("name", NAMES)
def test_generated_module_imports(name: str) -> None:
    importlib.import_module(f"src.pulsoflota.models.read.{name}")


@pytest.mark.parametrize("name", ["source_status", "corridor_now"])
def test_normal_fixture_round_trips(name: str) -> None:
    module = importlib.import_module(f"src.pulsoflota.models.read.{name}")
    data = json.loads((ROOT / "contracts/read/fixtures/normal" / f"{name}.json").read_text())
    model = _model_root(module).model_validate(data)
    assert model.model_dump(mode="json") == data


def test_decision_inputs_sample_round_trips() -> None:
    """No decision_inputs fixture exists under contracts/read/fixtures, so build one from `normal`."""
    module = importlib.import_module("src.pulsoflota.models.read.decision_inputs")
    normal = json.loads((ROOT / "contracts/read/fixtures/normal/corridor_now.json").read_text())
    data = {
        **normal,
        "travel_time_forecast": [{"segment_id": k, "forecast_travel_s": 60.0 + k} for k in range(1, 18)],
        "demand_15min": {"window_start_ts": "2026-11-24T22:15:00Z", "window_end_ts": "2026-11-24T22:30:00Z",
                         "arrivals_forecast": 12},
        "resources": {"reserve_free": ["B-106", "B-107"], "drivers_free": 2},
        "action_cost": {"hold_penalty_s": 0, "early_departure_penalty_s": 0},
        "active_incidents": ["11111111-1111-4111-8111-111111111111"],
        "enabled_stops": ["P-883", "P-884"],
    }
    model = _model_root(module).model_validate(data)
    assert model.model_dump(mode="json") == data
