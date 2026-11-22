"""T040 — idempotent ingestion and recompute (SC-004, FR-005, US2 scenario 7, R5)."""
from __future__ import annotations

from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import count, cycle
from src.data.tests.fixtures.silver_support import dump

GOLD_TABLES = ("snapshots", "source_status", "corridor_now", "service_metric", "decision_inputs",
               "service_metric_stop", "stop_ewt_band", "stop_boarding_band")


def _gold_dump(conn) -> dict[str, list]:
    out = {}
    for table in GOLD_TABLES:
        rows = conn.execute(f"SELECT * FROM gold.{table} ORDER BY 1, 2, 3").fetchall()  # noqa: S608 - fixed names
        out[table] = [tuple(repr(v) for v in r) for r in rows]
    return out


def test_reingesting_the_same_batch_and_recomputing_changes_nothing(gold_conn) -> None:
    events = bb.c1_bunching().events
    assert all(r.accepted for r in bb.ingest_all(gold_conn, events))
    first = cycle(gold_conn, 2400)
    silver_before, gold_before = dump(gold_conn), _gold_dump(gold_conn)
    bronze_before = count(gold_conn, "bronze.events")

    again = bb.ingest_all(gold_conn, events)
    assert all(not r.accepted for r in again)                       # every event is a duplicate
    assert count(gold_conn, "bronze.events") == bronze_before
    second = cycle(gold_conn, 2400)

    assert second.snapshot_id == first.snapshot_id and second.max_bronze_id == first.max_bronze_id
    assert second.created is False and first.created is True
    assert count(gold_conn, "gold.snapshots") == 1
    assert dump(gold_conn) == silver_before
    assert _gold_dump(gold_conn) == gold_before


def test_recomputing_twice_in_a_row_keeps_one_snapshot(gold_conn) -> None:
    bb.ingest_all(gold_conn, bb.normal().events)
    a, b = cycle(gold_conn, 3000), cycle(gold_conn, 3000)
    assert a.snapshot_id == b.snapshot_id
    assert count(gold_conn, "gold.snapshots") == 1
    assert count(gold_conn, "gold.corridor_now") == count(gold_conn, "gold.source_status") == 1
    assert count(gold_conn, "gold.service_metric") == 1


def test_new_bronze_data_gives_a_new_snapshot(gold_conn) -> None:
    b = bb.Builder("late")
    b.drive("B-101", 0, 100)
    bb.ingest_all(gold_conn, b.events)
    first = cycle(gold_conn, 100)
    b2 = bb.Builder("late2")
    b2.position("B-101", bb.trip_id("B-101"), 90, 5.0)      # late arrival, event time before as_of
    bb.ingest_all(gold_conn, b2.events)
    second = cycle(gold_conn, 100)
    assert second.snapshot_id != first.snapshot_id and second.max_bronze_id > first.max_bronze_id
    assert count(gold_conn, "gold.snapshots") == 2
