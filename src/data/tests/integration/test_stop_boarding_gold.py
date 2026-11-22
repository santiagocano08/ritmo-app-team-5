"""005 US4 — P(board <= t) counts in gold (FR-040 to FR-045, SC-009 to SC-011).

C1 seed 42, 2,700 s, through the real ingestion boundary into a throwaway database. Counts are compared with the
independent oracle (`fixtures/oracle_stop_metrics.py`, a recomputation from the raw events) and with the plan's figures.
The read queries are those of `specs/005-data-fixes-metrics/contracts/gold-stop-metrics.md` (Q-P1), run as written.
"""
from __future__ import annotations

from datetime import date

import pytest

from src.data.ingestion.bronze import ingest
from src.data.rules import RULES_VERSION
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.config import load_scenarios
from src.data.simulator.scenarios.truth import TruthSink
from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures import oracle_stop_metrics as oracle
from src.data.tests.fixtures.gold_support import cycle
from src.data.tests.integration.test_scenarios_gold import FIXTURES

T0 = oracle.epoch("2026-11-24T22:00:00Z")
DURATION = 2700
AS_OF = 2700        # 22:45:00Z
DAY = date(2026, 11, 24)
DAY_S = DAY.isoformat()

Q_P1 = (
    "SELECT sum(n_riders) AS n_riders, "
    "sum(n_board_le_5)::numeric  / nullif(sum(n_riders), 0) AS p_board_le_5, "
    "sum(n_board_le_10)::numeric / nullif(sum(n_riders), 0) AS p_board_le_10, "
    "sum(n_board_le_15)::numeric / nullif(sum(n_riders), 0) AS p_board_le_15 "
    "FROM gold.stop_boarding_band_v "
    "WHERE local_date = %(day)s AND band BETWEEN %(from_band)s AND %(to_band)s AND final")

Q_P1_STOP = Q_P1.replace("SELECT sum(n_riders)", "SELECT stop_id, sum(n_riders)") + " GROUP BY stop_id ORDER BY stop_id"


@pytest.fixture
def load(gold_conn):
    def go(scenario: str = "c1_bunching") -> list[dict]:
        scenarios = load_scenarios(FIXTURES / f"{scenario}.json")
        events = list(scenario_events(scenarios, 42, DURATION, TruthSink(scenarios)))
        for e in events:
            ingest(gold_conn, e)
        return events

    return go


def _rows(conn) -> dict[tuple, tuple]:
    rows = conn.execute("SELECT local_date, band, stop_id, n_riders, n_board_le_5, n_board_le_10, n_board_le_15 "
                        "FROM gold.stop_boarding_band").fetchall()
    return {(r[0].isoformat(), r[1], r[2]): r[3:] for r in rows}


def _band_totals(conn) -> dict[int, tuple]:
    out: dict[int, list] = {}
    for (_, band, _s), v in _rows(conn).items():
        acc = out.setdefault(band, [0, 0, 0, 0])
        for i, n in enumerate(v):
            acc[i] += n
    return {b: tuple(v) for b, v in out.items()}


# -- (a) counts equal the oracle and the plan ---------------------------------------------------------------------
def test_counts_equal_the_oracle_and_the_plan(gold_conn, load) -> None:
    events = load()
    result = cycle(gold_conn, AS_OF)
    got = _rows(gold_conn)
    want = oracle.riders(events, T0 + AS_OF)
    assert set(got) == set(want)
    for key, w in want.items():
        assert got[key] == (w["n_riders"], w["n_le_5"], w["n_le_10"], w["n_le_15"]), key
    assert _band_totals(gold_conn) == {68: (9, 3, 9, 9), 69: (16, 10, 16, 16), 70: (21, 9, 14, 15)}
    assert sum(v[0] for v in got.values()) == 46
    assert sum(v[0] for k, v in got.items() if k[2] == "P-883") == 37
    lineage = gold_conn.execute("SELECT DISTINCT rules_version, max_bronze_id FROM gold.stop_boarding_band").fetchall()
    assert lineage == [(RULES_VERSION, result.max_bronze_id)]


# -- (b) riders without a departure -------------------------------------------------------------------------------
def test_a_rider_with_no_departure_is_in_n_riders_only(gold_conn) -> None:
    b = bb.Builder("lonely-rider")
    b.position("B-101", bb.trip_id("B-101"), 50, 100.0)
    b.rider_arrival("P-884", 100, "P-890")
    assert all(r.accepted for r in bb.ingest_all(gold_conn, b.events))
    cycle(gold_conn, 500)
    assert _rows(gold_conn) == {(DAY_S, 68, "P-884"): (1, 0, 0, 0)}


def test_open_riders_of_the_stream_are_only_in_n_riders(gold_conn, load) -> None:
    events = load()
    cycle(gold_conn, AS_OF)
    open_riders = [e for e in events if e["event_type"] == "rider_arrival"
                   and not any(d >= oracle.epoch(e["event_ts"]) and d <= T0 + AS_OF
                               for d in (x[0] for x in oracle.departures(events).get(e["payload"]["stop_id"], [])))]
    assert len(open_riders) == 6
    assert all(oracle.band_of(oracle.epoch(e["event_ts"]))[1] == 70 for e in open_riders)


# -- (c) determinism and lineage ----------------------------------------------------------------------------------
def test_rerun_and_rebuild_give_identical_rows(gold_conn, load) -> None:
    load()
    first = cycle(gold_conn, AS_OF)
    before = sorted(map(repr, gold_conn.execute("SELECT * FROM gold.stop_boarding_band").fetchall()))
    assert before
    again = cycle(gold_conn, AS_OF)
    assert again.snapshot_id == first.snapshot_id
    assert sorted(map(repr, gold_conn.execute("SELECT * FROM gold.stop_boarding_band").fetchall())) == before

    gold_conn.execute("DELETE FROM gold.stop_boarding_band")
    for table in ("mpc_projection", "incident", "service_metric", "service_metric_stop", "stop_ewt_band", "decision_inputs",
                  "corridor_now", "source_status", "snapshots"):
        gold_conn.execute(f"DELETE FROM gold.{table}")  # noqa: S608 - fixed names
    gold_conn.commit()
    cycle(gold_conn, AS_OF)
    assert sorted(map(repr, gold_conn.execute("SELECT * FROM gold.stop_boarding_band").fetchall())) == before


# -- (d) duplicates, (e) unknown stops ----------------------------------------------------------------------------
def test_a_duplicated_rider_arrival_is_counted_once(gold_conn) -> None:
    b = bb.Builder("dup-rider")
    b.position("B-101", bb.trip_id("B-101"), 50, 100.0)
    rider = b.rider_arrival("P-884", 100, "P-890")
    b.stop_visit("B-101", bb.trip_id("B-101"), "P-884", 90, 200)
    assert all(r.accepted for r in bb.ingest_all(gold_conn, b.events))
    assert ingest(gold_conn, rider).accepted is False   # same source + event_id: recorded as a duplicate
    cycle(gold_conn, 500)
    assert _rows(gold_conn) == {(DAY_S, 68, "P-884"): (1, 1, 1, 1)}


def test_a_rider_at_an_unknown_stop_is_counted_nowhere(gold_conn) -> None:
    b = bb.Builder("unknown-stop")
    b.position("B-101", bb.trip_id("B-101"), 50, 100.0)
    b.rider_arrival("P-999", 100, "P-890")
    b.rider_arrival("P-884", 110, "P-890")
    assert all(r.accepted for r in bb.ingest_all(gold_conn, b.events))
    cycle(gold_conn, 500)
    assert _rows(gold_conn) == {(DAY_S, 68, "P-884"): (1, 0, 0, 0)}


# -- (f), (g) read queries ------------------------------------------------------------------------------------------
def test_q_p1_reads_final_bands_only(gold_conn, load) -> None:
    events = load()
    cycle(gold_conn, AS_OF)
    flags = {r[0]: r[1:] for r in gold_conn.execute(
        "SELECT DISTINCT band, closed, final FROM gold.stop_boarding_band_v").fetchall()}
    assert flags[68] == (True, True) and flags[69] == (True, True)
    assert flags[70] == (True, False)   # band 70 ends at 22:45:00Z: closed, but its riders have not had 15 minutes
    bounds = gold_conn.execute(
        "SELECT band, band_start_ts, band_end_ts FROM gold.stop_boarding_band_v WHERE band = 69 LIMIT 1").fetchone()
    assert bounds[1].isoformat() == "2026-11-24T22:15:00+00:00" and bounds[2].isoformat() == "2026-11-24T22:30:00+00:00"

    p = gold_conn.execute(Q_P1, {"day": DAY, "from_band": 68, "to_band": 69}).fetchone()
    assert p[0] == 25
    assert float(p[1]) == pytest.approx(13 / 25) and float(p[2]) == 1 and float(p[3]) == 1
    p69 = gold_conn.execute(Q_P1, {"day": DAY, "from_band": 69, "to_band": 69}).fetchone()
    assert float(p69[1]) == pytest.approx(0.625) and float(p69[2]) == 1
    # the open band is excluded by `final`, even when asked for
    p70 = gold_conn.execute(Q_P1, {"day": DAY, "from_band": 70, "to_band": 70}).fetchone()
    assert p70 == (None, None, None, None)
    # no rider in the range: NULL, never 0
    assert gold_conn.execute(Q_P1, {"day": DAY, "from_band": 10, "to_band": 11}).fetchone() == (None,) * 4
    # without `final` the provisional value of band 70 is the plan's 9/21, 14/21, 15/21
    prov = gold_conn.execute(Q_P1.replace(" AND final", ""), {"day": DAY, "from_band": 70, "to_band": 70}).fetchone()
    assert prov[0] == 21 and float(prov[1]) == pytest.approx(9 / 21) and float(prov[2]) == pytest.approx(14 / 21)

    # (g) per stop
    per_stop = gold_conn.execute(Q_P1_STOP, {"day": DAY, "from_band": 68, "to_band": 69}).fetchall()
    want = oracle.riders(events, T0 + AS_OF)
    expect: dict[str, list[int]] = {}
    for (_, band, stop), v in want.items():
        if band in (68, 69):
            acc = expect.setdefault(stop, [0, 0, 0, 0])
            for i, k in enumerate(("n_riders", "n_le_5", "n_le_10", "n_le_15")):
                acc[i] += v[k]
    assert [r[0] for r in per_stop] == sorted(expect)
    for r in per_stop:
        n, a, b, c = expect[r[0]]
        assert r[1] == n and float(r[2]) == pytest.approx(a / n) and float(r[3]) == pytest.approx(b / n)
        assert float(r[4]) == pytest.approx(c / n)


def test_flags_with_the_band_still_open_and_with_no_snapshot(gold_conn, load) -> None:
    load()
    cycle(gold_conn, AS_OF - 5)    # 22:44:55Z
    flags = {r[0]: r[1:] for r in gold_conn.execute(
        "SELECT DISTINCT band, closed, final FROM gold.stop_boarding_band_v").fetchall()}
    assert flags[70] == (False, False) and flags[69] == (True, False) and flags[68] == (True, True)
    # no snapshot: both false
    for table in ("mpc_projection", "incident", "service_metric", "service_metric_stop", "stop_ewt_band", "decision_inputs",
                  "corridor_now", "source_status", "snapshots"):
        gold_conn.execute(f"DELETE FROM gold.{table}")  # noqa: S608 - fixed names
    gold_conn.commit()
    assert gold_conn.execute("SELECT count(*) FROM gold.stop_boarding_band_v").fetchone()[0] > 0
    assert gold_conn.execute("SELECT bool_or(closed) OR bool_or(final) FROM gold.stop_boarding_band_v").fetchone()[0] is False


# -- (h) the EWT rows are unchanged by the new step -------------------------------------------------------------------
def test_ewt_rows_are_unchanged_by_the_boarding_step(gold_conn, load) -> None:
    events = load()
    cycle(gold_conn, AS_OF)
    got = {(r[0].isoformat(), r[1], r[2]): r[3:] for r in gold_conn.execute(
        "SELECT local_date, band, stop_id, n_headways, sum_headway_s, sum_headway_sq_s, sum_planned_s, "
        "sum_planned_sq_s, n_excluded FROM gold.stop_ewt_band").fetchall()}
    want = oracle.bands(events, T0 + AS_OF)
    assert set(got) == set(want)
    for key, w in want.items():
        assert got[key] == (w["n"], w["sum_h"], w["sum_h2"], w["sum_p"], w["sum_p2"], w["n_excluded"]), key
