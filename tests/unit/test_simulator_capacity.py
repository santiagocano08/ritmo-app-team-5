"""T019 — Capacity and FIFO boarding (FR-021)."""
from __future__ import annotations

from collections import deque

from src.simulator.engine import run
from src.simulator.model import CAPACITY, Rider, board_fifo


def test_board_fifo_order_and_rejection() -> None:
    q = deque(Rider(dest_idx=5, ts=i) for i in range(10))
    boarded, rejected = board_fifo(q, free=4)
    assert [r.ts for r in boarded] == [0, 1, 2, 3]
    assert rejected == 6
    assert [r.ts for r in q] == [4, 5, 6, 7, 8, 9]  # the rest keep waiting, in order


def test_board_fifo_no_free_seats() -> None:
    q = deque(Rider(dest_idx=5, ts=i) for i in range(3))
    boarded, rejected = board_fifo(q, free=0)
    assert boarded == [] and rejected == 3


def test_occupancy_never_exceeds_capacity_under_overload() -> None:
    events = list(run(42, 3600, demand_scale=25.0))
    assert CAPACITY == 40
    assert all(e["payload"]["occupancy"] <= 40 for e in events if "occupancy" in e["payload"])
    stops = [e["payload"] for e in events if e["event_type"] == "stop_arrival"]
    assert sum(p["rejected"] for p in stops) > 0
    assert all(p["boarded"] + p["rejected"] >= p["boarded"] for p in stops)


def test_departure_occupancy_is_arrival_minus_alighted_plus_boarded() -> None:
    events = list(run(42, 3600, demand_scale=25.0))
    arr = {}
    for e in events:
        p = e["payload"]
        if e["event_type"] == "stop_arrival":
            arr[(p["bus_id"], p["stop_id"], p["trip_id"])] = p
        elif e["event_type"] == "stop_departure":
            a = arr[(p["bus_id"], p["stop_id"], p["trip_id"])]
            assert p["occupancy"] == a["occupancy"] - a["alighted"] + a["boarded"]


def test_base_case_17h_demand_is_low_and_buses_do_not_fill() -> None:
    events = list(run(42, 3600, start_hour=17))
    arrivals = [e for e in events if e["event_type"] == "rider_arrival"]
    assert 40 <= len(arrivals) <= 110
    assert max(e["payload"]["occupancy"] for e in events if "occupancy" in e["payload"]) < 40
    assert sum(e["payload"]["rejected"] for e in events if e["event_type"] == "stop_arrival") == 0
