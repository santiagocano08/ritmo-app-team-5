"""T035 — bus state, FR-011 suppression, summary and source status (FR-011, FR-018-FR-023)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.data.rules.classify import classify_buses, corridor_status, summarize
from src.data.rules.headway import BusObs, Headway, order_buses

T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
PLANNED = 600


def obs(bus_id: str, distance: float, estimated: bool = False, broken_down: bool = False) -> BusObs:
    return BusObs(bus_id=bus_id, distance_along_m=distance, position_ts=T0, history=(),
                  estimated=estimated, broken_down=broken_down)


def states(buses: list[BusObs], headways: dict[str, tuple[float | None, str | None]],
           planned: float = PLANNED) -> dict[str, str]:
    h = {k: Headway(seconds=v[0], ahead_bus_id=v[1]) for k, v in headways.items()}
    return classify_buses(order_buses(buses), h, planned)


def chain(*items) -> tuple[list[BusObs], dict]:
    """Buses from the leader back; each item is (bus_id, headway_to_bus_ahead, flags dict)."""
    buses, headways, prev = [], {}, None
    for i, (bus_id, h, flags) in enumerate(items):
        buses.append(obs(bus_id, 1000 - i * 100, **flags))
        headways[bus_id] = (h, prev)
        prev = None if flags.get("broken_down") else bus_id
    return buses, headways


def test_state_order_and_boundaries() -> None:
    buses, h = chain(("B-105", None, {}), ("B-104", 299.9, {}), ("B-103", 300, {}),
                     ("B-102", 900, {}), ("B-101", 900.1, {}))
    h["B-103"] = (300, "B-104"); h["B-102"] = (900, "B-103"); h["B-101"] = (900.1, "B-102")
    assert states(buses, h) == {"B-105": "leader", "B-104": "bunched", "B-103": "regular",
                                "B-102": "regular", "B-101": "gap"}


def test_broken_down_wins_over_everything_and_keeps_no_headway() -> None:
    buses, h = chain(("B-105", None, {}), ("B-104", None, {"broken_down": True}), ("B-103", 1500, {}))
    h["B-103"] = (1500, "B-105")
    assert states(buses, h) == {"B-105": "leader", "B-104": "broken_down", "B-103": "gap"}


def test_planned_headway_is_a_parameter() -> None:
    buses, h = chain(("B-105", None, {}), ("B-104", 400, {}))
    assert states(buses, h, planned=600)["B-104"] == "regular"
    assert states(buses, h, planned=1000)["B-104"] == "bunched"  # 400 < 500
    assert states(buses, h, planned=200)["B-104"] == "gap"       # 400 > 300


def test_estimated_bus_and_the_bus_behind_it_are_regular_but_keep_their_values() -> None:
    buses, h = chain(("B-105", None, {}), ("B-104", 100, {"estimated": True}), ("B-103", 1000, {}),
                     ("B-102", 100, {}))
    s = states(buses, h)
    assert s == {"B-105": "leader", "B-104": "regular", "B-103": "regular", "B-102": "bunched"}
    assert h["B-104"][0] == 100  # the headway value is not touched by classification


def test_two_consecutive_estimated_buses_suppress_three_buses() -> None:
    buses, h = chain(("B-105", None, {}), ("B-104", 100, {"estimated": True}),
                     ("B-103", 100, {"estimated": True}), ("B-102", 1200, {}), ("B-101", 100, {}))
    s = states(buses, h)
    assert [s[b] for b in ("B-104", "B-103", "B-102")] == ["regular"] * 3
    assert s["B-101"] == "bunched"


def test_estimated_leader_keeps_leader_and_bus_behind_is_regular() -> None:
    buses, h = chain(("B-105", None, {"estimated": True}), ("B-104", 100, {}))
    assert states(buses, h) == {"B-105": "leader", "B-104": "regular"}


def test_all_buses_silent_gives_no_bunched_or_gap() -> None:
    est = {"estimated": True}
    buses, h = chain(("B-105", None, est), ("B-104", 100, est), ("B-103", 2000, est))
    s = states(buses, h)
    assert s == {"B-105": "leader", "B-104": "regular", "B-103": "regular"}
    assert summarize(s) == (3, 0, 0)


def test_equal_distance_is_zero_headway_and_bunched_with_the_tie_broken_by_bus_id() -> None:
    buses = [obs("B-102", 500), obs("B-101", 500)]
    s = states(buses, {"B-101": (None, None), "B-102": (0.0, "B-101")})
    assert s == {"B-101": "leader", "B-102": "bunched"}


def test_single_operational_bus_is_the_leader() -> None:
    assert states([obs("B-101", 5)], {"B-101": (None, None)}) == {"B-101": "leader"}


def test_summary_counts_exclude_broken_down_from_service() -> None:
    s = {"B-105": "leader", "B-104": "broken_down", "B-103": "bunched", "B-102": "gap", "B-101": "gap"}
    assert summarize(s) == (4, 1, 2)
    assert summarize({}) == (0, 0, 0)


@pytest.mark.parametrize("has_reports,n_estimated,expected", [
    (False, 0, "no_data"), (True, 0, "live"), (True, 1, "estimated"), (True, 5, "estimated"),
])
def test_corridor_status(has_reports: bool, n_estimated: int, expected: str) -> None:
    assert corridor_status(has_reports, n_estimated) == expected
