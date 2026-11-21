"""
pytest shared fixtures.

Integration tests that need a real DB connection pick up DATABASE_URL from the
environment (set by docker-compose or the CI matrix).  Unit and contract tests
run without any DB.
"""
from __future__ import annotations

import os
import pytest


@pytest.fixture(scope="session")
def db_dsn() -> str:
    """Return the DATABASE_URL for integration tests.

    Skip the test if the env var is not set so unit tests run offline.
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL not set — skipping integration test")
    return dsn


@pytest.fixture(scope="session")
def db_conn(db_dsn):
    """Open a single psycopg3 connection for the whole test session."""
    import psycopg
    with psycopg.connect(db_dsn, autocommit=False) as conn:
        yield conn


@pytest.fixture(scope="session")
def db_template(db_dsn):
    """Template database built once per session from src/data/db/init/*.sql + reference tables (R10)."""
    from src.data.tests.db_helpers import build_template, drop_database

    name = build_template(db_dsn)
    try:
        yield name
    finally:
        drop_database(db_dsn, name)


@pytest.fixture(scope="module")
def module_db_dsn(db_dsn, db_template):
    """DSN of a database private to the test module, dropped at teardown (R10)."""
    from src.data.tests.db_helpers import throwaway_database

    with throwaway_database(db_dsn, db_template) as dsn:
        yield dsn
