"""T007 — the score of an action (006 FR-011, research R11).

score = W (rider-seconds waiting at stops) + O (onboard delay) + C (reserve cost).

Link with the stop EWT of story 005 (`rules/stop_metrics.py`): stop 0 has 0.02 riders/s (72/h) and four
waiting buses whose slots are 200, 500, 1000 and 1500 s; window 1500 s. With no one left behind,
W = sum(lambda * h^2 / 2) over the intervals 200, 300, 500, 500 = 0.01 * (40000 + 90000 + 250000 + 250000)
= 6300 rider-seconds, riders = 0.02 * 1500 = 30, so W / riders = 210 s. `stop_metrics` gives
sum(h^2) / (2 * sum(h)) = 630000 / 3000 = 210 s from the same instants (0, 200, 500, 1000, 1500).
The instants are those at which riders board (bus arrival), as in the simulator; a departure is the arrival
plus a dwell that varies with the riders boarded, so headways between departures would differ by that dwell.

Left behind: stops 1 has queue 6 at 0.1/s, window 200 s, leader L at 900 m, follower F at 100 m (arrives 10
and 90). L full (40 on board): q = 6 + 0.1 t until 90: 6*90 + 0.1*90^2/2 = 945; F boards 15; then
0.1 * 110^2 / 2 = 605. W = 1550, riders = 6 + 0.1 * 200 = 26. L empty: it boards 7 at t = 10:
65 + 0.1 * 80^2 / 2 = 320 + 605 -> W = 990. A rider left behind is counted only through the longer queue.

Reserve: 4 riders at stop 0, no rate, window 1800. Without the reserve W = 4 * 1800 = 7200. With it the
reserve boards them at 120: W = 480, C = 900, score 1380, riders 4, saving (7200 - 1380) / 4 = 1455.0.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from src.data.rules.projector import Action, evaluate, project, saving_s_per_rider
from src.data.rules.stop_metrics import Departure, stop_intervals
from src.data.tests.unit.projector_support import bus, inputs, rate, with_params


def test_do_nothing_has_no_onboard_delay_and_no_reserve_cost() -> None:
    p = project(inputs([bus("B", distance_m=630.0, next_stop_idx=1, occupancy=10)], queues={2: 3}))
    assert p.onboard_delay_s == 0.0 and p.reserve_cost_s == 0.0
    assert p.score_s == pytest.approx(p.wait_s)


def test_wait_per_rider_equals_the_stop_ewt_numerator() -> None:
    slots = (200, 500, 1000, 1500)
    buses = [bus(f"W-{i}", kind="waiting", next_stop_idx=0) for i in range(4)]
    inp = inputs(buses, rates={0: rate(72)}, next_departures=slots, params=with_params(scoring_window_s=1500))
    p = project(inp)
    assert p.wait_s == pytest.approx(6300.0)
    assert p.riders == pytest.approx(30.0)
    t0 = datetime(2026, 11, 24, 22, 0, tzinfo=timezone.utc)
    deps = [Departure("S-0", "x", "t", t0 + timedelta(seconds=s)) for s in (0, *slots)]
    intervals = stop_intervals(deps)
    sum_h = sum(i.headway_s for i in intervals)
    sum_h2 = sum(i.headway_s ** 2 for i in intervals)
    assert float(sum_h2 / (2 * sum_h)) == pytest.approx(p.wait_s / p.riders) == pytest.approx(210.0)


def _left_behind(occupancy: int):
    inp = inputs([bus("L", distance_m=900.0, next_stop_idx=1, occupancy=occupancy),
                  bus("F", distance_m=100.0, next_stop_idx=1)],
                 queues={1: 6}, rates={1: rate(360)}, params=with_params(scoring_window_s=200))
    return project(inp)


def test_rider_left_behind_counts_through_the_longer_queue() -> None:
    full, empty = _left_behind(40), _left_behind(0)
    assert full.wait_s == pytest.approx(1550.0)
    assert empty.wait_s == pytest.approx(990.0)
    assert full.riders == pytest.approx(26.0)
    assert full.score_s == pytest.approx(full.wait_s)  # no separate term for riders left behind


def test_riders_still_queued_at_the_end_of_the_window_count_to_its_end() -> None:
    p = project(inputs([bus("B", distance_m=630.0, next_stop_idx=1)], queues={0: 4}))
    assert p.wait_s == pytest.approx(4 * 1800)


def test_saving_per_rider_with_a_reserve() -> None:
    inp = inputs([bus("B", distance_m=630.0, next_stop_idx=1, occupancy=10), bus("B-106", kind="reserve")],
                 queues={0: 4})
    base = project(inp)
    act = project(inp, Action("reserve_dispatch", "B-106"))
    assert base.wait_s == pytest.approx(7200.0) and base.riders == pytest.approx(4.0)
    assert act.wait_s == pytest.approx(480.0)
    assert act.score_s == pytest.approx(480.0 + 0.0 + 900.0)
    assert saving_s_per_rider(base, act) == 1455.0


def test_saving_is_rounded_to_a_tenth_and_safe_without_riders() -> None:
    p = project(inputs([bus("B", distance_m=630.0, next_stop_idx=1)], queues={0: 1}))
    assert saving_s_per_rider(replace(p, score_s=131.0, riders=3.0), replace(p, score_s=100.0, riders=3.0)) == 10.3
    assert saving_s_per_rider(replace(p, score_s=50.0, riders=0.0), replace(p, score_s=10.0, riders=0.0)) == 0.0


def test_evaluate_ranks_by_saving() -> None:
    inp = inputs([bus("B", distance_m=630.0, next_stop_idx=1, occupancy=10), bus("B-106", kind="reserve")],
                 queues={0: 4})
    scored = evaluate(inp, [Action("hold", "B", stop_idx=1, hold_s=30), Action("reserve_dispatch", "B-106")])
    assert [s.action.type for s in scored] == ["reserve_dispatch", "hold"]
    assert scored[0].saving_s == 1455.0
