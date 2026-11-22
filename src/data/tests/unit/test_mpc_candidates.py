"""T022 — which actions are evaluated (006 FR-008, FR-009, FR-016, SC-005; research R12).

"Candidate only when" is a filter, not the decision: a normal snapshot has no candidate at all.
Crafted corridor of `projector_support`: 4 stops (indices 0..3), buses in service at 630 m (next stop 1).
"""
from __future__ import annotations

import pytest

from src.data.rules.mpc import generate_candidates
from src.data.tests.unit.projector_support import bus, facts, inputs


def _types(cands) -> list[str]:
    return [c.action.type for c in cands]


def _normal_buses():
    return [bus("B-101", distance_m=2500.0, next_stop_idx=3),
            bus("B-102", distance_m=630.0, next_stop_idx=1),
            bus("B-103", kind="waiting"), bus("B-106", kind="reserve")]


NORMAL = {"B-101": "leader", "B-102": "regular"}


def test_a_normal_snapshot_has_no_candidate() -> None:
    """No bunched, gap or broken bus and no queue above 20: nothing is evaluated (SC-005)."""
    assert generate_candidates(inputs(_normal_buses(), next_departures=(300,)), facts(NORMAL)) == []


def test_one_bunched_follower_gives_ten_candidates() -> None:
    buses = [bus("B-101", distance_m=2500.0, next_stop_idx=3), bus("B-102", distance_m=630.0, next_stop_idx=1),
             bus("B-103", kind="waiting"), bus("B-106", kind="reserve")]
    cands = generate_candidates(inputs(buses, next_departures=(300,)), facts({"B-101": "leader", "B-102": "bunched"}))
    assert len(cands) == 10
    kinds = _types(cands)
    assert kinds.count("slow_down") == 2 and kinds.count("hold") == 3
    assert kinds.count("adjust_departure") == 4 and kinds.count("reserve_dispatch") == 1
    # catalog order: reserve, slow down, hold, adjust (ties are broken the same way later)
    assert kinds == ["reserve_dispatch", "slow_down", "slow_down", "hold", "hold", "hold",
                     "adjust_departure", "adjust_departure", "adjust_departure", "adjust_departure"]
    assert {c.case for c in cands} == {"C1"}
    holds = [c.action for c in cands if c.action.type == "hold"]
    assert [h.hold_s for h in holds] == [30, 60, 90] and {h.bus_id for h in holds} == {"B-102"}
    assert {h.stop_idx for h in holds} == {1}  # the next stop of the follower
    slows = [c.action for c in cands if c.action.type == "slow_down"]
    assert [s.share for s in slows] == [0.10, 0.20] and {s.duration_s for s in slows} == {300}
    assert [c.action.shift_s for c in cands if c.action.type == "adjust_departure"] == [-120, -60, 60, 120]
    reserve = next(c.action for c in cands if c.action.type == "reserve_dispatch")
    assert reserve.bus_id == "B-106" and reserve.stop_idx == 0
    adjust = next(c.action for c in cands if c.action.type == "adjust_departure")
    assert adjust.bus_id == "B-103" and adjust.stop_idx == 0


def test_a_gap_makes_skip_stop_a_candidate_for_the_bus_behind_the_gap() -> None:
    buses = [bus("B-101", distance_m=2500.0, next_stop_idx=3), bus("B-102", distance_m=630.0, next_stop_idx=1),
             bus("B-103", kind="waiting"), bus("B-106", kind="reserve")]
    cands = generate_candidates(inputs(buses, next_departures=(300,)), facts({"B-101": "leader", "B-102": "gap"}))
    skip = [c for c in cands if c.action.type == "skip_stop"]
    assert len(skip) == 1 and skip[0].case == "C2"
    assert skip[0].action.bus_id == "B-102" and skip[0].action.stop_idx == 1
    assert "hold" not in _types(cands) and "slow_down" not in _types(cands)
    assert _types(cands).count("adjust_departure") == 4 and _types(cands).count("reserve_dispatch") == 1
    assert {c.case for c in cands} == {"C2"}


@pytest.mark.parametrize("queue,expected", [(20, 0), (21, 5)])
def test_a_queue_above_half_a_bus_is_trouble(queue, expected) -> None:
    cands = generate_candidates(inputs(_normal_buses(), queues={2: queue}, next_departures=(300,)), facts(NORMAL))
    assert len(cands) == expected
    assert set(_types(cands)) <= {"adjust_departure", "reserve_dispatch"}


def test_a_breakdown_needs_a_free_reserve_and_a_free_driver() -> None:
    buses = [bus("B-101", distance_m=900.0, next_stop_idx=1, broken_until=600.0), bus("B-103", kind="waiting"),
             bus("B-106", kind="reserve")]
    states = {"B-101": "broken_down"}
    cands = generate_candidates(inputs(buses, next_departures=(300,)), facts(states))
    assert "reserve_dispatch" in _types(cands) and {c.case for c in cands} == {"C5"}
    assert "reserve_dispatch" not in _types(generate_candidates(inputs(buses, next_departures=(300,)),
                                                               facts(states, drivers=0)))
    no_reserve = [b for b in buses if b.kind != "reserve"]
    assert "reserve_dispatch" not in _types(generate_candidates(inputs(no_reserve, next_departures=(300,)),
                                                               facts(states)))
    assert "hold" not in _types(cands)  # a broken bus is never held or slowed


def test_the_first_free_reserve_in_id_order_is_used() -> None:
    buses = [bus("B-102", distance_m=630.0, next_stop_idx=1), bus("B-107", kind="reserve"),
             bus("B-106", kind="reserve")]
    cands = generate_candidates(inputs(buses), facts({"B-102": "bunched"}))
    assert [c.action.bus_id for c in cands if c.action.type == "reserve_dispatch"] == ["B-106"]


def test_no_action_targets_an_estimated_or_sources_down_bus() -> None:
    est = [bus("B-102", distance_m=630.0, next_stop_idx=1, quality="estimated"), bus("B-106", kind="reserve")]
    cands = generate_candidates(inputs(est), facts({"B-102": "bunched"}))
    assert not [c for c in cands if c.action.bus_id == "B-102"]
    down = [bus("B-102", distance_m=630.0, next_stop_idx=1)]
    cands = generate_candidates(inputs(down), facts({"B-102": "bunched"}, down=("B-102",)))
    assert not [c for c in cands if c.action.bus_id == "B-102"]


def test_no_stop_left_before_the_end_is_not_a_candidate() -> None:
    last = [bus("B-102", distance_m=2500.0, next_stop_idx=3)]  # the next stop is the last one (index 3)
    assert not [c for c in generate_candidates(inputs(last), facts({"B-102": "bunched"}))
                if c.action.type in ("hold", "slow_down", "skip_stop")]
    gap = generate_candidates(inputs(last), facts({"B-102": "gap"}))
    assert "skip_stop" not in _types(gap)


def test_only_enabled_stops_receive_an_action() -> None:
    buses = [bus("B-102", distance_m=630.0, next_stop_idx=1)]
    cands = generate_candidates(inputs(buses), facts({"B-102": "bunched"}, enabled={0, 2, 3}))
    assert not [c for c in cands if c.action.type in ("hold", "slow_down")]


def test_a_bus_dwelling_now_is_acted_on_at_the_stop_after() -> None:
    """The executor matches a visit that starts after the decision, so the target is never the current stop."""
    buses = [bus("B-102", distance_m=1000.0, next_stop_idx=2, at_stop=(-5.0, 20.0))]
    cands = generate_candidates(inputs(buses), facts({"B-102": "bunched"}))
    assert {c.action.stop_idx for c in cands if c.action.type == "hold"} == {2}


def test_candidates_do_not_depend_on_the_input_order() -> None:
    buses = [bus("B-101", distance_m=2500.0, next_stop_idx=3), bus("B-102", distance_m=630.0, next_stop_idx=1),
             bus("B-103", kind="waiting"), bus("B-106", kind="reserve")]
    f = facts({"B-101": "leader", "B-102": "bunched"})
    a = generate_candidates(inputs(buses, next_departures=(300,)), f)
    b = generate_candidates(inputs(list(reversed(buses)), next_departures=(300,)), f)
    assert a == b
