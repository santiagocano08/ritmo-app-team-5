"""P(board <= t) counts, simple method (005 US4; data-model E7; FR-040 to FR-042, FR-045).

Pure and deterministic: no I/O, no wall clock. A rider at a stop waits for the next departure of **any** bus
from that stop with `arrival <= departure <= as_of`. A departure at the arrival second counts (wait 0). No
capacity, no FIFO, no rejections: that is the evolution. A rider counts in `n_riders` always, and in
`n_le_t` only when a departure exists and the wait is at most `t`; a rider still waiting stays in `n_riders`
only and moves into the columns when a later cycle sees the departure. The counts belong to the band of the
rider's **arrival**, so they are additive over stops, bands and days.

`departures_by_stop` lists the stops that count (the reference stops); a rider at any other stop counts nowhere.
"""
from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from src.data.rules.timebands import local_date, m2_band

BOARDING_THRESHOLDS_S = (300, 600, 900)

_MICRO = Decimal(10) ** 6


@dataclass(frozen=True)
class BoardCounts:
    n_riders: int
    n_le_5: int
    n_le_10: int
    n_le_15: int


def local_band(ts: datetime) -> tuple[date, int]:
    """(local date, 15-minute band 0..95) of an instant."""
    return local_date(ts), m2_band(ts)


def wait_s(arrival: datetime, departures_sorted: Sequence[datetime], as_of: datetime) -> Decimal | None:
    """Exact seconds to the first departure at or after `arrival` and not after `as_of`; None when there is none."""
    i = bisect_left(departures_sorted, arrival)
    if i == len(departures_sorted) or departures_sorted[i] > as_of:
        return None
    delta = departures_sorted[i] - arrival
    return (Decimal((delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds) / _MICRO)


def count_riders(arrivals: Iterable[tuple[str, datetime]], departures_by_stop: Mapping[str, Sequence[datetime]],
                 as_of: datetime,
                 band_fn: Callable[[datetime], tuple[date, int]] = local_band
                 ) -> dict[tuple[date, int, str], BoardCounts]:
    """Counts per (local date, band of the arrival, stop) for riders who arrived at or before `as_of`."""
    t5, t10, t15 = BOARDING_THRESHOLDS_S
    acc: dict[tuple[date, int, str], list[int]] = {}
    for stop, arrived in arrivals:
        if stop not in departures_by_stop or arrived > as_of:
            continue
        day, band = band_fn(arrived)
        row = acc.setdefault((day, band, stop), [0, 0, 0, 0])
        row[0] += 1
        wait = wait_s(arrived, departures_by_stop[stop], as_of)
        if wait is not None:
            row[1] += wait <= t5
            row[2] += wait <= t10
            row[3] += wait <= t15
    return {k: BoardCounts(*v) for k, v in acc.items()}
