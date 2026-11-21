"""T065 — the `refresh` compose service (FR-041, R16, Principle III) and its healthcheck."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module")
def services() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]


def _depends(service: dict) -> dict:
    deps = service.get("depends_on", {})
    return {k: {} for k in deps} if isinstance(deps, list) else deps


def test_refresh_service_runs_the_loop_from_the_existing_image(services: dict) -> None:
    refresh = services["refresh"]
    assert refresh["build"]["dockerfile"] == "Dockerfile"
    assert refresh["build"].get("target", "prod") == "prod"
    assert refresh["command"] == ["python", "-m", "src.data.refresh.run"]
    assert refresh["restart"] == "unless-stopped"


def test_refresh_depends_only_on_a_healthy_db(services: dict) -> None:
    deps = _depends(services["refresh"])
    assert set(deps) == {"db"}
    assert deps["db"]["condition"] == "service_healthy"


def test_refresh_takes_its_settings_from_the_environment(services: dict) -> None:
    env = services["refresh"]["environment"]
    for key in ("DATABASE_URL", "LOG_LEVEL", "REFRESH_CLOCK", "REFRESH_INTERVAL_S", "REFRESH_HEALTH_MAX_AGE_S"):
        assert key in env
    assert "${REFRESH_CLOCK:-data}" in env["REFRESH_CLOCK"]
    assert "${REFRESH_INTERVAL_S:-5}" in env["REFRESH_INTERVAL_S"]
    assert "${REFRESH_HEALTH_MAX_AGE_S:-30}" in env["REFRESH_HEALTH_MAX_AGE_S"]
    # no literal secret: the DSN is interpolated
    assert env["DATABASE_URL"] == "${DATABASE_URL}"


def test_refresh_has_a_freshness_healthcheck(services: dict) -> None:
    hc = services["refresh"]["healthcheck"]
    assert hc["test"] == ["CMD", "python", "-m", "src.data.refresh.health"]
    assert hc.get("start_period")


def test_no_service_depends_on_refresh_and_ingestion_depends_only_on_db(services: dict) -> None:
    for name, svc in services.items():
        if name != "refresh":
            assert "refresh" not in _depends(svc), name
    assert set(_depends(services["ingestion"])) == {"db"}
