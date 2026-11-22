"""Builders for crafted projector inputs (006 phase 1, test support).

Crafted corridors have 4 stops (indices 0..3, last = 3), 1,000 m apart, a flat M1 time per segment
and no riders unless a test asks for them, so every expected value can be computed on paper.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from src.data.rules.mpc_params import MpcParams
from src.data.rules.projector import BusState, Inputs, StopState

# 22:00 UTC is 17:00 local (UTC-5).
AS_OF_1700 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
AS_OF_1755 = datetime(2026, 11, 24, 22, 55, 0, tzinfo=timezone.utc)

NO_RATE = (0.0,) * 24


def rate(per_hour: float) -> tuple[float, ...]:
    """The same arrival rate (riders per hour) in all 24 local hours."""
    return (float(per_hour),) * 24


def stops(n: int = 4, queues: dict[int, float] | None = None, rates: dict[int, tuple[float, ...]] | None = None,
          batches: dict[int, tuple[tuple[float, float], ...]] | None = None) -> tuple[StopState, ...]:
    queues, rates, batches = queues or {}, rates or {}, batches or {}
    return tuple(
        StopState(stop_id=f"S-{i}", distance_m=1000.0 * i, queue=float(queues.get(i, 0.0)),
                  rate_by_hour=rates.get(i, NO_RATE), train_batches=batches.get(i, ()))
        for i in range(n)
    )


def m1_flat(seconds: float = 100.0, n_segments: int = 3, per_hour: dict[int, float] | None = None):
    """M1 table: `m1[hour][segment]`; `per_hour` overrides the flat value for some hours."""
    per_hour = per_hour or {}
    return tuple((float(per_hour.get(h, seconds)),) * n_segments for h in range(24))


def alight(n: int = 4, shares: dict[int, float] | None = None) -> tuple[float, ...]:
    """No one alights before the last stop (share 1.0) unless `shares` says otherwise."""
    shares = shares or {}
    return tuple(1.0 if i == n - 1 else float(shares.get(i, 0.0)) for i in range(n))


def bus(bus_id: str = "B-101", **kw) -> BusState:
    return BusState(bus_id=bus_id, **kw)


def inputs(buses, *, n: int = 4, queues=None, rates=None, batches=None, m1=None, shares=None,
           next_departures=(), as_of=AS_OF_1700, params: MpcParams | None = None, trend=None) -> Inputs:
    return Inputs(
        as_of=as_of,
        buses=tuple(buses),
        stops=stops(n, queues, rates, batches),
        m1=m1 if m1 is not None else m1_flat(n_segments=n - 1),
        trend=trend if trend is not None else (1.0,) * (n - 1),
        alight_share=alight(n, shares),
        next_departures=tuple(next_departures),
        params=params or MpcParams(),
    )


def with_params(**kw) -> MpcParams:
    return replace(MpcParams(), **kw)


def facts(states: dict[str, str] | None = None, *, drivers: int = 2, n: int = 4, enabled=None, down=(),
          quality: str = "live", snapshot_id: str = "00000000-0000-4000-8000-000000000001"):
    """`mpc.Facts` of a crafted snapshot: `states` maps bus id to its corridor_now `bus_state`."""
    from src.data.rules.mpc import Facts

    return Facts(snapshot_id=snapshot_id, rules_version="1.6.0",
                 bus_states=tuple(sorted((states or {}).items())), drivers_free=drivers,
                 enabled_stops=frozenset(range(n) if enabled is None else enabled),
                 sources_down=frozenset(down), data_quality=quality)
