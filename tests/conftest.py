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
