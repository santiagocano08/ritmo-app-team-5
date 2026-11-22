"""006 T049c — the recommend step appends the "do nothing" projection every cycle (FR-035, SC-001, SC-016).

Forced-mode runs (seed 42, fixed duration, a cycle every 15 simulated seconds). The oracle is the pure projector
itself: after each cycle the test rebuilds the cycle's `Inputs` with `load_inputs` and compares the stored rows with
`projection_record(inputs, project(inputs))`.
"""
from __future__ import annotations

import hashlib

import psycopg
import pytest

import src.data.pipeline.cycle as cycle_module
import src.data.rules.mpc as mpc_module
from src.data.pipeline import recommend
from src.data.rules import RULES_VERSION
from src.data.rules.projector import project, projection_record
from src.data.tests.fixtures.gold_support import clear_all, cycle
from src.data.tests.fixtures.mpc_runs import ingest_run

STEP_S = 15
STORED = ("SELECT bus_id, stop_id, projected_departure_ts, lead_s::float8, as_of_ts, rules_version, max_bronze_id "
          "FROM gold.mpc_projection WHERE snapshot_id = %s ORDER BY bus_id, stop_id")
ALL_ROWS = ("SELECT snapshot_id, bus_id, stop_id, as_of_ts, projected_departure_ts, lead_s, rules_version, "
            "max_bronze_id FROM gold.mpc_projection ORDER BY snapshot_id, bus_id, stop_id")


@pytest.fixture()
def conn(module_db_dsn):
    with psycopg.connect(module_db_dsn) as c:
        clear_all(c)
        yield c
        c.rollback()


def _digest(conn: psycopg.Connection) -> str:
    rows = conn.execute(ALL_ROWS).fetchall()
    conn.rollback()
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def _run(conn: psycopg.Connection, scenario: str | None, duration: int, scale: float = 1.0, start: int = 300):
    ingest_run(conn, scenario, duration, demand_scale=scale)
    return [cycle(conn, t) for t in range(start, duration, STEP_S)]


def test_every_cycle_stores_the_departures_the_projector_gives(conn) -> None:
    ingest_run(conn, "c1_bunching", 1500, demand_scale=3.0)
    params = recommend.load_params(conn)
    conn.rollback()
    with_service_bus = 0
    for t in range(300, 1500, STEP_S):
        res = cycle(conn, t)
        inp, _ = recommend.load_inputs(conn, res.snapshot_id, res.as_of_ts, res.max_bronze_id, params)
        expected = projection_record(inp, project(inp))
        stored = conn.execute(STORED, (str(res.snapshot_id),)).fetchall()
        conn.rollback()
        assert [(r[0], r[1], r[2], r[3]) for r in stored] == [(b, s, ts, lead) for b, s, ts, lead in expected], t
        assert all(0 <= r[3] <= params.scoring_window_s for r in stored)
        assert all(r[4] == res.as_of_ts and r[5] == RULES_VERSION and r[6] == res.max_bronze_id for r in stored)
        if any(b.kind == "service" for b in inp.buses):
            with_service_bus += 1
            assert stored, f"a bus is in service at {t} s but no row was stored"
    assert with_service_bus > 50


def test_a_normal_run_stores_rows_although_it_has_no_candidate(conn) -> None:
    _run(conn, None, 900)
    assert conn.execute("SELECT count(*) FROM gold.mpc_projection").fetchone()[0] > 0
    assert conn.execute("SELECT count(*) FROM gold.mpc_evaluation").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM gold.recommendation").fetchone()[0] == 0


def test_running_the_same_cycle_twice_adds_no_row(conn) -> None:
    ingest_run(conn, "c1_bunching", 900)
    cycle(conn, 600)
    first = _digest(conn)
    n = conn.execute("SELECT count(*) FROM gold.mpc_projection").fetchone()[0]
    assert n > 0
    cycle(conn, 600)
    assert _digest(conn) == first
    assert conn.execute("SELECT count(*) FROM gold.mpc_projection").fetchone()[0] == n


def test_the_same_bronze_gives_identical_rows(conn) -> None:
    _run(conn, "c1_bunching", 1200, scale=3.0)
    first, n = _digest(conn), conn.execute("SELECT count(*) FROM gold.mpc_projection").fetchone()[0]
    conn.rollback()
    clear_all(conn)
    _run(conn, "c1_bunching", 1200, scale=3.0)
    assert _digest(conn) == first and n > 0


def test_a_rolled_back_cycle_leaves_no_row(conn, monkeypatch: pytest.MonkeyPatch) -> None:
    ingest_run(conn, "c1_bunching", 900)
    real = recommend.run_model

    def run_then_fail(*a, **kw):
        real(*a, **kw)
        raise RuntimeError("boom after the writes")

    monkeypatch.setattr(cycle_module.recommend, "run_model", run_then_fail)
    with pytest.raises(cycle_module.CycleError):
        cycle(conn, 600)
    assert conn.execute("SELECT count(*) FROM gold.mpc_projection").fetchone()[0] == 0


def test_a_stale_snapshot_stores_nothing(conn, monkeypatch: pytest.MonkeyPatch) -> None:
    ingest_run(conn, "c1_bunching", 900)
    monkeypatch.setattr(recommend, "snapshot_age_s", lambda c, s: 20.0)
    cycle(conn, 600)
    assert conn.execute("SELECT count(*) FROM gold.mpc_projection").fetchone()[0] == 0


def test_a_cycle_with_no_bus_report_stores_nothing(conn) -> None:
    """Found by the first live run: before the first report the roster buses are placeholders with terminal slots at
    the cycle's reference time. The view would pair them with a departure of the later feed (error of days), and the
    record would say nothing about the model, so no row is stored until a bus has reported."""
    assert conn.execute("SELECT count(*) FROM bronze.events").fetchone()[0] == 0
    res = cycle(conn, 600)
    assert res is not None
    assert conn.execute("SELECT count(*) FROM gold.mpc_projection").fetchone()[0] == 0
    ingest_run(conn, "c1_bunching", 900)
    cycle(conn, 600)
    assert conn.execute("SELECT count(*) FROM gold.mpc_projection").fetchone()[0] > 0


def test_a_model_that_is_off_stores_nothing(conn, monkeypatch: pytest.MonkeyPatch) -> None:
    ingest_run(conn, "c1_bunching", 900)
    monkeypatch.setenv("MPC_ENABLED", "off")
    cycle(conn, 600)
    assert conn.execute("SELECT count(*) FROM gold.mpc_projection").fetchone()[0] == 0


def test_the_baseline_is_projected_once_per_cycle(conn, monkeypatch: pytest.MonkeyPatch) -> None:
    """One projection for "do nothing" plus one per candidate: the record does not add a second baseline."""
    ingest_run(conn, "c1_bunching", 1500, demand_scale=3.0)
    calls = []
    real = project

    def counting(inp, action=None):
        calls.append(action)
        return real(inp, action)

    monkeypatch.setattr(recommend, "project", counting)
    monkeypatch.setattr(mpc_module, "project", counting)
    checked = 0
    for t in range(1380, 1500, STEP_S):  # the bunching window of C1
        calls.clear()
        cycle(conn, t)
        n_candidates = conn.execute("SELECT count(*) FROM gold.mpc_evaluation WHERE seq > 0").fetchone()[0]
        conn.rollback()
        assert len(calls) == 1 + n_candidates, t
        checked += n_candidates > 0
    assert checked > 0


def test_the_record_does_not_change_what_is_recommended(conn) -> None:
    """Rows of `gold.recommendation` and `gold.mpc_evaluation` come from the same inputs whether or not the record
    is written: the evaluation of every cycle keeps its baseline score in row 0."""
    ingest_run(conn, "c1_bunching", 1500, demand_scale=3.0)
    for t in range(1380, 1500, STEP_S):
        res = cycle(conn, t)
        inp, _ = recommend.load_inputs(conn, res.snapshot_id, res.as_of_ts, res.max_bronze_id)
        base = conn.execute("SELECT score_s::float8 FROM gold.mpc_evaluation WHERE seq = 0").fetchone()
        conn.rollback()
        if base is not None:
            assert base[0] == pytest.approx(project(inp).score_s, abs=1e-6)
