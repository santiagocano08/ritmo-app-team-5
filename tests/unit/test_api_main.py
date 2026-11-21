"""
Unit tests for src/api/main.py using FastAPI TestClient (no network required).
Covers the /healthz endpoint and the unhandled-exception handler.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_healthz_status_200() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200


def test_healthz_body() -> None:
    response = client.get("/healthz")
    assert response.json() == {"status": "healthy"}


def test_healthz_content_type() -> None:
    response = client.get("/healthz")
    assert "application/json" in response.headers["content-type"]


def test_unknown_route_returns_404() -> None:
    response = client.get("/not-a-route")
    assert response.status_code == 404


def test_unhandled_exception_returns_500_with_correlation_id() -> None:
    """The exception handler must return 500 with a correlation_id and no
    stack trace. Inject a route that deliberately raises."""
    from fastapi import APIRouter
    from src.api.main import app

    router = APIRouter()

    @router.get("/test-crash")
    async def _crash():
        raise RuntimeError("deliberate crash for test")

    app.include_router(router)
    client2 = TestClient(app, raise_server_exceptions=False)
    response = client2.get("/test-crash")
    assert response.status_code == 500
    body = response.json()
    assert "correlation_id" in body
    assert "error" in body
    # Must NOT contain stack trace fragments
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text
