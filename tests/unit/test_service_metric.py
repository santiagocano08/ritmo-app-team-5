"""T036 — corridor service metric (FR-024, SC-007)."""
from __future__ import annotations

import pytest

from src.rules.service_metric import service_metric


def test_two_headways_300_and_900() -> None:
    m = service_metric([300, 900], 600)
    assert m.computable and m.n_headways == 2
    assert m.mean_wait_s == pytest.approx(375.0)   # (300^2 + 900^2) / (2 * 1200)
    assert m.scheduled_wait_s == pytest.approx(300.0)
    assert m.ewt_s == pytest.approx(75.0)


def test_four_regular_headways_have_zero_ewt() -> None:
    m = service_metric([600] * 4, 600)
    assert (m.mean_wait_s, m.scheduled_wait_s, m.ewt_s) == (300.0, 300.0, 0.0)


def test_scheduled_wait_follows_the_planned_headway_parameter() -> None:
    assert service_metric([400], 400).scheduled_wait_s == 200.0


def test_zero_headways_count_as_samples() -> None:
    m = service_metric([0, 600], 600)
    assert m.computable and m.n_headways == 2
    assert m.mean_wait_s == pytest.approx(300.0)


def test_no_headway_is_not_computable() -> None:
    m = service_metric([], 600)
    assert not m.computable and m.n_headways == 0
    assert m.mean_wait_s is None and m.scheduled_wait_s is None and m.ewt_s is None


def test_all_zero_headways_are_not_computable() -> None:
    m = service_metric([0, 0], 600)
    assert not m.computable and m.n_headways == 2 and m.ewt_s is None
