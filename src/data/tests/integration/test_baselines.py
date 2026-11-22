"""T052-T054 — M1 and M2 baselines against independent oracles (SC-006, FR-026..FR-031, R12, R13).

Oracles are recomputed from `data/reference/*.csv` with `Decimal` and `statistics.median`; nothing
here calls the code under test to build an expected value.
"""
from __future__ import annotations

import csv
import statistics
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from src.data.rules import RULES_VERSION
from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import cycle

REF = Path(__file__).resolve().parents[4] / "data" / "reference"
pytestmark = pytest.mark.usefixtures("config_reset")

DAY = 86_400
# T0 = 22:00Z = 17:00 local: M1 hour band 17, M2 bands 68..71.
HOUR = 17
BAND = 68


def _csv(name: str) -> list[dict]:
    with (REF / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _m1_reference(segment: int, hour: int) -> Decimal:
    seg = next(r for r in _csv("segments.csv") if int(r["segment_id"]) == segment)
    factor = next(r for r in _csv("congestion_factor.csv") if int(r["hour"]) == hour)
    return Decimal(seg["length_m"]) / (Decimal(seg["free_flow_kmh"]) / Decimal("3.6")) / Decimal(factor["congestion_factor"])


def _m2_reference(hour: int, volume: Decimal | None = None, shapes: dict[int, Decimal] | None = None) -> int:
    vol = volume if volume is not None else Decimal(_csv("demand_volume.csv")[0]["daily_riders_dir1"])
    if shapes is not None and hour in shapes:
        shape = shapes[hour]
    else:
        shape = Decimal(next(r for r in _csv("demand_params.csv") if int(r["hour"]) == hour)["metro_line_a_shape"])
    return int((vol * shape / Decimal(4)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _m1(conn) -> dict[tuple[int, int], tuple]:
    rows = conn.execute("SELECT segment_id, hour_band, forecast_travel_s, source, n_samples, rules_version, "
                        "max_bronze_id FROM gold.m1_baseline").fetchall()
    return {(r[0], r[1]): r[2:] for r in rows}


def _m2(conn) -> dict[int, tuple]:
    rows = conn.execute("SELECT band, arrivals_forecast, source, n_samples, stop_id, rules_version, "
                        "max_bronze_id FROM gold.m2_baseline").fetchall()
    return {r[0]: r[1:] for r in rows}


def _traversal(b: bb.Builder, bus: str, n: int, segment: int, depart: float, travel: float,
               reports: bool = True) -> None:
    """One segment traversal with a position report every 30 s inside it (so it is not flagged)."""
    trip = bb.trip_id(bus, n)
    b.traversal(bus, trip, segment, depart, depart + travel)
    if reports:
        t = depart + 30
        while t < depart + travel:
            b.position(bus, trip, t, 100.0)
            t += 30


def _clean(b: bb.Builder, segment: int, travels: list[float], base: float = 0, bus: str = "B-101") -> None:
    for i, travel in enumerate(travels, start=1):
        _traversal(b, bus, i, segment, base + 300 * i, travel)


def _run(conn, b: bb.Builder, as_of_s: float):
    assert all(r.accepted for r in bb.ingest_all(conn, b.events))
    conn.commit()
    result = cycle(conn, as_of_s)
    assert result is not None
    return result


# ------------------------------------------------------------------------------ M1 (T052)
def test_m1_without_history_is_the_reference_formula_for_all_408_rows(gold_conn) -> None:
    result = _run(gold_conn, bb.Builder("m1-empty"), 3600)
    m1 = _m1(gold_conn)
    assert len(m1) == 17 * 24
    for (segment, hour), (value, source, n, rules_version, max_id) in m1.items():
        assert source == "reference" and n == 0
        assert abs(Decimal(value) - _m1_reference(segment, hour)) <= Decimal("0.1"), (segment, hour)
        assert rules_version == RULES_VERSION and max_id == result.max_bronze_id


def test_m1_observed_is_the_median_of_eligible_traversals(gold_conn) -> None:
    b = bb.Builder("m1-observed")
    travels = [100.0, 200.0, 300.0, 400.0, 500.0, 650.0]  # even count: mean of 300 and 400
    _clean(b, 3, travels)
    _run(gold_conn, b, 9000)
    value, source, n, *_ = _m1(gold_conn)[(3, HOUR)]
    assert source == "observed" and n == 6
    assert Decimal(value) == Decimal(str(statistics.median(travels))) == Decimal("350")
    # A neighbouring band and segment of the same run stay on the reference.
    assert _m1(gold_conn)[(3, HOUR - 1)][1] == "reference"
    assert _m1(gold_conn)[(4, HOUR)][1] == "reference"


def test_m1_odd_count_uses_the_middle_value(gold_conn) -> None:
    b = bb.Builder("m1-odd")
    travels = [90.0, 410.0, 120.0, 300.0, 250.0]
    _clean(b, 5, travels)
    _run(gold_conn, b, 9000)
    value, source, n, *_ = _m1(gold_conn)[(5, HOUR)]
    assert (source, n) == ("observed", 5)
    assert Decimal(value) == Decimal(str(statistics.median(travels)))


def test_m1_four_samples_fall_back_to_the_reference_and_record_the_count(gold_conn) -> None:
    b = bb.Builder("m1-four")
    _clean(b, 3, [100.0, 200.0, 300.0, 400.0])
    _run(gold_conn, b, 9000)
    value, source, n, *_ = _m1(gold_conn)[(3, HOUR)]
    assert (source, n) == ("reference", 4)
    assert abs(Decimal(value) - _m1_reference(3, HOUR)) <= Decimal("0.1")


def test_m1_flagged_traversals_are_not_counted(gold_conn) -> None:
    b = bb.Builder("m1-flagged")
    clean = [100.0, 200.0, 300.0, 400.0, 500.0]
    _clean(b, 3, clean)
    # Estimated: only the stop events inside a 300 s traversal, so the bus is silent for more than 120 s.
    _traversal(b, "B-103", 1, 3, 600, 300.0, reports=False)
    # Broken down: B-102 has an active bus_breakdown while it crosses the segment.
    _traversal(b, "B-102", 1, 3, 600, 100.0)
    b.incident("bus_breakdown", "B-102", at=500, duration_min=30.0)
    _run(gold_conn, b, 9000)
    value, source, n, *_ = _m1(gold_conn)[(3, HOUR)]
    assert (source, n) == ("observed", 5)
    assert Decimal(value) == Decimal(str(statistics.median(clean)))


def test_m1_minimum_sample_count_comes_from_config(gold_conn) -> None:
    gold_conn.execute("UPDATE config.corridor_settings SET min_sample_count = 3")
    b = bb.Builder("m1-config")
    _clean(b, 3, [100.0, 300.0, 500.0])
    _run(gold_conn, b, 9000)
    value, source, n, *_ = _m1(gold_conn)[(3, HOUR)]
    assert (source, n) == ("observed", 3) and Decimal(value) == 300


# ------------------------------------------------------------------------------ M2 (T053)
def test_m2_without_history_is_the_reference_formula_for_all_96_bands(gold_conn) -> None:
    result = _run(gold_conn, bb.Builder("m2-empty"), 3600)
    m2 = _m2(gold_conn)
    assert sorted(m2) == list(range(96))
    for band, (value, source, n, stop_id, rules_version, max_id) in m2.items():
        assert (source, n, stop_id) == ("reference", 0, "P-883")
        assert value == _m2_reference(band // 4), band
        assert rules_version == RULES_VERSION and max_id == result.max_bronze_id


def _days(b: bb.Builder, counts: list[int], start_day: int = 0, running: bool = True) -> None:
    """For each day: one bus report inside band 68 (if `running`) and `counts[i]` riders at P-883."""
    for i, count in enumerate(counts, start=start_day):
        base = i * DAY
        if running:
            b.position("B-101", bb.trip_id("B-101", i + 1), base + 300, 10.0)
        for k in range(count):
            b.rider_arrival("P-883", base + 60 + k, "P-890")


def test_m2_five_days_is_observed_and_a_zero_day_is_a_sample(gold_conn) -> None:
    b = bb.Builder("m2-observed")
    counts = [0, 1, 4, 5, 9]                    # the first day has the simulator running and no riders
    _days(b, counts)
    _run(gold_conn, b, 4 * DAY + 3600)
    value, source, n, *_ = _m2(gold_conn)[BAND]
    assert (source, n) == ("observed", 5)
    assert value == statistics.median(counts) == 4
    assert _m2(gold_conn)[BAND + 1][1:3] == ("reference", 0)   # no sample in the next band


def test_m2_half_rounds_away_from_zero_on_the_observed_path(gold_conn) -> None:
    gold_conn.execute("UPDATE config.corridor_settings SET min_sample_count = 2")
    b = bb.Builder("m2-half-observed")
    _days(b, [2, 3])                            # median 2.5 -> 3 (banker's rounding would give 2)
    _run(gold_conn, b, 1 * DAY + 3600)
    value, source, n, *_ = _m2(gold_conn)[BAND]
    assert (source, n, value) == ("observed", 2, 3)


def test_m2_half_rounds_away_from_zero_on_the_reference_path(gold_conn) -> None:
    gold_conn.execute("UPDATE config.ref_demand_volume SET daily_riders_dir1 = 40")
    gold_conn.execute("UPDATE config.ref_demand_shape SET metro_line_a_shape = 0.25 WHERE hour = %s", (HOUR,))
    gold_conn.commit()
    _run(gold_conn, bb.Builder("m2-half-reference"), 3600)
    m2 = _m2(gold_conn)
    volume, shapes = Decimal(40), {HOUR: Decimal("0.25")}
    assert volume * shapes[HOUR] / 4 == Decimal("2.5")            # exactly x.5 by construction
    for band, (value, source, *_rest) in m2.items():
        assert source == "reference"
        assert value == _m2_reference(band // 4, volume, shapes), band
    assert all(m2[band][0] == 3 for band in range(4 * HOUR, 4 * HOUR + 4))


# ------------------------------------------------------------------------------ M2 R12 (T054)
def test_m2_a_band_that_has_not_ended_is_not_a_sample(gold_conn) -> None:
    gold_conn.execute("UPDATE config.corridor_settings SET min_sample_count = 1")
    b = bb.Builder("m2-open")
    _days(b, [3])
    _run(gold_conn, b, 600)                      # 22:10Z, the band 22:00-22:15Z is still open
    assert _m2(gold_conn)[BAND][1:3] == ("reference", 0)


def test_m2_a_band_without_bus_reports_is_not_a_sample(gold_conn) -> None:
    gold_conn.execute("UPDATE config.corridor_settings SET min_sample_count = 1")
    b = bb.Builder("m2-no-bus")
    _days(b, [3], running=False)                 # riders only
    _run(gold_conn, b, 3600)
    assert _m2(gold_conn)[BAND][1:3] == ("reference", 0)


def test_m2_backend_events_do_not_count_as_the_simulator_running(gold_conn) -> None:
    gold_conn.execute("UPDATE config.corridor_settings SET min_sample_count = 1")
    b = bb.Builder("m2-backend")
    b.position("B-101", bb.trip_id("B-101"), 300, 10.0, source="backend")
    b.rider_arrival("P-883", 60, "P-890")
    _run(gold_conn, b, 3600)
    assert _m2(gold_conn)[BAND][1:3] == ("reference", 0)


def test_m2_todays_completed_bands_count(gold_conn) -> None:
    gold_conn.execute("UPDATE config.corridor_settings SET min_sample_count = 1")
    b = bb.Builder("m2-today")
    _days(b, [3])
    _run(gold_conn, b, 1500)                     # 22:25Z, the band ended at 22:15Z the same day
    value, source, n, *_ = _m2(gold_conn)[BAND]
    assert (source, n, value) == ("observed", 1, 3)
