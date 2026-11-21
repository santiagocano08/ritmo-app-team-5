"""T026 — silver current state (US1 scenarios 1-3, FR-003, FR-007-FR-011, R4, R7)."""
from __future__ import annotations

from datetime import timedelta

import pytest
from psycopg.types.json import Jsonb

from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.silver_support import at, build, state


def _load(conn, builder: bb.Builder) -> None:
    results = bb.ingest_all(conn, builder.events)
    assert all(r.accepted for r in results)


def test_one_row_per_bus_with_its_latest_position_and_neighbour_stops(silver_conn) -> None:
    tl = bb.normal()
    bb.ingest_all(silver_conn, tl.events)
    build(silver_conn, 3000)
    rows = state(silver_conn)
    assert sorted(rows) == ["B-101", "B-102", "B-103", "B-104", "B-105"]
    # B-105 started at 0 and drives at 1.2 m/s: 3000 s -> 3600 m (last sample at 3000 s).
    assert float(rows["B-105"]["distance_along_m"]) == pytest.approx(3600.0)
    assert rows["B-105"]["position_ts"] == at(3000)
    assert rows["B-105"]["last_report_ts"] == at(3000)
    assert rows["B-105"]["trip_id"] == rows["B-105"]["position_trip_id"] == bb.trip_id("B-105")
    assert rows["B-105"]["data_quality"] == "live"
    assert rows["B-105"]["on_corridor"] is True
    assert rows["B-105"]["operational_status"] == "in_service"
    assert rows["B-105"]["as_of_ts"] == at(3000)
    assert (rows["B-105"]["prev_stop_id"], rows["B-105"]["next_stop_id"]) == ("P-892", "P-893")


def test_bus_dwelling_at_a_stop_has_that_stop_as_previous_and_the_next_as_next(silver_conn) -> None:
    b = bb.Builder("dwell")
    b.position("B-101", bb.trip_id("B-101"), 100, 3240.5)
    _load(silver_conn, b)
    build(silver_conn, 100)
    row = state(silver_conn)["B-101"]
    assert (row["prev_stop_id"], row["next_stop_id"]) == ("P-891", "P-892")


def test_before_first_stop_has_no_previous_and_past_the_last_has_no_next(silver_conn) -> None:
    b = bb.Builder("ends")
    b.position("B-101", bb.trip_id("B-101"), 10, 0.0)
    b.position("B-102", bb.trip_id("B-102"), 10, 5119.4)
    _load(silver_conn, b)
    build(silver_conn, 10)
    rows = state(silver_conn)
    assert (rows["B-101"]["prev_stop_id"], rows["B-101"]["next_stop_id"]) == ("P-883", "P-884")
    assert (rows["B-102"]["prev_stop_id"], rows["B-102"]["next_stop_id"]) == ("P-900", None)


def test_ties_on_event_time_are_broken_by_the_higher_bronze_id(silver_conn) -> None:
    b = bb.Builder("ties")
    b.position("B-101", bb.trip_id("B-101"), 50, 100.0)
    b.position("B-101", bb.trip_id("B-101"), 50, 200.0)  # same event_ts, ingested later
    _load(silver_conn, b)
    build(silver_conn, 60)
    assert float(state(silver_conn)["B-101"]["distance_along_m"]) == 200.0


def test_events_are_taken_by_event_time_not_arrival_order(silver_conn) -> None:
    b = bb.Builder("order")
    b.position("B-101", bb.trip_id("B-101"), 80, 300.0)
    b.position("B-101", bb.trip_id("B-101"), 40, 100.0)  # older event, arrives later
    _load(silver_conn, b)
    build(silver_conn, 90)
    assert float(state(silver_conn)["B-101"]["distance_along_m"]) == 300.0


@pytest.mark.parametrize("age_s,quality", [(0, "live"), (119, "live"), (120, "live"), (121, "estimated"), (600, "estimated")])
def test_estimated_rule_is_strictly_more_than_120_seconds(silver_conn, age_s: int, quality: str) -> None:
    b = bb.Builder(f"est{age_s}")
    b.position("B-101", bb.trip_id("B-101"), 1000, 500.0)
    _load(silver_conn, b)
    build(silver_conn, 1000 + age_s)
    row = state(silver_conn)["B-101"]
    assert row["data_quality"] == quality
    assert float(row["distance_along_m"]) == 500.0  # kept, never extrapolated (FR-010)
    assert row["last_report_ts"] == at(1000)


def test_an_estimated_bus_returns_to_live_with_a_new_report(silver_conn) -> None:
    b = bb.Builder("revive")
    b.position("B-101", bb.trip_id("B-101"), 1000, 500.0)
    _load(silver_conn, b)
    build(silver_conn, 1200)
    assert state(silver_conn)["B-101"]["data_quality"] == "estimated"
    b2 = bb.Builder("revive2")
    b2.position("B-101", bb.trip_id("B-101"), 1190, 540.0)
    _load(silver_conn, b2)
    build(silver_conn, 1200)
    row = state(silver_conn)["B-101"]
    assert row["data_quality"] == "live"
    assert float(row["distance_along_m"]) == 540.0


def test_a_backend_event_never_refreshes_the_last_report(silver_conn) -> None:
    b = bb.Builder("backend")
    b.position("B-101", bb.trip_id("B-101"), 1000, 500.0)
    b.position("B-101", bb.trip_id("B-101"), 1190, 900.0, source="backend")
    _load(silver_conn, b)
    build(silver_conn, 1200)
    row = state(silver_conn)["B-101"]
    assert row["last_report_ts"] == at(1000)
    assert float(row["distance_along_m"]) == 500.0
    assert row["data_quality"] == "estimated"


def test_a_bus_that_never_reported_has_no_row_and_backend_only_does_not_create_one(silver_conn) -> None:
    b = bb.Builder("never")
    b.position("B-101", bb.trip_id("B-101"), 10, 5.0)
    b.position("B-104", bb.trip_id("B-104"), 10, 5.0, source="backend")
    _load(silver_conn, b)
    build(silver_conn, 20)
    assert sorted(state(silver_conn)) == ["B-101"]


def test_stop_arrival_and_departure_count_as_reports_for_freshness(silver_conn) -> None:
    b = bb.Builder("freshness")
    trip = bb.trip_id("B-101")
    b.position("B-101", trip, 1000, 500.0)
    b.stop_arrival("B-101", trip, "P-885", 1100)
    _load(silver_conn, b)
    build(silver_conn, 1200)
    row = state(silver_conn)["B-101"]
    assert row["last_report_ts"] == at(1100)
    assert row["data_quality"] == "live"
    assert float(row["distance_along_m"]) == 500.0  # latest *position*, not the arrival


def test_bus_that_reached_the_terminus_is_off_the_corridor(silver_conn) -> None:
    b = bb.Builder("terminus")
    trip = bb.trip_id("B-101")
    b.position("B-101", trip, 1000, 5100.0)
    b.stop_arrival("B-101", trip, "P-900", 1010)
    _load(silver_conn, b)
    build(silver_conn, 1020)
    row = state(silver_conn)["B-101"]
    assert row["on_corridor"] is False
    assert row["operational_status"] == "off_corridor"


def test_a_new_trip_after_the_terminus_is_on_the_corridor_again(silver_conn) -> None:
    b = bb.Builder("newtrip")
    old, new = bb.trip_id("B-101", 1), bb.trip_id("B-101", 2)
    b.stop_arrival("B-101", old, "P-900", 1010)
    b.position("B-101", new, 1500, 10.0)
    _load(silver_conn, b)
    build(silver_conn, 1510)
    row = state(silver_conn)["B-101"]
    assert row["trip_id"] == new and row["on_corridor"] is True
    assert row["operational_status"] == "in_service"


def test_reserve_bus_is_reserve_when_off_corridor_and_in_service_when_dispatched(silver_conn) -> None:
    b = bb.Builder("reserve")
    old = bb.trip_id("B-106", 1)
    b.stop_arrival("B-106", old, "P-900", 1010)  # roster says reserve, finished a trip
    b.position("B-107", bb.trip_id("B-107"), 1000, 40.0)  # reserve injected on the corridor
    b.stop_arrival("B-101", bb.trip_id("B-101"), "P-900", 1010)  # in-service roster, finished
    _load(silver_conn, b)
    build(silver_conn, 1020)
    rows = state(silver_conn)
    assert rows["B-106"]["operational_status"] == "reserve"
    assert rows["B-107"]["operational_status"] == "in_service"
    assert rows["B-101"]["operational_status"] == "off_corridor"
    assert "B-105" not in rows  # undispatched buses have no row at all


def test_undispatched_reserve_buses_have_no_row(silver_conn) -> None:
    bb.ingest_all(silver_conn, bb.normal().events)
    build(silver_conn, 3000)
    assert {"B-106", "B-107"}.isdisjoint(state(silver_conn))


def test_broken_down_takes_precedence_while_the_incident_is_active(silver_conn) -> None:
    tl = bb.c5_breakdown()  # B-104 breakdown at 1500 s, 60 min
    bb.ingest_all(silver_conn, tl.events)
    build(silver_conn, 3000)
    rows = state(silver_conn)
    assert rows["B-104"]["operational_status"] == "broken_down"
    assert rows["B-104"]["data_quality"] == "live"
    assert all(rows[b]["operational_status"] == "in_service" for b in ("B-101", "B-102", "B-103", "B-105"))


def test_breakdown_not_yet_started_or_already_ended_does_not_apply(silver_conn) -> None:
    b = bb.Builder("window")
    b.position("B-101", bb.trip_id("B-101"), 1000, 100.0)
    b.incident("bus_breakdown", "B-101", at=1100, duration_min=1.0)  # [1100, 1160)
    _load(silver_conn, b)
    build(silver_conn, 1099)
    assert state(silver_conn)["B-101"]["operational_status"] == "in_service"
    build(silver_conn, 1159)
    assert state(silver_conn)["B-101"]["operational_status"] == "broken_down"
    build(silver_conn, 1160)
    assert state(silver_conn)["B-101"]["operational_status"] == "in_service"


def test_an_incident_of_another_type_or_target_does_not_break_the_bus(silver_conn) -> None:
    b = bb.Builder("other")
    b.position("B-101", bb.trip_id("B-101"), 1000, 100.0)
    b.incident("stop_closed", "P-885", at=1000, duration_min=30.0)
    b.incident("other", "B-101", at=1000, duration_min=30.0)
    b.incident("bus_breakdown", "B-102", at=1000, duration_min=30.0)
    _load(silver_conn, b)
    build(silver_conn, 1050)
    assert state(silver_conn)["B-101"]["operational_status"] == "in_service"


def test_a_backend_breakdown_incident_counts(silver_conn) -> None:
    b = bb.Builder("backend-inc")
    b.position("B-101", bb.trip_id("B-101"), 1000, 100.0)
    _load(silver_conn, b)
    bb.insert_backend_commands(silver_conn, [b.command_incident(1010, "B-101", duration_min=10.0)])
    build(silver_conn, 1050)
    assert state(silver_conn)["B-101"]["operational_status"] == "broken_down"


def test_events_later_than_as_of_or_beyond_m_are_ignored(silver_conn) -> None:
    b = bb.Builder("cutoff")
    trip = bb.trip_id("B-101")
    b.position("B-101", trip, 100, 10.0)
    b.position("B-101", trip, 200, 20.0)  # after as_of
    _load(silver_conn, b)
    build(silver_conn, 150)
    assert float(state(silver_conn)["B-101"]["distance_along_m"]) == 10.0

    b2 = bb.Builder("cutoff2")
    b2.position("B-101", trip, 140, 14.0)  # inside the time window but id > M
    m = silver_conn.execute("SELECT max(id) FROM bronze.events").fetchone()[0]
    _load(silver_conn, b2)
    build(silver_conn, 150, max_bronze_id=m)
    assert float(state(silver_conn)["B-101"]["distance_along_m"]) == 10.0
    build(silver_conn, 150)
    assert float(state(silver_conn)["B-101"]["distance_along_m"]) == 14.0


def test_arrival_time_is_never_used(silver_conn) -> None:
    # Bronze is insert-only, so the odd arrival_ts is written at insert time.
    event = bb.Builder("arrival").position("B-101", bb.trip_id("B-101"), 100, 10.0)
    silver_conn.execute(
        "INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload) "
        "VALUES (%s, %s, %s, %s, %s, now() + interval '30 days', %s)",
        (event["source"], event["event_id"], event["schema_version"], event["event_type"],
         event["event_ts"], Jsonb(event["payload"])))
    silver_conn.commit()
    build(silver_conn, 150)
    row = state(silver_conn)["B-101"]
    assert row["last_report_ts"] == at(100)
    assert row["data_quality"] == "live"


def test_empty_bronze_gives_empty_silver(silver_conn) -> None:
    build(silver_conn, 100)
    assert state(silver_conn) == {}


def test_as_of_is_stored_on_every_row(silver_conn) -> None:
    bb.ingest_all(silver_conn, bb.d1_source_outage().events)
    build(silver_conn, 3000)
    assert {r["as_of_ts"] for r in state(silver_conn).values()} == {at(3000)}
    assert at(3000) - at(2875) == timedelta(seconds=125)
    assert state(silver_conn)["B-103"]["data_quality"] == "estimated"
