"""Stop headways and their additive sums (005 US3; research R4, R5; data-model E10).

Pure and deterministic: no I/O, no wall clock. The headway between two consecutive departures from one
stop belongs to the **closing** (later) departure, so it is in a window or a band when that departure is.
A headway is excluded when either of its two departures was reported after a gap (`estimated`) and is
counted in `n_excluded`. Seconds are exact: integer microseconds converted to `Decimal`, so rebuilds are
byte-identical.

Turn-1 limit (data owner, 2026-11-21): a departure that was never reported leaves no row, so it is neither
a headway nor an exclusion.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from src.data.rules.timebands import WINDOW, local_date, m2_band

_MICRO = Decimal(10) ** 6
_MICRO_SQ = Decimal(10) ** 12


@dataclass(frozen=True)
class Departure:
    stop_id: str
    bus_id: str
    trip_id: str
    ts: datetime
    estimated: bool = False


@dataclass(frozen=True)
class Interval:
    stop_id: str
    closing_ts: datetime
    headway_s: Decimal
    excluded: bool


@dataclass(frozen=True)
class StopSums:
    n: int
    sum_h: Decimal
    sum_h2: Decimal
    n_excluded: int


ZERO = StopSums(0, Decimal(0), Decimal(0), 0)


def _utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return ts.astimezone(timezone.utc)


def _micros(delta) -> int:
    return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds


def stop_intervals(departures: Iterable[Departure]) -> list[Interval]:
    """Headways between consecutive departures at each stop, ordered by (stop, closing time)."""
    by_stop: dict[str, list[Departure]] = defaultdict(list)
    for d in departures:
        by_stop[d.stop_id].append(d)
    out: list[Interval] = []
    for stop in sorted(by_stop):
        rows = sorted(by_stop[stop], key=lambda d: (_utc(d.ts), d.bus_id, d.trip_id))
        for a, b in zip(rows, rows[1:]):
            out.append(Interval(stop, _utc(b.ts), Decimal(_micros(_utc(b.ts) - _utc(a.ts))) / _MICRO,
                                a.estimated or b.estimated))
    return out


def _sums(intervals: Iterable[Interval]) -> StopSums:
    n, sum_h, sum_h2, excluded = 0, Decimal(0), Decimal(0), 0
    for i in intervals:
        if i.excluded:
            excluded += 1
        else:
            n += 1
            sum_h += i.headway_s
            sum_h2 += i.headway_s * i.headway_s
    return StopSums(n, sum_h, sum_h2, excluded)


def window_sums(departures: Iterable[Departure], lo: datetime, hi: datetime) -> StopSums:
    """Sums over the headways whose closing departure is in `(lo, hi]` (all the stops given)."""
    lo_u, hi_u = _utc(lo), _utc(hi)
    return _sums(i for i in stop_intervals(departures) if lo_u < i.closing_ts <= hi_u)


def window_sums_by_stop(departures: Iterable[Departure], lo: datetime, hi: datetime) -> dict[str, StopSums]:
    """`window_sums` per stop; only stops with at least one candidate headway appear."""
    lo_u, hi_u = _utc(lo), _utc(hi)
    grouped: dict[str, list[Interval]] = defaultdict(list)
    for i in stop_intervals(departures):
        if lo_u < i.closing_ts <= hi_u:
            grouped[i.stop_id].append(i)
    return {stop: _sums(rows) for stop, rows in grouped.items()}


def band_sums(departures: Iterable[Departure], as_of: datetime) -> dict[tuple[date, int, str], StopSums]:
    """Sums per (local date, band 0..95, stop) for the **closed** bands only (band end <= `as_of`).

    A band is a clock-aligned 15-minute local interval; the local offset is a whole number of hours, so it
    coincides with the UTC 15-minute grid. A key exists when the stop has at least one candidate headway
    (counted or excluded) closing in the band; no key means zeros.
    """
    as_of_u = _utc(as_of)
    grouped: dict[tuple[date, int, str], list[Interval]] = defaultdict(list)
    for i in stop_intervals(departures):
        floor = i.closing_ts.replace(minute=i.closing_ts.minute - i.closing_ts.minute % 15, second=0, microsecond=0)
        if floor + WINDOW <= as_of_u:
            grouped[(local_date(i.closing_ts), m2_band(i.closing_ts), i.stop_id)].append(i)
    return {key: _sums(rows) for key, rows in grouped.items()}


def add(a: StopSums, b: StopSums) -> StopSums:
    return StopSums(a.n + b.n, a.sum_h + b.sum_h, a.sum_h2 + b.sum_h2, a.n_excluded + b.n_excluded)
