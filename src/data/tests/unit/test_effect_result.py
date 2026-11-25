"""Effect result rule (ADR-0007): worked / partial / did_not_work / no_data."""
from __future__ import annotations

from typing import Any

from src.data.rules.effect_result import classify_effect_result


def classify(**overrides: Any) -> str:
    inputs: dict[str, Any] = {
        "ewt_before_s": 100.0,
        "ewt_after_s": 60.0,
        "expected_saving_s": 40.0,
        "headway_before_s": 300.0,
        "headway_after_s": 280.0,
        "headway_planned_s": 240.0,
        "coverage_ratio": 1.0,
        "worked_ratio": 0.5,
        "min_coverage": 0.9,
    }
    inputs.update(overrides)
    return classify_effect_result(**inputs)


def test_baseline_worked() -> None:
    assert classify() == "worked"


def test_saving_exactly_half_of_expected_is_worked() -> None:
    assert classify(ewt_after_s=80.0) == "worked"


def test_saving_just_below_half_is_partial() -> None:
    assert classify(ewt_after_s=80.5) == "partial"


def test_small_saving_is_partial_even_if_headway_not_closer_to_plan() -> None:
    assert classify(ewt_after_s=80.5, headway_before_s=300.0, headway_after_s=300.0) == "partial"
    assert classify(ewt_after_s=80.5, headway_before_s=None) == "partial"


def test_saving_above_half_is_worked() -> None:
    assert classify(ewt_after_s=70.0) == "worked"


def test_no_saving_with_headway_closer_to_plan_is_partial() -> None:
    assert classify(ewt_after_s=100.0, headway_before_s=400.0, headway_after_s=300.0) == "partial"


def test_negative_saving_with_headway_closer_to_plan_is_partial() -> None:
    assert classify(ewt_after_s=120.0, headway_before_s=400.0, headway_after_s=300.0) == "partial"


def test_no_saving_with_headway_not_closer_is_did_not_work() -> None:
    assert classify(ewt_after_s=100.0, headway_before_s=300.0, headway_after_s=300.0) == "did_not_work"
    assert classify(ewt_after_s=110.0, headway_before_s=300.0, headway_after_s=400.0) == "did_not_work"


def test_no_saving_with_missing_headway_is_did_not_work() -> None:
    assert classify(ewt_after_s=100.0, headway_before_s=None) == "did_not_work"
    assert classify(ewt_after_s=100.0, headway_after_s=None) == "did_not_work"


def test_low_coverage_is_no_data() -> None:
    assert classify(coverage_ratio=0.89) == "no_data"


def test_coverage_at_minimum_is_evaluated() -> None:
    assert classify(coverage_ratio=0.90) == "worked"


def test_invalid_expected_saving_is_no_data() -> None:
    assert classify(expected_saving_s=None) == "no_data"
    assert classify(expected_saving_s=0.0) == "no_data"
    assert classify(expected_saving_s=-5.0) == "no_data"


def test_missing_ewt_is_no_data() -> None:
    assert classify(ewt_before_s=None) == "no_data"
    assert classify(ewt_after_s=None) == "no_data"


def test_zero_expected_and_zero_observed_saving_is_no_data() -> None:
    assert classify(expected_saving_s=0.0, ewt_after_s=100.0) == "no_data"


def test_several_failing_conditions_is_no_data() -> None:
    assert (
        classify(coverage_ratio=0.1, expected_saving_s=None, ewt_before_s=None, ewt_after_s=None)
        == "no_data"
    )


def test_worked_ratio_is_configurable() -> None:
    assert classify(ewt_after_s=80.5, worked_ratio=0.5) == "partial"
    assert classify(ewt_after_s=80.5, worked_ratio=0.4) == "worked"


def test_min_coverage_is_configurable() -> None:
    assert classify(coverage_ratio=0.8, min_coverage=0.9) == "no_data"
    assert classify(coverage_ratio=0.8, min_coverage=0.7) == "worked"


def test_headway_planned_is_configurable() -> None:
    kwargs: dict[str, Any] = {"ewt_after_s": 100.0, "headway_before_s": 300.0, "headway_after_s": 260.0}
    assert classify(headway_planned_s=240.0, **kwargs) == "partial"
    assert classify(headway_planned_s=400.0, **kwargs) == "did_not_work"
