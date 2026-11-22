"""T028 — the hold observation rule shared by the simulator and data (004 FR-012, FR-013, FR-015, FR-016, SC-007).

Pure functions of `src.data.rules.holds`: no database, no clock.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.data.rules import holds
from src.data.rules.holds import MAX_HOLD_S, EXECUTED_TOLERANCE_S, Order, Visit, hold_in_range, match_visit, observe

T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)


def at(s: float) -> datetime:
    return T0 + timedelta(seconds=s)


def order(rec: str = "r1", hold_s: float = 90, decided: float | None = 100, expires: float = 600,
          bus: str = "B-103", stop: str = "P-887") -> Order:
    return Order(rec, bus, stop, hold_s, None if decided is None else at(decided), at(expires))


def visit(arrive: float, depart: float | None) -> Visit:
    return Visit(at(arrive), None if depart is None else at(depart))


KEY = ("B-103", "P-887")


def run(orders, visits, breakdowns=None, ref: float = 10_000):
    return observe(orders, {KEY: visits}, breakdowns or {}, at(ref))


def test_constants_are_the_contract_numbers() -> None:
    assert MAX_HOLD_S == 90 and EXECUTED_TOLERANCE_S == 15


@pytest.mark.parametrize("hold_s,ok", [(0, True), (45, True), (90, True), (90.5, False), (120, False), (-1, False)])
def test_hold_range(hold_s: float, ok: bool) -> None:
    assert hold_in_range(hold_s) is ok


def test_visit_matches_strictly_after_the_decision_and_up_to_expiry() -> None:
    assert holds.visit_matches(at(101), at(100), at(600))
    assert not holds.visit_matches(at(100), at(100), at(600))  # same instant as the decision: too late
    assert not holds.visit_matches(at(99), at(100), at(600))
    assert holds.visit_matches(at(600), at(100), at(600))  # not after expires_ts
    assert not holds.visit_matches(at(601), at(100), at(600))
    assert holds.visit_matches(at(0), None, at(600))  # decision before every report: any visit


def test_match_visit_takes_the_first_matching_by_arrival() -> None:
    visits = [visit(400, 410), visit(50, 60), visit(200, 210)]
    assert match_visit(visits, at(100), at(600)) == visit(200, 210)
    assert match_visit(visits, at(500), at(600)) is None


@pytest.mark.parametrize("dwell,status", [(90, "executed"), (76, "executed"), (104, "executed"), (105, "executed"),
                                          (75, "executed"), (74, "not_executed"), (106, "not_executed"),
                                          (10, "not_executed")])
def test_tolerance_is_fifteen_seconds(dwell: float, status: str) -> None:
    (out,) = run([order(hold_s=90)], [visit(200, 200 + dwell)])
    assert out.status == status
    assert out.ts == at(200 + dwell) and out.observed_dwell_s == dwell


def test_fourteen_and_fifteen_seconds_off_are_executed_sixteen_is_not() -> None:
    for off, status in ((14, "executed"), (15, "executed"), (16, "not_executed")):
        (out,) = run([order(hold_s=60)], [visit(200, 200 + 60 + off)])
        assert out.status == status
        (out,) = run([order(hold_s=60)], [visit(200, 200 + 60 - off)])
        assert out.status == status


def test_cap_refuses_over_ninety_seconds_without_waiting() -> None:
    (out,) = run([order(hold_s=91, expires=600)], [], ref=100)
    assert (out.status, out.ts, out.reason, out.observed_dwell_s) == ("not_executed", at(600), "over_cap", None)
    (ok,) = run([order(hold_s=90)], [visit(200, 290)])
    assert ok.status == "executed"


def test_pending_while_the_window_is_open_and_no_visit() -> None:
    assert run([order(expires=600)], [], ref=300) == []
    assert run([order(expires=600)], [], ref=600) == []  # not yet past expires_ts


def test_expired_window_without_visit_is_not_executed_at_expires_ts() -> None:
    (out,) = run([order(expires=600)], [], ref=601)
    assert (out.status, out.ts, out.reason) == ("not_executed", at(600), "expired")


def test_bus_that_departed_before_the_decision_ends_at_expires_ts() -> None:
    (out,) = run([order(decided=300, expires=600)], [visit(200, 210)], ref=700)
    assert (out.status, out.ts, out.reason) == ("not_executed", at(600), "expired")


def test_visit_without_departure_is_pending_even_after_expiry() -> None:
    assert run([order(expires=600)], [visit(500, None)], ref=900) == []


def test_conflict_first_order_by_bronze_id_wins() -> None:
    first, second = order("r1", 90), order("r2", 90)
    out = run([first, second], [visit(200, 290)])
    assert [(o.rec_id, o.status, o.reason) for o in out] == [
        ("r1", "executed", "observed"), ("r2", "not_executed", "conflict")]
    assert out[1].ts == at(200)  # the arrival of the visit that the first order took (stable once seen)


def test_conflicting_order_with_a_later_window_takes_the_later_visit() -> None:
    first, second = order("r1", 90, decided=100), order("r2", 90, decided=250)
    out = run([first, second], [visit(200, 290), visit(400, 490)])
    assert [(o.rec_id, o.status) for o in out] == [("r1", "executed"), ("r2", "executed")]


def test_refused_order_does_not_take_the_visit() -> None:
    out = run([order("r1", 120), order("r2", 90)], [visit(200, 290)])
    assert [(o.rec_id, o.status, o.reason) for o in out] == [
        ("r1", "not_executed", "over_cap"), ("r2", "executed", "observed")]


def test_breakdown_before_the_visit_wins_even_if_the_dwell_matches() -> None:
    (out,) = run([order(decided=100)], [visit(300, 390)], {"B-103": [at(200)]})
    assert (out.status, out.reason, out.ts) == ("not_executed", "breakdown", at(200))


def test_breakdown_without_visit_is_not_executed_at_the_breakdown() -> None:
    (out,) = run([order(decided=100, expires=600)], [], {"B-103": [at(200)]}, ref=250)
    assert (out.status, out.reason, out.ts) == ("not_executed", "breakdown", at(200))


def test_breakdown_before_the_decision_or_after_the_departure_does_not_count() -> None:
    (a,) = run([order(decided=100)], [visit(300, 390)], {"B-103": [at(50)]})
    (b,) = run([order(decided=100)], [visit(300, 390)], {"B-103": [at(500)]})
    assert a.status == b.status == "executed"


def test_breakdown_of_another_bus_does_not_count() -> None:
    (out,) = run([order(decided=100)], [visit(300, 390)], {"B-104": [at(200)]})
    assert out.status == "executed"


def test_observe_is_a_pure_function() -> None:
    args = ([order("r1"), order("r2")], [visit(200, 290)], {"B-103": [at(5)]})
    assert run(*args) == run(*args)


def test_refused_breakdown_and_conflict_orders_all_have_a_reason() -> None:
    out = run([order("r1", 100), order("r2", 90), order("r3", 90)], [visit(300, 390)], {"B-103": [at(200)]})
    assert {o.reason for o in out} == {"over_cap", "breakdown"}
