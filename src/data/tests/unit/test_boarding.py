"""005 US4 — pure boarding rule, simple method (FR-040 to FR-042, FR-045, SC-009, SC-010)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from src.data.rules import boarding
from src.data.rules.boarding import BOARDING_THRESHOLDS_S, BoardCounts, count_riders, wait_s
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.config import load_scenarios
from src.data.simulator.scenarios.truth import TruthSink
from src.data.tests.fixtures import oracle_stop_metrics as oracle

T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)   # 17:00 local, band 68
C1 = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios" / "c1_bunching.json"
DAY = date(2026, 11, 24)


def at(secs: float) -> datetime:
    return T0 + timedelta(seconds=secs)


def run(arrivals, deps, as_of):
    return count_riders(arrivals, {s: [at(x) for x in v] for s, v in deps.items()}, at(as_of))


def test_thresholds_are_a_named_constant() -> None:
    assert BOARDING_THRESHOLDS_S == (300, 600, 900)
    assert boarding.BOARDING_THRESHOLDS_S is BOARDING_THRESHOLDS_S


def test_arrival_exactly_at_a_departure_counts_with_wait_zero() -> None:
    assert wait_s(at(100), [at(100)], at(200)) == Decimal(0)
    got = run([("P-884", at(100))], {"P-884": [100]}, 200)
    assert got == {(DAY, 68, "P-884"): BoardCounts(1, 1, 1, 1)}


def test_wait_is_to_the_next_departure_only() -> None:
    deps = [at(50), at(400), at(2000)]
    assert wait_s(at(100), deps, at(5000)) == Decimal(300)
    assert wait_s(at(401), deps, at(5000)) == Decimal(1599)
    assert wait_s(at(2001), deps, at(5000)) is None


def test_departure_after_as_of_is_not_seen() -> None:
    assert wait_s(at(100), [at(400)], at(399)) is None
    assert wait_s(at(100), [at(400)], at(400)) == Decimal(300)


def test_thresholds_are_inclusive() -> None:
    got = run([("P-884", at(0)), ("P-885", at(0)), ("P-886", at(0)), ("P-887", at(0))],
              {"P-884": [300], "P-885": [600], "P-886": [900], "P-887": [901]}, 5000)
    assert got[(DAY, 68, "P-884")] == BoardCounts(1, 1, 1, 1)
    assert got[(DAY, 68, "P-885")] == BoardCounts(1, 0, 1, 1)
    assert got[(DAY, 68, "P-886")] == BoardCounts(1, 0, 0, 1)
    assert got[(DAY, 68, "P-887")] == BoardCounts(1, 0, 0, 0)


def test_a_rider_with_no_departure_counts_only_in_n_riders() -> None:
    got = run([("P-884", at(100))], {"P-884": []}, 5000)
    assert got == {(DAY, 68, "P-884"): BoardCounts(1, 0, 0, 0)}


def test_open_rider_moves_into_the_columns_when_a_later_cycle_sees_the_departure() -> None:
    arrivals = [("P-884", at(100))]
    early = run(arrivals, {"P-884": [350]}, 300)       # departure after as_of: still open
    assert early[(DAY, 68, "P-884")] == BoardCounts(1, 0, 0, 0)
    later = run(arrivals, {"P-884": [350]}, 400)
    assert later[(DAY, 68, "P-884")] == BoardCounts(1, 1, 1, 1)


def test_a_rider_whose_wait_exceeds_t_is_never_counted_for_that_t() -> None:
    got = run([("P-884", at(0))], {"P-884": [700]}, 5000)
    assert got[(DAY, 68, "P-884")] == BoardCounts(1, 0, 0, 1)
    assert run([("P-884", at(0))], {"P-884": []}, 700)[(DAY, 68, "P-884")] == BoardCounts(1, 0, 0, 0)


def test_the_band_is_the_one_of_the_arrival() -> None:
    arrive = datetime(2026, 11, 24, 22, 14, 59, tzinfo=timezone.utc)   # 17:14:59 local
    served = datetime(2026, 11, 24, 22, 15, 30, tzinfo=timezone.utc)
    got = count_riders([("P-884", arrive)], {"P-884": [served]}, served)
    assert got == {(DAY, 68, "P-884"): BoardCounts(1, 1, 1, 1)}
    got = count_riders([("P-884", arrive + timedelta(seconds=1))], {"P-884": [served]}, served)
    assert list(got) == [(DAY, 69, "P-884")]


def test_a_stop_outside_the_reference_stops_counts_nowhere() -> None:
    assert run([("P-999", at(10))], {"P-884": [20]}, 100) == {}


def test_counts_are_ordered_and_additive_by_stop() -> None:
    arrivals = [("P-884", at(i * 37)) for i in range(30)] + [("P-885", at(i * 53)) for i in range(20)]
    got = run(arrivals, {"P-884": [100, 900, 1500], "P-885": [700]}, 1200)
    assert sum(v.n_riders for v in got.values()) == 50
    for v in got.values():
        assert v.n_le_5 <= v.n_le_10 <= v.n_le_15 <= v.n_riders


# -- the independent oracle agrees with the plan (self-check, no database) ----------------------------------------
@pytest.fixture(scope="module")
def c1_events() -> list[dict]:
    scenarios = load_scenarios(C1)
    return list(scenario_events(scenarios, 42, 2700, TruthSink(scenarios)))


def test_oracle_matches_the_quickstart_table(c1_events) -> None:
    as_of = oracle.epoch("2026-11-24T22:45:00Z")
    by_band = oracle.riders_by_band(c1_events, as_of)
    got = {b: tuple(v.values()) for (_, b), v in by_band.items()}
    assert got == {68: (9, 3, 9, 9), 69: (16, 10, 16, 16), 70: (21, 9, 14, 15)}
    per_stop = oracle.riders(c1_events, as_of)
    assert sum(v["n_riders"] for v in per_stop.values()) == 46
    assert sum(v["n_riders"] for (_, _, s), v in per_stop.items() if s == "P-883") == 37


def test_pure_rule_equals_the_oracle_on_the_c1_stream(c1_events) -> None:
    as_of = oracle.epoch("2026-11-24T22:45:00Z")

    def ts(e):
        return datetime.fromisoformat(e["event_ts"].replace("Z", "+00:00"))

    deps: dict[str, list[datetime]] = {s: [] for s in oracle.STOPS}
    for e in c1_events:
        if e["event_type"] == "stop_departure":
            deps[e["payload"]["stop_id"]].append(ts(e))
    for v in deps.values():
        v.sort()
    arrivals = [(e["payload"]["stop_id"], ts(e)) for e in c1_events if e["event_type"] == "rider_arrival"]
    got = count_riders(arrivals, deps, at(2700))
    want = oracle.riders(c1_events, as_of)
    assert {(d.isoformat(), b, s) for d, b, s in got} == set(want)
    for (d, b, s), c in got.items():
        w = want[(d.isoformat(), b, s)]
        assert (c.n_riders, c.n_le_5, c.n_le_10, c.n_le_15) == (w["n_riders"], w["n_le_5"], w["n_le_10"], w["n_le_15"])
