"""Bus state, summary counts and corridor status (FR-011, FR-018, FR-019, FR-021-FR-023).

Pure functions. The planned headway is always an argument (it comes from `config`).
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from src.data.rules.headway import BusObs, Headway

# FR-022 / corridor_now schema: bunched below 0.5 x planned, gap above 1.5 x planned.
BUNCHED_BELOW = 0.5
GAP_ABOVE = 1.5


def classify_buses(ordered: Sequence[BusObs], headways: Mapping[str, Headway],
                   planned_s: float) -> dict[str, str]:
    """`bus_state` of each bus. Order: broken_down, leader, bunched, gap, regular.

    FR-011: an Estimated bus and the bus measured against it are `regular` instead of
    `bunched` or `gap`; `leader` and `broken_down` are unchanged.
    """
    estimated = {b.bus_id for b in ordered if b.estimated}
    states: dict[str, str] = {}
    for bus in ordered:
        hw = headways[bus.bus_id]
        if bus.broken_down:
            states[bus.bus_id] = "broken_down"
        elif hw.seconds is None:
            states[bus.bus_id] = "leader"
        elif bus.bus_id in estimated or hw.ahead_bus_id in estimated:
            states[bus.bus_id] = "regular"
        elif hw.seconds < BUNCHED_BELOW * planned_s:
            states[bus.bus_id] = "bunched"
        elif hw.seconds > GAP_ABOVE * planned_s:
            states[bus.bus_id] = "gap"
        else:
            states[bus.bus_id] = "regular"
    return states


def summarize(states: Mapping[str, str]) -> tuple[int, int, int]:
    """(buses_in_service, n_bunched, n_gaps) (FR-023)."""
    values = list(states.values())
    return (sum(1 for s in values if s != "broken_down"),
            sum(1 for s in values if s == "bunched"),
            sum(1 for s in values if s == "gap"))


def corridor_status(has_reports: bool, n_estimated: int) -> str:
    """Overall `source_status.status` (FR-018)."""
    if not has_reports:
        return "no_data"
    return "estimated" if n_estimated > 0 else "live"
