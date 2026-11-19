"""T014 — throwaway-database fixture (R10): isolation from the live compose database."""
from __future__ import annotations

import uuid

import psycopg
from psycopg.conninfo import conninfo_to_dict

from tests.db_helpers import db_exists, throwaway_database


def _dbname(dsn: str) -> str:
    return conninfo_to_dict(dsn)["dbname"]


def test_module_database_is_separate_from_the_live_one(db_dsn: str, module_db_dsn: str) -> None:
    assert _dbname(module_db_dsn) != _dbname(db_dsn)
    with psycopg.connect(module_db_dsn) as conn:
        names = {r[0] for r in conn.execute(
            "SELECT schema_name FROM information_schema.schemata").fetchall()}
        assert {"bronze", "silver", "gold"} <= names
        assert conn.execute("SELECT count(*) FROM bronze.events").fetchone()[0] == 0


def test_writes_stay_in_the_throwaway_database(db_dsn: str, module_db_dsn: str) -> None:
    marker = str(uuid.uuid4())
    with psycopg.connect(module_db_dsn) as conn:
        conn.execute(
            "INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload)"
            " VALUES ('test', %s, '1.0.0', 'bus_position', now(), now(), '{}')", (marker,))
    with psycopg.connect(db_dsn) as live:
        assert live.execute(
            "SELECT count(*) FROM bronze.events WHERE source = 'test' AND event_id = %s", (marker,)
        ).fetchone()[0] == 0


def test_each_database_is_its_own_and_is_dropped_at_teardown(db_dsn: str, db_template: str) -> None:
    with throwaway_database(db_dsn, db_template) as a, throwaway_database(db_dsn, db_template) as b:
        assert _dbname(a) != _dbname(b)
        assert db_exists(db_dsn, _dbname(a)) and db_exists(db_dsn, _dbname(b))
    assert not db_exists(db_dsn, _dbname(a))
    assert not db_exists(db_dsn, _dbname(b))


def test_template_is_a_session_level_database_that_is_not_the_live_one(db_dsn: str, db_template: str) -> None:
    assert db_template != _dbname(db_dsn)
    assert db_exists(db_dsn, db_template)


def test_init_scripts_are_applied_to_the_template(module_db_dsn: str) -> None:
    with psycopg.connect(module_db_dsn) as conn:
        assert conn.execute("SELECT to_regclass('bronze.events')").fetchone()[0] is not None
        assert conn.execute("SELECT to_regclass('bronze.rejections')").fetchone()[0] is not None
