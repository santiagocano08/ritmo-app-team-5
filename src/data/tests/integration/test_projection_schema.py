"""006 T049a — DDL of phase 2b: `gold.mpc_projection` and `gold.v_projection_accuracy` (data-model M10, M11; FR-035)."""
from __future__ import annotations

import re
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[4]
SQL = ROOT / "src" / "data" / "db" / "init" / "009_decision_mpc.sql"

TABLE_COLUMNS = {"snapshot_id", "bus_id", "stop_id", "as_of_ts", "projected_departure_ts", "lead_s",
                 "rules_version", "max_bronze_id"}
VIEW_COLUMNS = {"snapshot_id", "bus_id", "stop_id", "as_of_ts", "projected_departure_ts", "lead_s", "lead_bucket",
                "actual_departure_ts", "error_s", "abs_error_s", "affected_by_decision", "rules_version",
                "max_bronze_id"}


@pytest.fixture()
def conn(module_db_dsn):
    with psycopg.connect(module_db_dsn) as c:
        yield c
        c.rollback()


def _cols(conn, table: str) -> set[str]:
    rows = conn.execute("SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'gold' AND table_name = %s", (table,)).fetchall()
    return {r[0] for r in rows}


def test_apply_twice_is_idempotent(conn) -> None:
    conn.execute(SQL.read_text(encoding="utf-8"))
    conn.execute(SQL.read_text(encoding="utf-8"))
    conn.commit()
    assert _cols(conn, "mpc_projection") == TABLE_COLUMNS
    assert _cols(conn, "v_projection_accuracy") == VIEW_COLUMNS


def test_primary_key_foreign_key_and_index(conn) -> None:
    pk = conn.execute("SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
                      "AND a.attnum = ANY (i.indkey) WHERE i.indrelid = 'gold.mpc_projection'::regclass "
                      "AND i.indisprimary ORDER BY a.attname").fetchall()
    assert [r[0] for r in pk] == ["bus_id", "snapshot_id", "stop_id"]
    fk = conn.execute("SELECT confrelid::regclass::text FROM pg_constraint "
                      "WHERE conrelid = 'gold.mpc_projection'::regclass AND contype = 'f'").fetchall()
    assert [r[0] for r in fk] == ["gold.snapshots"]
    idx = conn.execute("SELECT indexdef FROM pg_indexes WHERE schemaname = 'gold' "
                       "AND tablename = 'mpc_projection' AND NOT indexdef LIKE '%UNIQUE%'").fetchall()
    assert any("(bus_id, stop_id, as_of_ts)" in r[0] for r in idx)


def test_lead_is_bounded_by_the_scoring_window(conn) -> None:
    sid = "aaaa0000-0000-4000-8000-00000000002b"
    conn.execute("INSERT INTO gold.snapshots (snapshot_id, as_of_ts, rules_version, max_bronze_id) "
                 "VALUES (%s, now(), 'x', 1)", (sid,))
    sql = "INSERT INTO gold.mpc_projection VALUES (%s, 'B-1', %s, now(), now(), %s, 'x', 1)"
    conn.execute(sql, (sid, "P-1", 1800))
    conn.execute(sql, (sid, "P-2", 0))
    for stop, bad in (("P-3", 1801), ("P-4", -1)):
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction():  # a savepoint: the failed insert does not poison the test transaction
                conn.execute(sql, (sid, stop, bad))
    assert conn.execute("SELECT count(*) FROM gold.mpc_projection").fetchone()[0] == 2


def test_the_only_writer_is_the_recommend_step() -> None:
    """The record is append-only: no module of the pipeline or the rules updates or deletes it (FR-035)."""
    writers = []
    for base in ("pipeline", "rules", "refresh", "simulator", "ingestion"):
        for path in (ROOT / "src" / "data" / base).rglob("*"):
            if path.suffix not in {".py", ".sql"}:
                continue
            text = path.read_text(encoding="utf-8")
            if "mpc_projection" not in text:
                continue
            writers.append(path.name)
            assert not re.search(r"\b(UPDATE|DELETE\s+FROM|TRUNCATE)\b[^;'\"]{0,40}mpc_projection", text, re.I), path
    assert writers == ["recommend.py"]
