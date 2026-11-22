"""006 T049b — rows of the projection record from a projection (FR-035, SC-001, SC-016).

Crafted case (a) of `test_projector_crafted.py`: one bus at 630 m, 4 stops, M1 = 100 s, departures 50, 160 and 270 s
after `as_of` at stops 1, 2 and 3 (hand-computed there). The record is those three departures, with the stop ids
of the crafted corridor (`S-1`, `S-2`, `S-3`), `lead_s` equal to the seconds and the timestamp `as_of + seconds`.
"""
from __future__ import annotations

from datetime import timedelta

from src.data.rules.projector import project, projection_record
from src.data.tests.unit.projector_support import AS_OF_1700, bus, inputs, with_params


def test_rows_equal_the_hand_computed_departures() -> None:
    inp = inputs([bus("B-101", distance_m=630.0, next_stop_idx=1)])
    rows = projection_record(inp, project(inp))
    assert rows == (("B-101", "S-1", AS_OF_1700 + timedelta(seconds=50), 50.0),
                    ("B-101", "S-2", AS_OF_1700 + timedelta(seconds=160), 160.0),
                    ("B-101", "S-3", AS_OF_1700 + timedelta(seconds=270), 270.0))


def test_rows_are_sorted_by_bus_then_stop_order_and_repeatable() -> None:
    buses = [bus("L", distance_m=900.0, next_stop_idx=1), bus("F", distance_m=100.0, next_stop_idx=1)]
    inp = inputs(buses, queues={1: 6})
    first = projection_record(inp, project(inp))
    again = projection_record(inp, project(inp))
    assert first == again
    assert [(r[0], r[1]) for r in first] == [("F", "S-1"), ("F", "S-2"), ("F", "S-3"),
                                             ("L", "S-1"), ("L", "S-2"), ("L", "S-3")]
    shuffled = projection_record(inputs(list(reversed(buses)), queues={1: 6}), project(inputs(list(reversed(buses)),
                                                                                              queues={1: 6})))
    assert shuffled == first


def test_nothing_beyond_the_window_is_returned() -> None:
    inp = inputs([bus("B-101", distance_m=630.0, next_stop_idx=1)], params=with_params(scoring_window_s=150))
    rows = projection_record(inp, project(inp))
    assert [r[1] for r in rows] == ["S-1"]
    assert all(0 <= r[3] <= 150 for r in rows)


def test_a_bus_with_no_departure_in_the_window_has_no_row() -> None:
    # 5 s window: the first departure of the bus is at 50 s.
    inp = inputs([bus("B-101", distance_m=630.0, next_stop_idx=1)], params=with_params(scoring_window_s=5))
    assert projection_record(inp, project(inp)) == ()


def test_a_bus_dwelling_now_has_a_lead_of_its_remaining_dwell() -> None:
    inp = inputs([bus("B-101", next_stop_idx=2, at_stop=(-5.0, 20.0))])
    rows = projection_record(inp, project(inp))
    assert rows[0][:2] == ("B-101", "S-1") and rows[0][3] == 15.0
