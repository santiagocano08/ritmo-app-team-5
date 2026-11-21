"""Freshness healthcheck of the `refresh` service: unhealthy when no gold snapshot was committed
in the last REFRESH_HEALTH_MAX_AGE_S seconds of wall-clock time (DataOps signal; M3 limitation)."""
from __future__ import annotations

import uuid

import psycopg
import pytest

from src.data.refresh import health
from src.data.tests.db_helpers import INIT_DIR


@pytest.fixture
def conn(gold_conn):
    gold_conn.execute("DELETE FROM gold.snapshot_commits")
    gold_conn.commit()
    return gold_conn


def _insert(conn, age_s: float) -> None:
    """A commit-log row written `age_s` seconds ago."""
    conn.execute(
        "INSERT INTO gold.snapshot_commits (snapshot_id, committed_at) "
        "VALUES (%s, clock_timestamp() - make_interval(secs => %s))",
        (uuid.uuid4(), age_s))
    conn.commit()


def _snapshot(conn, sid: uuid.UUID) -> None:
    conn.execute(
        "INSERT INTO gold.snapshots (snapshot_id, as_of_ts, rules_version, max_bronze_id) "
        "VALUES (%s, now(), '1.0.0', %s)", (sid, sid.int % 1_000_000))


def test_empty_gold_is_unhealthy(conn) -> None:
    assert health.snapshot_age_s(conn) is None
    assert health.is_healthy(conn, 30) is False


def test_recent_snapshot_is_healthy(conn) -> None:
    _insert(conn, 2)
    assert 1 <= health.snapshot_age_s(conn) < 10
    assert health.is_healthy(conn, 30) is True


def test_old_snapshot_is_unhealthy(conn) -> None:
    _insert(conn, 120)
    assert health.is_healthy(conn, 30) is False
    assert health.is_healthy(conn, 300) is True


def test_newest_snapshot_counts(conn) -> None:
    _insert(conn, 600)
    _insert(conn, 1)
    assert health.is_healthy(conn, 30) is True


def test_committed_snapshot_is_logged_and_makes_the_service_healthy(conn) -> None:
    sid = uuid.uuid4()
    _snapshot(conn, sid)
    conn.commit()
    assert conn.execute("SELECT count(*) FROM gold.snapshot_commits WHERE snapshot_id = %s",
                        (sid,)).fetchone()[0] == 1
    assert health.is_healthy(conn, 30) is True


def test_rolled_back_snapshot_leaves_no_commit_row(conn) -> None:
    _snapshot(conn, uuid.uuid4())
    conn.rollback()
    assert health.snapshot_age_s(conn) is None


def test_snapshot_columns_unchanged_and_ddl_idempotent(conn) -> None:
    ddl = (INIT_DIR / "005_gold.sql").read_text(encoding="utf-8")
    conn.execute(ddl)  # second run must not fail
    conn.commit()
    cols = [r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='gold' AND table_name='snapshots' ORDER BY ordinal_position").fetchall()]
    assert cols == ["snapshot_id", "as_of_ts", "rules_version", "max_bronze_id"]


def test_max_age_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REFRESH_HEALTH_MAX_AGE_S", raising=False)
    assert health.get_max_age_s() == 30.0
    monkeypatch.setenv("REFRESH_HEALTH_MAX_AGE_S", "12")
    assert health.get_max_age_s() == 12.0
    monkeypatch.setenv("REFRESH_HEALTH_MAX_AGE_S", "0")
    with pytest.raises(RuntimeError):
        health.get_max_age_s()


def test_main_exit_codes(conn, module_db_dsn, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", module_db_dsn)
    monkeypatch.setenv("REFRESH_HEALTH_MAX_AGE_S", "30")
    assert health.main() == 1  # empty gold
    _insert(conn, 1)
    assert health.main() == 0
    out = capsys.readouterr().out + capsys.readouterr().err
    assert "password" not in out.lower()


def test_main_unreachable_database_is_unhealthy_without_detail(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:topsecret@127.0.0.1:1/x?connect_timeout=1")
    assert health.main() == 1
    captured = capsys.readouterr()
    assert "topsecret" not in captured.out + captured.err
    assert isinstance(psycopg.OperationalError("x"), Exception)
