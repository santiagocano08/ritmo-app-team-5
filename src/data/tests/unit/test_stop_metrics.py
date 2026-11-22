"""005 US3 — pure stop-headway rules (FR-030, FR-031, FR-032, FR-035, SC-005, SC-006)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from src.data.rules.service_metric import ewt_from_sums
from src.data.rules.stop_metrics import Departure, StopSums, add, band_sums, stop_intervals, window_sums
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.config import load_scenarios
from src.data.simulator.scenarios.truth import TruthSink
from src.data.tests.fixtures import oracle_stop_metrics as oracle

T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
C1 = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios" / "c1_bunching.json"


def dep(stop: str, secs: float, bus: str = "B-101", trip: str = "T", estimated: bool = False) -> Departure:
    return Departure(stop, bus, trip, T0 + timedelta(seconds=secs), estimated)


def test_headway_belongs_to_the_closing_departure() -> None:
    deps = [dep("P-884", 0), dep("P-884", 600, "B-102"), dep("P-884", 1300, "B-103")]
    assert [(i.closing_ts, i.headway_s) for i in stop_intervals(deps)] == [
        (T0 + timedelta(seconds=600), Decimal(600)), (T0 + timedelta(seconds=1300), Decimal(700))]
    # the opening departure may lie before the window; only the closing one decides
    s = window_sums(deps, T0 + timedelta(seconds=100), T0 + timedelta(seconds=700))
    assert (s.n, s.sum_h, s.sum_h2) == (1, Decimal(600), Decimal(360000))


def test_window_is_open_at_the_start_and_closed_at_the_end() -> None:
    deps = [dep("P-884", 0), dep("P-884", 600, "B-102")]
    assert window_sums(deps, T0 + timedelta(seconds=600), T0 + timedelta(seconds=900)).n == 0
    assert window_sums(deps, T0 + timedelta(seconds=300), T0 + timedelta(seconds=600)).n == 1


def test_one_departure_means_no_headway() -> None:
    deps = [dep("P-884", 0)]
    assert stop_intervals(deps) == []
    assert window_sums(deps, T0 - timedelta(hours=1), T0 + timedelta(hours=1)) == StopSums(0, Decimal(0), Decimal(0), 0)
    assert window_sums([], T0, T0) == StopSums(0, Decimal(0), Decimal(0), 0)


def test_stops_are_measured_separately() -> None:
    deps = [dep("P-884", 0), dep("P-885", 100, "B-102"), dep("P-884", 600, "B-103"), dep("P-885", 800, "B-104")]
    s = window_sums(deps, T0, T0 + timedelta(hours=1))
    assert (s.n, s.sum_h) == (2, Decimal(600 + 700))


def test_equal_timestamps_are_ordered_deterministically_and_give_a_zero_headway() -> None:
    a = [dep("P-884", 0, "B-102"), dep("P-884", 0, "B-101"), dep("P-884", 600, "B-103")]
    b = list(reversed(a))
    assert stop_intervals(a) == stop_intervals(b)
    assert [i.headway_s for i in stop_intervals(a)] == [Decimal(0), Decimal(600)]


def test_estimated_departure_excludes_both_headways_that_touch_it() -> None:
    deps = [dep("P-884", 0), dep("P-884", 600, "B-102", estimated=True), dep("P-884", 1200, "B-103"),
            dep("P-884", 1800, "B-104")]
    s = window_sums(deps, T0 - timedelta(seconds=1), T0 + timedelta(hours=1))
    assert (s.n, s.sum_h, s.n_excluded) == (1, Decimal(600), 2)


def test_a_lost_departure_leaves_no_trace() -> None:
    """Turn-1 limit (data owner, 2026-11-21): nothing is counted for a departure that was never reported."""
    deps = [dep("P-884", 0), dep("P-884", 1200, "B-103")]
    s = window_sums(deps, T0 - timedelta(seconds=1), T0 + timedelta(hours=1))
    assert (s.n, s.sum_h, s.n_excluded) == (1, Decimal(1200), 0)


def test_add_is_additive() -> None:
    a, b = StopSums(2, Decimal(900), Decimal(500000), 1), StopSums(3, Decimal(1500), Decimal(900000), 0)
    assert add(a, b) == StopSums(5, Decimal(2400), Decimal(1400000), 1)


def test_band_boundary_17_14_59_vs_17_15_00_local() -> None:
    # 22:14:59Z = 17:14:59 local (band 68); 22:15:00Z = 17:15:00 local (band 69)
    deps = [dep("P-884", 0), dep("P-884", 899, "B-102"), dep("P-884", 900, "B-103")]
    bands = band_sums(deps, T0 + timedelta(hours=2))
    assert set(bands) == {(datetime(2026, 11, 24).date(), 68, "P-884"), (datetime(2026, 11, 24).date(), 69, "P-884")}
    assert bands[(datetime(2026, 11, 24).date(), 68, "P-884")].sum_h == Decimal(899)
    assert bands[(datetime(2026, 11, 24).date(), 69, "P-884")].sum_h == Decimal(1)


def test_only_closed_bands_are_returned() -> None:
    deps = [dep("P-884", 0), dep("P-884", 899, "B-102"), dep("P-884", 900, "B-103")]
    day = datetime(2026, 11, 24).date()
    # band 69 ends at 22:30:00Z (1800 s): open at 1799, closed at 1800
    assert (day, 69, "P-884") not in band_sums(deps, T0 + timedelta(seconds=1799))
    assert (day, 68, "P-884") in band_sums(deps, T0 + timedelta(seconds=1799))
    assert (day, 69, "P-884") in band_sums(deps, T0 + timedelta(seconds=1800))


def test_a_band_row_exists_for_a_stop_with_only_excluded_headways() -> None:
    deps = [dep("P-884", 0), dep("P-884", 300, "B-102", estimated=True)]
    (key, sums), = band_sums(deps, T0 + timedelta(hours=2)).items()
    assert key[1:] == (68, "P-884") and (sums.n, sums.n_excluded) == (0, 1)


def test_local_date_changes_at_local_midnight() -> None:
    midnight = datetime(2026, 11, 25, 5, 0, 0, tzinfo=timezone.utc)  # 00:00 local
    deps = [Departure("P-884", "B-1", "T", midnight - timedelta(seconds=10), False),
            Departure("P-884", "B-2", "T", midnight + timedelta(seconds=10), False)]
    ((day, band, _),) = band_sums(deps, midnight + timedelta(hours=1))
    assert (day.isoformat(), band) == ("2026-11-25", 0)


@pytest.fixture(scope="module")
def c1_events() -> list[dict]:
    scenarios = load_scenarios(C1)
    return list(scenario_events(scenarios, 42, 2700, TruthSink(scenarios)))


def _departures(events: list[dict]) -> list[Departure]:
    return [Departure(e["payload"]["stop_id"], e["payload"]["bus_id"], e["payload"]["trip_id"],
                      datetime.fromisoformat(e["event_ts"].replace("Z", "+00:00")), False)
            for e in events if e["event_type"] == "stop_departure"]


def test_the_16_minute_oracle_window_without_the_hold(c1_events) -> None:
    deps = [d for d in _departures(c1_events) if d.stop_id in oracle.CORRIDOR_STOPS]
    s = window_sums(deps, T0 + timedelta(seconds=28 * 60 + 55), T0 + timedelta(seconds=44 * 60 + 55))
    assert (s.n, s.sum_h, s.sum_h2) == (27, Decimal(13290), Decimal(8660350))
    ewt = ewt_from_sums(s.n, s.sum_h, s.sum_h2, 600)[2]
    assert round(ewt, 1) == 25.8


def test_pure_rule_equals_the_oracle_on_every_stop_and_band(c1_events) -> None:
    deps = _departures(c1_events)
    as_of = T0 + timedelta(minutes=45)
    got = band_sums(deps, as_of)
    want = oracle.bands(c1_events, oracle.epoch("2026-11-24T22:45:00Z"))
    assert {(d.isoformat(), b, s) for d, b, s in got} == set(want)
    for (d, b, s), sums in got.items():
        w = want[(d.isoformat(), b, s)]
        assert (sums.n, sums.sum_h, sums.sum_h2, sums.n_excluded) == (w["n"], w["sum_h"], w["sum_h2"], w["n_excluded"])


def test_naive_timestamps_are_refused() -> None:
    naive = Departure("P-884", "B-101", "T", datetime(2026, 11, 24, 22, 0, 0))
    with pytest.raises(ValueError):
        stop_intervals([naive, dep("P-884", 600)])
