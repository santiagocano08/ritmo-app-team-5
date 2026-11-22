"""T008 — read-contract fixtures and the feature-local notify schema are valid.

Every fixture under contracts/read/fixtures/ validates against its schema
(draft 2020-12, format checks on). SC-001, Gate 1, R9.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[4]
READ = ROOT / "contracts" / "read"
NOTIFY = ROOT / "specs" / "002-silver-gold-baselines" / "contracts" / "gold_snapshot_notify.schema.json"

FIXTURES = sorted((READ / "fixtures").glob("*/*.json"))


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema_path: Path) -> Draft202012Validator:
    return Draft202012Validator(_load(schema_path), format_checker=FormatChecker())


def test_there_are_20_fixtures() -> None:
    """18 of the first release (unchanged) + c1_slow_down and c2_skip_stop (006 phase 2, FR-029)."""
    assert len(FIXTURES) == 20


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_fixture_validates_against_its_schema(fixture: Path) -> None:
    schema = READ / f"{fixture.stem}.schema.json"
    assert schema.exists(), f"no schema for fixture {fixture.name}"
    validator = _validator(schema)
    errors = [e.message for e in validator.iter_errors(_load(fixture))]
    assert not errors, errors


@pytest.mark.parametrize("schema", sorted(READ.glob("*.schema.json")), ids=lambda p: p.name)
def test_read_schemas_are_valid_draft_2020_12(schema: Path) -> None:
    Draft202012Validator.check_schema(_load(schema))


def test_notify_schema_is_valid_and_discriminates() -> None:
    Draft202012Validator.check_schema(_load(NOTIFY))
    v = _validator(NOTIFY)
    assert not list(v.iter_errors({"snapshot_id": "cccc0003-0000-4000-8000-000000000003"}))
    assert list(v.iter_errors({"snapshot_id": "not-a-uuid"}))
    assert list(v.iter_errors({}))
    assert list(v.iter_errors({"snapshot_id": "cccc0003-0000-4000-8000-000000000003", "x": 1}))


# -- T075: bus_state must agree with headway_ahead_s (planned 600 s: bunched < 300, gap > 900) --------
CORRIDOR_NOW = sorted((READ / "fixtures").glob("*/corridor_now.json"))


def _expected_state(headway: float, planned: float = 600) -> str:
    if headway < 0.5 * planned:
        return "bunched"
    if headway > 1.5 * planned:
        return "gap"
    return "regular"


@pytest.mark.parametrize("fixture", CORRIDOR_NOW, ids=lambda p: p.parent.name)
def test_bus_state_is_consistent_with_headway(fixture: Path) -> None:
    buses = _load(fixture)["buses"]
    for i, bus in enumerate(buses):
        if bus["bus_state"] in ("leader", "broken_down"):
            continue
        # FR-011: an Estimated bus and the bus directly behind it are forced to `regular`.
        if bus["data_quality"] == "estimated" or (i > 0 and buses[i - 1]["data_quality"] == "estimated"):
            assert bus["bus_state"] == "regular"
            continue
        expected = _expected_state(bus["headway_ahead_s"], bus["headway_planned_s"])
        assert bus["bus_state"] == expected, (
            f"{fixture.parent.name}/{bus['bus_id']}: headway {bus['headway_ahead_s']} s is {expected}, "
            f"fixture says {bus['bus_state']}")
