"""T034 — headway rules (FR-020, R8, ADR-0003 gate decisions 1-2)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.rules.headway import BusObs, compute_headways, headway_s, order_buses, pass_time

T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)


def t(s: float) -> datetime:
    return T0 + timedelta(seconds=s)


def bus(bus_id: str, distance: float, ts: float, history=None, broken_down: bool = False) -> BusObs:
    hist = tuple((t(a), d) for a, d in (history if history is not None else [(ts, distance)]))
    return BusObs(bus_id=bus_id, distance_along_m=distance, position_ts=t(ts), history=hist,
                  broken_down=broken_down)


def test_pass_time_interpolates_between_the_samples_around_the_distance() -> None:
    history = ((t(0), 0.0), (t(100), 100.0), (t(200), 300.0))
    assert pass_time(history, 50.0) == t(50)
    assert pass_time(history, 200.0) == t(150)


def test_pass_time_uses_the_sample_time_when_the_distance_is_hit_exactly() -> None:
    history = ((t(0), 0.0), (t(100), 100.0), (t(200), 300.0))
    assert pass_time(history, 100.0) == t(100)


def test_pass_time_uses_the_first_sample_when_it_is_already_at_or_past_the_distance() -> None:
    history = ((t(10), 500.0), (t(20), 600.0))
    assert pass_time(history, 400.0) == t(10)


def test_pass_time_is_none_when_no_sample_reaches_the_distance_or_history_is_empty() -> None:
    assert pass_time(((t(0), 0.0), (t(10), 10.0)), 50.0) is None
    assert pass_time((), 1.0) is None


def test_headway_is_the_follower_time_minus_the_pass_time() -> None:
    ahead = ((t(0), 0.0), (t(100), 100.0))
    assert headway_s(50.0, t(250), 100.0, ahead) == 200.0


def test_equal_distance_gives_exactly_zero_even_if_interpolation_would_not() -> None:
    dwelling = ((t(0), 0.0), (t(50), 100.0), (t(150), 100.0))
    assert headway_s(100.0, t(150), 100.0, dwelling) == 0.0


def test_negative_difference_is_clamped_to_zero() -> None:
    ahead = ((t(0), 0.0), (t(100), 100.0))
    assert headway_s(50.0, t(20), 100.0, ahead) == 0.0  # stale follower: reported before the pass


def test_headway_falls_back_to_the_latest_position_time_without_history() -> None:
    assert headway_s(50.0, t(300), 100.0, (), ahead_ts=t(100)) == 200.0


def test_order_is_distance_descending_with_ties_by_bus_id() -> None:
    buses = [bus("B-103", 100, 0), bus("B-101", 300, 0), bus("B-102", 100, 0)]
    assert [b.bus_id for b in order_buses(buses)] == ["B-101", "B-102", "B-103"]


def test_leader_and_broken_down_buses_have_no_headway_and_nearest_operational_bus_is_ahead() -> None:
    ordered = order_buses([
        bus("B-105", 3000, 1000, [(0, 0), (1000, 3000)]),
        bus("B-104", 2000, 1000, [(0, 0), (1000, 2000)], broken_down=True),
        bus("B-103", 1000, 1000, [(0, 0), (1000, 1000)]),
    ])
    h = compute_headways(ordered)
    assert h["B-105"].seconds is None and h["B-105"].ahead_bus_id is None
    assert h["B-104"].seconds is None and h["B-104"].ahead_bus_id is None
    # B-103 skips the broken-down B-104 and measures against B-105, which passed 1,000 m at 333.33 s.
    assert h["B-103"].ahead_bus_id == "B-105"
    assert h["B-103"].seconds == pytest.approx(1000 - 1000 / 3, abs=0.01)


def test_a_broken_down_leader_hands_the_leader_role_to_the_furthest_operational_bus() -> None:
    ordered = order_buses([
        bus("B-105", 3000, 1000, broken_down=True),
        bus("B-104", 2000, 1000, [(0, 0), (1000, 2000)]),
        bus("B-103", 1000, 1000, [(0, 0), (1000, 1000)]),
    ])
    h = compute_headways(ordered)
    assert h["B-104"].seconds is None
    assert h["B-103"].ahead_bus_id == "B-104" and h["B-103"].seconds == 500.0


def test_single_operational_bus_has_no_headway() -> None:
    h = compute_headways(order_buses([bus("B-101", 10, 5)]))
    assert h["B-101"].seconds is None


def test_no_buses_gives_no_headways() -> None:
    assert compute_headways([]) == {}
