"""T014: the ingestion service in docker-compose.yml receives the retry settings and stays isolated."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]


def _ingestion() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))["services"]["ingestion"]


def test_retry_settings_are_passed_with_defaults() -> None:
    env = _ingestion()["environment"]
    assert env["INGESTION_RETRY_INITIAL_S"] == "${INGESTION_RETRY_INITIAL_S:-1}"
    assert env["INGESTION_RETRY_MAX_WAIT_S"] == "${INGESTION_RETRY_MAX_WAIT_S:-5}"
    assert env["INGESTION_RETRY_TOTAL_S"] == "${INGESTION_RETRY_TOTAL_S:-120}"


def test_ingestion_depends_only_on_db() -> None:
    assert set(_ingestion()["depends_on"]) == {"db"}


def test_ingestion_healthcheck_is_the_freshness_probe() -> None:
    svc = _ingestion()
    hc = svc["healthcheck"]
    assert hc["test"] == ["CMD", "python", "-m", "src.data.ingestion.health"]
    assert (hc["interval"], hc["timeout"], hc["retries"], hc["start_period"]) == ("5s", "3s", 1, "20s")
    assert svc["environment"]["INGESTION_HEALTH_MAX_AGE_S"] == "${INGESTION_HEALTH_MAX_AGE_S:-15}"
    assert set(svc["depends_on"]) == {"db"}


def test_healthcheck_block_documents_its_timing() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    block = text[text.index("  ingestion:"):text.index("  api:")]
    assert "retries: 1" in block
    assert "#" in block[block.index("healthcheck:") - 400:block.index("healthcheck:")]
    assert "interval" in block.lower() and "start period" in block.lower()


def test_demand_scale_reaches_the_simulator_with_the_real_demand_as_default() -> None:
    """006 T044: the compose file lists variables explicitly, so the demo scale must be listed to arrive."""
    assert _ingestion()["environment"]["SIM_DEMAND_SCALE"] == "${SIM_DEMAND_SCALE:-1.0}"


def test_the_seed_variable_is_gone_from_ingestion() -> None:
    assert "SEED_" + "RECOMMENDATIONS_PATH" not in _ingestion()["environment"]
