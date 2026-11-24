"""005 US3 — stop-based EWT in gold (FR-030 to FR-036, SC-005 to SC-008).

C1 seed 42, 2,700 s, through the real ingestion boundary into a throwaway database, with and without
the seeded 90 s hold of B-103 at P-887. Every number is compared with the independent oracle
(`fixtures/oracle_stop_metrics.py`, a recomputation from the raw events) and with the plan's figures.
"""
from __future__ import annotations

import io
import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from src.data.ingestion.bronze import ingest
from src.data.rules import RULES_VERSION
from src.data.rules.service_metric import ewt_from_sums
from src.data.rules.stop_metrics import Departure, window_sums
from src.data.simulator.main import main
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.config import load_scenarios
from src.data.simulator.scenarios.truth import TruthSink
from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures import oracle_stop_metrics as oracle
from src.data.tests.fixtures.gold_support import cycle, docs
from src.data.tests.fixtures.rec_support import insert_seed_like
from src.data.tests.integration.test_hold_loop import REC1, decision, write_decision
from src.data.tests.integration.test_scenarios_gold import FIXTURES

T0 = oracle.epoch("2026-11-24T22:00:00Z")
DURATION = 2700
LIVE_AT = 2695      # 22:44:55Z, the end of the oracle window
BANDS_AT = 2700     # 22:45:00Z: band 70 is closed from here
DAY = date(2026, 11, 24)
HOLD = [False, True]


@pytest.fixture
def load(gold_conn, module_db_dsn, monkeypatch, tmp_path):
    """load(hold, scenario) -> raw events, already ingested into the throwaway database."""

    def go(hold: bool = False, scenario: str = "c1_bunching") -> list[dict]:
        path = FIXTURES / f"{scenario}.json"
        if hold:
            insert_seed_like(gold_conn)
            write_decision(gold_conn, decision(REC1))
            monkeypatch.setenv("DATABASE_URL", module_db_dsn)
            monkeypatch.setenv("SIM_TRUTH_PATH", str(tmp_path / "truth.jsonl"))
            monkeypatch.setenv("SIM_SCENARIO_FILE", str(path))
            monkeypatch.setenv("SIM_HOLD_NONCOMPLIANCE", "0.0")
            buf = io.StringIO()
            main(["--seed", "42", "--duration", str(DURATION), "--holds", "on"], out=buf)
            events = [json.loads(x) for x in buf.getvalue().splitlines()]
        else:
            scenarios = load_scenarios(path)
            events = list(scenario_events(scenarios, 42, DURATION, TruthSink(scenarios)))
        for e in events:
            ingest(gold_conn, e)
        return events

    return go


def _stop_rows(conn, snapshot_id) -> dict[str, tuple]:
    rows = conn.execute(
        "SELECT stop_id, n_headways, sum_headway_s, sum_headway_sq_s, sum_planned_s, sum_planned_sq_s, "
        "n_excluded, computable FROM gold.service_metric_stop WHERE snapshot_id = %s", (snapshot_id,)).fetchall()
    return {r[0]: r[1:] for r in rows}


def _metric(conn, snapshot_id) -> tuple:
    return conn.execute("SELECT n_headways, mean_wait_s, scheduled_wait_s, ewt_s, computable "
                        "FROM gold.service_metric WHERE snapshot_id = %s", (snapshot_id,)).fetchone()


def _ewt(n: int, sum_h, sum_h2) -> float | None:
    if n == 0 or sum_h <= 0:
        return None
    return float(ewt_from_sums(n, Decimal(sum_h), Decimal(sum_h2), oracle.PLANNED_S)[2])


def _sum_stops(rows: dict[str, tuple], stops) -> tuple[int, Decimal, Decimal]:
    pick = [rows[s] for s in stops]
    return sum(r[0] for r in pick), sum(r[1] for r in pick), sum(r[2] for r in pick)


def _silver_departures(conn) -> list[Departure]:
    return [Departure(*r) for r in conn.execute(
        "SELECT stop_id, bus_id, trip_id, departure_ts, estimated_at_departure FROM silver.stop_visits").fetchall()]


# -- (a), (b), (c): live trailing window and the 16-minute oracle window ---------------------------------------
@pytest.mark.parametrize("hold", HOLD)
def test_live_rows_equal_the_oracle_and_the_plan(gold_conn, load, hold) -> None:
    events = load(hold)
    result = cycle(gold_conn, LIVE_AT)
    rows = _stop_rows(gold_conn, result.snapshot_id)
    assert set(rows) == set(oracle.STOPS) and len(rows) == 18

    want = oracle.live_by_stop(events, T0 + LIVE_AT)
    for stop, w in want.items():
        n, sh, sh2, sp, sp2, excl, computable = rows[stop]
        assert (n, sh, sh2, sp, sp2, excl) == (w["n"], w["sum_h"], w["sum_h2"], w["sum_p"], w["sum_p2"], w["n_excluded"])
        assert computable is (w["n"] >= 1)

    # Figures re-pinned for the 7 + 4 fleet at 420 s and the retimed c1_bunching (issue #42); the pipeline still equals
    # the independent oracle above. (a) all 18 stops: 42 headways +9.6 s without the hold, 43 headways -4.0 s with it
    n, mean, sched, ewt, ok = _metric(gold_conn, result.snapshot_id)
    assert (n, ok) == ((43, True) if hold else (42, True))
    assert float(ewt) == pytest.approx(-4.01 if hold else 9.58, abs=0.05)
    assert float(mean) - float(sched) == pytest.approx(float(ewt), abs=0.002)
    assert float(ewt) == pytest.approx(oracle.ewt(oracle.window(events, T0 + LIVE_AT - 900, T0 + LIVE_AT)), abs=0.0006)

    # (b) P-888..P-900 from the per-stop rows: 31 headways +11.0 s / 32 headways -7.8 s
    n13, sh13, sh213 = _sum_stops(rows, oracle.CORRIDOR_STOPS)
    assert n13 == (32 if hold else 31)
    assert _ewt(n13, sh13, sh213) == pytest.approx(-7.78 if hold else 11.03, abs=0.05)

    # (c) the 16-minute oracle window (22:28:55, 22:44:55]Z through the pure rule on silver.stop_visits
    deps = [d for d in _silver_departures(gold_conn) if d.stop_id in oracle.CORRIDOR_STOPS]
    lo = datetime(2026, 11, 24, 22, 28, 55, tzinfo=timezone.utc)
    hi = datetime(2026, 11, 24, 22, 44, 55, tzinfo=timezone.utc)
    s = window_sums(deps, lo, hi)
    assert s.n == (33 if hold else 32)
    assert float(ewt_from_sums(s.n, s.sum_h, s.sum_h2, oracle.PLANNED_S)[2]) == pytest.approx(-9.51 if hold else 9.65, abs=0.1)


def test_the_hold_lowers_the_oracle_window_ewt(gold_conn, load) -> None:
    """Saving of 19.2 s on the 16-minute window (15.2 s in the data owner's mock with the 5 + 2 fleet at 600 s)."""
    events = load(True)
    held = oracle.window(events, T0 + 28 * 60 + 55, T0 + 44 * 60 + 55, oracle.CORRIDOR_STOPS)
    assert held["n"] == 33 and oracle.ewt(held) == pytest.approx(-9.51, abs=0.05)
    assert 9.65 - oracle.ewt(held) == pytest.approx(19.2, abs=0.1)


# -- (d) closed bands ------------------------------------------------------------------------------------------
def _band_rows(conn) -> dict[tuple, tuple]:
    rows = conn.execute(
        "SELECT local_date, band, stop_id, n_headways, sum_headway_s, sum_headway_sq_s, sum_planned_s, "
        "sum_planned_sq_s, n_excluded FROM gold.stop_ewt_band").fetchall()
    return {(r[0].isoformat(), r[1], r[2]): r[3:] for r in rows}


@pytest.mark.parametrize("hold", HOLD)
def test_band_rows_equal_the_oracle_grouped_by_band(gold_conn, load, hold) -> None:
    events = load(hold)
    result = cycle(gold_conn, BANDS_AT)
    got = _band_rows(gold_conn)
    want = oracle.bands(events, T0 + BANDS_AT)
    assert set(got) == set(want)
    for key, w in want.items():
        assert got[key] == (w["n"], w["sum_h"], w["sum_h2"], w["sum_p"], w["sum_p2"], w["n_excluded"]), key
    assert all(b in (68, 69, 70) for _, b, _ in got)

    def band_sum(band: int, stops) -> tuple[int, Decimal, Decimal]:
        pick = [v for (d, b, s), v in got.items() if b == band and s in stops]
        return sum(v[0] for v in pick), sum(v[1] for v in pick), sum(v[2] for v in pick)

    corridor = set(oracle.CORRIDOR_STOPS)
    assert band_sum(68, corridor) == (0, 0, 0)   # no closing departure on these stops in band 68
    b69, b70 = band_sum(69, corridor), band_sum(70, corridor)
    assert (b69[0], b70[0]) == ((14, 32) if hold else (15, 31))
    assert (b69[0] + b70[0], b69[1] + b70[1], b69[2] + b70[2]) == (
        (46, 17530, 7936250) if hold else (46, 17520, 8405450))
    if not hold:
        assert b69[1:] == (5640, 3153800) and b70[1:] == (11880, 5251650)
    # lineage on every band row
    lineage = gold_conn.execute("SELECT DISTINCT rules_version, max_bronze_id FROM gold.stop_ewt_band").fetchall()
    assert lineage == [(RULES_VERSION, result.max_bronze_id)]


def test_only_closed_bands_have_rows(gold_conn, load) -> None:
    load(False)
    cycle(gold_conn, BANDS_AT - 5)          # 22:44:55Z: band 70 still open
    assert {b for _, b, _ in _band_rows(gold_conn)} == {68, 69}
    cycle(gold_conn, BANDS_AT)              # the rebuild replaces the table
    assert {b for _, b, _ in _band_rows(gold_conn)} == {68, 69, 70}


# -- (e) bunching no longer reads "better than planned" --------------------------------------------------------
def test_bunched_snapshot_has_positive_stop_ewt(gold_conn, load) -> None:
    load(False)
    result = cycle(gold_conn, 1800)  # 22:30:00Z, B-103 100 s behind B-102 (7 + 4 fleet at 420 s, issue #42)
    n, _, _, ewt, ok = _metric(gold_conn, result.snapshot_id)
    assert (n, ok) == (28, True) and float(ewt) == pytest.approx(56.6, abs=0.05)

    seen = 0
    for t in range(960, 2140, 20):  # B-103 stays bunched (72 to 135 s behind B-102) for this whole stretch
        r = cycle(gold_conn, t)
        buses = {b["bus_id"]: b for b in docs(gold_conn, r.snapshot_id)["corridor_now"]["buses"]}
        if buses["B-103"]["bus_state"] == "bunched":
            seen += 1
            n, _, _, ewt, ok = _metric(gold_conn, r.snapshot_id)
            assert ok and float(ewt) > 0, t   # the spatial rule gave -202 s with B-103 195 s behind
    assert seen >= 55


# -- (f) a bus with no departure in the window does not move the value ------------------------------------------
def test_a_bus_without_departures_changes_nothing(gold_conn, load) -> None:
    load(False)
    first = cycle(gold_conn, LIVE_AT)
    before = _metric(gold_conn, first.snapshot_id)
    b = bb.Builder("extra-bus")
    b.drive("B-108", 2600, LIVE_AT)  # a reserve bus reporting positions only
    assert all(r.accepted for r in bb.ingest_all(gold_conn, b.events))
    second = cycle(gold_conn, LIVE_AT)
    assert second.snapshot_id != first.snapshot_id
    assert _metric(gold_conn, second.snapshot_id) == before
    assert _stop_rows(gold_conn, second.snapshot_id) == _stop_rows(gold_conn, first.snapshot_id)


# -- (g) a stop with one departure ------------------------------------------------------------------------------
def test_a_stop_with_one_departure_has_a_row_and_is_not_computable(gold_conn, load) -> None:
    events = load(False)
    as_of = 200
    result = cycle(gold_conn, as_of)
    rows = _stop_rows(gold_conn, result.snapshot_id)
    deps = oracle.departures([e for e in events if oracle.epoch(e["event_ts"]) <= T0 + as_of])
    single = [s for s in oracle.STOPS if len(deps.get(s, [])) == 1]
    assert single, "the fixture must have a stop with exactly one departure at this time"
    for stop in single:
        assert rows[stop] == (0, 0, 0, 0, 0, 0, False)
    assert len(rows) == 18
    n, mean, sched, ewt, ok = _metric(gold_conn, result.snapshot_id)
    assert (n, mean, sched, ewt, ok) == (sum(r[0] for r in rows.values()), None, None, None, False)


# -- (h) the minimum sample --------------------------------------------------------------------------------------
def test_corridor_row_is_computable_from_the_configured_minimum(gold_conn, load) -> None:
    events = load(False)
    minimum = gold_conn.execute("SELECT min_stop_headways FROM config.corridor_settings").fetchone()[0]
    assert minimum == 5
    kinds = set()
    for t in range(100, DURATION, 100):
        r = cycle(gold_conn, t)
        n, mean, sched, ewt, ok = _metric(gold_conn, r.snapshot_id)
        w = oracle.window(events, T0 + t - 900, T0 + t)
        assert n == w["n"]
        assert ok is (w["n"] >= minimum and w["sum_h"] > 0)
        if ok:
            assert float(ewt) == pytest.approx(oracle.ewt(w), abs=0.0006)
        else:
            assert mean is None and sched is None and ewt is None
        kinds.add((ok, n > 0))
    assert (True, True) in kinds and (False, True) in kinds


# -- (i) estimated departures ------------------------------------------------------------------------------------
def _crafted_stream() -> list[dict]:
    """P-884 departures at 100, 400, 700 and 1,300 s; B-102 is silent for 200 s before its departure.

    The arrival of a visit is a report too, so the visits use arrival = departure (a strictly earlier
    report is needed for the gap): B-102 last reported at 200 s and departs at 400 s (gap 200 s > 120 s).
    """
    b = bb.Builder("crafted-estimated")
    for bus, depart, last_report in (("B-101", 100, 95), ("B-102", 400, 200), ("B-103", 700, 695),
                                     ("B-104", 1300, 1295)):
        b.position(bus, bb.trip_id(bus), last_report, 100.0)
        b.stop_visit(bus, bb.trip_id(bus), "P-884", depart, depart)
    return b.events


def test_estimated_departure_excludes_both_headways_and_counts_them(gold_conn) -> None:
    events = _crafted_stream()
    assert all(r.accepted for r in bb.ingest_all(gold_conn, events))
    # silver sees the flag
    live = cycle(gold_conn, 1400)   # window (500, 1400]: closings 700 (touches B-102) and 1,300
    flags = dict(gold_conn.execute("SELECT bus_id, estimated_at_departure FROM silver.stop_visits").fetchall())
    assert flags == {"B-101": False, "B-102": True, "B-103": False, "B-104": False}
    assert _stop_rows(gold_conn, live.snapshot_id)["P-884"] == (1, 600, 360000, 420, 176400, 1, True)
    assert _metric(gold_conn, live.snapshot_id)[0] == 1

    cycle(gold_conn, 1800)  # bands 68 (0..900 s) and 69 (900..1800 s) closed
    want = oracle.bands(events, T0 + 1800)
    got = _band_rows(gold_conn)
    assert set(got) == set(want) == {("2026-11-24", 68, "P-884"), ("2026-11-24", 69, "P-884")}
    assert got[("2026-11-24", 68, "P-884")] == (0, 0, 0, 0, 0, 2)    # both headways touch B-102
    assert got[("2026-11-24", 69, "P-884")] == (1, 600, 360000, 420, 176400, 0)


def test_d1_silence_stream_equals_the_oracle(gold_conn, load) -> None:
    events = load(False, "d1_silence")
    cycle(gold_conn, BANDS_AT)
    want = oracle.bands(events, T0 + BANDS_AT)
    got = _band_rows(gold_conn)
    assert set(got) == set(want)
    for key, w in want.items():
        assert got[key] == (w["n"], w["sum_h"], w["sum_h2"], w["sum_p"], w["sum_p2"], w["n_excluded"]), key


# -- (j) determinism, lineage -------------------------------------------------------------------------------------
def _dump(conn) -> dict:
    return {
        "bands": sorted(map(repr, conn.execute("SELECT * FROM gold.stop_ewt_band").fetchall())),
        "stops": sorted(map(repr, conn.execute("SELECT * FROM gold.service_metric_stop").fetchall())),
        "metric": sorted(map(repr, conn.execute("SELECT * FROM gold.service_metric").fetchall())),
    }


def test_rerun_and_rebuild_give_identical_rows_with_lineage(gold_conn, load) -> None:
    load(False)
    first = cycle(gold_conn, BANDS_AT)
    before = _dump(gold_conn)
    again = cycle(gold_conn, BANDS_AT)
    assert again.snapshot_id == first.snapshot_id and again.created is False
    assert _dump(gold_conn) == before

    for table in ("mpc_projection", "incident", "service_metric", "service_metric_stop", "stop_ewt_band", "decision_inputs",
                  "corridor_now", "source_status", "snapshots"):
        gold_conn.execute(f"DELETE FROM gold.{table}")  # noqa: S608 - fixed names
    gold_conn.commit()
    rebuilt = cycle(gold_conn, BANDS_AT)
    assert rebuilt.snapshot_id == first.snapshot_id
    assert _dump(gold_conn) == before

    for table in ("service_metric", "service_metric_stop", "stop_ewt_band"):
        lineage = gold_conn.execute(
            f"SELECT DISTINCT rules_version, max_bronze_id FROM gold.{table}").fetchall()  # noqa: S608
        assert lineage == [(RULES_VERSION, first.max_bronze_id)], table


# -- (k) the table keeps its shape -------------------------------------------------------------------------------
def test_service_metric_keeps_its_columns_and_one_row_per_snapshot(gold_conn, load) -> None:
    load(False)
    for t in (1000, 1500, 2000):
        cycle(gold_conn, t)
    cols = {r[0] for r in gold_conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'gold' "
        "AND table_name = 'service_metric'")}
    assert cols == {"snapshot_id", "n_headways", "mean_wait_s", "scheduled_wait_s", "ewt_s", "computable",
                    "rules_version", "max_bronze_id"}
    assert gold_conn.execute("SELECT count(*) FROM gold.snapshots").fetchone()[0] == 3
    assert gold_conn.execute("SELECT count(*) FROM gold.service_metric").fetchone()[0] == 3
    assert gold_conn.execute("SELECT count(*) FROM gold.service_metric_stop").fetchone()[0] == 3 * 18


# -- (l) the read queries of contracts/gold-stop-metrics.md, as written -------------------------------------------
Q_S1 = """SELECT s.as_of_ts, m.n_headways, m.mean_wait_s, m.scheduled_wait_s, m.ewt_s, m.computable
FROM gold.service_metric m JOIN gold.snapshots s USING (snapshot_id)
WHERE m.snapshot_id = %(snapshot_id)s"""

Q_S2 = """SELECT stop_id, n_headways, n_excluded, computable,
       sum_headway_sq_s / nullif(2 * sum_headway_s, 0)
     - sum_planned_sq_s / nullif(2 * sum_planned_s, 0) AS ewt_s
FROM gold.service_metric_stop
WHERE snapshot_id = %(snapshot_id)s
ORDER BY stop_id"""

Q_E1 = """SELECT sum(n_headways) AS n_headways, sum(n_excluded) AS n_excluded,
       sum(sum_headway_sq_s) / nullif(2 * sum(sum_headway_s), 0)
     - sum(sum_planned_sq_s) / nullif(2 * sum(sum_planned_s), 0) AS ewt_s,
       sum(n_headways) >= (SELECT min_stop_headways FROM config.corridor_settings) AS computable,
       max(rules_version) AS rules_version, max(max_bronze_id) AS max_bronze_id
FROM gold.stop_ewt_band
WHERE local_date = %(day)s AND band BETWEEN %(from_band)s AND %(to_band)s"""

Q_E1_STOP = Q_E1.replace("SELECT sum(n_headways) AS n_headways", "SELECT stop_id, sum(n_headways) AS n_headways") \
    + " GROUP BY stop_id ORDER BY stop_id"


def test_read_queries_run_as_written_and_agree_with_the_oracle(gold_conn, load) -> None:
    events = load(False)
    result = cycle(gold_conn, BANDS_AT)
    params = {"snapshot_id": result.snapshot_id}

    s1 = gold_conn.execute(Q_S1, params).fetchone()
    assert s1[0] == datetime(2026, 11, 24, 22, 45, tzinfo=timezone.utc) and s1[5] is True

    s2 = gold_conn.execute(Q_S2, params).fetchall()
    assert [r[0] for r in s2] == sorted(oracle.STOPS)
    live = oracle.live_by_stop(events, T0 + BANDS_AT)
    for stop, n, excl, computable, ewt in s2:
        w = live[stop]
        assert (n, excl, computable) == (w["n"], w["n_excluded"], w["n"] >= 1)
        if w["n"] and w["sum_h"] > 0:
            assert float(ewt) == pytest.approx(oracle.ewt(w), abs=1e-6)
        else:
            assert ewt is None

    q = {"day": DAY, "from_band": 68, "to_band": 70}
    n, excl, ewt, computable, rv, mx = gold_conn.execute(Q_E1, q).fetchone()
    total = oracle.window(events, T0, T0 + BANDS_AT)  # bands 68..70 are exactly 22:00:00Z to 22:45:00Z
    assert (n, excl, computable) == (total["n"], total["n_excluded"], True)
    assert float(ewt) == pytest.approx(oracle.ewt(total), abs=1e-6)
    assert (rv, mx) == (RULES_VERSION, result.max_bronze_id)

    per_stop = gold_conn.execute(Q_E1_STOP, q).fetchall()
    assert [r[0] for r in per_stop] == sorted({s for _, _, s in oracle.bands(events, T0 + BANDS_AT)})
    assert sum(r[1] for r in per_stop) == n
