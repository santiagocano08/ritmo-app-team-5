"""Corridor service metric from headways (FR-024, SC-007).

mean wait = sum(h^2) / (2 sum(h)); scheduled wait = sum(hp^2) / (2 sum(hp)) over the same
buses; EWT = mean wait - scheduled wait.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceMetric:
    n_headways: int
    mean_wait_s: float | None
    scheduled_wait_s: float | None
    ewt_s: float | None
    computable: bool


def _expected_wait(values: Sequence[float]) -> float:
    return sum(v * v for v in values) / (2 * sum(values))


def service_metric(headways: Sequence[float], planned_s: float) -> ServiceMetric:
    """Not computable (all values None) when there is no headway or they sum to zero."""
    n = len(headways)
    if n == 0 or sum(headways) <= 0:
        return ServiceMetric(n, None, None, None, False)
    mean = _expected_wait(headways)
    scheduled = _expected_wait([planned_s] * n)
    return ServiceMetric(n, round(mean, 3), round(scheduled, 3), round(mean - scheduled, 3), True)
