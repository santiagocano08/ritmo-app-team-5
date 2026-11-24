"""T008 — hidden scenario truth (004 FR-010, FR-011, SC-001, SC-006; data-model E2)."""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path

from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.config import load_scenarios, parse_scenarios
from src.data.simulator.scenarios.truth import TruthSink

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios"
T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
COMMON = {"scenario_id", "type", "params", "bus", "stop", "fired", "effective_ts"}


def secs(ts: str) -> int:
    return int((datetime.fromisoformat(ts.replace("Z", "+00:00")) - T0).total_seconds())


def run_truth(scenarios, duration=3600, seed=42, **sink_kw):
    truth = TruthSink(scenarios, **sink_kw)
    events = list(scenario_events(scenarios, seed, duration, truth))
    truth.close()
    return events, truth


def test_one_record_per_injector_with_the_data_model_fields() -> None:
    scenarios = load_scenarios(FIXTURES / "phase1_live.json")
    _, truth = run_truth(scenarios)
    recs = {r["scenario_id"]: r for r in truth.records()}
    assert set(recs) == {"c1-b102", "c5-b104", "d1-silence-b101", "d1-dup"}
    assert set(recs["c1-b102"]) == COMMON | {"follower_gap_s", "target_reached"}
    assert set(recs["c5-b104"]) == COMMON
    assert set(recs["d1-silence-b101"]) == COMMON
    assert set(recs["d1-dup"]) == COMMON | {"event_ids"}
    assert recs["c1-b102"]["params"] == {"start_s": 520, "extra_s": 310}
    assert recs["c1-b102"]["bus"] == "B-102" and recs["c1-b102"]["stop"] == "P-884"
    assert recs["d1-dup"]["bus"] is None and recs["d1-dup"]["stop"] is None
    assert all(r["fired"] for r in recs.values())


def test_records_are_ordered_by_effective_time_then_configuration_order() -> None:
    scenarios = load_scenarios(FIXTURES / "phase1_live.json")
    _, truth = run_truth(scenarios)
    ids = [r["scenario_id"] for r in truth.records()]
    # d1-silence-b101 starts 250 s, d1-dup 500 s, c1 fires at its arrival (535 s), c5 at 1,860 s
    assert ids == ["d1-silence-b101", "d1-dup", "c1-b102", "c5-b104"]
    times = [r["effective_ts"] for r in truth.records()]
    assert times == sorted(times)


def test_tie_on_effective_time_follows_configuration_order() -> None:
    scenarios = parse_scenarios([
        {"id": "z", "type": "D1_SILENCE", "start_s": 0, "bus": "B-101", "duration_s": 5},
        {"id": "a", "type": "D1_SILENCE", "start_s": 0, "bus": "B-101", "duration_s": 5},
    ])
    _, truth = run_truth(scenarios, duration=60)
    assert [r["scenario_id"] for r in truth.records()] == ["z", "a"]


def test_never_fired_records_come_last_with_fired_false() -> None:
    scenarios = parse_scenarios([
        {"id": "late", "type": "C5", "start_s": 99999, "bus": "B-101", "duration_s": 60},
        {"id": "c1", "type": "C1", "start_s": 520, "bus": "B-102", "stop": "P-884", "extra_s": 310},
        {"id": "late-dup", "type": "D1_DUPLICATES", "start_s": 99999, "count": 3},
    ])
    _, truth = run_truth(scenarios)
    recs = truth.records()
    assert [r["scenario_id"] for r in recs] == ["c1", "late", "late-dup"]
    assert recs[1]["fired"] is False and recs[1]["effective_ts"] is None
    assert recs[2]["fired"] is False and recs[2]["event_ids"] == []


def test_c1_records_the_follower_gap_and_whether_the_target_was_reached() -> None:
    events, truth = run_truth(load_scenarios(FIXTURES / "c1_bunching.json"))
    (rec,) = truth.records()

    def dep(bus: str) -> int:
        return next(secs(e["event_ts"]) for e in events if e["event_type"] == "stop_departure"
                    and e["payload"]["bus_id"] == bus and e["payload"]["stop_id"] == "P-884"
                    and e["payload"]["trip_id"].endswith("001"))

    assert rec["follower_gap_s"] == dep("B-103") - dep("B-102")
    assert rec["target_reached"] is (rec["follower_gap_s"] < 300)
    assert rec["target_reached"] is True


def test_c1_gap_is_null_until_a_follower_departs() -> None:
    scenarios = load_scenarios(FIXTURES / "c1_bunching.json")
    _, truth = run_truth(scenarios, duration=800)  # the delayed bus is still dwelling at the stop (535 + 310 s)
    (rec,) = truth.records()
    assert rec["fired"] is True
    assert rec["follower_gap_s"] is None and rec["target_reached"] is None


def test_duplicate_event_ids_are_listed() -> None:
    _, truth = run_truth(load_scenarios(FIXTURES / "d1_duplicates.json"))
    ids = truth.records()[0]["event_ids"]
    assert len(ids) == 20 and len(set(ids)) == 20


def test_two_runs_give_identical_records() -> None:
    scenarios = load_scenarios(FIXTURES / "phase1_live.json")
    assert run_truth(scenarios)[1].records() == run_truth(scenarios)[1].records()


def test_records_hold_no_event_payload_and_no_secret() -> None:
    _, truth = run_truth(load_scenarios(FIXTURES / "phase1_live.json"))
    text = json.dumps(truth.records())
    for forbidden in ("payload", "postgresql://", "password", "PASSWORD", "DATABASE_URL"):
        assert forbidden not in text


def test_sink_writes_json_lines_to_the_path_at_close(tmp_path: Path) -> None:
    path = tmp_path / "truth.jsonl"
    _, truth = run_truth(load_scenarios(FIXTURES / "phase1_live.json"), path=path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == truth.records()
    truth.close()  # closing twice must not write twice
    assert len(path.read_text(encoding="utf-8").splitlines()) == len(lines)


def test_sink_writes_to_the_stream_when_no_path() -> None:
    err = io.StringIO()
    _, truth = run_truth(load_scenarios(FIXTURES / "c5_demo.json"), stream=err)
    assert [json.loads(line) for line in err.getvalue().splitlines()] == truth.records()


def test_empty_scenario_list_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    TruthSink([], path=path).close()
    assert not path.exists()
