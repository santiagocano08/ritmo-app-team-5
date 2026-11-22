"""T005 — the local hour of every projected step (006 FR-003, FR-005).

Segments take 400 s in local hour 17 and 800 s in hour 18. A bus at the start of segment 0 at 17:55:00
(300 s before 18:00:00):
- 300 s at hour-17 speed cover 300/400 = 0.75 of the segment; the remaining 0.25 at hour-18 speed takes
  0.25 * 800 = 200 s. Arrival at stop 1: 500; dwell 10 -> departs 510.
- Segment 1 starts at 510 (hour 18): 800 s -> arrives 1310, departs 1320. Segment 2 would arrive at 2120,
  after the 1,800 s window.
The same bus at 17:00 uses hour 17 until 18:00 (3,600 s away): arrivals 400, 810, 1220 (last stop, empty
bus, dwell 10), departures 410, 820, 1230.
A street rate of 0 riders/h in hour 17 and 360/h in hour 18 gives the queue at stop 1 at t = 500:
0.1 * (500 - 300) = 20 riders -> dwell 10 + 60 = 70 -> departs 570; segment 1 -> 1370, departs 1380.
"""
from __future__ import annotations

from src.data.rules.projector import project
from src.data.tests.unit.projector_support import AS_OF_1700, AS_OF_1755, bus, inputs, m1_flat

M1 = m1_flat(per_hour={17: 400.0, 18: 800.0}, n_segments=3)


def run(as_of, rates=None):
    return dict(project(inputs([bus("B-101", distance_m=0.0, next_stop_idx=1)], m1=M1, as_of=as_of,
                               rates=rates)).departures)


def test_hour_18_values_after_the_boundary() -> None:
    assert run(AS_OF_1755) == {("B-101", 1): 510, ("B-101", 2): 1320}


def test_same_input_at_1700_uses_hour_17() -> None:
    d = run(AS_OF_1700)
    assert d == {("B-101", 1): 410, ("B-101", 2): 820, ("B-101", 3): 1230}


def test_rate_changes_at_the_boundary() -> None:
    zero_then_360 = tuple(360.0 if h == 18 else 0.0 for h in range(24))
    d = run(AS_OF_1755, rates={1: zero_then_360})
    assert d == {("B-101", 1): 570, ("B-101", 2): 1380}
