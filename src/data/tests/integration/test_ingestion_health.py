"""T026 — ingestion freshness healthcheck (`python -m src.data.ingestion.health`).

Exit 0 when the newest bronze insert is at most INGESTION_HEALTH_MAX_AGE_S old (default 15).
Any failure is `unhealthy: check failed` with no connection detail (FR-020, FR-021, FR-023, SC-008).
"""
from __future__ import annotations

import ast
import uuid
from pathlib import Path

import psycopg
import pytest

from src.data.ingestion import health

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def conn(silver_conn):
    return silver_conn


@pytest.fixture
def dsn(module_db_dsn, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", module_db_dsn)
    monkeypatch.delenv("INGESTION_HEALTH_MAX_AGE_S", raising=False)
    return module_db_dsn


def _event(conn, age_s: float) -> None:
    conn.execute(
        "INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload) "
        "VALUES ('sim', %s, '1.0.0', 'bus_position', now(), clock_timestamp() - make_interval(secs => %s), '{}')",
        (uuid.uuid4(), age_s))
    conn.commit()


def test_empty_bronze_is_unhealthy(conn, dsn, capsys) -> None:
    assert health.main() == 1
    out = capsys.readouterr().out.strip()
    assert out.startswith("unhealthy: no insert in the last 15 s")


def test_fresh_row_is_healthy(conn, dsn, capsys) -> None:
    _event(conn, 1)
    assert health.main() == 0
    assert capsys.readouterr().out.strip() == "healthy"


def test_stale_row_is_unhealthy(conn, dsn, capsys) -> None:
    _event(conn, 40)
    assert health.main() == 1
    assert capsys.readouterr().out.startswith("unhealthy: no insert in the last")


def test_threshold_override(conn, dsn, monkeypatch) -> None:
    _event(conn, 40)
    assert health.main() == 1
    monkeypatch.setenv("INGESTION_HEALTH_MAX_AGE_S", "120")
    assert health.main() == 0


def test_max_age_default_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INGESTION_HEALTH_MAX_AGE_S", raising=False)
    assert health.get_max_age_s() == 15.0
    monkeypatch.setenv("INGESTION_HEALTH_MAX_AGE_S", "7.5")
    assert health.get_max_age_s() == 7.5
    for bad in ("abc", "0", "-3"):
        monkeypatch.setenv("INGESTION_HEALTH_MAX_AGE_S", bad)
        with pytest.raises(RuntimeError):
            health.get_max_age_s()


@pytest.mark.parametrize("bad", ["abc", "0", "-1"])
def test_bad_setting_is_check_failed(conn, dsn, monkeypatch, capsys, bad) -> None:
    _event(conn, 1)
    monkeypatch.setenv("INGESTION_HEALTH_MAX_AGE_S", bad)
    assert health.main() == 1
    assert capsys.readouterr().out.strip() == "unhealthy: check failed"


def test_unreachable_database_prints_no_detail(monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://secretuser:topsecret@192.0.2.1:1/secretdb?connect_timeout=1")
    assert health.main() == 1
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert captured.out.strip() == "unhealthy: check failed"
    for leak in ("secretuser", "topsecret", "192.0.2.1", "secretdb", "postgresql://", "Traceback"):
        assert leak not in text


def test_missing_view_is_check_failed_without_detail(module_db_dsn, monkeypatch, capsys) -> None:
    from src.data.tests.db_helpers import _admin, drop_database, dsn_for
    from psycopg import sql

    name = f"pf_health_{uuid.uuid4().hex[:10]}"
    with _admin(module_db_dsn) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
            sql.Identifier(name), sql.Identifier(_current_db(module_db_dsn))))
    try:
        with psycopg.connect(dsn_for(module_db_dsn, name), autocommit=True) as c:
            c.execute("DROP SCHEMA ops CASCADE")
        monkeypatch.setenv("DATABASE_URL", dsn_for(module_db_dsn, name))
        assert health.main() == 1
        captured = capsys.readouterr()
        assert captured.out.strip() == "unhealthy: check failed"
        assert "ops" not in captured.err and "ingestion_health" not in captured.out
    finally:
        drop_database(module_db_dsn, name)


def _current_db(dsn: str) -> str:
    # Copying a database that has other open connections can fail; use a fresh connection-free
    # template instead: the module database is only used as a source when nobody else is connected.
    with psycopg.connect(dsn) as c:
        return c.execute("SELECT current_database()").fetchone()[0]


def test_module_imports_only_psycopg_and_config() -> None:
    tree = ast.parse((ROOT / "src" / "data" / "ingestion" / "health.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    project = {m for m in imported if m.startswith(("src.", "src"))}
    assert project <= {"src.pulsoflota.config"}
    for forbidden in ("run", "api", "refresh"):
        assert not any(forbidden in m.split(".") for m in project)
