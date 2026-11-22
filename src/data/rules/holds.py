"""Hold rules shared by the simulator and data (004 FR-012 to FR-016, SC-007; research R4.3, R5).

Pure functions of their arguments: no I/O, no clock. One definition of the cap, the tolerance, the
visit matching and the observation, like `ESTIMATED_AFTER_S`. The simulator applies the matching in the
engine; the pipeline applies it to `silver.stop_visits` to report `executed` or `not_executed`.

Order of the rules for one order (orders are processed in bronze id order):

1. A hold above `MAX_HOLD_S` is refused: `not_executed` at `expires_ts`, at once, and it takes no visit.
2. The order matches the first visit of its bus at its stop whose arrival is strictly after the decision
   and not after `expires_ts`.
3. A breakdown of the bus that starts after the decision and before that visit (or, with no visit yet,
   at any time) wins: `not_executed` at the breakdown start, and the order takes no visit.
4. A visit already taken by an earlier order is a conflict: `not_executed` at the arrival.
5. A visit with a departure is observed: `executed` when the dwell is within `EXECUTED_TOLERANCE_S` of
   the hold, else `not_executed`, both at the departure. A visit still at the stop is pending.
6. No visit: pending while the window is open, `not_executed` at `expires_ts` once the reference time is
   past it.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MAX_HOLD_S = 90  # ADR-0003 gate decision 8: a hold is 0 to 90 s
EXECUTED_TOLERANCE_S = 15  # ADR-0003, instruction schema: dwell within +-15 s of the instructed hold

HOLD_ORDERS_SQL = Path(__file__).resolve().parent / "sql" / "hold_orders.sql"


@dataclass(frozen=True)
class Visit:
    """A stop visit: `departure_ts` is None while the bus is still at the stop."""
    arrival_ts: datetime
    departure_ts: datetime | None


@dataclass(frozen=True)
class Order:
    rec_id: str
    bus_id: str
    stop_id: str
    hold_s: float
    decided_at: datetime | None  # None: the decision precedes every bus report
    expires_ts: datetime


@dataclass(frozen=True)
class Outcome:
    rec_id: str
    status: str  # executed | not_executed
    ts: datetime
    observed_dwell_s: float | None
    reason: str  # observed | over_cap | breakdown | conflict | expired


def hold_in_range(hold_s: float) -> bool:
    return 0 <= hold_s <= MAX_HOLD_S


def visit_matches(arrival_ts: datetime, decided_at: datetime | None, expires_ts: datetime) -> bool:
    """Strictly after the decision (a decision that comes after the arrival cannot hold that visit)."""
    return (decided_at is None or arrival_ts > decided_at) and arrival_ts <= expires_ts


def match_visit(visits: Sequence[Visit], decided_at: datetime | None, expires_ts: datetime) -> Visit | None:
    matching = [v for v in visits if visit_matches(v.arrival_ts, decided_at, expires_ts)]
    return min(matching, key=lambda v: v.arrival_ts) if matching else None


def observe(orders: Sequence[Order], visits: Mapping[tuple[str, str], Sequence[Visit]],
            breakdowns: Mapping[str, Sequence[datetime]], reference_ts: datetime) -> list[Outcome]:
    """One `Outcome` per order that has a status; pending orders are left out.

    `orders` must be in bronze id order. `visits` maps (bus_id, stop_id) to every visit seen, including
    a visit that has not departed. `breakdowns` maps a bus to the start times of its breakdowns.
    """
    taken: set[tuple[str, str, datetime]] = set()
    out: list[Outcome] = []
    for o in orders:
        if not hold_in_range(o.hold_s):
            out.append(Outcome(o.rec_id, "not_executed", o.expires_ts, None, "over_cap"))
            continue
        visit = match_visit(visits.get((o.bus_id, o.stop_id), ()), o.decided_at, o.expires_ts)
        broke = [b for b in breakdowns.get(o.bus_id, ())
                 if (o.decided_at is None or b > o.decided_at) and (visit is None or b < visit.arrival_ts)]
        if broke:
            out.append(Outcome(o.rec_id, "not_executed", min(broke), None, "breakdown"))
            continue
        if visit is None:
            if reference_ts > o.expires_ts:
                out.append(Outcome(o.rec_id, "not_executed", o.expires_ts, None, "expired"))
            continue
        key = (o.bus_id, o.stop_id, visit.arrival_ts)
        if key in taken:
            out.append(Outcome(o.rec_id, "not_executed", visit.arrival_ts, None, "conflict"))
            continue
        taken.add(key)
        if visit.departure_ts is None:
            continue  # the bus is still at the stop: pending
        dwell = (visit.departure_ts - visit.arrival_ts).total_seconds()
        status = "executed" if abs(dwell - o.hold_s) <= EXECUTED_TOLERANCE_S else "not_executed"
        out.append(Outcome(o.rec_id, status, visit.departure_ts, dwell, "observed"))
    return out
