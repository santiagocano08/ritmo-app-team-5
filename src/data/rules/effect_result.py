"""Effect result rule (ADR-0007): did a recommendation work, partly work, fail, or lack data."""
from __future__ import annotations

from typing import Literal

EffectResult = Literal["worked", "partial", "did_not_work", "no_data"]


def classify_effect_result(
    *,
    ewt_before_s: float | None,
    ewt_after_s: float | None,
    expected_saving_s: float | None,
    headway_before_s: float | None,
    headway_after_s: float | None,
    headway_planned_s: float,
    coverage_ratio: float,
    worked_ratio: float,
    min_coverage: float,
) -> EffectResult:
    if (
        coverage_ratio < min_coverage
        or expected_saving_s is None
        or expected_saving_s <= 0
        or ewt_before_s is None
        or ewt_after_s is None
    ):
        return "no_data"

    observed_saving_s = ewt_before_s - ewt_after_s
    if observed_saving_s >= worked_ratio * expected_saving_s:
        return "worked"

    if observed_saving_s > 0 or _closer_to_plan(headway_before_s, headway_after_s, headway_planned_s):
        return "partial"
    return "did_not_work"


def _closer_to_plan(before_s: float | None, after_s: float | None, planned_s: float) -> bool:
    if before_s is None or after_s is None:
        return False
    return abs(after_s - planned_s) < abs(before_s - planned_s)
