"""Time headway between consecutive buses (FR-020, research R8, ADR-0003 gate decisions 1-2).

Pure functions, no I/O. Input is what silver holds about each bus on the corridor.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

# (event_ts, distance_along_m) samples of one bus on its current trip, oldest first.
History = Sequence[tuple[datetime, float]]


@dataclass(frozen=True)
class BusObs:
    """One bus on the corridor at the reference time."""

    bus_id: str
    distance_along_m: float
    position_ts: datetime
    history: tuple[tuple[datetime, float], ...]
    estimated: bool = False
    broken_down: bool = False


@dataclass(frozen=True)
class Headway:
    """`seconds` is None for the leader and for a broken-down bus; `ahead_bus_id` names the
    operational bus the value was measured against (None when there is none)."""

    seconds: float | None
    ahead_bus_id: str | None


def order_buses(buses: Sequence[BusObs]) -> list[BusObs]:
    """Leader first: distance descending, ties by bus id ascending (FR-019)."""
    return sorted(buses, key=lambda b: (-b.distance_along_m, b.bus_id))


def pass_time(history: History, distance_m: float) -> datetime | None:
    """Moment the bus first reached `distance_m`, interpolated linearly between samples.

    The first sample at or past the distance gives the time; when it is the first sample of
    the trip its own time is used. None when no sample reaches the distance.
    """
    previous: tuple[datetime, float] | None = None
    for ts, dist in history:
        if dist >= distance_m:
            if previous is None or dist == previous[1]:
                return ts
            fraction = (distance_m - previous[1]) / (dist - previous[1])
            return previous[0] + (ts - previous[0]) * fraction
        previous = (ts, dist)
    return None


def headway_s(follower_distance_m: float, follower_ts: datetime, ahead_distance_m: float,
              ahead_history: History, ahead_ts: datetime | None = None) -> float:
    """Seconds between the bus ahead passing the follower's distance and the follower's position time.

    Equal distances give exactly 0; a negative difference (stale follower) is clamped to 0
    (R8, decided). Without usable history the bus ahead's own position time is used.
    """
    if follower_distance_m == ahead_distance_m:
        return 0.0
    passed = pass_time(ahead_history, follower_distance_m) or ahead_ts
    if passed is None:
        return 0.0
    seconds = (follower_ts - passed) / timedelta(seconds=1)
    return round(max(0.0, seconds), 3)


def compute_headways(ordered: Sequence[BusObs]) -> dict[str, Headway]:
    """Headway of every bus in `ordered` (leader first) to the nearest operational bus ahead."""
    result: dict[str, Headway] = {}
    nearest_ahead: BusObs | None = None
    for bus in ordered:
        if bus.broken_down:
            result[bus.bus_id] = Headway(None, None)
            continue
        if nearest_ahead is None:
            result[bus.bus_id] = Headway(None, None)
        else:
            seconds = headway_s(bus.distance_along_m, bus.position_ts, nearest_ahead.distance_along_m,
                                nearest_ahead.history, nearest_ahead.position_ts)
            result[bus.bus_id] = Headway(seconds, nearest_ahead.bus_id)
        nearest_ahead = bus
    return result
