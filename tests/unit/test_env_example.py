"""T002 — .env.example documents the new settings, with no secrets (R3, R14, R16)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.pulsoflota.config import get_sim_planned_headway_s

ROOT = Path(__file__).resolve().parents[2]


def _env_example() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
    return values


def test_new_settings_documented_with_safe_defaults() -> None:
    env = _env_example()
    assert env["SIM_PLANNED_HEADWAY_S"] == "600"
    assert env["REFRESH_INTERVAL_S"] == "5"
    assert env["REFRESH_CLOCK"] == "data"


def test_no_new_setting_holds_a_secret() -> None:
    env = _env_example()
    for key in ("SIM_PLANNED_HEADWAY_S", "REFRESH_INTERVAL_S", "REFRESH_CLOCK"):
        assert env[key].replace(".", "").isalnum()
        assert "://" not in env[key] and "@" not in env[key]


def test_planned_headway_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIM_PLANNED_HEADWAY_S", raising=False)
    assert get_sim_planned_headway_s() == 600
    monkeypatch.setenv("SIM_PLANNED_HEADWAY_S", "450")
    assert get_sim_planned_headway_s() == 450


def test_planned_headway_rejects_invalid_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIM_PLANNED_HEADWAY_S", "abc")
    with pytest.raises(RuntimeError):
        get_sim_planned_headway_s()
    monkeypatch.setenv("SIM_PLANNED_HEADWAY_S", "0")
    with pytest.raises(RuntimeError):
        get_sim_planned_headway_s()


def test_compose_passes_planned_headway_to_ingestion() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    env = compose["services"]["ingestion"]["environment"]
    assert env["SIM_PLANNED_HEADWAY_S"] == "${SIM_PLANNED_HEADWAY_S:-600}"


def test_ingestion_retry_settings_documented_without_secrets() -> None:
    env = _env_example()
    assert env["INGESTION_RETRY_INITIAL_S"] == "1"
    assert env["INGESTION_RETRY_MAX_WAIT_S"] == "5"
    assert env["INGESTION_RETRY_TOTAL_S"] == "120"
    for key in ("INGESTION_RETRY_INITIAL_S", "INGESTION_RETRY_MAX_WAIT_S", "INGESTION_RETRY_TOTAL_S"):
        assert env[key].isdigit()
