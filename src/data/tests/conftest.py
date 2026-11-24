"""
pytest shared fixtures.

Integration tests that need a real DB connection pick up DATABASE_URL from the
environment (set by docker-compose or the CI matrix).  Unit and contract tests
run without any DB.
"""
from __future__ import annotations

import os
import pytest


def pytest_collection_modifyitems(config, items):
    # Mark every test collected under src/data/tests with `data` so the slow
    # bronze/gold ETL suite can be deselected with -m "not data" when a change
    # does not touch src/data/. Applied by path to avoid per-file decorators.
    here = os.path.dirname(__file__)
    for item in items:
        if str(item.fspath).startswith(here):
            item.add_marker(pytest.mark.data)


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
