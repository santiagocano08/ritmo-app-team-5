"""Corridor service metric from stop-headway sums (FR-024, FR-030, FR-031, FR-035, FR-036; 005 US3).

mean wait = sum(h^2) / (2 sum(h)); scheduled wait = sum(hp^2) / (2 sum(hp)) with `hp` = the planned
headway once per headway; EWT = mean wait - scheduled wait. The inputs are additive sums (count, sum of
headways, sum of squares), so stops, bands and days are added before the formula is applied.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ServiceMetric:
    n_headways: int
    mean_wait_s: float | None
    scheduled_wait_s: float | None
    ewt_s: float | None
    computable: bool


def ewt_from_sums(n: int, sum_h: Decimal | float, sum_h2: Decimal | float,
                  planned_s: Decimal | float) -> tuple[float, float, float]:
    """(mean wait, scheduled wait, EWT), unrounded. The caller checks that `n > 0` and `sum_h > 0`."""
    sum_h, sum_h2, planned = Decimal(sum_h), Decimal(sum_h2), Decimal(planned_s)
    mean = sum_h2 / (2 * sum_h)
    scheduled = (n * planned * planned) / (2 * n * planned)
    return float(mean), float(scheduled), float(mean - scheduled)


def service_metric(n: int, sum_h: Decimal | float, sum_h2: Decimal | float, planned_s: Decimal | float,
                   min_headways: int) -> ServiceMetric:
    """Not computable (values None, `n_headways` kept) below `min_headways` or when the headways sum to zero."""
    if n < min_headways or n == 0 or Decimal(sum_h) <= 0:
        return ServiceMetric(n, None, None, None, False)
    mean, scheduled, _ = ewt_from_sums(n, sum_h, sum_h2, planned_s)
    # round the difference of the exact values, not of the rounded parts
    ewt = round(Decimal(sum_h2) / (2 * Decimal(sum_h)) - Decimal(planned_s) / 2, 3)
    return ServiceMetric(n, round(mean, 3), round(scheduled, 3), float(ewt), True)
