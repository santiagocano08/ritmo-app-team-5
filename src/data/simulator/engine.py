"""Deterministic event engine (T022): `run(seed, duration)` yields envelope dicts.

No DB, no I/O, no wall clock. A single `random.Random(seed)` drives everything
(event ids, travel-time noise, rider arrivals, destinations) in a fixed call order.
"""
from __future__ import annotations

import bisect
import heapq
import random
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Iterator

from src.pulsoflota.config import get_sim_planned_headway_s
from src.data.simulator.model import (
    CAPACITY,
    IN_SERVICE,
    OPERATOR,
    SOURCE,
    STEP_S,
    TRAIN_SHARE,
    WALK_MAX_S,
    WALK_MIN_S,
    Profile,
    Reference,
    Rider,
    board_fifo,
    build_profile,
    dwell_s,
    load_reference,
)

LOCAL_TZ = timezone(timedelta(hours=-5))  # Medellin; reference hours are local
SIM_DATE = (2026, 11, 24)


@dataclass
class Bus:
    bus_id: str
    start_at: int
    first_start: int = 0  # scheduled start of trip 1; later trips follow `cycle` (R14)
    trip_n: int = 1
    phase: str = "waiting"  # waiting | dwell | driving | layover
    phase_end: int = 0
    drive_t: float = 0.0
    next_idx: int = 0
    idx: int = 0  # index of the stop the bus is at (or last served)
    profile: Profile | None = None
    load: list[Rider] = field(default_factory=list)
    pending: tuple[int, int, int, int] = (0, 0, 0, 0)  # boarded, alighted, rejected, occupancy_in

    @property
    def trip_id(self) -> str:
        return f"C6-008-{self.bus_id}-{self.trip_n:03d}"


def run(seed: int, duration: int, start_hour: int = 17, demand_scale: float = 1.0,
        ref: Reference | None = None) -> Iterator[dict]:
    ref = ref or load_reference()
    rng = random.Random(seed)
    base = datetime(*SIM_DATE, start_hour, tzinfo=LOCAL_TZ)
    start_s = start_hour * 3600
    last = len(ref.stops) - 1
    # R14: buses start one planned headway apart; each bus is re-dispatched from P-883
    # every `cycle` seconds (the terminal layover stands in for the unsimulated return leg).
    planned_s = get_sim_planned_headway_s()
    cycle = len(IN_SERVICE) * planned_s
    buses = [Bus(b, i * planned_s, first_start=i * planned_s) for i, b in enumerate(IN_SERVICE)]
    queues = [deque() for _ in ref.stops]
    train_times = [s for s, _ in ref.train_secs]
    pend: list[tuple[int, int, int, Rider]] = []  # heap of (ts, seq, stop_idx, rider)
    seq = 0
    n_street = max(last - 1, 1)

    def env(etype: str, ts: int, payload: dict) -> dict:
        eid = str(uuid.UUID(int=rng.getrandbits(128), version=4))
        when = (base + timedelta(seconds=ts)).astimezone(timezone.utc)
        return {
            "schema_version": "1.0.0",
            "event_id": eid,
            "event_type": etype,
            "source": SOURCE,
            "event_ts": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "payload": payload,
        }

    def hour_of(t: int) -> int:
        return ((start_s + t) // 3600) % 24

    def start_trip(bus: Bus, t: int) -> None:
        bus.profile = build_profile(ref, ref.congestion[hour_of(t)], rng)
        bus.idx, bus.next_idx, bus.drive_t, bus.load = 0, 0, 0.0, []

    for b in buses:
        start_trip(b, 0)

    for t in range(0, duration, STEP_S):
        hour = hour_of(t)
        cur_s = start_s + t
        out: list[dict] = []

        # 1. Metro trains reaching Prado in (cur_s - STEP, cur_s] -> batch + walk
        lo = bisect.bisect_right(train_times, cur_s - STEP_S)
        hi = bisect.bisect_right(train_times, cur_s)
        for k in range(lo, hi):
            sec, trip = ref.train_secs[k]
            h = sec // 3600
            mean = (ref.daily_riders_dir1 * TRAIN_SHARE * ref.shape[h] * demand_scale
                    / max(ref.trains_per_hour.get(h, 1), 1))
            for _ in range(int(mean * rng.uniform(0.7, 1.3) + 0.5)):
                walk = rng.randint(WALK_MIN_S, WALK_MAX_S)
                dest = rng.randint(1, last)
                seq += 1
                heapq.heappush(pend, (sec - start_s + walk, seq, 0, Rider(dest, sec - start_s + walk, "train", trip)))

        # 2. Street drip at the non-Prado, non-terminal stops
        rate = (ref.daily_riders_dir1 * (1 - TRAIN_SHARE) * ref.shape[hour] * demand_scale / n_street)
        p = rate * STEP_S / 3600.0
        for i in range(1, last):
            if rng.random() < p:
                seq += 1
                heapq.heappush(pend, (t, seq, i, Rider(rng.randint(i + 1, last), t, "street")))

        # 3. Release riders whose time has come
        while pend and pend[0][0] <= t:
            ts, _, stop_i, r = heapq.heappop(pend)
            queues[stop_i].append(r)
            payload = {"stop_id": ref.stops[stop_i].stop_id, "direction": 1, "origin": r.origin,
                       "destination_stop_id": ref.stops[r.dest_idx].stop_id}
            if r.train_trip_id:
                payload["train_trip_id"] = r.train_trip_id
            out.append(env("rider_arrival", ts, payload))

        # 4. Buses
        for b in buses:
            if b.phase == "driving":
                b.drive_t += STEP_S
                target = b.profile.time_at(ref.stops[b.next_idx].distance_m)
                if b.drive_t >= target:
                    b.drive_t, b.idx = target, b.next_idx
                    _arrive(b, t, ref, queues, last, out, env)
            if b.phase == "layover" and t >= b.phase_end:
                b.trip_n += 1
                start_trip(b, t)
                b.phase, b.start_at = "waiting", t
            if b.phase == "waiting" and t >= b.start_at:
                _arrive(b, t, ref, queues, last, out, env)
            elif b.phase == "dwell" and t >= b.phase_end:
                boarded, alighted, rejected, occ_in = b.pending
                out.append(env("stop_departure", t, _stop_payload(b, ref, boarded, alighted, rejected, len(b.load))))
                if b.idx == last:
                    # R14: next trip leaves P-883 at its scheduled time, or now if already late
                    b.phase, b.phase_end = "layover", max(t, b.first_start + b.trip_n * cycle)
                else:
                    b.phase, b.next_idx = "driving", b.idx + 1
            out.append(env("bus_position", t, _position_payload(b, ref)))

        yield from out


def _stop_payload(b: Bus, ref: Reference, boarded: int, alighted: int, rejected: int, occupancy: int) -> dict:
    return {"bus_id": b.bus_id, "trip_id": b.trip_id, "stop_id": ref.stops[b.idx].stop_id,
            "boarded": boarded, "alighted": alighted, "rejected": rejected, "occupancy": occupancy}


def _arrive(b: Bus, t: int, ref: Reference, queues: list[deque], last: int, out: list[dict], env) -> None:
    occ_in = len(b.load)
    staying = [r for r in b.load if b.idx != last and r.dest_idx != b.idx]
    alighted = occ_in - len(staying)
    b.load = staying
    if b.idx == last:
        boarded, rejected = [], 0
    else:
        boarded, rejected = board_fifo(queues[b.idx], CAPACITY - len(b.load))
        b.load = b.load + boarded
    nb = len(boarded)
    out.append(env("stop_arrival", t, _stop_payload(b, ref, nb, alighted, rejected, occ_in)))
    b.pending = (nb, alighted, rejected, occ_in)
    b.phase, b.phase_end = "dwell", t + dwell_s(nb, alighted)


def _position_payload(b: Bus, ref: Reference) -> dict:
    if b.phase == "driving":
        dist, speed = b.profile.pos_at(b.drive_t)
    else:
        dist, speed = ref.stops[b.idx].distance_m, 0.0
    return {"bus_id": b.bus_id, "operator": OPERATOR, "trip_id": b.trip_id, "direction": 1,
            "distance_along_m": round(float(dist), 1), "speed_kmh": round(float(speed), 1),
            "schedule_deviation_s": 0, "doors_open": b.phase == "dwell", "occupancy": len(b.load)}
