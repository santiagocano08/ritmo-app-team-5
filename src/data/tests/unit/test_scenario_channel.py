"""T007 — D1 channel layer (004 FR-008, FR-009, SC-005).

The layer wraps the finished event stream: it drops or repeats lines and touches nothing else.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.data.simulator.engine import run
from src.data.simulator.scenarios.channel import apply_channel
from src.data.simulator.scenarios.config import load_scenarios, parse_scenarios
from src.data.simulator.scenarios.truth import TruthSink

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios"
T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
BUS_TYPES = {"bus_position", "stop_arrival", "stop_departure"}


def secs(event: dict) -> int:
    return int((datetime.fromisoformat(event["event_ts"].replace("Z", "+00:00")) - T0).total_seconds())


@pytest.fixture(scope="module")
def base() -> list[dict]:
    return list(run(42, 3600))


def wrap(base, scenarios):
    truth = TruthSink(scenarios)
    out = list(apply_channel(iter(base), scenarios, T0, truth))
    truth.close()
    return out, truth.records()


def test_silence_drops_only_the_three_bus_report_types_of_the_target_in_its_window(base) -> None:
    out, truth = wrap(base, load_scenarios(FIXTURES / "d1_silence.json"))

    def dropped(e):
        return (e["event_type"] in BUS_TYPES and e["payload"]["bus_id"] == "B-101" and 250 <= secs(e) < 550)

    assert out == [e for e in base if not dropped(e)]
    removed = [e for e in base if dropped(e)]
    assert removed and {e["event_type"] for e in removed} <= BUS_TYPES
    (rec,) = truth
    assert rec["fired"] is True and rec["effective_ts"] == removed[0]["event_ts"]


def test_silence_leaves_rider_arrivals_and_incident_reports(base) -> None:
    scen = parse_scenarios([{"id": "s", "type": "D1_SILENCE", "start_s": 0, "bus": "B-101", "duration_s": 3600}])
    out, _ = wrap(base, scen)
    assert [e for e in out if e["event_type"] == "rider_arrival"] == [e for e in base if e["event_type"] == "rider_arrival"]
    assert not [e for e in out if e["event_type"] in BUS_TYPES and e["payload"]["bus_id"] == "B-101"]
    # every other bus is untouched
    assert [e for e in out if e["event_type"] in BUS_TYPES and e["payload"]["bus_id"] != "B-101"] == \
        [e for e in base if e["event_type"] in BUS_TYPES and e["payload"]["bus_id"] != "B-101"]


def test_silence_window_with_no_events_is_recorded_as_not_fired(base) -> None:
    scen = parse_scenarios([{"id": "s", "type": "D1_SILENCE", "start_s": 100000, "bus": "B-101", "duration_s": 5}])
    out, truth = wrap(base, scen)
    assert out == base
    assert truth[0]["fired"] is False and truth[0]["effective_ts"] is None


def test_duplicates_repeat_exactly_count_consecutive_lines(base) -> None:
    out, truth = wrap(base, load_scenarios(FIXTURES / "d1_duplicates.json"))
    assert len(out) == len(base) + 20
    firsts = [i for i, e in enumerate(base) if secs(e) >= 100][:20]
    chosen = [base[i] for i in firsts]
    expected: list[dict] = []
    for i, e in enumerate(base):
        expected.append(e)
        if i in firsts:
            expected.append(e)
    assert out == expected
    # same source, same event_id, same bytes
    for a, b in zip(out, out[1:]):
        if a["event_id"] == b["event_id"]:
            assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    (rec,) = truth
    assert rec["event_ids"] == [e["event_id"] for e in chosen]
    assert rec["fired"] is True and rec["effective_ts"] == chosen[0]["event_ts"]


def test_duplicates_beyond_the_end_of_the_run_are_fewer_than_count(base) -> None:
    scen = parse_scenarios([{"id": "d", "type": "D1_DUPLICATES", "start_s": 100000, "count": 5}])
    out, truth = wrap(base, scen)
    assert out == base and truth[0]["fired"] is False and truth[0]["event_ids"] == []


def test_world_scenarios_are_ignored_by_the_channel(base) -> None:
    out, truth = wrap(base, load_scenarios(FIXTURES / "c5_breakdown.json"))
    assert out == base
    assert truth[0]["fired"] is False  # the world hook, not the channel, fires it


def test_channel_is_deterministic(base) -> None:
    scen = load_scenarios(FIXTURES / "phase1_live.json")
    assert wrap(base, scen) == wrap(base, scen)
