"""
Integration test — T009 (US-2): isolation test.

Verifies Principle III: stopping the API container does not stop the ingestion
container.  After 'docker compose stop api', the ingestion container must still
be running and bronze.events must keep growing.

NOTE: This test scaffold is intentionally written in US-2. It finalises once
US-3 (ingestion write) and US-4 (simulator) are implemented; until then the
bronze growth assertion is relaxed to a 'container still running' check.

Requires:
  - Docker Compose stack already up (make up).
  - DATABASE_URL env var pointing at the running db service.
  - COMPOSE_PROJECT set to the docker-compose project name (default: ritmo-app-team-5).

The test stops the API container, waits, checks ingestion is still up, then
restarts the API so subsequent tests in the same session are unaffected.
"""
from __future__ import annotations

import os
import subprocess
import time

import pytest

COMPOSE_PROJECT = os.environ.get("COMPOSE_PROJECT", "ritmo-app-team-5")

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _compose(*args: str) -> subprocess.CompletedProcess:
    """Run a docker compose command and return the result."""
    cmd = ["docker", "compose"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def _container_running(service: str) -> bool:
    """Return True if the named compose service has a running container."""
    result = _compose("ps", "--status", "running", "--services")
    running = result.stdout.strip().splitlines()
    return service in running


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=False)
def api_stopped_then_restored():
    """Stop the API container before the test, restart it after."""
    # Pre-condition: api must be running
    if not _container_running("api"):
        pytest.skip("API service is not running — skipping isolation test")

    _compose("stop", "api")
    # Give Docker a moment to register the stop
    time.sleep(2)

    yield

    # Restore the API so other tests are not affected
    _compose("start", "api")
    # Wait for it to be healthy again (up to 15 s)
    for _ in range(15):
        if _container_running("api"):
            break
        time.sleep(1)


def test_ingestion_still_running_after_api_stop(api_stopped_then_restored) -> None:
    """After stopping the API, the ingestion container must still be running
    (Principle III: ingestion is isolated from the web/API service)."""
    assert _container_running("ingestion"), (
        "ingestion container is NOT running after the API was stopped — "
        "Principle III (isolated ingestion) is violated."
    )


def test_api_stopped(api_stopped_then_restored) -> None:
    """Confirm the API container is actually stopped (fixture worked)."""
    assert not _container_running("api"), (
        "API container is still running — the fixture did not stop it correctly."
    )


def test_db_still_running_after_api_stop(api_stopped_then_restored) -> None:
    """The database container must also survive the API stop."""
    assert _container_running("db"), (
        "db container stopped when the API was stopped — unexpected."
    )
