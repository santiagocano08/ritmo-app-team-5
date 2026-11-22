"""T004 — a backend incident_report with a null duration must not break the silver rebuild (004 FR-021, SC-012).

Pre-existing 002 failure: `silver.incidents.end_ts` is NOT NULL and the rebuild computed it from
`duration_min`, so a null duration aborted the whole rebuild. An unknown duration is an open-ended
incident: `end_ts = 'infinity'`. The infinite value is only ever read in SQL (psycopg cannot load it).
"""
from __future__ import annotations

from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.silver_support import at, build, incidents, state


def _load(conn, with_normal_incident: bool = False) -> tuple[bb.Builder, str, str | None]:
    b = bb.Builder("null_duration")
    b.drive("B-101", 0, 600)
    b.drive("B-102", 0, 600)
    bb.ingest_all(conn, b.events)
    open_ended = b.command_incident(at=100, target_id="B-101", duration_min=None)
    cmds = [open_ended]
    normal = None
    if with_normal_incident:
        normal_ev = b.command_incident(at=200, target_id="B-102", duration_min=15.0)
        cmds.append(normal_ev)
        normal = normal_ev["event_id"]
    bb.insert_backend_commands(conn, cmds)
    return b, open_ended["event_id"], normal


def test_null_duration_incident_does_not_break_the_rebuild_and_is_open_ended(silver_conn) -> None:
    _, inc_id, _ = _load(silver_conn)
    build(silver_conn, 300)  # must not raise
    row = silver_conn.execute(
        "SELECT end_ts = 'infinity'::timestamptz, NOT isfinite(end_ts), start_ts "
        "FROM silver.incidents WHERE inc_id = %s", (inc_id,)).fetchone()
    assert row is not None
    assert row[0] is True and row[1] is True
    assert row[2] == at(100)


def test_open_ended_incident_is_active_from_its_start_at_every_later_time(silver_conn) -> None:
    _, inc_id, _ = _load(silver_conn)
    for as_of_s in (100, 300, 86_400 * 30):
        build(silver_conn, as_of_s)
        active = silver_conn.execute(
            "SELECT start_ts <= %s AND %s < end_ts FROM silver.incidents WHERE inc_id = %s",
            (at(as_of_s), at(as_of_s), inc_id)).fetchone()[0]
        assert active is True, as_of_s


def test_the_targeted_bus_is_broken_down(silver_conn) -> None:
    _load(silver_conn)
    build(silver_conn, 300)
    rows = state(silver_conn)
    assert rows["B-101"]["operational_status"] == "broken_down"
    assert rows["B-102"]["operational_status"] == "in_service"


def test_incident_helper_returns_the_open_ended_row_without_raising(silver_conn) -> None:
    _, inc_id, _ = _load(silver_conn)
    build(silver_conn, 300)
    rows = incidents(silver_conn)  # psycopg would raise DataError on a raw 'infinity' end_ts
    (row,) = [r for r in rows if str(r["inc_id"]) == inc_id]
    assert row["open_ended"] is True and row["end_ts"] is None


def test_a_normal_incident_in_the_same_bronze_keeps_its_end(silver_conn) -> None:
    _, _, normal_id = _load(silver_conn, with_normal_incident=True)
    build(silver_conn, 300)
    rows = {str(r["inc_id"]): r for r in incidents(silver_conn)}
    normal = rows[normal_id]
    assert normal["open_ended"] is False
    assert normal["end_ts"] == at(200 + 15 * 60)
