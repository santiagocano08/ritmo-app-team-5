"""T047 (US6, FR-060, FR-062 to FR-064): the clock guard rule. Pure, no database, no wall clock."""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

from src.data.rules import ESTIMATED_AFTER_S, clock
from src.data.rules.clock import MIN_BUSES_FOR_CLOCK_GUARD, ClockDecision, trusted_clock

T0 = datetime(2026, 11, 24, 22, 40, 0, tzinfo=timezone.utc)


def at(s: float) -> datetime:
    return T0 + timedelta(seconds=s)


def run(latest: dict[str, float]) -> ClockDecision:
    return trusted_clock({b: at(s) for b, s in latest.items()}, ESTIMATED_AFTER_S)


def test_constants_are_named_and_the_limit_is_the_single_120_s() -> None:
    assert MIN_BUSES_FOR_CLOCK_GUARD == 2
    assert ESTIMATED_AFTER_S == 120


def test_no_bus_gives_no_data_clock() -> None:
    assert run({}) == ClockDecision(None, frozenset())


def test_one_bus_uses_its_own_latest_report_and_nobody_is_untrusted() -> None:
    far = run({"B-101": 10_000_000})
    assert far.as_of == at(10_000_000) and far.untrusted == frozenset()


def test_two_buses_the_one_ahead_by_more_than_the_limit_is_untrusted() -> None:
    d = run({"B-101": 0, "B-102": 500})
    assert d.untrusted == frozenset({"B-102"}) and d.as_of == at(0)


def test_two_buses_far_apart_in_the_past_direction_trust_the_newer_one() -> None:
    # the bus behind is never untrusted: only the one ahead of the others is suspect
    d = run({"B-101": 0, "B-102": 100})
    assert d.untrusted == frozenset() and d.as_of == at(100)


def test_three_buses_one_outlier_cannot_move_the_reference() -> None:
    d = run({"B-101": 0, "B-102": 3, "B-103": 10_000_000_000})
    assert d.untrusted == frozenset({"B-103"}) and d.as_of == at(3)


def test_five_buses_one_outlier() -> None:
    d = run({"B-101": 0, "B-102": 2, "B-103": 4, "B-104": 5, "B-105": 99_999_999})
    assert d.untrusted == frozenset({"B-105"}) and d.as_of == at(5)


def test_exactly_the_limit_is_trusted_and_one_second_more_is_not() -> None:
    assert run({"B-101": 0, "B-102": 120}).untrusted == frozenset()
    assert run({"B-101": 0, "B-102": 121}).untrusted == frozenset({"B-102"})


def test_an_even_number_of_others_uses_the_lower_middle_value() -> None:
    # others of B-105: 0, 10, 20, 30 -> lower middle is 10 (the upper one, 20, would give 140)
    base = {"B-101": 0, "B-102": 10, "B-103": 20, "B-104": 30}
    assert run({**base, "B-105": 130}).untrusted == frozenset()
    assert run({**base, "B-105": 131}).untrusted == frozenset({"B-105"})


def test_all_buses_within_five_seconds_the_clock_is_the_old_maximum() -> None:
    latest = {"B-101": 0, "B-102": 1, "B-103": 3, "B-104": 4, "B-105": 5}
    d = run(latest)
    assert d.untrusted == frozenset() and d.as_of == max(at(s) for s in latest.values())


def test_the_rule_is_pure_it_reads_no_wall_clock_and_no_arrival_time() -> None:
    source = inspect.getsource(clock)
    for forbidden in ("datetime.now", "time.time", "utcnow", "arrival_ts", "import psycopg"):
        assert forbidden not in source


def test_input_is_not_modified_and_the_result_is_deterministic() -> None:
    latest = {"B-101": at(0), "B-102": at(500), "B-103": at(1)}
    snapshot = dict(latest)
    assert trusted_clock(latest, 120) == trusted_clock(dict(reversed(list(latest.items()))), 120)
    assert latest == snapshot
