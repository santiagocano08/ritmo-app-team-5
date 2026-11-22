"""T036, rewritten for 005 US3 — corridor service metric over additive sums (FR-030, FR-031, FR-035, FR-036)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.data.rules.service_metric import ewt_from_sums, service_metric


def sums(headways: list[int]) -> tuple[int, Decimal, Decimal]:
    return len(headways), Decimal(sum(headways)), Decimal(sum(h * h for h in headways))


def test_two_headways_300_and_900() -> None:
    n, s1, s2 = sums([300, 900])
    m = service_metric(n, s1, s2, 600, 1)
    assert m.computable and m.n_headways == 2
    assert m.mean_wait_s == pytest.approx(375.0)   # (300^2 + 900^2) / (2 * 1200)
    assert m.scheduled_wait_s == pytest.approx(300.0)
    assert m.ewt_s == pytest.approx(75.0)


def test_four_regular_headways_have_zero_ewt() -> None:
    n, s1, s2 = sums([600] * 4)
    m = service_metric(n, s1, s2, 600, 1)
    assert (m.mean_wait_s, m.scheduled_wait_s, m.ewt_s) == (300.0, 300.0, 0.0)


def test_scheduled_wait_follows_the_planned_headway_parameter() -> None:
    n, s1, s2 = sums([400])
    assert service_metric(n, s1, s2, 400, 1).scheduled_wait_s == 200.0


def test_zero_headways_count_as_samples() -> None:
    n, s1, s2 = sums([0, 600])
    m = service_metric(n, s1, s2, 600, 1)
    assert m.computable and m.n_headways == 2
    assert m.mean_wait_s == pytest.approx(300.0)


def test_no_headway_is_not_computable() -> None:
    m = service_metric(0, Decimal(0), Decimal(0), 600, 1)
    assert not m.computable and m.n_headways == 0
    assert m.mean_wait_s is None and m.scheduled_wait_s is None and m.ewt_s is None


def test_all_zero_headways_are_not_computable() -> None:
    m = service_metric(2, Decimal(0), Decimal(0), 600, 1)
    assert not m.computable and m.n_headways == 2 and m.ewt_s is None


def test_below_the_minimum_the_values_are_null_but_the_count_shows() -> None:
    n, s1, s2 = sums([300, 900, 600, 600])
    m = service_metric(n, s1, s2, 600, 5)
    assert not m.computable and m.n_headways == 4
    assert m.mean_wait_s is None and m.scheduled_wait_s is None and m.ewt_s is None


def test_exactly_the_minimum_is_computable() -> None:
    n, s1, s2 = sums([300, 900, 600, 600, 600])
    m = service_metric(n, s1, s2, 600, 5)
    assert m.computable and m.n_headways == 5 and m.ewt_s is not None


def test_values_are_rounded_to_three_decimals() -> None:
    n, s1, s2 = sums([301, 899, 640])
    m = service_metric(n, s1, s2, 600, 1)
    for v in (m.mean_wait_s, m.scheduled_wait_s, m.ewt_s):
        assert v == round(v, 3)


def test_ewt_from_sums_is_unrounded_and_returns_mean_scheduled_and_ewt() -> None:
    n, s1, s2 = sums([300, 900])
    mean, scheduled, ewt = ewt_from_sums(n, s1, s2, 600)
    assert (mean, scheduled, ewt) == (pytest.approx(375.0), pytest.approx(300.0), pytest.approx(75.0))


def test_better_than_planned_is_negative() -> None:
    n, s1, s2 = sums([500] * 5)
    assert service_metric(n, s1, s2, 600, 5).ewt_s == pytest.approx(-50.0)
