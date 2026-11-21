"""T020 — Peak-hour (fixed 17:00) trip duration and reserve buses (SC-006)."""
from __future__ import annotations

from datetime import datetime

from src.simulator.engine import run

FIRST, LAST = "P-883", "P-900"


def _trip_minutes(events) -> list[float]:
    dep, out = {}, []
    for e in events:
        p = e["payload"]
        ts = datetime.fromisoformat(e["event_ts"].replace("Z", "+00:00"))
        if e["event_type"] == "stop_departure" and p["stop_id"] == FIRST:
            dep[(p["bus_id"], p["trip_id"])] = ts
        elif e["event_type"] == "stop_arrival" and p["stop_id"] == LAST:
            out.append((ts - dep[(p["bus_id"], p["trip_id"])]).total_seconds() / 60)
    return out


def test_peak_trip_is_about_25_minutes() -> None:
    trips = _trip_minutes(run(42, 3600, start_hour=17))
    assert len(trips) >= 3
    mean = sum(trips) / len(trips)
    assert 20.0 <= mean <= 30.0, mean


def test_reserve_buses_emit_nothing() -> None:
    ids = {e["payload"].get("bus_id") for e in run(42, 600)}
    assert not ({"B-106", "B-107"} & ids)
    assert {"B-101", "B-102", "B-103", "B-104", "B-105"} <= ids
