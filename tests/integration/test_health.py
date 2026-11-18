"""
Integration test — T008 (US-2): GET /healthz → 200 {"status": "healthy"}

Requires the API service to be reachable. The base URL is read from the
API_BASE_URL environment variable (default: http://localhost:8000).

When running against docker-compose, set:
    API_BASE_URL=http://localhost:8000
"""
from __future__ import annotations

import os

import pytest

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")


@pytest.fixture(scope="module")
def http_client():
    """Return an httpx client scoped to the module."""
    httpx = pytest.importorskip("httpx")
    with httpx.Client(base_url=API_BASE_URL, timeout=10.0) as client:
        yield client


def test_healthz_returns_200(http_client) -> None:
    """GET /healthz must return HTTP 200."""
    response = http_client.get("/healthz")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )


def test_healthz_body(http_client) -> None:
    """GET /healthz body must be {\"status\": \"healthy\"}."""
    response = http_client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "healthy"}, (
        f"Unexpected response body: {body}"
    )


def test_healthz_content_type(http_client) -> None:
    """GET /healthz must respond with application/json content type."""
    response = http_client.get("/healthz")
    assert "application/json" in response.headers.get("content-type", ""), (
        f"Expected application/json, got: {response.headers.get('content-type')}"
    )
