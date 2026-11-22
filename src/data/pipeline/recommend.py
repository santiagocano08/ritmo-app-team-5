"""Decision model step of the cycle: inputs, candidates, top 3, `gold.recommendation` (006 FR-001 to FR-022).

Runs inside `run_cycle`, after the snapshot and the instruction status, before COMMIT. Every read is either a table
rebuilt in this same transaction or bronze filtered by `id <= M` and `event_ts <= as_of`, so the model sees exactly
the world the snapshot was built from (research R1). It writes `gold.recommendation` and `gold.mpc_evaluation`
only, never bronze, and never opens a transaction of its own: the caller commits or rolls back.

The rules live in `rules/mpc.py` and `rules/projector.py` (pure); this module is orchestration. No network call, no
LLM, no clock other than the database's own (Principle III, SC-012).
"""
from __future__ import annotations

import bisect
import hashlib
import json
import logging
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.data.rules import RULES_VERSION
from src.data.rules.holds import HOLD_ORDERS_SQL
from src.data.rules.mpc import (CycleCtx, Decision, Existing, Facts, Row, action_doc, action_key, apply_picks,
                                derive_all, evaluate_candidates, generate_candidates, is_fresh, rank_candidates,
                                resting_keys)
from src.data.rules.mpc_params import MpcParams
from src.data.rules.projector import (DWELL_BASE_S, DWELL_PER_ALIGHTED_S, DWELL_PER_BOARDED_S, NON_LIVE, BusState,
                                      Inputs, StopState, alight_share, inputs_json)
from src.data.rules.timebands import LOCAL_OFFSET
from src.pulsoflota.config import get_mpc_enabled
from src.pulsoflota.models.read.recommendation import RecommendationV110

SQL_DIR = Path(__file__).resolve().parents[1] / "rules" / "sql"
HOUR_S = 3600
DAY_S = 86400
BAND_S = 900  # M2 band: 15 minutes
BROKEN_FOREVER_S = 10**7  # an open-ended breakdown: the bus never moves inside any window
logger = logging.getLogger("pulsoflota.recommend")

_REC_COLUMNS = ("rec_id::text AS rec_id, key, \"case\", status, stale, proposed_ts, expires_ts, close_ts, "
                "first_snapshot_id::text AS first_snapshot_id, doc, params")
_UPSERT = (
    "INSERT INTO gold.recommendation (rec_id, doc, key, \"case\", status, stale, proposed_ts, expires_ts, close_ts, "
    "first_snapshot_id, params, lineage_detail, rules_version, max_bronze_id) "
    "VALUES (%(rec_id)s, %(doc)s, %(key)s, %(case)s, %(status)s, %(stale)s, %(proposed_ts)s, %(expires_ts)s, "
    "%(close_ts)s, %(first_snapshot_id)s, %(params)s, coalesce(%(lineage)s, '{}'::jsonb), %(rules_version)s, "
    "%(max_id)s) "
    "ON CONFLICT (rec_id) DO UPDATE SET doc = EXCLUDED.doc, \"case\" = EXCLUDED.\"case\", status = EXCLUDED.status, "
    "stale = EXCLUDED.stale, close_ts = EXCLUDED.close_ts, "
    "lineage_detail = coalesce(%(lineage)s, gold.recommendation.lineage_detail), "
    "rules_version = EXCLUDED.rules_version, max_bronze_id = EXCLUDED.max_bronze_id")
_EVAL_INSERT = (
    "INSERT INTO gold.mpc_evaluation (snapshot_id, seq, action, \"case\", score_s, saving_s_per_rider, recommended, "
    "reason_not, rules_version, max_bronze_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")


@dataclass(frozen=True)
class ModelResult:
    ran: bool  # candidates were generated (the model is on and the snapshot is fresh)
    n_candidates: int
    n_published: int  # rows in this cycle's top list
    n_written: int


# -- configuration ----------------------------------------------------------------------------------------------


def load_params(conn: psycopg.Connection) -> MpcParams:
    """`config.decision_model` as `MpcParams` (FR-010: nothing is a constant in the code)."""
    with conn.cursor(row_factory=dict_row) as cur:
        row = cur.execute("SELECT * FROM config.decision_model ORDER BY corridor_id LIMIT 1").fetchone()
    if row is None:
        raise RuntimeError("config.decision_model has no row")
    defaults = MpcParams()
    kw = {}
    for f in fields(MpcParams):
        value, want = row[f.name], getattr(defaults, f.name)
        if isinstance(want, tuple):
            value = tuple(float(x) if isinstance(want[0], float) else int(x) for x in value)
        elif isinstance(want, bool):
            value = bool(value)
        elif isinstance(want, int):
            value = int(value)
        elif isinstance(want, float):
            value = float(value)
        kw[f.name] = value
    return MpcParams(**kw)


def snapshot_age_s(conn: psycopg.Connection, snapshot_id: UUID | str) -> float:
    """Wall-clock seconds since the snapshot was committed (ADR-0006, FR-017). A missing log row counts as old."""
    row = conn.execute("SELECT extract(epoch FROM clock_timestamp() - committed_at) FROM gold.snapshot_commits "
                       "WHERE snapshot_id = %s", (str(snapshot_id),)).fetchone()
    return float("inf") if row is None else float(row[0])


# -- inputs -------------------------------------------------------------------------------------------------------


def _sql(name: str) -> str:
    return (SQL_DIR / name).read_text(encoding="utf-8")


def _utc(ts: datetime) -> datetime:
    return ts.astimezone(timezone.utc)


def _broken_left(row: dict, broken: dict) -> float | None:
    """Seconds until the breakdown of a broken-down bus ends (an open-ended one never ends inside a window)."""
    if row["operational_status"] != "broken_down":
        return None
    left = broken.get(row["bus_id"])
    return float(BROKEN_FOREVER_S if left is None else max(left, 0.0))


def _rates(ref_street: list[float], observed_n: int | None, shape: list[float], hour_now: int,
           min_sample: int, window_s: int) -> tuple[float, ...]:
    """Riders per hour for each local hour: the reference, or the observed rate of the last window scaled by the
    shape of each hour when the stop has at least `min_sample` events."""
    if observed_n is None or observed_n < min_sample:
        return tuple(ref_street)
    now = observed_n / window_s * HOUR_S
    return tuple(now * (shape[h] / shape[hour_now]) if shape[hour_now] > 0 else now for h in range(24))


def load_inputs(conn: psycopg.Connection, snapshot_id: UUID | str, as_of: datetime, max_bronze_id: int,
                params: MpcParams | None = None) -> tuple[Inputs, Facts]:
    """Everything the projector and the candidate rules need, from one consistent read (FR-001, FR-003)."""
    params = params or load_params(conn)
    as_of = _utc(as_of)
    q = {"as_of_ts": as_of, "max_bronze_id": max_bronze_id}
    with conn.cursor(row_factory=dict_row) as cur:
        stops_ref = cur.execute("SELECT stop_id, distance_along_m FROM config.ref_stops ORDER BY stop_seq").fetchall()
        stop_ids = [r["stop_id"] for r in stops_ref]
        dist = [float(r["distance_along_m"]) for r in stops_ref]
        n, last = len(stop_ids), len(stop_ids) - 1
        idx_of = {s: i for i, s in enumerate(stop_ids)}
        shape = [0.0] * 24
        for r in cur.execute("SELECT hour, metro_line_a_shape FROM config.ref_demand_shape").fetchall():
            shape[r["hour"]] = float(r["metro_line_a_shape"])
        daily = float(cur.execute("SELECT daily_riders_dir1 FROM config.ref_demand_volume LIMIT 1").fetchone()[
            "daily_riders_dir1"])
        settings = cur.execute("SELECT headway_planned_s, drivers_free, min_sample_count "
                               "FROM config.corridor_settings").fetchone()
        m1 = [[0.0] * (n - 1) for _ in range(24)]
        for r in cur.execute("SELECT segment_id, hour_band, forecast_travel_s FROM gold.m1_baseline").fetchall():
            m1[r["hour_band"]][r["segment_id"] - 1] = float(r["forecast_travel_s"])
        m2 = {r["band"]: (int(r["arrivals_forecast"]), r["source"]) for r in cur.execute(
            "SELECT band, arrivals_forecast, source FROM gold.m2_baseline").fetchall()}
        trains = [(r["arrival_sec"]) for r in cur.execute(
            "SELECT arrival_sec FROM config.ref_train_arrival ORDER BY arrival_sec, train_trip_id").fetchall()]
        queue = {r["stop_id"]: int(r["queue_riders"]) for r in cur.execute(
            "SELECT stop_id, queue_riders FROM silver.stop_queue").fetchall()}
        counts = {r["stop_id"]: int(r["n"]) for r in cur.execute(
            _sql("mpc_inputs_rates.sql"), {**q, "window_s": params.rate_window_s}).fetchall()}
        open_visits = cur.execute(_sql("mpc_inputs_open_visits.sql"),
                                  {**q, "lookback_s": params.rate_window_s}).fetchall()
        last_dep = cur.execute(_sql("mpc_inputs_last_departure.sql")).fetchone()
        silver = cur.execute("SELECT bus_id, distance_along_m, data_quality, on_corridor, waiting, "
                             "operational_status, occupancy FROM silver.bus_current_state ORDER BY bus_id").fetchall()
        broken = {r["target_id"]: r["left_s"] for r in cur.execute(
            "SELECT target_id, CASE WHEN isfinite(end_ts) THEN extract(epoch FROM end_ts - %(as_of_ts)s) END AS left_s "
            "FROM silver.incidents WHERE incident_type = 'bus_breakdown' AND start_ts <= %(as_of_ts)s "
            "AND %(as_of_ts)s < end_ts", q).fetchall()}
        roster = {r["bus_id"]: r["role"] for r in cur.execute("SELECT bus_id, role FROM config.fleet_roster").fetchall()}
        doc = cur.execute("SELECT doc FROM gold.decision_inputs WHERE snapshot_id = %s", (str(snapshot_id),)).fetchone()["doc"]
        status_doc = cur.execute("SELECT doc FROM gold.source_status WHERE snapshot_id = %s",
                                 (str(snapshot_id),)).fetchone()["doc"]

    local = as_of + LOCAL_OFFSET
    sod = local.hour * HOUR_S + local.minute * 60 + local.second
    hour_now = local.hour

    # -- stops: queue, rates, train batches ---------------------------------------------------------------------
    n_street = max(last - 1, 1)
    street_ref = [daily * (1 - params.train_share) * shape[h] / n_street for h in range(24)]
    per_hour_trains: dict[int, int] = {}
    per_band_trains: dict[int, int] = {}
    for sec in trains:
        per_hour_trains[sec // HOUR_S] = per_hour_trains.get(sec // HOUR_S, 0) + 1
        band = ((sec + params.walk_mean_s) % DAY_S) // BAND_S
        per_band_trains[band] = per_band_trains.get(band, 0) + 1
    batches = []
    for sec in trains:
        t_rel = sec + params.walk_mean_s - sod
        if not 0 < t_rel <= params.scoring_window_s:
            continue
        band = ((sec + params.walk_mean_s) % DAY_S) // BAND_S
        forecast, source = m2.get(band, (0, "reference"))
        if source == "observed":
            riders = forecast / max(per_band_trains.get(band, 1), 1)
        else:
            riders = daily * params.train_share * shape[sec // HOUR_S] / max(per_hour_trains.get(sec // HOUR_S, 1), 1)
        batches.append((float(t_rel), float(riders)))
    stops = []
    for i, sid in enumerate(stop_ids):
        if i == 0:
            rate = (0.0,) * 24  # Prado receives riders in train batches only
        elif i == last:
            rate = (0.0,) * 24
        else:
            rate = _rates(street_ref, counts.get(sid), shape, hour_now, int(settings["min_sample_count"]),
                          params.rate_window_s)
        stops.append(StopState(sid, dist[i], float(queue.get(sid, 0)), rate, tuple(batches) if i == 0 else ()))

    # -- buses --------------------------------------------------------------------------------------------------
    def dwell(boarded: int, alighted: int) -> float:
        return float(max(DWELL_BASE_S, DWELL_BASE_S + DWELL_PER_BOARDED_S * boarded + DWELL_PER_ALIGHTED_S * alighted))

    open_by_bus: dict[str, dict] = {}
    for r in open_visits:  # the newest open visit of each bus
        open_by_bus[r["bus_id"]] = r
    first_open_dep = None
    reserve_free = set(doc["resources"]["reserve_free"])
    buses: list[BusState] = []
    waiting_at_terminal: set[str] = set()  # waiting at the first stop for the scheduled departure (silver `waiting`)
    seen: set[str] = set()
    for r in silver:
        bid = r["bus_id"]
        seen.add(bid)
        d = None if r["distance_along_m"] is None else float(r["distance_along_m"])
        ov = open_by_bus.get(bid)
        if d is not None and ov is not None and ov["stop_id"] in idx_of:
            # at a stop now: the remaining dwell is known (a bus at the terminal in its dwell is one of these)
            si = idx_of[ov["stop_id"]]
            arr = (_utc(ov["event_ts"]) - as_of).total_seconds()
            at_stop = (arr, dwell(ov["boarded"], ov["alighted"]))
            if si == 0:
                dep = _utc(ov["event_ts"]) + timedelta(seconds=at_stop[1])
                first_open_dep = dep if first_open_dep is None else max(first_open_dep, dep)
            buses.append(BusState(bid, "service", dist[si], si + 1, float(r["occupancy"] or 0), at_stop,
                                  r["data_quality"], _broken_left(r, broken)))
        elif d is not None and r["on_corridor"]:
            buses.append(BusState(bid, "service", d, bisect.bisect_right(dist, d), float(r["occupancy"] or 0), None,
                                  r["data_quality"], _broken_left(r, broken)))
        elif roster.get(bid, "in_service") == "reserve":
            if bid in reserve_free:
                buses.append(BusState(bid, "reserve"))
        else:  # waiting at the terminal for its scheduled departure, or in layover after its trip
            buses.append(BusState(bid, "waiting"))
            if r["waiting"]:
                waiting_at_terminal.add(bid)
    for bid, role in sorted(roster.items()):
        if bid in seen:
            continue
        if role == "reserve":
            if bid in reserve_free:
                buses.append(BusState(bid, "reserve"))
        else:
            buses.append(BusState(bid, "waiting"))

    planned = float(settings["headway_planned_s"])
    last_departure = last_dep["max"] if last_dep and last_dep["max"] is not None else None
    if first_open_dep is not None:
        last_departure = first_open_dep if last_departure is None else max(_utc(last_departure), first_open_dep)
    base = 0.0 if last_departure is None else (_utc(last_departure) - as_of).total_seconds()
    # Terminal slots: one planned headway after the last departure, one slot per waiting bus. The buses already
    # waiting at the terminal leave first (by id), then the ones coming back from their trip or not yet seen (by
    # id). The projector pairs the slots with the waiting buses in bus-id order, so the tuple is returned in that order.
    waiting_ids = sorted(b.bus_id for b in buses if b.kind == "waiting")
    queue_order = sorted(waiting_ids, key=lambda b: (b not in waiting_at_terminal, b))
    slot_of = {b: (max(0.0, base + planned * (k + 1)) if last_departure is not None else planned * k)
               for k, b in enumerate(queue_order)}
    slots = tuple(slot_of[b] for b in waiting_ids)

    inp = Inputs(as_of=as_of, buses=tuple(buses), stops=tuple(stops), m1=tuple(tuple(r) for r in m1),
                 trend=(1.0,) * (n - 1), alight_share=tuple(alight_share(i, last) for i in range(n)),
                 next_departures=slots, params=params)
    down = frozenset(s["bus_id"] for s in status_doc["sources_down"])
    facts = Facts(snapshot_id=str(snapshot_id), rules_version=RULES_VERSION,
                  bus_states=tuple(sorted((b["bus_id"], b["bus_state"]) for b in doc["buses"])),
                  drivers_free=int(doc["resources"]["drivers_free"]),
                  enabled_stops=frozenset(idx_of[s] for s in doc["enabled_stops"] if s in idx_of),
                  sources_down=down, data_quality="estimated" if down else "live")
    return inp, facts


# -- existing rows, decisions, passing --------------------------------------------------------------------------


def load_existing(conn: psycopg.Connection) -> list[Existing]:
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(f"SELECT {_REC_COLUMNS} FROM gold.recommendation ORDER BY proposed_ts, rec_id"  # noqa: S608
                           ).fetchall()
    return [Existing(r["rec_id"], r["key"], r["case"], r["status"], r["stale"], r["proposed_ts"], r["expires_ts"],
                     r["close_ts"], r["first_snapshot_id"], r["doc"], r["params"]) for r in rows]


def load_decisions(conn: psycopg.Connection, max_bronze_id: int) -> dict[str, Decision]:
    """The first backend `decision` per `rec_id` by bronze id (the query shared with the simulator's poller)."""
    out: dict[str, Decision] = {}
    sql = HOLD_ORDERS_SQL.read_text(encoding="utf-8")
    for _id, rec_id, action, decided_at in conn.execute(sql, {"last_id": 0, "max_id": max_bronze_id}).fetchall():
        out.setdefault(str(rec_id).lower(), Decision(str(action), None if decided_at is None else _utc(decided_at)))
    return out


def load_passed(conn: psycopg.Connection, existing: list[Existing]) -> dict[str, datetime]:
    """When the bus passed the stop of each still-proposed row (FR-021): a completed visit that began after the
    proposal; for a reserve dispatch, the reserve seen leaving the terminal."""
    out: dict[str, datetime] = {}
    for e in existing:
        if e.status != "proposed":
            continue
        a = e.doc["action"]
        column = "departure_ts" if a["type"] == "reserve_dispatch" else "arrival_ts"
        row = conn.execute(
            f"SELECT min({column}) FROM silver.stop_visits WHERE bus_id = %s AND stop_id = %s "  # noqa: S608
            f"AND arrival_ts >= %s", (a["bus_id"], a["stop_id"], e.proposed_ts)).fetchone()
        if row and row[0] is not None:
            out[e.rec_id] = _utc(row[0])
    return out


# -- the step -----------------------------------------------------------------------------------------------------


def _changed(row: Row, old: Existing | None) -> bool:
    return (old is None or row.status != old.status or row.stale != old.stale or row.close_ts != old.close_ts
            or row.doc != old.doc or row.case != old.case)


def run_model(conn: psycopg.Connection, snapshot_id: UUID | str, as_of: datetime, max_bronze_id: int, *,
              enabled: bool | None = None, age_s: float | None = None) -> ModelResult:
    """One model step in the caller's transaction. Existing rows always get their derived status (even when the
    model is off or the snapshot is old); candidates are generated only when the model is on and the snapshot is
    at most `freshness_max_s` old (FR-017)."""
    as_of = _utc(as_of)
    sid = str(snapshot_id)
    params = load_params(conn)
    on = get_mpc_enabled() if enabled is None else enabled
    existing = load_existing(conn)
    derived = derive_all(existing, load_decisions(conn, max_bronze_id), load_passed(conn, existing), as_of, params)
    picks, evaluation, lineage, n_cands = None, [], {}, 0
    ran = False
    if on and is_fresh(snapshot_age_s(conn, sid) if age_s is None else age_s, params):
        inp, facts = load_inputs(conn, sid, as_of, max_bronze_id, params)
        stop_ids = [s.stop_id for s in inp.stops]
        cands = generate_candidates(inp, facts)
        picks, ran, n_cands = [], True, len(cands)
        if cands:
            base, evs = evaluate_candidates(inp, cands)
            unsafe = frozenset(b.bus_id for b in inp.buses if b.quality in NON_LIVE)
            ranking = rank_candidates(evs, params, stop_ids, resting_keys(derived, as_of, params.rest_s), unsafe)
            picks = ranking.picks
            chosen = {p.key for p in picks}
            evaluation.append((0, {"type": "none"}, None, base.score_s, 0.0, False, None))
            for seq, ev in enumerate(evs, start=1):
                doc = action_doc(ev.candidate.action, stop_ids)
                key = action_key(doc)
                evaluation.append((seq, doc, ev.candidate.case, ev.score_s, ev.saving_s, key in chosen,
                                   None if key in chosen else ranking.not_picked.get(key)))
            inputs = inputs_json(inp)
            digest = hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            lineage = {"params": {f.name: _jsonable(getattr(params, f.name)) for f in fields(params)},
                       "inputs": inputs, "inputs_sha256": digest, "base_score_s": base.score_s,
                       "riders": base.riders, "candidates_evaluated": len(cands), "snapshot_id": sid}
        ctx = CycleCtx(sid, as_of, RULES_VERSION, params.model_version, facts.data_quality, params)
    else:
        ctx = CycleCtx(sid, as_of, RULES_VERSION, params.model_version, "live", params)
    rows = apply_picks(derived, picks, ctx)
    by_id = {e.rec_id: e for e in existing}
    written = 0
    with conn.cursor() as cur:
        for r in rows:
            old = by_id.get(r.rec_id)
            if not _changed(r, old):
                continue
            RecommendationV110.model_validate(r.doc)  # the contract, before it reaches the table (Principle II)
            refreshed = r.is_new or (picks is not None and not r.stale and r.status == "proposed")
            cur.execute(_UPSERT, {"rec_id": r.rec_id, "doc": Jsonb(r.doc), "key": r.key, "case": r.case,
                                  "status": r.status, "stale": r.stale, "proposed_ts": r.proposed_ts,
                                  "expires_ts": r.expires_ts, "close_ts": r.close_ts,
                                  "first_snapshot_id": r.first_snapshot_id, "params": Jsonb(r.params),
                                  "lineage": Jsonb(lineage) if refreshed and lineage else None,
                                  "rules_version": RULES_VERSION, "max_id": max_bronze_id})
            written += 1
        cur.execute("DELETE FROM gold.mpc_evaluation")
        for seq, doc, case, score, saving, recommended, reason in evaluation:
            cur.execute(_EVAL_INSERT, (sid, seq, Jsonb(doc), case, score, saving, recommended, reason,
                                       RULES_VERSION, max_bronze_id))
    return ModelResult(ran, n_cands, len(picks or []), written)


def _jsonable(value):
    return list(value) if isinstance(value, tuple) else value
