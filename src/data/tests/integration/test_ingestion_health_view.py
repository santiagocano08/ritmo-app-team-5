"""T025 — `ops.ingestion_health` on a throwaway database with crafted bronze rows (US3).

Contract: specs/003-ops-ci-reliability/contracts/ops-ingestion-health.md.
"""
from __future__ import annotations

import uuid

import psycopg
import pytest

COLUMNS = [
    ("observed_at", "timestamp with time zone"),
    ("last_insert_age_s", "double precision"),
    ("events_60s", "bigint"),
    ("rejections_60s", "bigint"),
    ("duplicates_60s", "bigint"),
    ("rejection_rate_60s", "numeric"),
]


@pytest.fixture
def conn(silver_conn):
    return silver_conn


def _event(conn, age_s: float) -> None:
    """A bronze event whose arrival_ts is `age_s` seconds in the past."""
    conn.execute(
        "INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload) "
        "VALUES ('sim', %s, '1.0.0', 'bus_position', now(), clock_timestamp() - make_interval(secs => %s), '{}')",
        (uuid.uuid4(), age_s))
    conn.commit()


def _rejection(conn, reason: str, age_s: float = 1.0) -> None:
    conn.execute(
        "INSERT INTO bronze.rejections (original_message, reason, received_ts) "
        "VALUES ('{}', %s, clock_timestamp() - make_interval(secs => %s))", (reason, age_s))
    conn.commit()


def _view(conn) -> dict:
    cur = conn.execute("SELECT * FROM ops.ingestion_health")
    rows = cur.fetchall()
    conn.rollback()
    assert len(rows) == 1
    return dict(zip([d.name for d in cur.description], rows[0]))


def test_ops_schema_holds_only_views(conn) -> None:
    assert conn.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'ops'").fetchone()
    tables = conn.execute(
        "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = 'ops'").fetchall()
    assert tables == [("ingestion_health", "VIEW")]
    assert conn.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'ops' AND c.relkind IN ('r', 'p', 'm')").fetchone()[0] == 0


def test_columns_and_types_match_the_contract(conn) -> None:
    rows = conn.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'ops' AND table_name = 'ingestion_health' ORDER BY ordinal_position").fetchall()
    assert rows == COLUMNS


def test_empty_bronze_is_not_computable_not_zero(conn) -> None:
    row = _view(conn)
    assert row["last_insert_age_s"] is None
    assert row["events_60s"] == 0
    assert row["rejections_60s"] == 0
    assert row["duplicates_60s"] == 0
    assert row["rejection_rate_60s"] is None
    assert row["observed_at"] is not None


def test_fresh_row_is_below_15_s(conn) -> None:
    _event(conn, 1)
    assert 0 <= _view(conn)["last_insert_age_s"] < 15


def test_stale_row_is_above_15_s(conn) -> None:
    _event(conn, 40)
    assert _view(conn)["last_insert_age_s"] > 15


def test_age_follows_the_highest_id(conn) -> None:
    _event(conn, 100)
    _event(conn, 2)
    assert _view(conn)["last_insert_age_s"] < 15


def test_rows_older_than_60_s_are_excluded(conn) -> None:
    _event(conn, 5)
    _event(conn, 120)
    _rejection(conn, "wrong_type", 5)
    _rejection(conn, "wrong_type", 120)
    _rejection(conn, "duplicate_event", 120)
    row = _view(conn)
    assert (row["events_60s"], row["rejections_60s"], row["duplicates_60s"]) == (1, 1, 0)


def test_duplicates_are_not_rejections(conn) -> None:
    for _ in range(6):
        _event(conn, 3)
    _rejection(conn, "wrong_type")
    _rejection(conn, "undeclared_field")
    for _ in range(5):
        _rejection(conn, "duplicate_event")
    row = _view(conn)
    assert row["events_60s"] == 6
    assert row["rejections_60s"] == 2
    assert row["duplicates_60s"] == 5
    assert float(row["rejection_rate_60s"]) == pytest.approx(2 / 8)


def test_duplicates_only_gives_null_rate(conn) -> None:
    for _ in range(3):
        _rejection(conn, "duplicate_event")
    row = _view(conn)
    assert row["duplicates_60s"] == 3
    assert row["rejections_60s"] == 0
    assert row["rejection_rate_60s"] is None


def test_empty_window_is_null_never_zero_or_full(conn) -> None:
    _event(conn, 300)
    _rejection(conn, "wrong_type", 300)
    row = _view(conn)
    assert row["events_60s"] == 0 and row["rejections_60s"] == 0
    assert row["rejection_rate_60s"] is None


def test_a_duplicate_does_not_refresh_freshness(conn) -> None:
    _event(conn, 40)
    _rejection(conn, "duplicate_event", 0.5)
    assert _view(conn)["last_insert_age_s"] > 15


def test_the_view_writes_nothing(conn) -> None:
    _event(conn, 2)
    _rejection(conn, "wrong_type")

    def counts() -> list[int]:
        out = []
        for schema, table in [("bronze", "events"), ("bronze", "rejections"), ("silver", "position_history"),
                              ("silver", "stop_visits"), ("gold", "snapshots")]:
            out.append(conn.execute(f"SELECT count(*) FROM {schema}.{table}").fetchone()[0])  # noqa: S608
        conn.rollback()
        return out

    before = counts()
    _view(conn)
    _view(conn)
    assert counts() == before


def test_view_is_not_updatable(conn) -> None:
    with pytest.raises(psycopg.Error):
        conn.execute("DELETE FROM ops.ingestion_health")
    conn.rollback()
