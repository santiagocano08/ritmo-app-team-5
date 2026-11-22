"""Waiting buses (data owner decision 2026-11-20, research R7).

The 001 simulator reports `bus_position` at 0 m with a `trip_id` while a bus waits at P-883 for its
scheduled departure, both at the start of a run and during the terminal layover before trip n+1.
A bus is on the corridor from its `stop_departure` at the first stop until its `stop_arrival` at
the terminus. Before departing it is waiting: not on the corridor, not a "bus ahead", not counted;
its reports still count for the Estimated / `sources_down` rule.
"""
from __future__ import annotations

from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import cycle, docs
from src.data.tests.fixtures.silver_support import build, state

FIRST = bb.STOPS[0]
LAST = bb.TERMINUS


def _timeline() -> bb.Builder:
    b = bb.Builder("waiting")
    # B-101: departed P-883 at 0 s, driving.
    b.stop_departure("B-101", bb.trip_id("B-101"), FIRST, 0)
    b.drive("B-101", 0, 400)
    # B-102: waits at P-883 for its first trip (arrived at 300 s, has not departed).
    b.hold("B-102", bb.trip_id("B-102"), 0, 400, 0.0)
    b.stop_arrival("B-102", bb.trip_id("B-102"), FIRST, 300)
    # B-103: finished trip 1 and waits out the layover before trip 2.
    b.hold("B-103", bb.trip_id("B-103", 1), 0, 100, 5119.4)
    b.stop_arrival("B-103", bb.trip_id("B-103", 1), LAST, 100)
    b.stop_departure("B-103", bb.trip_id("B-103", 1), LAST, 110)
    b.hold("B-103", bb.trip_id("B-103", 2), 200, 400, 0.0)
    # B-104: left P-883 on trip 2 at 300 s (the departure step also reports 0 m).
    b.stop_departure("B-104", bb.trip_id("B-104", 2), FIRST, 300)
    b.drive("B-104", 300, 400, trip=bb.trip_id("B-104", 2))
    # B-105: waiting and silent since 100 s.
    b.hold("B-105", bb.trip_id("B-105"), 0, 100, 0.0)
    return b


def test_waiting_buses_are_not_on_the_corridor_departed_buses_are(silver_conn) -> None:
    bb.ingest_all(silver_conn, _timeline().events)
    build(silver_conn, 400)
    rows = state(silver_conn)
    for bus in ("B-101", "B-104"):
        assert rows[bus]["on_corridor"] is True and rows[bus]["waiting"] is False
        assert rows[bus]["operational_status"] == "in_service"
    for bus in ("B-102", "B-103", "B-105"):
        assert rows[bus]["on_corridor"] is False and rows[bus]["waiting"] is True
        assert rows[bus]["operational_status"] == "off_corridor"
    assert float(rows["B-104"]["distance_along_m"]) == 120.0


def test_a_waiting_bus_keeps_its_reports_for_the_estimated_rule(silver_conn) -> None:
    bb.ingest_all(silver_conn, _timeline().events)
    build(silver_conn, 400)
    rows = state(silver_conn)
    assert rows["B-102"]["data_quality"] == "live"
    assert rows["B-105"]["data_quality"] == "estimated"  # silent since 100 s


def test_a_bus_that_finished_a_trip_is_not_waiting(silver_conn) -> None:
    b = bb.Builder("finished")
    b.hold("B-101", bb.trip_id("B-101"), 0, 100, 5119.4)
    b.stop_arrival("B-101", bb.trip_id("B-101"), LAST, 100)
    bb.ingest_all(silver_conn, b.events)
    build(silver_conn, 110)
    row = state(silver_conn)["B-101"]
    assert row["on_corridor"] is False and row["waiting"] is False


def test_gold_ignores_waiting_buses_for_ahead_summary_and_metric(gold_conn) -> None:
    bb.ingest_all(gold_conn, _timeline().events)
    result = cycle(gold_conn, 400)
    d = docs(gold_conn, result.snapshot_id)
    buses = d["corridor_now"]["buses"]
    assert [b["bus_id"] for b in buses] == ["B-101", "B-104"]
    assert buses[0]["headway_ahead_s"] is None
    assert 300 <= buses[1]["headway_ahead_s"] <= 900
    assert [b["bus_state"] for b in buses] == ["leader", "regular"]
    assert d["corridor_now"]["summary"] == {"buses_in_service": 2, "n_bunched": 0, "n_gaps": 0}
    # 005: the metric is measured at stops from departures. Waiting buses have none, and this timeline has
    # departures without arrivals (no stop visit), so nothing is measured: not computable, no value, not 0.
    assert gold_conn.execute("SELECT n_headways, ewt_s, computable FROM gold.service_metric WHERE snapshot_id = %s",
                             (result.snapshot_id,)).fetchone() == (0, None, False)
    assert gold_conn.execute("SELECT count(*) FROM gold.service_metric_stop WHERE snapshot_id = %s AND "
                             "(n_headways <> 0 OR computable)", (result.snapshot_id,)).fetchone()[0] == 0
    # The silent waiting bus is still a silent source.
    assert d["source_status"]["status"] == "estimated"
    assert [s["bus_id"] for s in d["source_status"]["sources_down"]] == ["B-105"]
