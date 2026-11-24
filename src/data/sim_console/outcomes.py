"""Service outcome of a simulator run: is the corridor working better, and did each decision help?

Data team harness (8085 *Resultados* tab and the run archive), not product code. Reads gold only:

- per snapshot (`gold.service_metric`, `gold.corridor_now`, `gold.decision_inputs`): mean wait, scheduled wait and
  EWT (trailing 15-minute window, stop-based), buses in service, bunched, gaps, free reserves and drivers;
- probability of boarding within 5 / 10 / 15 minutes (`gold.stop_boarding_band`, story 005).

**Effect of a decision (descriptive, not causal).** EWT and mean wait use a trailing 15-minute window, so the value
at the decision time and the value 15 simulated minutes later cover two windows that do not overlap: "before" and
"after". The change is reported for every closed recommendation, applied or not, so applied ones can be compared
with the ones nobody acted on. It is not a counterfactual: traffic and demand also change. The real test is two
runs with the same seed (the simulator is deterministic) with and without decisions. The official verdict
(worked / partial / did not work) is the effect rule of ADR-0007 (`rules/effect.py`, issue #27); this module does
not implement it.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from statistics import mean, median
from typing import Any

import psycopg

HORIZON_S = 900       # the EWT window: "after" is read this long after the decision
SAME_BAND_S = 5.0     # |change in mean wait| below this is "no change"

Q_SERIES = """
SELECT s.as_of_ts, m.mean_wait_s::float AS mean_wait_s, m.scheduled_wait_s::float AS scheduled_wait_s,
       m.ewt_s::float AS ewt_s, m.n_headways, m.computable,
       (c.doc->'summary'->>'buses_in_service')::int AS in_service,
       (c.doc->'summary'->>'n_bunched')::int AS bunched, (c.doc->'summary'->>'n_gaps')::int AS gaps,
       jsonb_array_length(COALESCE(d.doc->'resources'->'reserve_free', '[]'::jsonb)) AS reserve_free,
       d.doc->'resources'->'reserve_free' AS reserve_ids,
       (d.doc->'resources'->>'drivers_free')::int AS drivers_free
FROM gold.snapshots s
JOIN gold.snapshot_commits USING (snapshot_id)
LEFT JOIN gold.service_metric m USING (snapshot_id)
LEFT JOIN gold.corridor_now c USING (snapshot_id)
LEFT JOIN gold.decision_inputs d USING (snapshot_id)
ORDER BY s.as_of_ts, s.max_bronze_id"""
Q_BOARDING = """
SELECT stop_id, sum(n_riders)::int AS riders, sum(n_board_le_5)::int AS le5,
       sum(n_board_le_10)::int AS le10, sum(n_board_le_15)::int AS le15
FROM gold.stop_boarding_band GROUP BY stop_id ORDER BY stop_id"""

# How well the model predicts: its "do nothing" departures vs the departures that happened (story 006 phase 2b),
# by lead time. Rows affected by an applied decision are left out (the action changed the outcome on purpose).
Q_ACCURACY = """
SELECT b.lead_bucket, count(a.error_s)::int AS n_compared,
       round(avg(a.abs_error_s), 1)::float AS mae_s,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY a.abs_error_s))::numeric, 1)::float AS median_s,
       max(a.abs_error_s)::float AS worst_s, round(avg(a.error_s), 1)::float AS mean_error_s
FROM (VALUES ('0-5 min', 1), ('5-10 min', 2), ('10-30 min', 3)) AS b(lead_bucket, ord)
LEFT JOIN gold.v_projection_accuracy a
       ON a.lead_bucket = b.lead_bucket AND NOT a.affected_by_decision AND a.error_s IS NOT NULL
GROUP BY b.lead_bucket, b.ord ORDER BY b.ord"""


def collect(conn: psycopg.Connection) -> dict[str, Any]:
    """Raw outcome data of the run in this database (one row per snapshot, one per stop)."""
    series = conn.execute(Q_SERIES).fetchall()
    try:
        boarding = conn.execute(Q_BOARDING).fetchall()
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        boarding = []
    try:
        accuracy = conn.execute(Q_ACCURACY).fetchall()
    except psycopg.errors.UndefinedTable:
        conn.rollback()
        accuracy = []
    return {"series": series, "boarding": boarding, "accuracy": accuracy}


def _pct(n: int, d: int) -> float | None:
    return round(100 * n / d, 1) if d else None


def boarding_summary(boarding: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """P(board within 5/10/15 min) over the whole run, all stops weighted by riders, plus per stop."""
    tot = {k: sum(r[k] for r in boarding) for k in ("riders", "le5", "le10", "le15")}
    per_stop = [{"stop_id": r["stop_id"], "riders": r["riders"], "p5": _pct(r["le5"], r["riders"]),
                 "p10": _pct(r["le10"], r["riders"]), "p15": _pct(r["le15"], r["riders"])} for r in boarding]
    return {"riders": tot["riders"], "p5": _pct(tot["le5"], tot["riders"]), "p10": _pct(tot["le10"], tot["riders"]),
            "p15": _pct(tot["le15"], tot["riders"]), "per_stop": per_stop}


def _at(series: Sequence[Mapping[str, Any]], t: datetime) -> Mapping[str, Any] | None:
    """Newest computable snapshot at or before `t`."""
    best = None
    for p in series:
        if p["as_of_ts"] > t:
            break
        if p.get("computable") and p.get("mean_wait_s") is not None:
            best = p
    return best


def effects(report_rows: Sequence[Mapping[str, Any]], series: Sequence[Mapping[str, Any]], as_of: datetime,
            horizon_s: int = HORIZON_S, run_over: bool = False) -> list[dict[str, Any]]:
    """Before/after of every closed recommendation: mean wait and EWT at the close, and `horizon_s` later.

    Verdict: better / same / worse, `measuring` while the after-window is still running, `ended` when the run
    stopped before it closed (it will never be measured), `no_data` when the metric was not computable."""
    out = []
    for r in report_rows:
        if r["outcome"] == "open" or r["close_ts"] is None:
            continue
        t, after_t = r["close_ts"], r["close_ts"] + timedelta(seconds=horizon_s)
        before = _at(series, t)
        e = {"rec_id": r["rec_id"], "outcome": r["outcome"], "reason": r.get("reason"), "action": r.get("action"),
             "bus_id": r.get("bus_id"), "stop_id": r.get("stop_id"), "case": r.get("case"),
             "predicted_saving_s": r.get("saving_s"), "close_ts": t, "after_ts": after_t,
             "wait_before_s": None, "wait_after_s": None, "ewt_before_s": None, "ewt_after_s": None,
             "delta_wait_s": None, "delta_ewt_s": None, "verdict": "measuring"}
        if before is None:
            e["verdict"] = "no_data"
        elif as_of < after_t and run_over:
            e["verdict"] = "ended"
        elif as_of >= after_t:
            after = _at(series, after_t)
            if after is None or after is before:
                e["verdict"] = "no_data"
            else:
                e.update(wait_before_s=before["mean_wait_s"], wait_after_s=after["mean_wait_s"],
                         ewt_before_s=before["ewt_s"], ewt_after_s=after["ewt_s"],
                         delta_wait_s=round(after["mean_wait_s"] - before["mean_wait_s"], 1),
                         delta_ewt_s=round(after["ewt_s"] - before["ewt_s"], 1))
                d = e["delta_wait_s"]
                e["verdict"] = "better" if d <= -SAME_BAND_S else "worse" if d >= SAME_BAND_S else "same"
        if e["wait_before_s"] is None and before is not None:
            e.update(wait_before_s=before["mean_wait_s"], ewt_before_s=before["ewt_s"])
        out.append(e)
    return out


def compare_groups(effs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Applied vs not applied (discarded + expired): how the wait moved in the 15 minutes after."""
    groups = {"applied": [e for e in effs if e["outcome"] == "applied"],
              "not_applied": [e for e in effs if e["outcome"] != "applied"]}
    out = []
    for name, g in groups.items():
        measured = [e for e in g if e["delta_wait_s"] is not None]
        deltas = [e["delta_wait_s"] for e in measured]
        out.append({"group": name, "n": len(g), "measured": len(measured),
                    "better": sum(1 for e in measured if e["verdict"] == "better"),
                    "same": sum(1 for e in measured if e["verdict"] == "same"),
                    "worse": sum(1 for e in measured if e["verdict"] == "worse"),
                    "median_delta_wait_s": round(median(deltas), 1) if deltas else None,
                    "mean_delta_wait_s": round(mean(deltas), 1) if deltas else None})
    return out


def run_summary(series: Sequence[Mapping[str, Any]], boarding: Mapping[str, Any]) -> dict[str, Any]:
    """Whole-run figures to compare runs (same seed with and without decisions)."""
    ok = [p for p in series if p.get("computable") and p.get("mean_wait_s") is not None]
    fleet = [p for p in series if p.get("in_service") is not None]
    return {
        "snapshots": len(series),
        "avg_wait_s": round(mean(p["mean_wait_s"] for p in ok), 1) if ok else None,
        "avg_scheduled_wait_s": round(mean(p["scheduled_wait_s"] for p in ok), 1) if ok else None,
        "avg_ewt_s": round(mean(p["ewt_s"] for p in ok), 1) if ok else None,
        "avg_in_service": round(mean(p["in_service"] for p in fleet), 1) if fleet else None,
        "max_in_service": max((p["in_service"] for p in fleet), default=None),
        "snapshots_bunched_pct": _pct(sum(1 for p in fleet if (p["bunched"] or 0) > 0), len(fleet)),
        "p_board_10": boarding.get("p10"),
    }


def build(raw: Mapping[str, Any], report_rows: Sequence[Mapping[str, Any]], as_of: datetime,
          run_over: bool = False, start: datetime | None = None) -> dict[str, Any]:
    # The refresh commits a bootstrap snapshot before the first simulator event (hours earlier on the simulated
    # clock); it is not part of the run and would stretch every chart axis.
    series = [p for p in raw["series"] if start is None or p["as_of_ts"] >= start]
    board = boarding_summary(raw["boarding"])
    effs = effects(report_rows, series, as_of, run_over=run_over)
    now = series[-1] if series else None
    return {"now": now, "series": series, "boarding": board, "effects": effs,
            "groups": compare_groups(effs), "run": run_summary(series, board), "horizon_s": HORIZON_S,
            "accuracy": raw.get("accuracy", [])}
