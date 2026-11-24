"""T038 — gold objects equal the fixture scenarios (SC-002, US2 scenarios 1-4).

Compares bus order, bus_state, data_quality, status, sources_down and summary counts, not
headway values. Crafted bronze comes from `tests/fixtures/bronze_builders.py`.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import clear_all, cycle, docs, fixture
from src.data.tests.fixtures.silver_support import T0

SCENARIOS = {
    "normal": bb.normal,
    "c1_bunching": bb.c1_bunching,
    "d1_source_outage": bb.d1_source_outage,
    "c2_gap": bb.c2_gap,
    "c5_breakdown": bb.c5_breakdown,
}


def _as_of_seconds(tl: bb.Timeline) -> float:
    return (datetime.fromisoformat(tl.as_of) - T0).total_seconds()


def _view(corridor_now: dict) -> list[tuple]:
    return [(b["bus_id"], b["bus_state"], b["data_quality"]) for b in corridor_now["buses"]]


@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_gold_matches_the_scenario_fixture(gold_conn, scenario: str) -> None:
    clear_all(gold_conn)
    tl = SCENARIOS[scenario]()
    assert all(r.accepted for r in bb.ingest_all(gold_conn, tl.events))
    result = cycle(gold_conn, _as_of_seconds(tl))
    got = docs(gold_conn, result.snapshot_id)
    want_cn, want_ss = fixture(scenario, "corridor_now"), fixture(scenario, "source_status")

    assert _view(got["corridor_now"]) == _view(want_cn)
    assert got["corridor_now"]["summary"] == want_cn["summary"]
    assert got["corridor_now"]["corridor_id"] == "C6-008" and got["corridor_now"]["direction"] == 1
    assert got["source_status"]["status"] == want_ss["status"]
    assert [(s["bus_id"], s["since"]) for s in got["source_status"]["sources_down"]] == \
        [(s["bus_id"], _iso_of(s["bus_id"], tl)) for s in want_ss["sources_down"]]
    for entry in got["corridor_now"]["buses"]:
        assert entry["headway_planned_s"] == 420  # config.corridor_settings since issue #42


def _iso_of(bus_id: str, tl: bb.Timeline) -> str:
    """`since` expected: the event time of the bus's last report in the crafted timeline."""
    last = max(e["event_ts"] for e in tl.events
               if e["event_type"] == "bus_position" and e["payload"]["bus_id"] == bus_id)
    return last


def test_headway_values_of_the_constant_speed_timelines_are_the_start_offsets(gold_conn) -> None:
    clear_all(gold_conn)
    tl = bb.normal()
    bb.ingest_all(gold_conn, tl.events)
    result = cycle(gold_conn, 3000)
    buses = {b["bus_id"]: b for b in docs(gold_conn, result.snapshot_id)["corridor_now"]["buses"]}
    assert buses["B-105"]["headway_ahead_s"] is None
    for bus_id in ("B-104", "B-103", "B-102", "B-101"):
        assert buses[bus_id]["headway_ahead_s"] == pytest.approx(600.0, abs=0.01)


def test_interpolation_uses_only_the_current_trip_of_the_bus_ahead(gold_conn) -> None:
    clear_all(gold_conn)
    b = bb.Builder("trips")
    # B-105 finished nothing but restarted: its old trip 001 reached 3,000 m early; trip 002 starts at 0 m.
    b.position("B-105", bb.trip_id("B-105", 1), 0, 3000.0)
    b.drive("B-105", 1000, 2000, trip=bb.trip_id("B-105", 2))        # 0 -> 1,200 m by 2000 s
    b.drive("B-101", 1500, 2000)                                      # 0 -> 600 m by 2000 s
    bb.ingest_all(gold_conn, b.events)
    result = cycle(gold_conn, 2000)
    buses = {x["bus_id"]: x for x in docs(gold_conn, result.snapshot_id)["corridor_now"]["buses"]}
    # Trip 002 passed 600 m at 1500 s; B-101 reports at 2000 s -> 500 s. Mixing in trip 001 would give 2,000 s.
    assert buses["B-101"]["headway_ahead_s"] == pytest.approx(500.0, abs=0.01)
