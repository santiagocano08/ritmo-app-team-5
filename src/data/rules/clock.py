"""Clock guard (feature 005, US6, FR-060 to FR-064; contracts/guards.md G3). Pure: no I/O, no wall clock.

A bus whose newest report (by arrival) is more than `limit_s` ahead of the `median_low` of the other
buses' newest reports is untrusted; the cycle clock is the newest report among trusted buses. With fewer
than `MIN_BUSES_FOR_CLOCK_GUARD` buses there is no reference, so nobody is untrusted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Mapping

MIN_BUSES_FOR_CLOCK_GUARD = 2


@dataclass(frozen=True)
class ClockDecision:
    as_of: datetime | None
    untrusted: frozenset[str]


def _median_low(values: list[datetime]) -> datetime:
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) // 2]


def trusted_clock(latest_by_bus: Mapping[str, datetime], limit_s: float) -> ClockDecision:
    """Decide the cycle clock from each bus's newest report time (`event_ts`)."""
    if not latest_by_bus:
        return ClockDecision(None, frozenset())
    if len(latest_by_bus) < MIN_BUSES_FOR_CLOCK_GUARD:
        return ClockDecision(max(latest_by_bus.values()), frozenset())
    limit = timedelta(seconds=limit_s)
    untrusted = set()
    for bus, ts in latest_by_bus.items():
        others = [v for b, v in latest_by_bus.items() if b != bus]
        if ts > _median_low(others) + limit:
            untrusted.add(bus)
    trusted = [ts for bus, ts in latest_by_bus.items() if bus not in untrusted]
    # median_low of the others is always an actual report, so at least one bus stays trusted
    return ClockDecision(max(trusted), frozenset(untrusted))
