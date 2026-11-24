"""T001 — R14 acceptance: the simulator base case must not look bunched.

Seeded 2-hour runs with no injections. Gaps between consecutive `stop_arrival`
events at P-883 (start of the corridor) must centre on the planned headway.
"""
from __future__ import annotations

import statistics
from datetime import datetime

import pytest

from src.pulsoflota.config import get_sim_planned_headway_s
from src.data.simulator.engine import run

FIRST = "P-883"


def _gaps(seed: int, duration: int = 7200) -> list[float]:
    ts = [
        datetime.fromisoformat(e["event_ts"].replace("Z", "+00:00"))
        for e in run(seed, duration)
        if e["event_type"] == "stop_arrival" and e["payload"]["stop_id"] == FIRST
    ]
    ts.sort()
    return [(b - a).total_seconds() for a, b in zip(ts, ts[1:])]


@pytest.mark.parametrize("seed", [42, 7])
def test_median_gap_is_planned_headway(seed: int) -> None:
    gaps = _gaps(seed)
    assert len(gaps) >= 10
    assert statistics.median(gaps) == pytest.approx(420, abs=42)


@pytest.mark.parametrize("seed", [42, 7])
def test_no_gap_below_300s(seed: int) -> None:
    assert min(_gaps(seed)) >= 300


def test_default_planned_headway_is_420(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIM_PLANNED_HEADWAY_S", raising=False)
    assert get_sim_planned_headway_s() == 420


def test_planned_headway_setting_changes_start_spacing(monkeypatch: pytest.MonkeyPatch) -> None:
    def starts() -> list[float]:
        ts = sorted(
            datetime.fromisoformat(e["event_ts"].replace("Z", "+00:00"))
            for e in run(42, 2400)
            if e["event_type"] == "stop_arrival" and e["payload"]["stop_id"] == FIRST
        )
        return [(b - a).total_seconds() for a, b in zip(ts, ts[1:4])]

    monkeypatch.setenv("SIM_PLANNED_HEADWAY_S", "600")
    base = starts()
    monkeypatch.setenv("SIM_PLANNED_HEADWAY_S", "300")
    other = starts()
    assert base == [600, 600, 600]
    assert other == [300, 300, 300]
