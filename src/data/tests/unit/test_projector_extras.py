"""Projector edge cases and validation (006 FR-007, FR-010). Same corridor as `test_projector_crafted`.

Hand values (4 stops, 100 s per segment, grid 5 s, bus at 630 m = 37 s from stop 1):
- A slow-down already in force (20 %, until 300 s): segment 0 takes 0.37 * 100 / 0.8 = 46.25 -> arrives 50,
  departs 60; segment 1 125 s -> 185, departs 195; segment 2: 105 s at 0.8 cover 0.84, the remaining 0.16 take
  16 s -> 316 -> arrives 320, departs 330. It is not an action, so its delay is not charged.
- A hold already ordered (60 s at stop 1): arrival 40, departs max(50, 100) = 100.
- `skip_until = 3` with empty queues: stops 1 and 2 are passed; arrives stop 3 at 240, departs 250.
- Bus at stop 1 since -5 s with a 20 s dwell: departs 15. A 60 s hold at that stop: max(15, -5 + 60) = 55, onboard
  delay 10 * 40 = 400. An order of 30 s already in force: max(15, 25) = 25. Broken until 100: departs 100.
- Riders from a train batch at stop 1: a batch of 5 at 20 s or at 40 s (the arrival) boards: dwell 25 -> departs 65;
  a batch at -5 s is already in the queue (ignored).
- Road trend (1, 2, 1): segment 1 takes 200 s: stop 1 departs 50, stop 2 arrives 250 departs 260.
"""
from __future__ import annotations

import pytest

from src.data.rules.projector import Action, canonical_json, project
from src.data.tests.unit.projector_support import bus, inputs, with_params


def deps(p) -> dict:
    return dict(p.departures)


def test_slow_down_already_in_force_is_not_charged() -> None:
    p = project(inputs([bus("B", distance_m=630.0, next_stop_idx=1, slow=(0.2, 300.0))]))
    assert deps(p) == {("B", 1): 60, ("B", 2): 195, ("B", 3): 330}
    assert p.onboard_delay_s == 0.0


def test_hold_already_ordered() -> None:
    p = project(inputs([bus("B", distance_m=630.0, next_stop_idx=1, holds=((1, 60.0),))]))
    assert deps(p)[("B", 1)] == 100 and p.onboard_delay_s == 0.0


def test_skip_already_active() -> None:
    p = project(inputs([bus("B", distance_m=630.0, next_stop_idx=1, skip_until=3)]))
    assert deps(p) == {("B", 3): 250}


def test_at_stop_hold_and_breakdown() -> None:
    at = dict(next_stop_idx=2, at_stop=(-5.0, 20.0), occupancy=10)
    p = project(inputs([bus("B", **at)]), Action("hold", "B", stop_idx=1, hold_s=60))
    assert deps(p)[("B", 1)] == 55 and p.onboard_delay_s == pytest.approx(400.0)
    assert deps(project(inputs([bus("B", holds=((1, 30.0),), **at)])))[("B", 1)] == 25
    assert deps(project(inputs([bus("B", broken_until=100.0, **at)])))[("B", 1)] == 100


def test_bus_at_the_last_stop_only_departs() -> None:
    p = project(inputs([bus("B", next_stop_idx=4, at_stop=(-5.0, 20.0))]))
    assert deps(p) == {("B", 3): 15}


def test_service_bus_at_the_terminal_and_a_bus_past_the_end() -> None:
    p = project(inputs([bus("B", next_stop_idx=0), bus("Z", next_stop_idx=9)]))
    assert deps(p)[("B", 0)] == 10 and deps(p)[("B", 1)] == 120
    assert not any(k[0] == "Z" for k in deps(p))


def test_train_batches() -> None:
    for at, expected in ((20.0, 65), (40.0, 65), (-5.0, 50)):
        inp = inputs([bus("B", distance_m=630.0, next_stop_idx=1)], batches={1: ((at, 5.0),)})
        assert deps(project(inp))[("B", 1)] == expected, at


def test_road_trend_scales_the_segment() -> None:
    inp = inputs([bus("B", distance_m=630.0, next_stop_idx=1)], trend=(1.0, 2.0, 1.0))
    assert deps(project(inp)) == {("B", 1): 50, ("B", 2): 260, ("B", 3): 370}


def test_waiting_bus_without_a_slot_or_outside_the_window_never_starts() -> None:
    w = bus("W", kind="waiting")
    assert deps(project(inputs([w]))) == {}
    assert deps(project(inputs([w], next_departures=(2000,)))) == {}
    r = inputs([bus("R", kind="reserve")], queues={0: 1}, params=with_params(scoring_window_s=100))
    assert deps(project(r, Action("reserve_dispatch", "R"))) == {}


@pytest.mark.parametrize("action", [
    Action("teleport", "B"),
    Action("hold", "ghost", stop_idx=1, hold_s=30),
    Action("hold", "B", hold_s=30),
    Action("slow_down", "B", stop_idx=1, share=1.0),
    Action("reserve_dispatch", "B"),
    Action("adjust_departure", "B", shift_s=60),
])
def test_invalid_actions_are_refused(action: Action) -> None:
    with pytest.raises(ValueError):
        project(inputs([bus("B", distance_m=630.0, next_stop_idx=1)]), action)


def test_the_none_action_equals_no_action() -> None:
    inp = inputs([bus("B", distance_m=630.0, next_stop_idx=1)], queues={1: 2})
    assert canonical_json(project(inp)) == canonical_json(project(inp, Action("none")))
