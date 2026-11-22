"""What-if runs of the decision model: the real model on edited inputs, nothing written.

Loads the inputs of the latest snapshot exactly as the refresh does (`pipeline.recommend.load_inputs`, SELECTs only,
in a read-only transaction), lets the caller change a few variables, and runs the same pure functions the cycle
runs (`generate_candidates` -> `evaluate_candidates` -> `rank_candidates`). The result is returned, never stored.

What can be edited, and how it maps to the model's inputs:
- per bus: position (distance along the corridor), occupancy, data quality, a breakdown of N minutes and the
  bus_state the snapshot classified it as (`facts.bus_states`; in the cycle it comes from corridor_now, which needs
  position history to recompute, so here it is set by hand);
- reserve buses: available or not; drivers free;
- demand: one multiplier on every stop's queue, its arrival rate and the train batches at the terminal;
- model parameters: any numeric field of `MpcParams` listed in EDITABLE_PARAMS.

Rest keys (recommendations resting after a decision) are left empty: a what-if asks what the model would propose
from scratch.
"""
from __future__ import annotations

import bisect
import dataclasses
from typing import Any

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from src.data.pipeline.recommend import load_inputs, load_params
from src.data.rules.mpc import (Facts, action_doc, action_key, evaluate_candidates, generate_candidates,
                                rank_candidates, trouble_case)
from src.data.rules.projector import NON_LIVE, Inputs, project

BUS_STATES = ("leader", "regular", "bunched", "gap", "broken_down")
EDITABLE_PARAMS = {
    "threshold_s_per_rider": (0.0, 600.0),
    "reserve_cost_s": (0.0, 20000.0),
    "reserve_ready_s": (0.0, 1800.0),
    "top_n": (1, 10),
    "queue_trigger_riders": (1, 200),
}
EDITABLE_TUPLES = {"hold_options_s": (5, 180)}  # each value; MAX_HOLD_S is still enforced by the guard

_CACHE: dict[str, tuple[str, Inputs, Facts]] = {}  # target -> (snapshot_id, inputs, facts)


class BusEdit(BaseModel):
    bus_id: str
    distance_m: float | None = Field(None, ge=0, le=20000)
    occupancy: float | None = Field(None, ge=0, le=200)
    quality: str | None = None
    broken_min: float | None = Field(None, ge=0, le=240)
    bus_state: str | None = None
    available: bool = True  # reserves only


class Scenario(BaseModel):
    buses: list[BusEdit] = []
    demand_scale: float = Field(1.0, ge=0.0, le=10.0)
    drivers_free: int | None = Field(None, ge=0, le=20)
    params: dict[str, float] = {}
    hold_options_s: list[int] | None = None


# ------------------------------------------------------------------------------------ load
def load_base(conn: psycopg.Connection, target: str) -> tuple[str, Inputs, Facts]:
    """Inputs and facts of the newest snapshot, cached per snapshot (load_inputs is ~20 queries)."""
    with conn.cursor(row_factory=dict_row) as cur:
        snap = cur.execute("SELECT s.snapshot_id::text AS sid, s.as_of_ts, s.max_bronze_id FROM gold.snapshots s "
                           "JOIN gold.snapshot_commits c USING (snapshot_id) "
                           "ORDER BY c.committed_at DESC LIMIT 1").fetchone()
    if snap is None:
        raise HTTPException(409, "no snapshot yet: start a simulator run first")
    cached = _CACHE.get(target)
    if cached and cached[0] == snap["sid"]:
        return cached
    try:
        params = load_params(conn)
        inp, facts = load_inputs(conn, snap["sid"], snap["as_of_ts"], snap["max_bronze_id"], params)
    except (psycopg.Error, RuntimeError, TypeError, KeyError) as exc:
        conn.rollback()
        raise HTTPException(409, f"this stack cannot feed the model ({type(exc).__name__}: "
                                 f"{str(exc).splitlines()[0][:160]}); is migration 009 applied?") from exc
    _CACHE[target] = (snap["sid"], inp, facts)
    return _CACHE[target]


def describe(sid: str, inp: Inputs, facts: Facts) -> dict[str, Any]:
    """The editable view of the inputs."""
    state = dict(facts.bus_states)
    p = inp.params
    return {
        "snapshot_id": sid, "as_of_ts": inp.as_of.isoformat(),
        "stops": [{"stop_id": s.stop_id, "distance_m": s.distance_m, "queue": s.queue} for s in inp.stops],
        "buses": [{"bus_id": b.bus_id, "kind": b.kind, "distance_m": round(b.distance_m, 1),
                   "next_stop": inp.stops[b.next_stop_idx].stop_id if b.next_stop_idx < len(inp.stops) else None,
                   "occupancy": b.occupancy, "quality": b.quality,
                   "broken_min": None if b.broken_until is None else round(b.broken_until / 60, 1),
                   "bus_state": state.get(b.bus_id)} for b in sorted(inp.buses, key=lambda b: b.bus_id)],
        "drivers_free": facts.drivers_free,
        "params": {k: getattr(p, k) for k in EDITABLE_PARAMS},
        "hold_options_s": list(p.hold_options_s),
        "bus_states": BUS_STATES,
    }


# ----------------------------------------------------------------------------------- apply
def apply(inp: Inputs, facts: Facts, sc: Scenario) -> tuple[Inputs, Facts]:
    dist = [s.distance_m for s in inp.stops]
    edits = {e.bus_id: e for e in sc.buses}
    states = dict(facts.bus_states)
    buses = []
    for b in inp.buses:
        e = edits.get(b.bus_id)
        if e is None:
            buses.append(b)
            continue
        if b.kind == "reserve" and not e.available:
            continue  # not free: the model cannot dispatch it
        changes: dict[str, Any] = {}
        if b.kind == "service":
            if e.distance_m is not None and abs(e.distance_m - b.distance_m) > 0.05:
                d = min(e.distance_m, dist[-1])
                changes.update(distance_m=d, next_stop_idx=bisect.bisect_right(dist, d), at_stop=None)
            if e.occupancy is not None:
                changes["occupancy"] = e.occupancy
            if e.quality in ("live", "estimated"):
                changes["quality"] = e.quality
            changes["broken_until"] = None if not e.broken_min else e.broken_min * 60
        if e.bus_state in BUS_STATES:
            states[b.bus_id] = e.bus_state
        buses.append(dataclasses.replace(b, **changes) if changes else b)

    k = sc.demand_scale
    stops = tuple(dataclasses.replace(s, queue=s.queue * k, rate_by_hour=tuple(r * k for r in s.rate_by_hour),
                                      train_batches=tuple((t, n * k) for t, n in s.train_batches))
                  for s in inp.stops)
    pkw: dict[str, Any] = {}
    for name, value in sc.params.items():
        if name not in EDITABLE_PARAMS:
            raise HTTPException(422, f"parameter {name!r} is not editable")
        lo, hi = EDITABLE_PARAMS[name]
        if not lo <= value <= hi:
            raise HTTPException(422, f"{name} must be between {lo} and {hi}")
        pkw[name] = int(value) if isinstance(lo, int) else float(value)
    if sc.hold_options_s:
        lo, hi = EDITABLE_TUPLES["hold_options_s"]
        if not all(lo <= h <= hi for h in sc.hold_options_s):
            raise HTTPException(422, f"hold options must be between {lo} and {hi} s")
        pkw["hold_options_s"] = tuple(sorted(set(sc.hold_options_s)))
    params = dataclasses.replace(inp.params, **pkw)
    new_inp = dataclasses.replace(inp, buses=tuple(buses), stops=stops, params=params)
    new_facts = dataclasses.replace(
        facts, bus_states=tuple(sorted(states.items())),
        drivers_free=facts.drivers_free if sc.drivers_free is None else sc.drivers_free)
    return new_inp, new_facts


# ------------------------------------------------------------------------------------- run
def run(inp: Inputs, facts: Facts) -> dict[str, Any]:
    """The model's candidate, scoring and ranking steps, as in pipeline.recommend.run_model, without writes."""
    stop_ids = [s.stop_id for s in inp.stops]
    base = project(inp)
    cands = generate_candidates(inp, facts)
    out: dict[str, Any] = {
        "trouble_case": trouble_case(inp, facts), "base_score_s": round(base.score_s, 1),
        "riders": round(base.riders, 1), "wait_s": round(base.wait_s, 1),
        "avg_wait_s": round(base.wait_s / base.riders, 1) if base.riders else None,
        "threshold_s_per_rider": inp.params.threshold_s_per_rider, "candidates": [], "picks": 0,
    }
    if not cands:
        return out
    base, evs = evaluate_candidates(inp, cands, base)
    unsafe = frozenset(b.bus_id for b in inp.buses if b.quality in NON_LIVE)
    ranking = rank_candidates(evs, inp.params, stop_ids, frozenset(), unsafe)
    picked = {p.key: p for p in ranking.picks}
    for ev in sorted(evs, key=lambda e: -e.saving_s):
        doc = action_doc(ev.candidate.action, stop_ids)
        key = action_key(doc)
        pick = picked.get(key)
        out["candidates"].append({
            "action": doc, "case": ev.candidate.case, "score_s": round(ev.score_s, 1),
            "saving_s": ev.saving_s, "published": pick is not None, "rank": pick.rank if pick else None,
            "reason": pick.reason if pick else None, "reason_not": None if pick else ranking.not_picked.get(key)})
    out["picks"] = len(ranking.picks)
    return out
