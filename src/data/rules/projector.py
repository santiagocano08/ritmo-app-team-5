"""Projector and score of the decision model (006 FR-002, FR-005 to FR-007, FR-010, FR-011; research R2, R11).

Pure and deterministic: no I/O, no clock, no randomness. Expected values only. The projector takes the
snapshot as an `Inputs` object and returns, for the next `scoring_window_s`, the departure of every bus at
every stop, the waiting score `W`, the onboard delay `O` and the reserve cost `C` of one candidate action
(or of "do nothing").

Dynamics
- Time is in seconds after `as_of` on the simulator's grid (`step_s`); an arrival and a departure are rounded
  **up** to the grid.
- Dwell is `max(10, 10 + 3*boarded + 2*alighted)` like `simulator/model.py`. `boarded = min(queue,
  capacity - occupancy_after_alighting)`, `alighted = occupancy * alight_share(stop)`.
- A segment takes the M1 time of the local hour (times the road trend) and is crossed as a fraction of the
  segment, so a segment that straddles an hour boundary, or the end of a slow-down, uses each speed for the
  time it applies. A slow-down of share `s` divides the speed by `1 - s` (time by `1 / (1 - s)`).
- Queues grow with a piecewise-constant rate per local hour (street stops) and with batches (Prado trains);
  cumulative arrivals are exact, so no 5 s stepping is needed. A bus boards at its arrival instant.
- Buses interact only through the queue of each stop. Ties between buses at the same instant are broken by
  position (leader first), then bus id.

Action semantics fixed here (the tasks leave them to the code)
- `hold`: at `stop_idx`, departure = max(natural, arrival + hold_s). Cost: occupancy * surplus.
- `slow_down`: the window starts at the departure from `stop_idx` and lasts `duration_s` (default
  `slow_duration_s`). Cost: occupancy * extra segment time.
- `reserve_dispatch`: the reserve bus reaches stop 0 at `reserve_ready_s`; cost `reserve_cost_s` once.
- `adjust_departure`: shifts the terminal slot of `bus_id` (a waiting bus) by `shift_s`, not before 0.
- `skip_stop`: from `stop_idx`, for `skip_reach_stops` stops, the bus does not stop where the queue is
  empty (it records no arrival or departure there and keeps its riders on board).
- A bus that is `estimated` or `sources_down` is projected from its last state and never receives an action
  (FR-007): `UnsafeTarget`.
"""
from __future__ import annotations

import dataclasses
import heapq
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from src.data.rules.holds import MAX_HOLD_S
from src.data.rules.mpc_params import MpcParams
from src.data.rules.timebands import LOCAL_OFFSET

EPS = 1e-9
HOUR_S = 3600
DWELL_BASE_S = 10  # simulator dwell rule: 10 + 3*boarded + 2*alighted, at least 10
DWELL_PER_BOARDED_S = 3
DWELL_PER_ALIGHTED_S = 2

ACTION_TYPES = ("none", "reserve_dispatch", "slow_down", "hold", "adjust_departure", "skip_stop")
CATALOG_ORDER = {"reserve_dispatch": 0, "slow_down": 1, "hold": 2, "adjust_departure": 3, "skip_stop": 4}
NON_LIVE = ("estimated", "sources_down")


class UnsafeTarget(ValueError):
    """An action aimed at a bus that is not live (FR-007)."""


@dataclass(frozen=True)
class BusState:
    bus_id: str
    kind: str = "service"  # service | waiting | reserve
    distance_m: float = 0.0
    next_stop_idx: int = 0  # the next stop to be served; a bus at stop s has next_stop_idx = s + 1
    occupancy: float = 0.0
    at_stop: tuple[float, float] | None = None  # (arrival second, planned dwell s), seconds after as_of
    quality: str = "live"  # live | estimated | sources_down
    broken_until: float | None = None  # seconds after as_of
    slow: tuple[float, float] | None = None  # (share, until second) already in force
    holds: tuple[tuple[int, float], ...] = ()  # (stop idx, seconds) already ordered
    skip_until: int | None = None  # stops before this index are skipped when empty


@dataclass(frozen=True)
class StopState:
    stop_id: str
    distance_m: float
    queue: float = 0.0
    rate_by_hour: tuple[float, ...] = (0.0,) * 24  # riders per hour, by local hour
    train_batches: tuple[tuple[float, float], ...] = ()  # (second after as_of, riders)


@dataclass(frozen=True)
class Inputs:
    as_of: datetime
    buses: tuple[BusState, ...]
    stops: tuple[StopState, ...]
    m1: tuple[tuple[float, ...], ...]  # m1[hour][segment] seconds
    trend: tuple[float, ...]  # ratio per segment (1.0 before phase 6)
    alight_share: tuple[float, ...]
    next_departures: tuple[float, ...]  # terminal slots, seconds after as_of
    params: MpcParams


@dataclass(frozen=True)
class Action:
    type: str
    bus_id: str = ""
    stop_idx: int | None = None
    hold_s: float = 0.0
    share: float = 0.0  # fraction; published as speed_reduction_pct = share * 100
    duration_s: float | None = None
    shift_s: float = 0.0


@dataclass(frozen=True)
class Projection:
    departures: tuple[tuple[tuple[str, int], float], ...]  # ((bus, stop idx), second), sorted
    arrivals: tuple[tuple[tuple[str, int], float], ...]
    wait_s: float
    onboard_delay_s: float
    reserve_cost_s: float
    score_s: float
    riders: float


@dataclass(frozen=True)
class Scored:
    action: Action
    projection: Projection
    saving_s: float


def alight_share(i: int, last: int = 17) -> float:
    """Share of the riders on board that alight at stop `i` (R2): destination uniform on `i..last`."""
    return 1.0 / (last - i + 1)


def _plain(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.astimezone(timezone.utc).isoformat()
    return obj


def canonical_json(obj: Any) -> bytes:
    """Sorted keys, no spaces: equal objects give equal bytes (SC-001)."""
    return json.dumps(_plain(obj), sort_keys=True, separators=(",", ":")).encode("utf-8")


def inputs_json(inp: Inputs) -> dict:
    """`Inputs` as plain data with the buses in id order (for lineage and the determinism test)."""
    return _plain(dataclasses.replace(inp, buses=tuple(sorted(inp.buses, key=lambda b: b.bus_id))))


def projection_record(inp: Inputs, projection: Projection) -> tuple[tuple[str, str, datetime, float], ...]:
    """Rows of the projection record (FR-035) from a projection: `(bus_id, stop_id, projected_departure_ts, lead_s)`.

    One row per departure the projection gives inside the scoring window, sorted by bus id and stop order, so the
    same input always gives the same rows (SC-001). `lead_s` is the projected second after `as_of` (rounded to
    milliseconds) and the timestamp is `as_of + lead_s`. A bus with no departure in the window has no row.
    """
    as_of = inp.as_of.astimezone(timezone.utc)
    window = inp.params.scoring_window_s
    rows = []
    for (bus_id, idx), seconds in projection.departures:
        lead = round(float(seconds), 3)
        if 0 <= lead <= window:
            rows.append((bus_id, inp.stops[idx].stop_id, as_of + timedelta(seconds=lead), lead))
    return tuple(rows)


def saving_s_per_rider(base: Projection, proj: Projection) -> float:
    """(score(do nothing) - score(action)) / riders, rounded to 0.1 s; 0 when there are no riders."""
    if base.riders <= EPS:
        return 0.0
    return round((base.score_s - proj.score_s) / base.riders, 1)


class _Bus:
    __slots__ = ("state", "rank", "occ", "base_windows", "act_windows", "holds", "skip_lo", "skip_hi",
                 "slot", "target")

    def __init__(self, state: BusState):
        self.state = state
        self.rank = 0
        self.occ = float(state.occupancy)
        self.base_windows: list[tuple[float, float, float]] = []
        self.act_windows: list[tuple[float, float, float]] = []
        self.holds = dict(state.holds)
        self.skip_lo, self.skip_hi = 0, 0
        self.slot: float | None = None
        self.target = False


class _Stop:
    __slots__ = ("q", "t", "rate", "batches", "bi", "integ", "arrived")

    def __init__(self, s: StopState):
        self.q = float(s.queue)
        self.t = 0.0
        self.rate = s.rate_by_hour
        self.batches = sorted((t, n) for t, n in s.train_batches if t > 0)
        self.bi = 0
        self.integ = 0.0
        self.arrived = 0.0


def _validate(inp: Inputs, action: Action) -> BusState | None:
    if action.type not in ACTION_TYPES:
        raise ValueError(f"unknown action type {action.type!r}")
    if action.type == "none":
        return None
    by_id = {b.bus_id: b for b in inp.buses}
    if action.bus_id not in by_id:
        raise ValueError(f"unknown bus {action.bus_id!r}")
    bus = by_id[action.bus_id]
    if action.type in ("hold", "slow_down", "skip_stop"):
        if bus.quality in NON_LIVE:
            raise UnsafeTarget(f"{action.bus_id} is {bus.quality}")
        if action.stop_idx is None:
            raise ValueError("stop_idx required")
    if action.type == "hold" and not 0 <= action.hold_s <= MAX_HOLD_S:
        raise ValueError(f"hold {action.hold_s} outside 0..{MAX_HOLD_S}")
    if action.type == "slow_down" and not 0 < action.share < 1:
        raise ValueError("slow-down share must be in (0, 1)")
    if action.type == "reserve_dispatch" and bus.kind != "reserve":
        raise ValueError("reserve_dispatch needs a reserve bus")
    if action.type == "adjust_departure" and bus.kind != "waiting":
        raise ValueError("adjust_departure needs a waiting bus")
    return bus


def project(inp: Inputs, action: Action | None = None) -> Projection:
    action = action or Action("none")
    _validate(inp, action)
    p = inp.params
    n = len(inp.stops)
    last = n - 1
    window = p.scoring_window_s
    step = p.step_s
    local = inp.as_of.astimezone(timezone.utc) + LOCAL_OFFSET
    sod = local.hour * HOUR_S + local.minute * 60 + local.second

    def grid(x: float) -> int:
        return math.ceil(x / step - EPS) * step

    def hour_at(t: float) -> int:
        return int((sod + t) // HOUR_S) % 24

    def hour_end(t: float) -> float:
        return ((sod + t) // HOUR_S + 1) * HOUR_S - sod

    # ---- buses --------------------------------------------------------------------------------
    states = sorted(inp.buses, key=lambda b: b.bus_id)
    waiting = [b.bus_id for b in states if b.kind == "waiting"]
    slots = dict(zip(waiting, inp.next_departures))
    if action.type == "adjust_departure" and action.bus_id in slots:
        slots[action.bus_id] = max(0.0, slots[action.bus_id] + action.shift_s)
    runs: list[_Bus] = []
    for st in states:
        if st.kind == "reserve" and not (action.type == "reserve_dispatch" and action.bus_id == st.bus_id):
            continue
        b = _Bus(st)
        if st.slow is not None:
            b.base_windows.append((0.0, float(st.slow[1]), float(st.slow[0])))
        if st.skip_until is not None:
            b.skip_lo, b.skip_hi = st.next_stop_idx, st.skip_until
        b.target = action.type != "none" and st.bus_id == action.bus_id
        if b.target and action.type == "skip_stop":
            b.skip_lo = min(b.skip_lo, action.stop_idx) if b.skip_hi else action.stop_idx
            b.skip_hi = max(b.skip_hi, action.stop_idx + p.skip_reach_stops)
        b.slot = slots.get(st.bus_id)
        runs.append(b)

    def eff_dist(b: _Bus) -> float:
        st = b.state
        if st.at_stop is not None:
            return inp.stops[st.next_stop_idx - 1].distance_m
        return st.distance_m

    for rank, b in enumerate(sorted(runs, key=lambda r: (-eff_dist(r), r.state.bus_id))):
        b.rank = rank

    stops = [_Stop(s) for s in inp.stops]
    heap: list[tuple[float, int, int, int]] = []
    arrivals: dict[tuple[str, int], float] = {}
    departures: dict[tuple[str, int], float] = {}
    onboard = 0.0
    reserve_cost = 0.0

    def advance(s: _Stop, t1: float) -> None:
        t = s.t
        while True:
            nb = s.batches[s.bi][0] if s.bi < len(s.batches) else math.inf
            if t >= t1 and nb > t1:
                break
            r = s.rate[hour_at(t)] / HOUR_S
            nxt = min(t1, hour_end(t), nb)
            dt = nxt - t
            s.integ += s.q * dt + r * dt * dt / 2
            s.q += r * dt
            s.arrived += r * dt
            t = nxt
            if nb <= nxt:
                s.q += s.batches[s.bi][1]
                s.arrived += s.batches[s.bi][1]
                s.bi += 1
        s.t = max(s.t, t1)

    def drive(k: int, t: float, frac: float, windows) -> float:
        """End time of crossing the rest (`frac`) of segment `k` starting at `t`."""
        while True:
            seg = inp.m1[hour_at(t)][k] * inp.trend[k]
            if seg <= 0:
                return t
            nxt = hour_end(t)
            share = 0.0
            for ws, we, sh in windows:
                if ws <= t < we:  # every window starts at or before the time it is first used
                    share = max(share, sh)
                    nxt = min(nxt, we)
            speed = 1.0 - share
            need = frac * seg / speed
            if t + need <= nxt + EPS:
                return t + need
            frac -= (nxt - t) * speed / seg
            t = nxt

    def leave(b: _Bus, i: int, dep: float, frac: float = 1.0) -> None:
        nonlocal onboard
        if i >= last:
            return
        if action.type == "slow_down" and b.target and action.stop_idx == i and not b.act_windows:
            dur = action.duration_s if action.duration_s is not None else p.slow_duration_s
            b.act_windows.append((dep, dep + dur, action.share))
        end = drive(i, dep, frac, b.base_windows + b.act_windows)
        if b.act_windows:
            onboard += b.occ * (end - drive(i, dep, frac, b.base_windows))
        arr = grid(end)
        if arr <= window + EPS:
            heapq.heappush(heap, (arr, b.rank, runs.index(b), i + 1))

    # ---- initial events ----------------------------------------------------------------------------
    for bi, b in enumerate(runs):
        st = b.state
        if st.kind == "reserve":
            reserve_cost = p.reserve_cost_s
            t0 = grid(p.reserve_ready_s)
            if t0 <= window + EPS:
                heapq.heappush(heap, (t0, b.rank, bi, 0))
        elif st.kind == "waiting":
            if b.slot is not None and grid(b.slot) <= window + EPS:
                heapq.heappush(heap, (grid(b.slot), b.rank, bi, 0))
        elif st.at_stop is not None:
            i = st.next_stop_idx - 1
            arr_t, dwell = st.at_stop
            nat = grid(arr_t + dwell)
            dep0 = nat
            if i in b.holds:
                dep0 = max(dep0, grid(arr_t + b.holds[i]))
            dep = dep0
            if action.type == "hold" and b.target and action.stop_idx == i:
                dep = max(dep, grid(arr_t + action.hold_s))
            onboard += b.occ * (dep - dep0)
            dep = max(dep, 0)
            if st.broken_until is not None:
                dep = max(dep, grid(st.broken_until))
            arrivals[(st.bus_id, i)] = arr_t
            if dep <= window + EPS:
                departures[(st.bus_id, i)] = dep
            leave(b, i, dep)
        else:
            i = st.next_stop_idx
            if i > last:
                continue
            start = grid(st.broken_until) if st.broken_until else 0
            if i == 0:
                if start <= window + EPS:
                    heapq.heappush(heap, (start, b.rank, bi, 0))
                continue
            d0, d1 = inp.stops[i - 1].distance_m, inp.stops[i].distance_m
            frac = min(max((d1 - st.distance_m) / (d1 - d0), 0.0), 1.0) if d1 > d0 else 0.0
            end = drive(i - 1, start, frac, b.base_windows)
            arr = grid(end)
            if arr <= window + EPS:
                heapq.heappush(heap, (arr, b.rank, bi, i))

    # ---- event loop --------------------------------------------------------------------------------
    while heap:
        t, _, bi, i = heapq.heappop(heap)
        b = runs[bi]
        s = stops[i]
        advance(s, t)
        if i != last and b.skip_lo <= i < b.skip_hi and s.q <= EPS:
            leave(b, i, t)
            continue
        alighted = b.occ * inp.alight_share[i]
        occ_after = b.occ - alighted
        boarded = 0.0 if i == last else min(s.q, max(p.capacity - occ_after, 0.0))
        s.q = max(s.q - boarded, 0.0)
        dwell = max(DWELL_BASE_S, DWELL_BASE_S + DWELL_PER_BOARDED_S * boarded + DWELL_PER_ALIGHTED_S * alighted)
        dep0 = grid(t + dwell)
        if i in b.holds:
            dep0 = max(dep0, grid(t + b.holds[i]))
        dep = dep0
        if action.type == "hold" and b.target and action.stop_idx == i:
            dep = max(dep, grid(t + action.hold_s))
        b.occ = occ_after + boarded
        onboard += b.occ * (dep - dep0)
        key = (b.state.bus_id, i)
        arrivals[key] = t
        if dep <= window + EPS:
            departures[key] = dep
        leave(b, i, dep)

    wait = 0.0
    riders = sum(s.queue for s in inp.stops)
    for s in stops:
        advance(s, window)
        wait += s.integ
        riders += s.arrived
    score = wait + onboard + reserve_cost
    return Projection(tuple(sorted(departures.items())), tuple(sorted(arrivals.items())),
                      wait, onboard, float(reserve_cost), score, riders)


def evaluate(inp: Inputs, actions: list[Action]) -> list[Scored]:
    """Score every action against "do nothing"; best saving first, ties by catalog order, bus, stop."""
    base = project(inp)
    scored = [Scored(a, pr, saving_s_per_rider(base, pr)) for a in actions for pr in (project(inp, a),)]
    scored.sort(key=lambda s: (-s.saving_s, CATALOG_ORDER.get(s.action.type, len(CATALOG_ORDER)),
                               s.action.bus_id, -1 if s.action.stop_idx is None else s.action.stop_idx,
                               s.action.hold_s, s.action.share))
    return scored
