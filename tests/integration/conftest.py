"""Fixtures for the silver integration tests: an empty throwaway database per test (R10)."""
from __future__ import annotations

import psycopg
import pytest


@pytest.fixture
def silver_conn(module_db_dsn):
    """Connection to the module's throwaway database with empty bronze and silver tables.

    Only ever points at a throwaway database, so clearing bronze here never touches the
    compose database (see tests/integration/test_db_fixture.py).
    """
    with psycopg.connect(module_db_dsn) as conn:
        conn.execute("TRUNCATE bronze.events, bronze.rejections RESTART IDENTITY")
        for table in ("segment_traversals", "stop_visits", "bus_current_state", "incidents", "position_history"):
            conn.execute(f"DELETE FROM silver.{table}")  # noqa: S608 - fixed names
        conn.commit()
        yield conn


@pytest.fixture
def gold_conn(module_db_dsn):
    """Like `silver_conn`, and the gold tables are empty too (throwaway database only)."""
    from tests.fixtures.gold_support import clear_all

    with psycopg.connect(module_db_dsn) as conn:
        clear_all(conn)
        yield conn


@pytest.fixture
def config_reset(module_db_dsn):
    """Restore the seeded `config` tables after a test that changed them (module database is shared)."""
    yield
    from src.pipeline.reference import load_reference
    from tests.db_helpers import INIT_DIR

    with psycopg.connect(module_db_dsn) as conn:
        conn.rollback()
        for table in ("corridor_settings", "fleet_roster", "enabled_stops"):
            conn.execute(f"DELETE FROM config.{table}")  # noqa: S608 - fixed names
        conn.execute((INIT_DIR / "003_config.sql").read_text(encoding="utf-8"))
        conn.commit()
        load_reference(conn)
