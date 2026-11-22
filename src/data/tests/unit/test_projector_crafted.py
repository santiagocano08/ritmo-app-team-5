"""T004 — crafted snapshots with hand-computed departures (006 SC-002, FR-005, FR-006).

Corridor: 4 stops 1,000 m apart (last = 3), M1 = 100 s per segment, capacity 40, grid 5 s, `ceil` on arrival
and on departure. Dwell = max(10, 10 + 3*boarded + 2*alighted). Times are seconds after `as_of`. Rates are
riders per hour (360/h = 0.1 per second). Nobody alights before the last stop unless a case says so.

(a) One bus, empty corridor. Bus at 630 m: 370 m left of segment 0 = 0.37 * 100 = 37 s -> arrives 40
    (grid). Dwell 10 -> departs 50. Segment 1: arrives 150, departs 160. Segment 2: arrives 260 at the last
    stop, nobody on board, dwell 10 -> departs 270.
(b) Leader L at 900 m (arrives stop 1 at 10), follower F at 100 m (0.9 * 100 = 90 s -> arrives 90). Stop 1
    has queue 6 and 0.1 riders/s. L: queue 6 + 0.1*10 = 7 boards 7, dwell 10 + 21 = 31 -> 41 -> departs 45.
    F finds the queue emptied at 10: 0.1 * 80 = 8 boards 8, dwell 34 -> 124 -> departs 125.
    L: stop 2 arrives 145 departs 155; stop 3 arrives 255, 7 alight, dwell 10 + 14 = 24 -> 279 -> 280.
    F: stop 2 arrives 225 departs 235; stop 3 arrives 335, 8 alight, dwell 26 -> 361 -> 365.
(c) Full bus L (occupancy 40) at 900 m, empty follower F at 100 m, stop 1 queue 6 at 0.1/s. L arrives 10,
    boards 0, dwell 10 -> departs 20 and leaves 7 riders. F arrives 90: queue 7 + 0.1 * 80 = 15, boards 15,
    dwell 10 + 45 = 55 -> 145. L: stop 2 arrives 120 departs 130; stop 3 arrives 230, 40 alight, dwell 90
    -> departs 320.
(d) Zero queue, zero rate, 20 riders on board and nobody alighting at stop 1: dwell 10.
"""
from __future__ import annotations

import pytest

from src.data.rules.projector import project
from src.data.tests.unit.projector_support import bus, inputs, rate, with_params


def deps(p) -> dict:
    return dict(p.departures)


def test_a_one_bus_empty_corridor() -> None:
    p = project(inputs([bus("B-101", distance_m=630.0, next_stop_idx=1)]))
    assert deps(p) == {("B-101", 1): 50, ("B-101", 2): 160, ("B-101", 3): 270}


def test_b_two_buses_with_a_queue() -> None:
    inp = inputs([bus("L", distance_m=900.0, next_stop_idx=1), bus("F", distance_m=100.0, next_stop_idx=1)],
                 queues={1: 6}, rates={1: rate(360)})
    d = deps(project(inp))
    assert d[("L", 1)] == 45 and d[("F", 1)] == 125
    assert d[("L", 2)] == 155 and d[("L", 3)] == 280
    assert d[("F", 2)] == 235 and d[("F", 3)] == 365


def test_c_full_bus_leaves_the_queue() -> None:
    inp = inputs([bus("L", distance_m=900.0, next_stop_idx=1, occupancy=40),
                  bus("F", distance_m=100.0, next_stop_idx=1)], queues={1: 6}, rates={1: rate(360)})
    d = deps(project(inp))
    assert d[("L", 1)] == 20
    assert d[("F", 1)] == 145  # 15 riders (7 left behind + 8 arrived since), dwell 55 s
    assert d[("L", 2)] == 130 and d[("L", 3)] == 320


def test_d_zero_queue_dwell_is_ten_seconds() -> None:
    p = project(inputs([bus("B-101", distance_m=900.0, next_stop_idx=1, occupancy=20)]))
    # arrives 10, dwell 10 -> 20 (no one boards, nobody alights at stop 1)
    assert deps(p)[("B-101", 1)] == 20


def test_projection_ends_at_the_last_stop_and_inside_the_window() -> None:
    inp = inputs([bus("B-101", distance_m=630.0, next_stop_idx=1)], params=with_params(scoring_window_s=150))
    p = project(inp)
    # stop 2 is reached at 150 (inside), but its departure (160) is outside the window.
    assert deps(p) == {("B-101", 1): 50}
    assert all(t <= 150 for t in deps(p).values())
    full = deps(project(inputs([bus("B-101", distance_m=630.0, next_stop_idx=1)])))
    assert max(k[1] for k in full) == 3  # nothing after the last stop


def test_bus_already_at_a_stop_departs_after_its_remaining_dwell() -> None:
    # Arrived at stop 1 five seconds ago with a 20 s dwell: departs at 15, then 100 s to stop 2.
    b = bus("B-101", next_stop_idx=2, at_stop=(-5.0, 20.0))
    d = deps(project(inputs([b])))
    assert d[("B-101", 1)] == 15
    assert d[("B-101", 2)] == 125  # arrives 115, dwell 10


@pytest.mark.parametrize("rate_per_hour", [0.0])
def test_zero_rate_stop_does_not_grow(rate_per_hour: float) -> None:
    p = project(inputs([bus("B-101", distance_m=900.0, next_stop_idx=1)], rates={1: rate(rate_per_hour)}))
    assert p.wait_s == 0.0
