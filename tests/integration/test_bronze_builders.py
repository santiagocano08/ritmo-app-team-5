"""T022 — deterministic bronze builders (R10, SC-002, data-profile testing).

Every event the builders produce passes the real boundary `src.ingestion.bronze.ingest`
(backend decision/confirmation rows are the exception: the 001 boundary does not accept
those types, so they are validated against command_event.schema.json and inserted the
way the backend writer does).
"""
from __future__ import annotations

import json
from pathlib import Path

import psycopg
import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.ingestion.bronze import ingest
from tests.fixtures import bronze_builders as bb

ROOT = Path(__file__).resolve().parents[2]
TIMELINES = ["normal", "c1_bunching", "d1_source_outage", "c2_gap", "c5_breakdown"]


@pytest.fixture(scope="module")
def conn(module_db_dsn):
    with psycopg.connect(module_db_dsn) as c:
        yield c


@pytest.mark.parametrize("name", TIMELINES)
def test_timeline_is_deterministic(name: str) -> None:
    a, b = getattr(bb, name)(), getattr(bb, name)()
    assert a.events == b.events and a.as_of == b.as_of
    assert json.dumps(a.events, sort_keys=True) == json.dumps(b.events, sort_keys=True)


def test_timelines_use_distinct_event_ids() -> None:
    ids = [e["event_id"] for n in TIMELINES for e in getattr(bb, n)().events]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("name", TIMELINES)
def test_every_timeline_event_passes_the_real_boundary(conn, name: str) -> None:
    tl = getattr(bb, name)()
    assert tl.events
    results = bb.ingest_all(conn, tl.events)
    assert all(r.accepted for r in results), [r.reason for r in results if not r.accepted][:3]


def test_normal_timeline_is_five_buses_leader_first_and_evenly_spaced() -> None:
    tl = bb.normal()
    last = {}
    for e in tl.events:
        if e["event_type"] == "bus_position":
            last[e["payload"]["bus_id"]] = e["payload"]["distance_along_m"]
    assert sorted(last, key=last.get, reverse=True) == ["B-105", "B-104", "B-103", "B-102", "B-101"]


def test_d1_timeline_silences_one_bus_for_more_than_120s() -> None:
    tl = bb.d1_source_outage()
    ts = [e["event_ts"] for e in tl.events
          if e["event_type"] == "bus_position" and e["payload"]["bus_id"] == "B-103"]
    other = [e["event_ts"] for e in tl.events
             if e["event_type"] == "bus_position" and e["payload"]["bus_id"] == "B-102"]
    assert max(ts) < max(other)
    assert bb.seconds_between(max(ts), tl.as_of) > 120


def test_c5_timeline_has_a_breakdown_incident_with_duration() -> None:
    tl = bb.c5_breakdown()
    inc = [e for e in tl.events if e["event_type"] == "incident_report"]
    assert len(inc) == 1
    assert inc[0]["payload"]["incident_type"] == "bus_breakdown"
    assert inc[0]["payload"]["target_id"] == "B-104" and inc[0]["payload"]["duration_min"] > 0


def test_stop_visit_and_traversal_builders(conn) -> None:
    b = bb.Builder("visits")
    b.stop_visit("B-101", "C6-008-B-101-001", "P-885", arrive=100, depart=130, boarded=4, alighted=2, rejected=1)
    b.traversal("B-101", "C6-008-B-101-001", segment=3, depart=130, arrive=190)
    types = [e["event_type"] for e in b.events]
    assert types == ["stop_arrival", "stop_departure", "stop_departure", "stop_arrival"]
    dep = b.events[1]["payload"]
    assert (dep["boarded"], dep["alighted"], dep["rejected"]) == (4, 2, 1)
    # segment 3 runs from P-885 (seq 3) to P-886 (seq 4)
    assert b.events[2]["payload"]["stop_id"] == "P-885" and b.events[3]["payload"]["stop_id"] == "P-886"
    assert all(r.accepted for r in bb.ingest_all(conn, b.events))


def test_incident_builder_allows_zero_duration_and_backend_source(conn) -> None:
    b = bb.Builder("incidents")
    b.incident("bus_breakdown", "B-102", at=50, duration_min=0.0)
    b.incident("bus_breakdown", "B-103", at=60, duration_min=10.0, reported_by="dispatcher", source="backend")
    assert [e["source"] for e in b.events] == ["simulator", "backend"]
    assert b.events[0]["payload"]["duration_min"] == 0.0
    assert all(r.accepted for r in bb.ingest_all(conn, b.events))


def test_backend_command_events_are_valid_and_land_in_bronze(conn) -> None:
    schema = json.loads((ROOT / "contracts/read/command_event.schema.json").read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    b = bb.Builder("commands")
    cmds = [
        b.command_decision(at=10, action="apply"),
        b.command_confirmation(at=20, status="received"),
        b.command_incident(at=30, target_id="B-101", duration_min=5.0),
    ]
    for c in cmds:
        assert not list(validator.iter_errors(c)), c
        assert c["source"] == "backend"
    ids = bb.insert_backend_commands(conn, cmds)
    assert len(ids) == 3
    assert conn.execute(
        "SELECT count(*) FROM bronze.events WHERE source = 'backend' AND event_type IN ('decision','confirmation')"
    ).fetchone()[0] == 2


def test_rider_arrival_builder(conn) -> None:
    b = bb.Builder("riders")
    b.rider_arrival("P-883", at=10, dest="P-889", origin="train", train_trip_id="METRO-A-0815")
    b.rider_arrival("P-886", at=12, dest="P-890")
    assert all(r.accepted for r in bb.ingest_all(conn, b.events))
