"""T005 — scenario file validation (004 FR-001, FR-004, AC10).

Every invalid case fails before any event is produced, with a clear message.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from src.data.simulator.main import main
from src.data.simulator.scenarios.config import ScenarioConfigError, load_scenarios, parse_scenarios

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios"
INVALID = sorted((FIXTURES / "invalid").glob("*.json"))


def _c1(**kw):
    return {"id": "a", "type": "C1", "start_s": 0, "bus": "B-101", "stop": "P-884", "extra_s": 400, **kw}


def _c2(**kw):
    return {"id": "a", "type": "C2", "start_s": 0, "bus": "B-101", "delay_s": 400, **kw}


def _c5(**kw):
    return {"id": "a", "type": "C5", "start_s": 0, "bus": "B-101", "duration_s": 100, **kw}


def _silence(**kw):
    return {"id": "a", "type": "D1_SILENCE", "start_s": 0, "bus": "B-101", "duration_s": 10, **kw}


def _dups(**kw):
    return {"id": "a", "type": "D1_DUPLICATES", "start_s": 0, "count": 5, **kw}


@pytest.mark.parametrize("name", ["c1_bunching", "c2_gap", "c5_breakdown", "c5_demo", "d1_silence",
                                  "d1_duplicates", "phase1_live"])
def test_valid_fixtures_load(name: str) -> None:
    assert load_scenarios(FIXTURES / f"{name}.json")


def test_empty_array_and_unset_mean_no_scenario() -> None:
    assert load_scenarios(FIXTURES / "empty.json") == []
    assert load_scenarios(None) == []
    assert load_scenarios("") == []


def test_there_is_one_invalid_fixture_per_case() -> None:
    assert len(INVALID) == 9


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_fixture_is_rejected_with_a_message(path: Path) -> None:
    with pytest.raises(ScenarioConfigError) as exc:
        load_scenarios(path)
    assert str(exc.value).strip()


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_cli_exits_before_any_event(path: Path) -> None:
    out = io.StringIO()
    with pytest.raises(SystemExit) as exc:
        main(["--duration", "60", "--scenario-file", str(path)], out=out)
    assert exc.value.code != 0
    assert out.getvalue() == ""


@pytest.mark.parametrize("scenario", [
    _c1(extra_s=300), _c1(extra_s=600.5), _c2(delay_s=300), _c2(delay_s=601),
    _c5(duration_s=0), _c5(duration_s=300.5), _silence(duration_s=0),
    _dups(count=0), _dups(count=1001), _c1(start_s=-1), _c1(start_s=1.5),
    _c1(bus="B-106"), _c1(stop="P-883"), _c1(stop="P-900"), _c1(id=""),
    _c1(extra="x"), {"type": "C1"},
], ids=lambda s: json.dumps(s, sort_keys=True)[:60])
def test_out_of_range_values_are_rejected(scenario: dict) -> None:
    with pytest.raises(ScenarioConfigError):
        parse_scenarios([scenario])


@pytest.mark.parametrize("scenario", [
    _c1(extra_s=300.5), _c1(extra_s=600), _c1(stop="P-884"), _c1(stop="P-899"),
    _c2(delay_s=300.5), _c2(delay_s=600), _c5(duration_s=0.5), _c5(duration_s=300),
    _silence(duration_s=1), _silence(duration_s=100000), _dups(count=1), _dups(count=1000),
    _c1(start_s=999999),
], ids=lambda s: json.dumps(s, sort_keys=True)[:60])
def test_range_edges_are_accepted(scenario: dict) -> None:
    assert len(parse_scenarios([scenario])) == 1


def test_top_level_must_be_an_array_of_objects() -> None:
    for bad in ({"type": "C1"}, ["x"], "text", 3):
        with pytest.raises(ScenarioConfigError):
            parse_scenarios(bad)


def test_overlap_rule_only_covers_world_scenarios_on_one_bus() -> None:
    with pytest.raises(ScenarioConfigError, match="B-101"):
        parse_scenarios([_c1(id="a"), _c5(id="b")])
    # different buses, and D1 next to anything, are accepted
    assert len(parse_scenarios([_c1(id="a"), _c5(id="b", bus="B-102"), _silence(id="c"), _dups(id="d")])) == 4


def test_unreadable_or_malformed_file_is_a_config_error(tmp_path: Path) -> None:
    with pytest.raises(ScenarioConfigError):
        load_scenarios(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ScenarioConfigError):
        load_scenarios(bad)


def test_config_getters_default_to_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.pulsoflota.config import get_sim_scenario_file, get_sim_truth_path

    monkeypatch.delenv("SIM_SCENARIO_FILE", raising=False)
    monkeypatch.delenv("SIM_TRUTH_PATH", raising=False)
    assert get_sim_scenario_file() is None
    assert get_sim_truth_path() is None
    monkeypatch.setenv("SIM_SCENARIO_FILE", "")
    assert get_sim_scenario_file() is None
    monkeypatch.setenv("SIM_SCENARIO_FILE", "x.json")
    monkeypatch.setenv("SIM_TRUTH_PATH", "t.jsonl")
    assert get_sim_scenario_file() == "x.json"
    assert get_sim_truth_path() == "t.jsonl"


def test_flag_overrides_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIM_SCENARIO_FILE", str(FIXTURES / "invalid" / "unknown_bus.json"))
    out = io.StringIO()
    main(["--duration", "10", "--scenario-file", str(FIXTURES / "empty.json")], out=out)
    assert out.getvalue()  # the flag (valid) won over the invalid variable
