"""Contract test for GET /api/v1/version (US-08).

Asserts the 200 response matches the fixed shape in
specs/007-backend-version-info/contracts/version-info.openapi.yaml: exactly the
three fields, no extras (extra="forbid", FR-005/SC-002); read_contract_version
equals 1.0.0; app_version and source_revision are non-empty strings (minLength 1).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app

EXPECTED_FIELDS = {"app_version", "read_contract_version", "source_revision"}


def test_version_response_matches_contract_shape() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/version")

    assert resp.status_code == 200
    body = resp.json()

    assert set(body.keys()) == EXPECTED_FIELDS
    assert body["read_contract_version"] == "1.0.0"
    assert isinstance(body["app_version"], str) and len(body["app_version"]) >= 1
    assert isinstance(body["source_revision"], str) and len(body["source_revision"]) >= 1
