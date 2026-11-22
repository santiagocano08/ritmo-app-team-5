"""Decision rules of the model: candidates, ranking, safety guard, lifecycle (006 FR-008 to FR-022, FR-030).

Pure and deterministic: no I/O, no clock, no randomness, no network or LLM client (Principle III, SC-012). The
projector (`rules/projector.py`) scores an action; this module chooses what is worth scoring, picks the top of the
list and keeps each proposal's identity, expiry and rest across cycles. Every number comes from `MpcParams`; the
only constant is `MAX_HOLD_S` of `rules/holds.py` (FR-010, FR-015).

"Candidate only when" (FR-009) is a filter on what is evaluated, never the decision: the choice between candidates
comes only from the score. Normal snapshot (no bunched, gap or broken bus, no queue above the trigger): no
candidate at all (SC-005).

Decisions made here where the tasks leave room (reported in verification.md)
- `case` of a trouble-wide action (reserve, adjust): C5 with a breakdown, else C1 with bunching, else C2 (a gap or a
  queue above the trigger). A queue-only trigger has no case of its own and the enum gains no value (FR-022).
- A stale proposal that returns to the top 3 keeps its `rec_id` and is un-staled (one row per key at a time).
- A proposal dominated by a stronger intensity of the same (type, bus, stop) is reported as `weaker_intensity`.
- Hold, slow down and skip stop target the bus's next stop (never the stop it is dwelling at): the story-004
  executor matches only a visit that starts after the decision.
"""
from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.data.rules.holds import MAX_HOLD_S
from src.data.rules.mpc_params import MpcParams
from src.data.rules.projector import CATALOG_ORDER, NON_LIVE, Action, BusState, Inputs, Projection, project
from src.data.rules.projector import saving_s_per_rider

SCHEMA_VERSION = "1.1.0"  # recommendation schema the model writes (FR-029)
CASE_BUNCHING, CASE_GAP, CASE_BREAKDOWN = "C1", "C2", "C5"
MIN_PER_S = 60
TERMINAL_STOP_IDX = 0  # P-883: where a reserve is dispatched and the next terminal departure leaves


@dataclass(frozen=True)
class Facts:
    """What the snapshot says besides the projector input (`gold.corridor_now`, `decision_inputs`, `source_status`)."""
    snapshot_id: str
    rules_version: str
    bus_states: tuple[tuple[str, str], ...] = ()  # (bus_id, bus_state) as in corridor_now
    drivers_free: int = 0
    enabled_stops: frozenset[int] = frozenset()  # stop indices where an action may be placed
    sources_down: frozenset[str] = frozenset()
    data_quality: str = "live"


@dataclass(frozen=True)
class Candidate:
    action: Action
    case: str


@dataclass(frozen=True)
class Evaluated:
    candidate: Candidate
    score_s: float
    saving_s: float  # per rider, 0.1 s resolution


# -- candidates ---------------------------------------------------------------------------------------------


def _live(bus: BusState, facts: Facts) -> bool:
    return bus.quality not in NON_LIVE and bus.bus_id not in facts.sources_down


def trouble_case(inp: Inputs, facts: Facts) -> str | None:
    """The case of the situation that makes the trouble-wide actions candidates, or None when all is calm."""
    states = {s for _, s in facts.bus_states}
    if "broken_down" in states or any(b.broken_until is not None for b in inp.buses):
        return CASE_BREAKDOWN
    if "bunched" in states:
        return CASE_BUNCHING
    if "gap" in states or any(s.queue > inp.params.queue_trigger_riders for s in inp.stops):
        return CASE_GAP
    return None


def generate_candidates(inp: Inputs, facts: Facts) -> list[Candidate]:
    """The catalog of FR-008, in its order of preference: reserve, slow down, hold, adjust departure, skip stop."""
    p = inp.params
    last = len(inp.stops) - 1
    state = dict(facts.bus_states)
    buses = sorted(inp.buses, key=lambda b: b.bus_id)
    trouble = trouble_case(inp, facts)
    out: list[Candidate] = []

    def at_stop(b: BusState) -> bool:  # a stop ahead, before the end of the corridor, where actions are allowed
        return b.next_stop_idx < last and b.next_stop_idx in facts.enabled_stops

    followers = [b for b in buses if b.kind == "service" and _live(b, facts) and state.get(b.bus_id) == "bunched"
                 and at_stop(b)]
    if trouble and facts.drivers_free > 0:
        reserves = [b for b in buses if b.kind == "reserve"]
        if reserves and TERMINAL_STOP_IDX in facts.enabled_stops:
            out.append(Candidate(Action("reserve_dispatch", reserves[0].bus_id, TERMINAL_STOP_IDX), trouble))
    for b in followers:
        for share in p.slow_shares:
            out.append(Candidate(Action("slow_down", b.bus_id, b.next_stop_idx, share=share,
                                        duration_s=p.slow_duration_s), CASE_BUNCHING))
    for b in followers:
        for hold_s in p.hold_options_s:
            out.append(Candidate(Action("hold", b.bus_id, b.next_stop_idx, hold_s=hold_s), CASE_BUNCHING))
    if trouble and TERMINAL_STOP_IDX in facts.enabled_stops:
        waiting = [b for b in buses if b.kind == "waiting"]
        if waiting:
            # the projector pairs the terminal slots with the waiting buses in bus-id order: the next to leave
            # is the one with the earliest slot (a bus with no slot is not scheduled and is not a target)
            slot = dict(zip((b.bus_id for b in waiting), inp.next_departures))
            if slot:
                nxt = min(slot, key=lambda bus_id: (slot[bus_id], bus_id))
                for shift in p.adjust_options_s:
                    out.append(Candidate(Action("adjust_departure", nxt, TERMINAL_STOP_IDX, shift_s=shift), trouble))
    for b in buses:
        if b.kind == "service" and _live(b, facts) and state.get(b.bus_id) == "gap" and at_stop(b):
            out.append(Candidate(Action("skip_stop", b.bus_id, b.next_stop_idx), CASE_GAP))
    return out


def evaluate_candidates(inp: Inputs, candidates: Sequence[Candidate]) -> tuple[Projection, list[Evaluated]]:
    """Project "do nothing" and every candidate; saving per rider against the baseline (FR-008, FR-011)."""
    base = project(inp)
    return base, [Evaluated(c, (pr := project(inp, c.action)).score_s, saving_s_per_rider(base, pr))
                  for c in candidates]


# -- safety guard (R14) -------------------------------------------------------------------------------------


def guard(evaluated: Sequence[Evaluated], unsafe_buses: frozenset[str], sources_down: frozenset[str]
          ) -> tuple[list[Evaluated], list[tuple[Evaluated, str]]]:
    """Drop what must never be published, whatever the candidate rules did: a hold above the cap, a target that
    is not live (FR-015, FR-016). Returns (kept, [(dropped, reason)])."""
    kept: list[Evaluated] = []
    dropped: list[tuple[Evaluated, str]] = []
    for ev in evaluated:
        a = ev.candidate.action
        if a.type == "hold" and a.hold_s > MAX_HOLD_S:
            dropped.append((ev, "hold_over_cap"))
        elif a.bus_id in unsafe_buses or a.bus_id in sources_down:
            dropped.append((ev, "unsafe_target"))
        else:
            kept.append(ev)
    return kept, dropped


def is_fresh(age_s: float, params: MpcParams) -> bool:
    """FR-017: a snapshot older than `freshness_max_s` of wall time creates no recommendation."""
    return age_s <= params.freshness_max_s


# -- documents ----------------------------------------------------------------------------------------------


def _num(x: float | int | None) -> float | int | None:
    if x is None:
        return None
    return int(x) if float(x).is_integer() else float(x)


def _g(x: float) -> str:
    return f"{x:g}"


def action_doc(a: Action, stop_ids: Sequence[str]) -> dict:
    """The `action` object of the recommendation schema 1.1.0."""
    duration = {"hold": a.hold_s, "adjust_departure": a.shift_s, "slow_down": a.duration_s}.get(a.type)
    doc: dict = {"type": a.type, "bus_id": a.bus_id, "stop_id": stop_ids[a.stop_idx], "duration_s": _num(duration)}
    if a.type == "slow_down":
        doc["speed_reduction_pct"] = _num(round(a.share * 100, 6))
    return doc


def action_key(doc_action: Mapping) -> str:
    """`type|bus|stop|duration|speed_reduction_pct`, read from the action object (R7)."""
    def part(v) -> str:
        return "" if v is None else str(_num(v))
    return "|".join((doc_action["type"], doc_action["bus_id"], doc_action["stop_id"],
                     part(doc_action.get("duration_s")), part(doc_action.get("speed_reduction_pct"))))


def make_rec_id(key: str, first_snapshot_id: str, model_version: str) -> str:
    """UUID shaped from sha256("rec|key|first snapshot|model version"), version-4 bits (R7, FR-014)."""
    digest = hashlib.sha256(f"rec|{key}|{first_snapshot_id}|{model_version}".encode()).digest()
    return str(uuid.UUID(int=int.from_bytes(digest[:16], "big"), version=4))


def _reason(a: Action, doc: Mapping, saving_s: float) -> str:
    s = f"saves {_g(saving_s)} s per rider"
    bus, stop = doc["bus_id"], doc["stop_id"]
    if a.type == "hold":
        return f"hold {bus} {_g(doc['duration_s'])} s at {stop} {s}"
    if a.type == "slow_down":
        dur = doc["duration_s"]
        span = f"{dur // MIN_PER_S} min" if dur % MIN_PER_S == 0 else f"{dur} s"
        return f"slow down {bus} by {_g(doc['speed_reduction_pct'])} % for {span} at {stop} {s}"
    if a.type == "reserve_dispatch":
        return f"dispatch reserve {bus} {s}"
    if a.type == "adjust_departure":
        verb = "advance" if a.shift_s < 0 else "delay"
        return f"{verb} the next departure from {stop} ({bus}) by {_g(abs(a.shift_s))} s {s}"
    return f"skip stops with an empty queue for {bus} from {stop} {s}"


@dataclass(frozen=True)
class Pick:
    candidate: Candidate
    saving_s: float
    key: str
    rank: int
    action_doc: dict
    reason: str

    @property
    def case(self) -> str:
        return self.candidate.case


@dataclass(frozen=True)
class RankResult:
    picks: list[Pick]
    not_picked: dict[str, str]  # key -> reason_not


def _order(ev: Evaluated) -> tuple:
    a = ev.candidate.action
    return (-ev.saving_s, CATALOG_ORDER.get(a.type, len(CATALOG_ORDER)), a.bus_id,
            -1 if a.stop_idx is None else a.stop_idx, a.hold_s, a.share, a.shift_s)


def rank_candidates(evaluated: Sequence[Evaluated], params: MpcParams, stop_ids: Sequence[str],
                    resting: frozenset[str] = frozenset(), unsafe_buses: frozenset[str] = frozenset()) -> RankResult:
    """Threshold, rest and top N (FR-012, FR-030). Best intensity per (type, bus, stop); ties by catalog order,
    then bus id. Reasons for everything that is not published are returned for `gold.mpc_evaluation`."""
    kept, dropped = guard(evaluated, unsafe_buses, frozenset())
    key_of = {id(ev): action_key(action_doc(ev.candidate.action, stop_ids)) for ev in evaluated}
    not_picked = {key_of[id(ev)]: reason for ev, reason in dropped}
    best: dict[tuple, Evaluated] = {}
    for ev in kept:
        a = ev.candidate.action
        slot = (a.type, a.bus_id, a.stop_idx)
        cur = best.get(slot)
        if cur is None or ev.saving_s > cur.saving_s:
            if cur is not None:
                not_picked[key_of[id(cur)]] = "weaker_intensity"
            best[slot] = ev
        else:
            not_picked[key_of[id(ev)]] = "weaker_intensity"
    picks: list[Pick] = []
    for ev in sorted(best.values(), key=_order):
        key = key_of[id(ev)]
        if ev.saving_s < params.threshold_s_per_rider:
            not_picked[key] = "below_threshold"
        elif key in resting:
            not_picked[key] = "resting"
        elif len(picks) >= params.top_n:
            not_picked[key] = "not_top_3"
        else:
            doc = action_doc(ev.candidate.action, stop_ids)
            picks.append(Pick(ev.candidate, ev.saving_s, key, len(picks) + 1, doc,
                              _reason(ev.candidate.action, doc, ev.saving_s)))
    return RankResult(picks, not_picked)


def conflicts_for(picks: Sequence[Pick]) -> dict[str, list[str]]:
    """Keys of the other picks on the same bus (a hold and a slow down of one follower cannot both be applied)."""
    return {p.key: [q.key for q in picks if q.key != p.key and q.action_doc["bus_id"] == p.action_doc["bus_id"]]
            for p in picks}


def _rfc3339(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_doc(pick: Pick, *, rec_id: str, status: str, expires_ts: datetime, conflicts: Sequence[str],
              snapshot_id: str, rules_version: str, model_version: str, data_quality: str, horizon_s: int) -> dict:
    """The recommendation, exactly as `contracts/read/recommendation.schema.json` 1.1.0 defines it."""
    return {"schema_version": SCHEMA_VERSION, "rec_id": rec_id, "case": pick.case, "action": dict(pick.action_doc),
            "reason": pick.reason, "ewt_saving_s": _num(pick.saving_s), "horizon_s": horizon_s,
            "data_quality": data_quality, "expires_ts": _rfc3339(expires_ts), "conflicts_with": list(conflicts),
            "rank": pick.rank, "status": status,
            "lineage": {"model_version": model_version, "rule_version": rules_version, "snapshot_id": snapshot_id}}


# -- lifecycle ----------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    action: str  # apply | discard
    decided_at: datetime | None  # simulated-time estimate of the decision (`decided_at_sim`), None if unknown


@dataclass(frozen=True)
class CycleCtx:
    snapshot_id: str
    as_of: datetime
    rules_version: str
    model_version: str
    data_quality: str
    params: MpcParams


@dataclass(frozen=True)
class Existing:
    rec_id: str
    key: str
    case: str
    status: str
    stale: bool
    proposed_ts: datetime
    expires_ts: datetime
    close_ts: datetime | None
    first_snapshot_id: str
    doc: dict
    params: dict


@dataclass(frozen=True)
class Derived:
    existing: Existing
    status: str
    close_ts: datetime | None

    @property
    def key(self) -> str:
        return self.existing.key


@dataclass(frozen=True)
class Row:
    rec_id: str
    key: str
    case: str
    status: str
    stale: bool
    proposed_ts: datetime
    expires_ts: datetime
    close_ts: datetime | None
    first_snapshot_id: str
    params: dict
    doc: dict
    is_new: bool = False


def to_existing(r: Row) -> Existing:
    return Existing(r.rec_id, r.key, r.case, r.status, r.stale, r.proposed_ts, r.expires_ts, r.close_ts,
                    r.first_snapshot_id, r.doc, r.params)


def derive_all(existing: Sequence[Existing], decisions: Mapping[str, Decision], passed: Mapping[str, datetime],
               as_of: datetime, params: MpcParams) -> list[Derived]:
    """Status of every row from facts only (FR-021): the first decision wins, else time or the bus passing the
    stop expires it, else it is proposed. `close_ts` is kept once set (it starts the rest of FR-030)."""
    out: list[Derived] = []
    for e in sorted(existing, key=lambda x: (x.proposed_ts, x.rec_id)):
        dec = decisions.get(e.rec_id)
        if dec is not None:
            status = "applied" if dec.action == "apply" else "discarded"
            out.append(Derived(e, status, dec.decided_at or e.close_ts or as_of))
            continue
        p = passed.get(e.rec_id)
        if e.status == "expired" or as_of > e.expires_ts or p is not None:  # expired stays expired without a decision
            close = e.close_ts if e.status == "expired" and e.close_ts else min(e.expires_ts, p or e.expires_ts)
            out.append(Derived(e, "expired", close))
        else:
            out.append(Derived(e, "proposed", None))
    return out


def resting_keys(derived: Sequence[Derived], as_of: datetime, rest_s: int) -> frozenset[str]:
    """Keys that closed less than `rest_s` ago: not proposed again until then (FR-030)."""
    return frozenset(d.key for d in derived if d.status != "proposed" and d.close_ts is not None
                     and as_of < d.close_ts + timedelta(seconds=rest_s))


def row_params(action_type: str, params: MpcParams) -> dict:
    """What the simulator needs and `doc` does not carry (data-model M5)."""
    return {"ready_s": params.reserve_ready_s} if action_type == "reserve_dispatch" else {}


def apply_picks(derived: Sequence[Derived], picks: Sequence[Pick] | None, ctx: CycleCtx) -> list[Row]:
    """The rows of this cycle. `picks=None` is a snapshot too old to create anything: rows only get their status."""
    live = {d.key: d for d in derived if d.status == "proposed"}
    chosen = {p.key: p for p in picks or []}
    rec_for = {k: (live[k].existing.rec_id if k in live else make_rec_id(k, ctx.snapshot_id, ctx.params.model_version))
               for k in chosen}
    conflicts = conflicts_for(list(picks or []))
    rows: list[Row] = []
    for d in derived:
        e = d.existing
        doc = {**e.doc, "status": d.status}
        stale = e.stale
        if d.status == "proposed" and picks is not None:
            pick = chosen.get(e.key)
            if pick is not None:
                doc = build_doc(pick, rec_id=e.rec_id, status="proposed", expires_ts=e.expires_ts,
                                conflicts=[rec_for[k] for k in conflicts[e.key]], snapshot_id=ctx.snapshot_id,
                                rules_version=ctx.rules_version, model_version=ctx.params.model_version,
                                data_quality=ctx.data_quality, horizon_s=ctx.params.horizon_s)
                stale = False
            else:
                stale = True  # still proposed, no longer in the top: last rank and numbers stay frozen
        rows.append(Row(e.rec_id, e.key, e.case, d.status, stale, e.proposed_ts, e.expires_ts, d.close_ts,
                        e.first_snapshot_id, e.params, doc))
    for pick in picks or []:
        if pick.key in live:
            continue
        rec_id = rec_for[pick.key]
        expires = ctx.as_of + timedelta(seconds=ctx.params.proposal_ttl_s)
        doc = build_doc(pick, rec_id=rec_id, status="proposed", expires_ts=expires,
                        conflicts=[rec_for[k] for k in conflicts[pick.key]], snapshot_id=ctx.snapshot_id,
                        rules_version=ctx.rules_version, model_version=ctx.params.model_version,
                        data_quality=ctx.data_quality, horizon_s=ctx.params.horizon_s)
        rows.append(Row(rec_id, pick.key, pick.case, "proposed", False, ctx.as_of, expires, None, ctx.snapshot_id,
                        row_params(pick.action_doc["type"], ctx.params), doc, is_new=True))
    # a refreshed row's conflicts may name a row created in this same call; the lists are already complete
    return sorted(rows, key=lambda r: r.rec_id)
