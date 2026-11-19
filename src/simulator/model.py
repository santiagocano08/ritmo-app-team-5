"""Simulator model (T021): fleet, reference data, travel time, dwell, FIFO boarding.

Pure functions and dataclasses; no I/O except `load_reference`. All randomness
comes from a `random.Random` passed in by the engine.
"""
from __future__ import annotations

import bisect
import csv
import random
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parents[2] / "data" / "reference"

CAPACITY = 40
STEP_S = 5
IN_SERVICE = ("B-101", "B-102", "B-103", "B-104", "B-105")
RESERVE = ("B-106", "B-107")  # not dispatched in turn 1
OPERATOR = "OP-01"
SOURCE = "simulator"
SIGMA = 0.20  # lognormal travel-time noise (mean-preserving)
WALK_MIN_S, WALK_MAX_S = 60, 180  # train -> stop walk
# ASSUMPTION (declared in data/reference/SOURCES.md): share of direction-1 daily
# riders who arrive at Prado by Metro train (batches); the rest are street riders
# at the other stops. The daily volume itself is derived in demand_volume.csv.
TRAIN_SHARE = 0.80


@dataclass(frozen=True)
class Segment:
    segment_id: int
    length_m: float
    free_flow_kmh: float


@dataclass(frozen=True)
class Stop:
    stop_id: str
    distance_m: float


@dataclass
class Rider:
    dest_idx: int
    ts: int  # arrival second (sim clock)
    origin: str = "street"
    train_trip_id: str | None = None


@dataclass
class Reference:
    segments: list[Segment]
    stops: list[Stop]
    train_secs: list[tuple[int, str]]  # (second of day, train_trip_id), sorted
    congestion: dict[int, float]
    shape: dict[int, float]
    feeder_share: float
    daily_riders_dir1: float = 0.0
    trains_per_hour: dict[int, int] = field(default_factory=dict)


def _rows(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_reference(directory: Path = REFERENCE_DIR) -> Reference:
    segments = [
        Segment(int(r["segment_id"]), float(r["length_m"]), float(r["free_flow_kmh"]))
        for r in _rows(directory / "segments.csv")
    ]
    stops = [Stop(r["stop_id"], float(r["distance_along_m"])) for r in _rows(directory / "stops.csv")]
    trains = []
    for r in _rows(directory / "train_arrivals.csv"):
        h, m, s = (int(x) for x in r["arrival_time"].split(":"))
        sec = h * 3600 + m * 60 + s
        if sec < 86400:
            trains.append((sec, r["train_trip_id"]))
    trains.sort()
    demand = _rows(directory / "demand_params.csv")
    volume = _rows(directory / "demand_volume.csv")
    per_hour: dict[int, int] = {}
    for sec, _ in trains:
        per_hour[sec // 3600] = per_hour.get(sec // 3600, 0) + 1
    return Reference(
        segments=segments,
        stops=stops,
        train_secs=trains,
        congestion={int(r["hour"]): float(r["congestion_factor"]) for r in _rows(directory / "congestion_factor.csv")},
        shape={int(r["hour"]): float(r["metro_line_a_shape"]) for r in demand},
        feeder_share=float(demand[0]["feeder_share_basin6"]),
        daily_riders_dir1=float(volume[0]["daily_riders_dir1"]),
        trains_per_hour=per_hour,
    )


def segment_time_s(length_m: float, free_flow_kmh: float, factor: float, rng: random.Random) -> float:
    """length / (free_flow_speed x congestion_factor) x lognormal noise."""
    noise = rng.lognormvariate(-SIGMA * SIGMA / 2, SIGMA)
    return length_m / (free_flow_kmh / 3.6 * factor) * noise


def dwell_s(boarded: int, alighted: int) -> int:
    return max(10, 10 + 3 * boarded + 2 * alighted)


def board_fifo(queue: deque[Rider], free: int) -> tuple[list[Rider], int]:
    """Board up to `free` riders in arrival order. Returns (boarded, rejected).

    `rejected` is the number left behind; they stay queued, in order.
    """
    boarded = [queue.popleft() for _ in range(min(max(free, 0), len(queue)))]
    return boarded, len(queue)


@dataclass
class Profile:
    """Piecewise-linear drive-time profile of one trip: (distance_m, time_s, speed_kmh)."""

    dists: list[float]
    times: list[float]
    speeds: list[float]

    def time_at(self, dist: float) -> float:
        i = min(max(bisect.bisect_left(self.dists, dist), 1), len(self.dists) - 1)
        d0, d1, t0, t1 = self.dists[i - 1], self.dists[i], self.times[i - 1], self.times[i]
        return t0 + (t1 - t0) * (dist - d0) / (d1 - d0)

    def pos_at(self, t: float) -> tuple[float, float]:
        i = min(max(bisect.bisect_left(self.times, t), 1), len(self.times) - 1)
        d0, d1, t0, t1 = self.dists[i - 1], self.dists[i], self.times[i - 1], self.times[i]
        frac = min(max((t - t0) / (t1 - t0), 0.0), 1.0)
        return d0 + (d1 - d0) * frac, self.speeds[i - 1]


def build_profile(ref: Reference, factor: float, rng: random.Random) -> Profile:
    """Draw per-segment travel times (fixed order) and build the trip profile."""
    last_stop_d = ref.stops[-1].distance_m
    total = sum(s.length_m for s in ref.segments)
    dists, times, speeds = [0.0], [0.0], []
    for k, seg in enumerate(ref.segments):
        length = seg.length_m
        if k == len(ref.segments) - 1 and last_stop_d > total:
            length += last_stop_d - total  # last stop lies slightly past the segment end
        t = segment_time_s(length, seg.free_flow_kmh, factor, rng)
        dists.append(dists[-1] + length)
        times.append(times[-1] + t)
        speeds.append(min(length / t * 3.6, 120.0))
    return Profile(dists, times, speeds)
