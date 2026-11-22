"""Shared fixtures for the read-API tests (US-05).

Reuses the data-layer DB-template machinery and gold-seeding helpers rather than
duplicating the harness: the session template, the per-module throwaway database and
the `gold_conn`-style empty-gold connection all come from `src/data/tests`. A
`TestClient` fixture mounts the FastAPI app and overrides the per-request DB
dependency so each request reads the test's own throwaway database.
"""
from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

# Reuse the data-layer DB-template fixtures (db_dsn, db_template, module_db_dsn)
# without duplicating the harness. F401: re-exported so pytest discovers them in
# this package's fixture scope.
from src.data.tests.conftest import (  # noqa: F401
    db_dsn,
    db_template,
    module_db_dsn,
)


@pytest.fixture
def gold_conn(module_db_dsn):  # noqa: F811
    """Connection to the module's throwaway database with empty bronze/silver/gold.

    Mirrors `src/data/tests/integration/conftest.py::gold_conn`; only ever points at a
    throwaway database, so clearing never touches the compose database.
    """
    from src.data.tests.fixtures.gold_support import clear_all

    with psycopg.connect(module_db_dsn) as conn:
        clear_all(conn)
        yield conn


@pytest.fixture
def client(module_db_dsn):  # noqa: F811
    """FastAPI TestClient whose DB dependency opens the test's throwaway database."""
    from src.api.deps import get_db_connection
    from src.api.main import app

    def _override_db_connection():
        with psycopg.connect(module_db_dsn, row_factory=psycopg.rows.dict_row) as conn:
            yield conn

    app.dependency_overrides[get_db_connection] = _override_db_connection
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
