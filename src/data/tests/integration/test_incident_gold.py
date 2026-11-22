"""T010 — the `incident` gold object (US-12; 004 FR-021, FR-026, FR-027, SC-004, SC-012)."""
from __future__ import annotations

import pytest

from src.data.rules import RULES_VERSION
from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import cycle, validator


@pytest.fixture
def loaded(gold_conn):
    """B-101 with a scripted 4-minute breakdown at 100 s, B-102 with an open-ended dispatcher one at 200 s."""
    b = bb.Builder("incident_gold")
    b.drive("B-101", 0, 1000)
    b.drive("B-102", 0, 1000)
    inc = b.incident("bus_breakdown", "B-101", at=100, duration_min=4.0)
    bb.ingest_all(gold_conn, b.events)
    open_ended = b.command_incident(at=200, target_id="B-102", duration_min=None)
    bb.insert_backend_commands(gold_conn, [open_ended])
    return gold_conn, inc["event_id"], open_ended["event_id"]


def rows_of(conn, snapshot_id) -> dict[str, dict]:
    got = conn.execute("SELECT inc_id, active, doc FROM gold.incident WHERE snapshot_id = %s", (snapshot_id,)).fetchall()
    return {str(r[0]): {"active": r[1], "doc": r[2]} for r in got}


def test_table_shape(gold_conn) -> None:
    cols = {r[0]: (r[1], r[2]) for r in gold_conn.execute(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'gold' AND table_name = 'incident'").fetchall()}
    assert cols == {
        "snapshot_id": ("uuid", "NO"), "inc_id": ("uuid", "NO"), "active": ("boolean", "NO"),
        "doc": ("jsonb", "NO"), "rules_version": ("text", "NO"), "max_bronze_id": ("bigint", "NO")}
    pk = gold_conn.execute(
        "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
        "WHERE i.indrelid = 'gold.incident'::regclass AND i.indisprimary ORDER BY array_position(i.indkey::int[], a.attnum)"
    ).fetchall()
    assert [r[0] for r in pk] == ["snapshot_id", "inc_id"]


def test_rows_validate_against_the_read_contract(loaded) -> None:
    conn, _, _ = loaded
    res = cycle(conn, 300)
    rows = rows_of(conn, res.snapshot_id)
    assert len(rows) == 2
    for row in rows.values():
        errors = list(validator("incident").iter_errors(row["doc"]))
        assert errors == [], errors


def test_scripted_incident_is_active_until_start_plus_duration(loaded) -> None:
    conn, inc_id, _ = loaded
    during = rows_of(conn, cycle(conn, 300).snapshot_id)[inc_id]
    assert during["active"] is True
    doc = during["doc"]
    assert doc["duration_s"] == 240 and doc["until"] is None
    assert doc["since"] == bb.iso(100) and doc["type"] == "bus_breakdown"
    assert doc["target_id"] == "B-101" and doc["reported_by"] == "script" and doc["schema_version"] == "1.0.0"
    after = rows_of(conn, cycle(conn, 400).snapshot_id)[inc_id]
    assert after["active"] is False
    assert after["doc"]["until"] == bb.iso(340) and after["doc"]["duration_s"] == 240


def test_incident_starts_not_before_its_report(loaded) -> None:
    conn, inc_id, _ = loaded
    assert inc_id not in rows_of(conn, cycle(conn, 50).snapshot_id)


def test_open_ended_incident_has_no_duration_and_no_end(loaded) -> None:
    conn, _, open_id = loaded
    for as_of in (300, 900):
        row = rows_of(conn, cycle(conn, as_of).snapshot_id)[open_id]
        assert row["active"] is True
        assert row["doc"]["duration_s"] is None and row["doc"]["until"] is None
        assert row["doc"]["reported_by"] == "dispatcher"
        assert list(validator("incident").iter_errors(row["doc"])) == []


def test_current_view_returns_the_newest_snapshot_of_the_current_rules_version(loaded) -> None:
    conn, inc_id, open_id = loaded
    cycle(conn, 300)
    latest = cycle(conn, 400)
    conn.commit()
    got = conn.execute("SELECT snapshot_id, inc_id, active, rules_version FROM gold.incident_current").fetchall()
    assert {str(r[1]) for r in got} == {inc_id, open_id}
    assert {r[0] for r in got} == {latest.snapshot_id} and {r[3] for r in got} == {RULES_VERSION}
    by_id = {str(r[1]): r[2] for r in got}
    assert by_id == {inc_id: False, open_id: True}


def test_current_view_is_empty_without_snapshots(gold_conn) -> None:
    assert gold_conn.execute("SELECT count(*) FROM gold.incident_current").fetchone()[0] == 0


def test_lineage_columns_and_rerun_stability(loaded) -> None:
    conn, _, _ = loaded
    res = cycle(conn, 300)
    first = rows_of(conn, res.snapshot_id)
    lineage = conn.execute("SELECT DISTINCT rules_version, max_bronze_id FROM gold.incident "
                           "WHERE snapshot_id = %s", (res.snapshot_id,)).fetchall()
    assert lineage == [(RULES_VERSION, res.max_bronze_id)]
    # recompute the same bronze from scratch: same snapshot id, same rows
    for table in ("mpc_projection", "incident", "service_metric", "service_metric_stop", "stop_ewt_band", "stop_boarding_band", "decision_inputs", "corridor_now",
                  "source_status", "snapshots"):
        conn.execute(f"DELETE FROM gold.{table}")  # noqa: S608 - fixed names
    conn.commit()
    again = cycle(conn, 300)
    assert again.snapshot_id == res.snapshot_id
    assert rows_of(conn, again.snapshot_id) == first
