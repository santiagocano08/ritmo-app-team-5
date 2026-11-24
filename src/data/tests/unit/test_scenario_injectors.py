"""T006 — world injectors C1, C2, C5 (004 FR-002, FR-005, FR-006, FR-007, SC-001).

Events are compared with the baseline run of the same seed; the injectors only change the world
at the stated point. Event time is converted to seconds after the run start (22:00:00Z).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.data.simulator.engine import run
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.config import load_scenarios
from src.data.simulator.scenarios.truth import TruthSink

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios"
T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
SEED, DURATION = 42, 3600


def secs(event: dict) -> int:
    return int((datetime.fromisoformat(event["event_ts"].replace("Z", "+00:00")) - T0).total_seconds())


def scenario_run(name: str, seed: int = SEED, duration: int = DURATION):
    scenarios = load_scenarios(FIXTURES / f"{name}.json")
    truth = TruthSink(scenarios)
    events = list(scenario_events(scenarios, seed, duration, truth))
    truth.close()
    return events, truth.records()


@pytest.fixture(scope="module")
def baseline() -> list[dict]:
    return list(run(SEED, DURATION))


def find(events, etype, bus, stop=None, trip_suffix="001"):
    return [e for e in events if e["event_type"] == etype and e["payload"].get("bus_id") == bus
            and (stop is None or e["payload"]["stop_id"] == stop)
            and e["payload"]["trip_id"].endswith(trip_suffix)]


def test_no_scenario_is_the_baseline_stream(baseline) -> None:
    assert list(scenario_events([], SEED, DURATION, TruthSink([]))) == baseline


def test_c1_extends_the_dwell_at_the_stop(baseline) -> None:
    events, truth = scenario_run("c1_bunching")
    arr = find(events, "stop_arrival", "B-102", "P-884")[0]
    dep = find(events, "stop_departure", "B-102", "P-884")[0]
    base_arr = find(baseline, "stop_arrival", "B-102", "P-884")[0]
    base_dep = find(baseline, "stop_departure", "B-102", "P-884")[0]
    assert secs(arr) == secs(base_arr) >= 520  # first arrival with t >= start_s, before the injector acts
    assert secs(dep) - secs(arr) == secs(base_dep) - secs(base_arr) + 310
    (rec,) = truth
    assert rec["fired"] is True and rec["effective_ts"] == arr["event_ts"]
    # the bus keeps reporting (speed 0) during the extra dwell
    reports = [e for e in events if e["event_type"] == "bus_position" and e["payload"]["bus_id"] == "B-102"
               and secs(arr) < secs(e) < secs(dep) and e["payload"]["trip_id"].endswith("001")]
    assert len(reports) >= 55 and {e["payload"]["speed_kmh"] for e in reports} == {0.0}


def test_c1_waits_for_the_first_arrival_at_or_after_start_s(baseline) -> None:
    scenarios = load_scenarios(FIXTURES / "c1_bunching.json")
    late = scenarios[0].model_copy(update={"start_s": 3460})
    truth = TruthSink([late])
    events = list(scenario_events([late], SEED, DURATION, truth))
    # 7 + 4 fleet at 420 s (issue #42): B-102 reaches P-884 at 535 s (trip 1) and 3,455 s (trip 2), both before
    # start_s; trip 3 is after the run ends, so the injector never fires and the stream is the baseline
    assert [secs(e) for e in events if e["event_type"] == "stop_arrival" and e["payload"]["bus_id"] == "B-102"
            and e["payload"]["stop_id"] == "P-884"] == [535, 3455]
    (rec,) = truth.records()
    assert rec["fired"] is False and rec["effective_ts"] is None
    assert events == baseline


def test_c2_delays_the_next_departure_from_the_origin(baseline) -> None:
    events, truth = scenario_run("c2_gap")
    arr = find(events, "stop_arrival", "B-103", "P-883")[0]
    base_arr = find(baseline, "stop_arrival", "B-103", "P-883")[0]
    assert secs(arr) == secs(base_arr) + 310
    (rec,) = truth
    assert rec["fired"] is True and rec["bus"] == "B-103"
    # buses not involved keep their baseline start
    other = find(events, "stop_arrival", "B-104", "P-883")[0]
    assert secs(other) == secs(find(baseline, "stop_arrival", "B-104", "P-883")[0])


def test_c5_halts_the_bus_and_reports_one_incident(baseline) -> None:
    events, truth = scenario_run("c5_breakdown")
    incidents = [e for e in events if e["event_type"] == "incident_report"]
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc["source"] == "simulator"
    assert inc["payload"] == {"incident_type": "bus_breakdown", "target_id": "B-102",
                              "duration_min": 4.0, "reported_by": "script"}
    t_inc = secs(inc)
    assert t_inc >= 1060
    window = [e for e in events if e["event_type"] == "bus_position" and e["payload"]["bus_id"] == "B-102"
              and t_inc <= secs(e) < t_inc + 240]
    assert len(window) == 48  # one report per 5 s step, the bus never goes silent
    assert {e["payload"]["speed_kmh"] for e in window} == {0.0}
    assert len({e["payload"]["distance_along_m"] for e in window}) == 1
    after = [e for e in events if e["event_type"] == "bus_position" and e["payload"]["bus_id"] == "B-102"
             and secs(e) >= t_inc + 240 and e["payload"]["trip_id"].endswith("001")]
    assert after[0]["payload"]["speed_kmh"] > 0
    (rec,) = truth
    assert rec["fired"] is True and rec["effective_ts"] == inc["event_ts"] and rec["bus"] == "B-102"
    # the stop is only a delay: the same trip still finishes
    assert find(events, "stop_arrival", "B-102", "P-900")


def test_c5_does_not_fire_when_the_bus_never_drives_after_start_s() -> None:
    scenarios = load_scenarios(FIXTURES / "c5_breakdown.json")
    never = [scenarios[0].model_copy(update={"start_s": 10_000})]
    truth = TruthSink(never)
    events = list(scenario_events(never, SEED, DURATION, truth))
    assert not [e for e in events if e["event_type"] == "incident_report"]
    assert truth.records()[0]["fired"] is False


@pytest.mark.parametrize("name", ["c1_bunching", "c2_gap", "c5_breakdown", "c5_demo"])
def test_world_injectors_keep_the_world_consistent(name: str) -> None:
    events, _ = scenario_run(name)
    # no bus over capacity
    assert max(e["payload"]["occupancy"] for e in events if e["event_type"] == "bus_position") <= 40
    # no overtaking on trip 1: an earlier starter is never behind a later one while both are on the road
    dist: dict[int, dict[str, float]] = {}
    for e in events:
        p = e["payload"]
        if e["event_type"] == "bus_position" and p["trip_id"].endswith("001"):
            dist.setdefault(secs(e), {})[p["bus_id"]] = p["distance_along_m"]
    order = ["B-101", "B-102", "B-103", "B-104", "B-105"]
    for t, row in dist.items():
        ahead = [row[b] for b in order if b in row and row[b] > 0]
        assert ahead == sorted(ahead, reverse=True), f"order inverted at {t} s: {row}"


def test_same_configuration_gives_the_same_events_and_truth() -> None:
    a = scenario_run("phase1_live")
    b = scenario_run("phase1_live")
    assert a == b


def test_modules_have_no_wall_clock_or_unseeded_random() -> None:
    root = Path(__file__).resolve().parents[2] / "simulator" / "scenarios"
    pattern = re.compile(r"(^\s*import\s+(time|random)\b)|(\btime\.(time|sleep|monotonic))|datetime\.now|"
                         r"\brandom\.|from\s+random\s+import|uuid\.uuid4|utcnow", re.MULTILINE)
    for name in ("injectors.py", "channel.py"):
        code = (root / name).read_text(encoding="utf-8")
        assert not pattern.search(code), name


# -- hold executor in the engine (T031; 004 FR-013, FR-014, FR-016, SC-007) --------------------------
from src.data.simulator.scenarios.config import parse_scenarios  # noqa: E402
from src.data.simulator.scenarios.holds import HoldBoard  # noqa: E402

INF = float("-inf")


def hold_run(orders, noncompliance: float = 0.0, scenarios=(), duration: int = 2400):
    """The scenario stream with `orders` on the board. Each order is (rec, bus, stop, hold_s, from_s, until_s)."""
    truth = TruthSink(list(scenarios))
    board = HoldBoard(seed=SEED, noncompliance=noncompliance, truth=truth, when=lambda t: f"t{t}")
    for o in orders:
        board.add_order(*o)
    events = list(scenario_events(list(scenarios), SEED, duration, truth, holds=board))
    truth.close()
    return events, truth.records()


def dwell_of(events, bus="B-103", stop="P-887") -> tuple[int, int]:
    arr = secs(find(events, "stop_arrival", bus, stop)[0])
    dep = secs(find(events, "stop_departure", bus, stop)[0])
    return arr, dep


@pytest.fixture(scope="module")
def base_events() -> list[dict]:
    return list(run(SEED, 2400))


def test_hold_extends_the_total_dwell_to_the_requested_seconds() -> None:
    events, truth = hold_run([("r1", "B-103", "P-887", 90, INF, 2100)])
    arr, dep = dwell_of(events)
    assert arr == 1295 and dep == 1295 + 90
    (rec,) = [r for r in truth if r["type"] == "HOLD"]
    assert rec["rec_id"] == "r1" and rec["complied"] is True and rec["hold_s"] == 90


def test_hold_keeps_reporting_with_doors_open_and_the_bus_does_not_move() -> None:
    events, _ = hold_run([("r1", "B-103", "P-887", 90, INF, 2100)])
    reports = [e for e in events if e["event_type"] == "bus_position" and e["payload"]["bus_id"] == "B-103"
               and 1295 < secs(e) < 1385 and e["payload"]["trip_id"].endswith("001")]
    assert len(reports) == 17 and all(e["payload"]["doors_open"] for e in reports)
    assert len({e["payload"]["distance_along_m"] for e in reports}) == 1


def test_a_natural_dwell_longer_than_the_hold_is_kept(base_events) -> None:
    events, _ = hold_run([("r1", "B-103", "P-887", 5, INF, 2100)])
    assert events == base_events


def test_non_compliance_leaves_with_the_natural_dwell(base_events) -> None:
    events, truth = hold_run([("r1", "B-103", "P-887", 90, INF, 2100)], noncompliance=1.0)
    assert events == base_events
    (rec,) = [r for r in truth if r["type"] == "HOLD"]
    assert rec["complied"] is False


def test_no_order_or_no_board_is_the_baseline(base_events) -> None:
    assert hold_run([])[0] == base_events
    assert list(scenario_events([], SEED, 2400, TruthSink([]), holds=None)) == base_events


def test_an_order_for_another_stop_or_bus_changes_nothing(base_events) -> None:
    events, _ = hold_run([("r1", "B-103", "P-890", 90, INF, 100)])  # window closes before the bus gets there
    assert events == base_events


def test_decision_must_precede_the_arrival_strictly(base_events) -> None:
    events, truth = hold_run([("r1", "B-103", "P-887", 90, 1295, 2100)])  # decided at the arrival instant
    assert events == base_events and not [r for r in truth if r["type"] == "HOLD"]
    events, _ = hold_run([("r1", "B-103", "P-887", 90, 1294, 2100)])
    assert dwell_of(events) == (1295, 1385)


def test_arrival_after_expiry_is_not_held(base_events) -> None:
    events, _ = hold_run([("r1", "B-103", "P-887", 90, INF, 1294)])
    assert events == base_events


def test_breakdown_cancels_the_pending_order() -> None:
    scenarios = parse_scenarios([{"id": "c5", "type": "C5", "start_s": 930, "bus": "B-103", "duration_s": 60}])
    events, truth = hold_run([("r1", "B-103", "P-887", 90, INF, 2400)], scenarios=scenarios)
    arr, dep = dwell_of(events)
    assert dep - arr <= 20  # natural dwell: the order was cancelled when the bus broke down
    assert not [r for r in truth if r["type"] == "HOLD"]


def test_second_order_for_the_same_visit_is_a_conflict_and_never_runs() -> None:
    events, truth = hold_run([("r1", "B-103", "P-887", 90, INF, 2100), ("r2", "B-103", "P-887", 80, INF, 2100)])
    assert dwell_of(events) == (1295, 1385)
    assert [r["rec_id"] for r in truth if r["type"] == "HOLD"] == ["r1"]


def test_hold_run_is_reproducible() -> None:
    assert hold_run([("r1", "B-103", "P-887", 90, INF, 2100)]) == hold_run([("r1", "B-103", "P-887", 90, INF, 2100)])
