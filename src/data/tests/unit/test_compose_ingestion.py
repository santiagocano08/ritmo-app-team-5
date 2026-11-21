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
