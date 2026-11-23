"""`SIM_START_HOUR` / `--start-hour`: the local hour the simulated day starts at (demo setting).

Default 17 keeps every reference stream (golden hash) byte-identical. Another hour moves the timestamps
and follows that hour's demand; anything outside 0-23 stops before the first event.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from src.data.simulator.main import main
from src.data.tests.unit.test_simulator_golden_hash import GOLDEN

C1 = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios" / "c1_bunching.json"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("SIM_SCENARIO_FILE", "SIM_TRUTH_PATH", "SIM_HOLDS", "SIM_DEMAND_SCALE", "SIM_START_HOUR"):
        monkeypatch.delenv(name, raising=False)


def _out(duration: int, extra: list[str] | None = None) -> str:
    buf = io.StringIO()
    main(["--seed", "42", "--duration", str(duration), *(extra or [])], out=buf)
    return buf.getvalue()


def _first_ts(text: str) -> str:
    return json.loads(text.splitlines()[0])["event_ts"]


def _riders(text: str) -> int:
    return sum(1 for line in text.splitlines() if '"event_type": "rider_arrival"' in line)


@pytest.mark.parametrize("value", [None, "17", ""])
def test_unset_empty_and_17_give_the_golden_hash(monkeypatch: pytest.MonkeyPatch, value) -> None:
    if value is not None:
        monkeypatch.setenv("SIM_START_HOUR", value)
    assert hashlib.sha256(_out(3600).encode()).hexdigest() == GOLDEN[42]


def test_the_env_moves_the_first_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIM_START_HOUR", "7")
    assert _first_ts(_out(300)) == "2026-11-24T12:00:00Z"  # 07:00 local = 12:00Z


def test_the_cli_wins_over_the_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIM_START_HOUR", "7")
    assert _first_ts(_out(300, ["--start-hour", "20"])) == "2026-11-25T01:00:00Z"  # 20:00 local, next day UTC


def test_the_hour_reaches_the_scenario_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIM_START_HOUR", "7")
    assert _first_ts(_out(300, ["--scenario-file", str(C1)])) == "2026-11-24T12:00:00Z"


def test_a_quiet_hour_has_fewer_riders_than_the_peak(monkeypatch: pytest.MonkeyPatch) -> None:
    peak = _riders(_out(1800))
    monkeypatch.setenv("SIM_START_HOUR", "2")
    assert _riders(_out(1800)) < peak / 10


@pytest.mark.parametrize("value", ["24", "-1", "abc", "7.5"])
def test_values_out_of_range_stop_before_the_first_event(monkeypatch: pytest.MonkeyPatch, value, capsys) -> None:
    monkeypatch.setenv("SIM_START_HOUR", value)
    buf = io.StringIO()
    with pytest.raises(SystemExit) as exc:
        main(["--seed", "42", "--duration", "300"], out=buf)
    assert exc.value.code == 2 and buf.getvalue() == ""
    assert "SIM_START_HOUR" in capsys.readouterr().err
