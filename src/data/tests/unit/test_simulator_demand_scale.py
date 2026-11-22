"""006 T031 — `SIM_DEMAND_SCALE` (FR-010 note; research R13; contracts/execution.md).

A demo setting of the simulator only: it changes how many riders are created, never the model.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest

from src.data.simulator.main import main
from src.data.tests.unit.test_simulator_golden_hash import GOLDEN

ROOT = Path(__file__).resolve().parents[4]
C1 = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios" / "c1_bunching.json"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("SIM_SCENARIO_FILE", "SIM_TRUTH_PATH", "SIM_HOLDS", "SIM_DEMAND_SCALE"):
        monkeypatch.delenv(name, raising=False)


def _out(seed: int, duration: int, extra: list[str] | None = None) -> str:
    buf = io.StringIO()
    main(["--seed", str(seed), "--duration", str(duration), *(extra or [])], out=buf)
    return buf.getvalue()


def _riders(text: str) -> int:
    return sum(1 for line in text.splitlines() if '"event_type": "rider_arrival"' in line)


@pytest.mark.parametrize("value", [None, "1.0", "1", ""])
def test_unset_and_one_give_the_golden_hash(monkeypatch: pytest.MonkeyPatch, value) -> None:
    if value is not None:
        monkeypatch.setenv("SIM_DEMAND_SCALE", value)
    assert hashlib.sha256(_out(42, 3600).encode()).hexdigest() == GOLDEN[42]


@pytest.mark.parametrize("value", ["0.1", "10", "3", "0.5"])
def test_values_in_range_are_accepted(monkeypatch: pytest.MonkeyPatch, value) -> None:
    monkeypatch.setenv("SIM_DEMAND_SCALE", value)
    assert _out(42, 300)


@pytest.mark.parametrize("value", ["0.05", "11", "abc", "0", "-1", "nan", "inf"])
def test_values_out_of_range_stop_before_the_first_event(monkeypatch: pytest.MonkeyPatch, value, capsys) -> None:
    monkeypatch.setenv("SIM_DEMAND_SCALE", value)
    buf = io.StringIO()
    with pytest.raises(SystemExit) as exc:
        main(["--seed", "42", "--duration", "300"], out=buf)
    assert exc.value.code == 2 and buf.getvalue() == ""
    assert "SIM_DEMAND_SCALE" in capsys.readouterr().err


def test_the_scale_creates_more_riders(monkeypatch: pytest.MonkeyPatch) -> None:
    base = _riders(_out(42, 1800))
    monkeypatch.setenv("SIM_DEMAND_SCALE", "3")
    assert _riders(_out(42, 1800)) > 2 * base


def test_the_scale_reaches_the_scenario_path(monkeypatch: pytest.MonkeyPatch) -> None:
    args = ["--scenario-file", str(C1)]
    base = _riders(_out(42, 1800, args))
    monkeypatch.setenv("SIM_DEMAND_SCALE", "3")
    scaled = _out(42, 1800, args)
    assert _riders(scaled) > 2 * base
    assert all(json.loads(line)["schema_version"] == "1.0.0" for line in scaled.splitlines()[:50])  # no new field


def test_the_scale_is_not_a_field_of_any_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIM_DEMAND_SCALE", "3")
    assert "demand_scale" not in _out(42, 300) and "SIM_DEMAND_SCALE" not in _out(42, 300)


def test_the_model_and_the_pipeline_never_read_it() -> None:
    """Principle III: the extra riders reach the model only as observed arrivals and queues."""
    paths = [ROOT / "src" / "pulsoflota" / "config.py",
             *sorted((ROOT / "src" / "data" / "rules").rglob("*.py")),
             *sorted((ROOT / "src" / "data" / "rules" / "sql").rglob("*.sql")),
             *sorted((ROOT / "src" / "data" / "pipeline").rglob("*.py"))]
    assert len(paths) > 10
    hits = [str(p.relative_to(ROOT)) for p in paths
            if "SIM_DEMAND_SCALE" in p.read_text(encoding="utf-8") or "demand_scale" in p.read_text(encoding="utf-8")]
    assert hits == []
