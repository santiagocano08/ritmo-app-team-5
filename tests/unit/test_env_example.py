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


def test_ingestion_health_setting_documented_without_secrets() -> None:
    env = _env_example()
    assert env["INGESTION_HEALTH_MAX_AGE_S"] == "15"
    assert env["INGESTION_HEALTH_MAX_AGE_S"].isdigit()


def test_scenario_settings_documented_and_enable_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """004: the scenario file and the truth path are optional; the documented defaults are empty."""
    from src.pulsoflota.config import get_sim_scenario_file, get_sim_truth_path

    env = _env_example()
    assert env["SIM_SCENARIO_FILE"] == "" and env["SIM_TRUTH_PATH"] == ""
    monkeypatch.setenv("SIM_SCENARIO_FILE", env["SIM_SCENARIO_FILE"])
    monkeypatch.setenv("SIM_TRUTH_PATH", env["SIM_TRUTH_PATH"])
    assert get_sim_scenario_file() is None and get_sim_truth_path() is None


def test_compose_passes_scenario_settings_to_ingestion_with_empty_defaults() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    env = compose["services"]["ingestion"]["environment"]
    assert env["SIM_SCENARIO_FILE"] == "${SIM_SCENARIO_FILE:-}"
    assert env["SIM_TRUTH_PATH"] == "${SIM_TRUTH_PATH:-}"


def test_hold_loop_settings_documented_with_safe_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """004 Phase 2: the hold loop is off by default; the documented values are safe and secret-free."""
    from src.pulsoflota.config import (get_seed_recommendations_path, get_sim_hold_noncompliance,
                                       get_sim_hold_poll_s, get_sim_holds)

    env = _env_example()
    assert env["SIM_HOLDS"] == "off" and env["SIM_HOLD_POLL_S"] == "1" and env["SIM_HOLD_NONCOMPLIANCE"] == "0.10"
    assert "SEED_RECOMMENDATIONS_PATH" in env
    for key in ("SIM_HOLDS", "SIM_HOLD_POLL_S", "SIM_HOLD_NONCOMPLIANCE", "SEED_RECOMMENDATIONS_PATH"):
        monkeypatch.setenv(key, env[key])
    assert get_sim_holds() is False and get_sim_hold_poll_s() == 1.0
    assert get_sim_hold_noncompliance() == 0.10 and get_seed_recommendations_path() is None
    for key in ("SIM_HOLDS", "SIM_HOLD_POLL_S", "SIM_HOLD_NONCOMPLIANCE", "SEED_RECOMMENDATIONS_PATH"):
        monkeypatch.delenv(key)
    assert get_sim_holds() is False and get_sim_hold_poll_s() == 1.0 and get_sim_hold_noncompliance() == 0.10


@pytest.mark.parametrize("name,value", [("SIM_HOLDS", "maybe"), ("SIM_HOLD_POLL_S", "0"), ("SIM_HOLD_POLL_S", "x"),
                                        ("SIM_HOLD_NONCOMPLIANCE", "1.5"), ("SIM_HOLD_NONCOMPLIANCE", "-0.1"),
                                        ("SIM_HOLD_NONCOMPLIANCE", "nan")])
def test_invalid_hold_settings_stop_the_process(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    from src.pulsoflota import config

    getter = {"SIM_HOLDS": config.get_sim_holds, "SIM_HOLD_POLL_S": config.get_sim_hold_poll_s,
              "SIM_HOLD_NONCOMPLIANCE": config.get_sim_hold_noncompliance}[name]
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        getter()


def test_compose_passes_hold_settings_to_ingestion_with_safe_defaults() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    env = compose["services"]["ingestion"]["environment"]
    assert env["SIM_HOLDS"] == "${SIM_HOLDS:-off}"
    assert env["SIM_HOLD_POLL_S"] == "${SIM_HOLD_POLL_S:-1}"
    assert env["SIM_HOLD_NONCOMPLIANCE"] == "${SIM_HOLD_NONCOMPLIANCE:-0.10}"
    assert env["SEED_RECOMMENDATIONS_PATH"] == "${SEED_RECOMMENDATIONS_PATH:-}"
    refresh = compose["services"]["refresh"]["environment"]
    assert refresh["SEED_RECOMMENDATIONS_PATH"] == "${SEED_RECOMMENDATIONS_PATH:-}"  # one seed file for both sides
