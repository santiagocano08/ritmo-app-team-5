"""006 T049g — SC-016: the projection error as `gold.v_projection_accuracy` reports it (data owner, 2026-11-22).

Replaces the one-off T048a script (which called `load_inputs` and `project` itself): this test only reads what the
model stored. C1 forced mode (seed 42, 2,700 s), a cycle every 15 s from 300 s (160 cycles), at scales 3 and 1.0.
After the last cycle it runs the aggregate query of `contracts/projection-accuracy.md` and prints the SC-016 table.
Only the structure is asserted (rows per cycle, identical rerun, NULL where nothing happened yet); no error value is
asserted and nothing is tuned.

Marked `slow` (about two minutes per scale); run it by hand at the phase gate:

    uv run --extra dev pytest -m slow src/data/tests/integration/test_projection_error.py -s

The table goes to stdout and to the file named by PF006_PROJECTION_ERROR_OUT (default /tmp/pf006_sc016.json).
"""
from __future__ import annotations

import hashlib
import json
import os

import psycopg
import pytest

from src.data.tests.fixtures.gold_support import clear_all, cycle
from src.data.tests.fixtures.mpc_runs import ingest_run
from src.data.tests.integration.test_projection_accuracy_query import aggregate_sql

DURATION, START_S, STEP_S = 2700, 300, 15
ROWS = ("SELECT snapshot_id, bus_id, stop_id, as_of_ts, projected_departure_ts, lead_s, rules_version, max_bronze_id "
        "FROM gold.mpc_projection ORDER BY snapshot_id, bus_id, stop_id")


def run_once(conn: psycopg.Connection, scale: float) -> dict:
    clear_all(conn)
    ingest_run(conn, "c1_bunching", DURATION, demand_scale=scale)
    per_cycle: list[int] = []
    empty_with_service_bus: list[int] = []
    for t in range(START_S, DURATION, STEP_S):
        res = cycle(conn, t)
        n = conn.execute("SELECT count(*) FROM gold.mpc_projection WHERE snapshot_id = %s", (str(res.snapshot_id),)
                         ).fetchone()[0]
        service = conn.execute("SELECT count(*) FROM silver.bus_current_state WHERE on_corridor "
                               "AND distance_along_m IS NOT NULL").fetchone()[0]
        conn.rollback()
        per_cycle.append(n)
        if service and not n:
            empty_with_service_bus.append(t)
    digest = hashlib.sha256(repr(conn.execute(ROWS).fetchall()).encode()).hexdigest()
    table = [dict(zip(("lead_bucket", "n_compared", "mae_s", "median_abs_error_s", "worst_abs_error_s", "mean_error_s"),
                      (str(v) if v is not None and not isinstance(v, (int, str)) else v for v in r)))
             for r in conn.execute(aggregate_sql()).fetchall()]
    totals = conn.execute("SELECT count(*), count(error_s), count(*) FILTER (WHERE affected_by_decision), "
                          "count(*) FILTER (WHERE (error_s IS NULL) <> (actual_departure_ts IS NULL)) "
                          "FROM gold.v_projection_accuracy").fetchone()
    conn.rollback()
    return {"scale": scale, "cycles": len(per_cycle), "rows": sum(per_cycle), "rows_per_cycle_min": min(per_cycle),
            "rows_per_cycle_median": sorted(per_cycle)[len(per_cycle) // 2], "rows_per_cycle_max": max(per_cycle),
            "empty_cycles_with_a_service_bus": empty_with_service_bus, "sha256": digest, "table": table,
            "view_rows": totals[0], "compared": totals[1], "affected": totals[2], "null_mismatch": totals[3]}


@pytest.mark.slow
@pytest.mark.parametrize("scale", [3.0, 1.0])
def test_projection_accuracy_is_reported(module_db_dsn, scale) -> None:
    with psycopg.connect(module_db_dsn) as conn:
        first = run_once(conn, scale)
        again = run_once(conn, scale)
    print("\nSC016 " + json.dumps(first, sort_keys=True))
    path = os.environ.get("PF006_PROJECTION_ERROR_OUT", "/tmp/pf006_sc016.json")
    try:
        existing = json.load(open(path))
    except (OSError, ValueError):
        existing = {}
    existing[str(scale)] = first
    with open(path, "w") as fh:
        json.dump(existing, fh, indent=1, sort_keys=True)
    assert first["rows"] > 0 and first["empty_cycles_with_a_service_bus"] == []
    assert first["sha256"] == again["sha256"], "the same bronze must give identical rows"
    assert first["null_mismatch"] == 0, "error_s is NULL exactly when there is no real departure"
    assert first["view_rows"] > first["compared"], "rows without a real departure yet have a NULL error"
    by_bucket = {r["lead_bucket"]: r for r in first["table"]}
    assert by_bucket["0-5 min"]["n_compared"] > 0 and by_bucket["5-10 min"]["n_compared"] > 0
