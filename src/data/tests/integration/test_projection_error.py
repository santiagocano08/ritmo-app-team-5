"""006 T048a — projection error of the model at the Phase 2 gate (data owner, 2026-11-22).

For every cycle of the C1 forced-mode run (seed 42, 2,700 s), the departures the projector gives for the next 300 s
and 600 s ("do nothing", as the model sees the snapshot) are compared with the departures that actually happened in
the same run (`silver.stop_visits` after the last cycle). Nothing is tuned: the numbers are reported as they are.
No production code: the test calls `load_inputs` and `project` and reads the run.

Marked `slow` (about two minutes per scale); it is run by hand at the gate, not in the default suite:

    uv run --extra dev pytest -m slow src/data/tests/integration/test_projection_error.py -s

The statistics go to stdout and to the file named by PF006_PROJECTION_ERROR_OUT (default /tmp/pf006_projection_error.json).
"""
from __future__ import annotations

import json
import os
import statistics
from datetime import timedelta

import psycopg
import pytest

from src.data.pipeline import recommend
from src.data.rules.projector import project
from src.data.tests.fixtures.gold_support import clear_all, cycle
from src.data.tests.fixtures.mpc_runs import ingest_run

DURATION, START_S, STEP_S = 2700, 300, 15
HORIZONS = (300, 600)
BUCKETS = ((0, 150), (150, 300), (300, 450), (450, 600))


def _stats(errors: list[float]) -> dict:
    abs_e = [abs(e) for e in errors]
    if not abs_e:
        return {"n": 0, "mean_abs_s": None, "median_abs_s": None, "worst_abs_s": None, "bias_s": None}
    return {"n": len(abs_e), "mean_abs_s": round(statistics.fmean(abs_e), 1),
            "median_abs_s": round(statistics.median(abs_e), 1), "worst_abs_s": round(max(abs_e), 1),
            "bias_s": round(statistics.fmean(errors), 1)}


def measure(conn: psycopg.Connection, scale: float) -> dict:
    clear_all(conn)
    ingest_run(conn, "c1_bunching", DURATION, demand_scale=scale)
    params = recommend.load_params(conn)
    conn.rollback()
    # (as_of, bus, stop_idx, stop_id, seconds ahead, kind of bus, stops ahead of its next stop); error = real - projected (the sign of FR-036: positive means the bus left later than projected)
    projected: list[tuple] = []
    for t in range(START_S, DURATION, STEP_S):
        res = cycle(conn, t)
        inp, _ = recommend.load_inputs(conn, res.snapshot_id, res.as_of_ts, res.max_bronze_id, params)
        conn.rollback()
        info = {b.bus_id: b for b in inp.buses}
        for (bus, idx), sec in project(inp).departures:
            b = info[bus]
            if b.kind != "service":
                where = "terminal_slot_bus"  # not on the corridor yet: its departure is the model's slot estimate
            elif b.at_stop is not None and idx == b.next_stop_idx - 1:
                where = "dwelling_now"  # the bus is at this stop: only the dwell is unknown
            else:
                where = f"stops_ahead_{min(max(idx - b.next_stop_idx, 0), 3)}"  # 0 = its next stop; 3 = three or more
            projected.append((res.as_of_ts, bus, idx, inp.stops[idx].stop_id, sec, where, idx))
    actual: dict[tuple[str, str], list] = {}
    for bus, stop, dep in conn.execute("SELECT bus_id, stop_id, departure_ts FROM silver.stop_visits "
                                       "ORDER BY bus_id, stop_id, departure_ts").fetchall():
        actual.setdefault((bus, stop), []).append(dep)
    conn.rollback()
    rows = []
    for as_of, bus, idx, stop, sec, where, _ in projected:
        later = [d for d in actual.get((bus, stop), ()) if d >= as_of]
        if not later:
            continue  # the run ended before the bus left this stop
        rows.append((sec, (later[0] - (as_of + timedelta(seconds=sec))).total_seconds(), where, idx))
    out: dict = {"scale": scale, "cycles": len(range(START_S, DURATION, STEP_S)), "projected": len(projected),
                 "matched": len(rows)}
    for h in HORIZONS:
        out[f"h{h}"] = _stats([e for sec, e, _, _ in rows if sec <= h])
    out["by_look_ahead_s"] = {f"{lo}-{hi}": _stats([e for sec, e, _, _ in rows if lo <= sec < hi or (hi == 600 and sec == hi)])
                              for lo, hi in BUCKETS}
    where_names = ("dwelling_now", "stops_ahead_0", "stops_ahead_1", "stops_ahead_2", "stops_ahead_3", "terminal_slot_bus")
    out["by_source_within_600s"] = {w: _stats([e for sec, e, ww, _ in rows if ww == w and sec <= 600]) for w in where_names}
    out["h300_on_the_corridor_only"] = _stats([e for sec, e, ww, _ in rows if sec <= 300 and ww != "terminal_slot_bus"])
    out["h600_on_the_corridor_only"] = _stats([e for sec, e, ww, _ in rows if sec <= 600 and ww != "terminal_slot_bus"])
    return out


@pytest.mark.slow
@pytest.mark.parametrize("scale", [3.0, 1.0])
def test_projection_error_is_reported(module_db_dsn, scale) -> None:
    with psycopg.connect(module_db_dsn) as conn:
        result = measure(conn, scale)
    print("\nPROJECTION_ERROR " + json.dumps(result, sort_keys=True))
    path = os.environ.get("PF006_PROJECTION_ERROR_OUT", "/tmp/pf006_projection_error.json")
    try:
        existing = json.load(open(path))
    except (OSError, ValueError):
        existing = {}
    existing[str(scale)] = result
    with open(path, "w") as fh:
        json.dump(existing, fh, indent=1, sort_keys=True)
    assert result["matched"] > 0 and result["h300"]["n"] > 0
