"""T006 — one hand-computed case per action modifier (006 FR-007, FR-008, FR-010).

Corridor as in `test_projector_crafted`: 4 stops, 100 s per segment, grid 5 s. Reference bus B at 630 m with
10 riders on board (arrives stop 1 at 40, natural dwell 10 -> departs 50; stop 2 arrives 150 departs 160;
stop 3 arrives 260, 10 alight, dwell 30 -> departs 290).

hold 60 s at stop 1: departure max(50, 40 + 60) = 100; stop 2 arrives 200 departs 210; stop 3 arrives 310,
  departs 340. Onboard delay = 10 riders * (100 - 50) = 500.
slow_down at stop 1 (window starts at the departure from the stop, 50 s):
  share 0.2, 300 s: segments take 100 / 0.8 = 125 s: stop 2 arrives 175 departs 185; stop 3 arrives 310
  departs 340. Extra time 25 + 25 s, onboard delay 10 * 50 = 500.
  share 0.1: 100 / 0.9 = 111.11 s: stop 2 at 161.11 -> 165 departs 175; stop 3 at 286.11 -> 290 departs 320.
  Onboard delay 10 * 2 * 11.11 = 222.2.
  share 0.2, 100 s window [50, 150]: 100 s at speed 0.8 cover 0.8 of segment 1, the remaining 0.2 takes 20 s
  -> arrives 170 departs 180; stop 3 arrives 280 departs 310. Onboard delay 10 * 20 = 200.
reserve_dispatch (B-106), 4 riders at stop 0, ready 120 s: arrives 120, dwell 10 + 12 = 22 -> 142 -> departs
  145; stop 1 arrives 245 departs 255; stop 2 arrives 355 departs 365; stop 3 arrives 465, 4 alight, dwell
  18 -> 483 -> 485. Cost 900 charged once.
adjust_departure: waiting bus with its slot at 300: departs stop 0 at 310; shift +60 -> 370; -120 -> 190.
broken bus: at 0 m, broken until 300 -> moves at 300, arrives stop 1 at 400, departs 410.
skip_stop at stop 1 with an empty queue: passes at 40 without dwell; stop 2 (queue 3) arrives 140, dwell
  10 + 9 = 19 -> 159 -> departs 160; stop 3 arrives 260 (3 alight, dwell 16) departs 280. With 2 riders at
  stop 1 it is not skipped: dwell 10 + 6 = 16 -> 56 -> departs 60.
"""
from __future__ import annotations

import pytest

from src.data.rules.projector import Action, UnsafeTarget, project
from src.data.tests.unit.projector_support import bus, inputs, with_params


def ref_bus(**kw):
    return bus("B", distance_m=630.0, next_stop_idx=1, occupancy=10, **kw)


def deps(p) -> dict:
    return dict(p.departures)


def test_reference_without_action() -> None:
    p = project(inputs([ref_bus()]))
    assert deps(p) == {("B", 1): 50, ("B", 2): 160, ("B", 3): 290}
    assert p.onboard_delay_s == 0.0 and p.reserve_cost_s == 0.0


def test_hold() -> None:
    p = project(inputs([ref_bus()]), Action("hold", "B", stop_idx=1, hold_s=60))
    assert deps(p) == {("B", 1): 100, ("B", 2): 210, ("B", 3): 340}
    assert p.onboard_delay_s == pytest.approx(500.0)


def test_hold_shorter_than_the_natural_dwell_changes_nothing() -> None:
    p = project(inputs([ref_bus()]), Action("hold", "B", stop_idx=1, hold_s=5))
    assert deps(p) == {("B", 1): 50, ("B", 2): 160, ("B", 3): 290}
    assert p.onboard_delay_s == 0.0


def test_slow_down_20_percent() -> None:
    p = project(inputs([ref_bus()]), Action("slow_down", "B", stop_idx=1, share=0.20))
    assert deps(p) == {("B", 1): 50, ("B", 2): 185, ("B", 3): 340}
    assert p.onboard_delay_s == pytest.approx(500.0)


def test_slow_down_10_percent() -> None:
    p = project(inputs([ref_bus()]), Action("slow_down", "B", stop_idx=1, share=0.10))
    assert deps(p) == {("B", 1): 50, ("B", 2): 175, ("B", 3): 320}
    assert p.onboard_delay_s == pytest.approx(10 * 2 * (100 / 0.9 - 100))


def test_slow_down_only_inside_its_window() -> None:
    p = project(inputs([ref_bus()]), Action("slow_down", "B", stop_idx=1, share=0.20, duration_s=100))
    assert deps(p) == {("B", 1): 50, ("B", 2): 180, ("B", 3): 310}
    assert p.onboard_delay_s == pytest.approx(200.0)


def test_reserve_dispatch() -> None:
    inp = inputs([ref_bus(), bus("B-106", kind="reserve")], queues={0: 4})
    p = project(inp, Action("reserve_dispatch", "B-106"))
    d = deps(p)
    assert [d[("B-106", i)] for i in range(4)] == [145, 255, 365, 485]
    assert p.reserve_cost_s == 900
    base = project(inp)
    assert not any(k[0] == "B-106" for k in deps(base))  # an undispatched reserve is not projected


def test_adjust_departure() -> None:
    waiting = bus("W-1", kind="waiting", next_stop_idx=0)
    inp = inputs([waiting], next_departures=(300,))
    assert deps(project(inp))[("W-1", 0)] == 310
    assert deps(project(inp, Action("adjust_departure", "W-1", shift_s=60)))[("W-1", 0)] == 370
    assert deps(project(inp, Action("adjust_departure", "W-1", shift_s=-120)))[("W-1", 0)] == 190


def test_broken_bus_waits_for_the_end_of_the_incident() -> None:
    p = project(inputs([bus("B", distance_m=0.0, next_stop_idx=1, broken_until=300.0)]))
    assert deps(p)[("B", 1)] == 410


def test_skip_stop_with_an_empty_queue() -> None:
    inp = inputs([bus("B", distance_m=630.0, next_stop_idx=1)], queues={2: 3})
    p = project(inp, Action("skip_stop", "B", stop_idx=1))
    assert deps(p) == {("B", 2): 160, ("B", 3): 280}
    assert deps(project(inp)) == {("B", 1): 50, ("B", 2): 170, ("B", 3): 290}


def test_skip_stop_never_skips_a_stop_with_riders() -> None:
    inp = inputs([bus("B", distance_m=630.0, next_stop_idx=1)], queues={1: 2})
    assert deps(project(inp, Action("skip_stop", "B", stop_idx=1)))[("B", 1)] == 60


@pytest.mark.parametrize("quality", ["estimated", "sources_down"])
def test_non_live_bus_is_an_obstacle_but_never_a_target(quality: str) -> None:
    b = bus("B", distance_m=630.0, next_stop_idx=1, quality=quality)
    inp = inputs([b])
    assert deps(project(inp)) == {("B", 1): 40 + 10, ("B", 2): 160, ("B", 3): 270}
    for action in (Action("hold", "B", stop_idx=1, hold_s=30),
                   Action("slow_down", "B", stop_idx=1, share=0.1),
                   Action("skip_stop", "B", stop_idx=1)):
        with pytest.raises(UnsafeTarget):
            project(inp, action)


def test_non_live_bus_still_boards_riders_for_the_buses_behind() -> None:
    """FR-007: an estimated bus ahead empties the queue; the follower finds only the new arrivals."""
    est = bus("A", distance_m=900.0, next_stop_idx=1, quality="estimated")
    follower = bus("F", distance_m=100.0, next_stop_idx=1)
    d = deps(project(inputs([est, follower], queues={1: 6})))
    assert d[("F", 1)] == 100  # arrives 90 with an empty queue, dwell 10


def test_hold_above_the_cap_is_refused() -> None:
    with pytest.raises(ValueError):
        project(inputs([ref_bus()]), Action("hold", "B", stop_idx=1, hold_s=91))
    project(inputs([ref_bus()]), Action("hold", "B", stop_idx=1, hold_s=90))


def test_params_drive_the_modifiers() -> None:
    inp = inputs([ref_bus(), bus("B-106", kind="reserve")], queues={0: 4},
                 params=with_params(reserve_ready_s=240, reserve_cost_s=100))
    p = project(inp, Action("reserve_dispatch", "B-106"))
    assert deps(p)[("B-106", 0)] == 265  # arrives 240, dwell 22 -> 262 -> 265
    assert p.reserve_cost_s == 100
