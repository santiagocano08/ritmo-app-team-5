"""Integration tests for GET /api/v1/version (US-08).

Asserts the route returns 200 with the three fields (FR-001/FR-002), that no
database connection/dependency is invoked while serving it (FR-006/SC-004), and
that with APP_REVISION unset the response reports source_revision = "unknown"
(FR-004/SC-003). Uses a plain TestClient with no database.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_db_connection
from src.api.main import app


def test_version_endpoint_returns_200_with_three_fields() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/version")

    assert resp.status_code == 200
    assert set(resp.json().keys()) == {
        "app_version",
        "read_contract_version",
        "source_revision",
    }


def test_version_endpoint_does_not_invoke_db_dependency() -> None:
    def _fail_if_db_used():
        raise AssertionError("version endpoint must not open a database connection")

    app.dependency_overrides[get_db_connection] = _fail_if_db_used
    try:
        with TestClient(app) as client:
            resp = client.get("/api/v1/version")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200


def test_version_endpoint_reports_unknown_without_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_REVISION", raising=False)
    with TestClient(app) as client:
        resp = client.get("/api/v1/version")

    assert resp.status_code == 200
    assert resp.json()["source_revision"] == "unknown"
