"""006 T015 — recommendation schema 1.1.0 (FR-029, SC-013; specs/006-decision-mpc/contracts/recommendation-1.1.0.md).

Variants are built from the committed fixtures, so no hand-written document can drift from the contract.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

READ = Path(__file__).resolve().parents[4] / "contracts" / "read"
FIX = READ / "fixtures"
V = Draft202012Validator(json.loads((READ / "recommendation.schema.json").read_text()), format_checker=FormatChecker())


def _doc(name: str) -> dict:
    return json.loads((FIX / name / "recommendation.json").read_text())


def _ok(doc: dict) -> bool:
    return not list(V.iter_errors(doc))


def _with(doc: dict, **action) -> dict:
    d = copy.deepcopy(doc)
    for k, v in action.items():
        if v is _DROP:
            d["action"].pop(k, None)
        else:
            d["action"][k] = v
    return d


_DROP = object()
SLOW = _doc("c1_slow_down")
HOLD = _doc("c1_bunching")
SKIP = _doc("c2_skip_stop")
ADJ = _doc("c2_gap")
RESERVE = _doc("c5_breakdown")


def test_new_fixtures_are_the_documented_shape() -> None:
    assert SLOW["action"]["type"] == "slow_down" and SLOW["action"]["duration_s"] == 300
    assert SLOW["action"]["speed_reduction_pct"] == 20 and SLOW["case"] == "C1" and SLOW["horizon_s"] == 600
    assert SLOW["schema_version"] == "1.1.0"
    assert SKIP["action"]["type"] == "skip_stop" and SKIP["action"]["duration_s"] is None and SKIP["case"] == "C2"
    assert _ok(SLOW) and _ok(SKIP)


def test_existing_fixtures_still_validate() -> None:
    for name in ("c1_bunching", "c2_gap", "c5_breakdown", "d1_source_outage"):
        assert _ok(_doc(name)), name


@pytest.mark.parametrize("pct", [10, 20, 50, 0.5])
def test_slow_down_accepts_a_reduction_in_range(pct) -> None:
    assert _ok(_with(SLOW, speed_reduction_pct=pct))


@pytest.mark.parametrize("pct", [0, -5, 51, 100])
def test_slow_down_rejects_a_reduction_out_of_range(pct) -> None:
    assert not _ok(_with(SLOW, speed_reduction_pct=pct))


def test_slow_down_requires_the_reduction() -> None:
    assert not _ok(_with(SLOW, speed_reduction_pct=_DROP))


@pytest.mark.parametrize("doc", [HOLD, ADJ, RESERVE, SKIP], ids=["hold", "adjust", "reserve", "skip"])
def test_other_types_forbid_the_reduction(doc) -> None:
    assert not _ok(_with(doc, speed_reduction_pct=10))


@pytest.mark.parametrize("dur,ok", [(0, False), (1, True), (300, True), (1800, True), (1801, False), (None, False)])
def test_slow_down_duration_range(dur, ok) -> None:
    assert _ok(_with(SLOW, duration_s=dur)) is ok


def test_skip_stop_duration_must_be_null() -> None:
    assert not _ok(_with(SKIP, duration_s=60))
    assert _ok(_with(SKIP, duration_s=None))


def test_hold_and_unknown_types_and_extra_fields() -> None:
    assert not _ok(_with(HOLD, duration_s=91))
    assert _ok(_with(HOLD, duration_s=90))
    assert not _ok(_with(SLOW, type="teleport"))
    assert not _ok(_with(SLOW, extra=1))
    assert not _ok(_with(RESERVE, duration_s=10))


@pytest.mark.parametrize("version,ok", [("1.0.0", True), ("1.1.0", True), ("1.2.0", False)])
def test_schema_version_enum(version, ok) -> None:
    d = copy.deepcopy(HOLD)
    d["schema_version"] = version
    assert _ok(d) is ok
