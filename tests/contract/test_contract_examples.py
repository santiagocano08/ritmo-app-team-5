"""T012 — contract examples through the ingestion validator.

Every valid example is accepted; every invalid example is rejected with the
reason its file name declares (R12 mapping). 10_duplicate_event is
schema-valid: the duplicate is only detected against bronze (see T013).
"""
from __future__ import annotations

import json
import pathlib

import pytest

from src.ingestion.validate import validate_envelope

EXAMPLES = pathlib.Path(__file__).resolve().parents[2] / "contracts" / "turn1-events" / "examples"

EXPECTED_REASON = {
    "01_missing_field.json": "missing_required_field",
    "02_wrong_type.json": "wrong_type",
    "03_out_of_range.json": "value_out_of_range",
    "04_unknown_event_type.json": "unknown_event_type",
    "05_unsupported_schema_version.json": "unsupported_schema_version",
    "06_extra_undeclared_field.json": "undeclared_field",
    "07_invalid_uuid.json": "invalid_uuid",
    "08_invalid_timestamp.json": "invalid_timestamp",
    "09_rider_missing_train_trip_id.json": "missing_required_field",
    "10_duplicate_event.json": None,  # schema-valid; rejected at bronze
}


@pytest.mark.parametrize("path", sorted((EXAMPLES / "valid").glob("*.json")), ids=lambda p: p.name)
def test_valid_examples_are_accepted(path: pathlib.Path) -> None:
    result = validate_envelope(json.loads(path.read_text()))
    assert result.ok, f"{path.name} rejected with {result.reason}"
    assert result.reason is None


@pytest.mark.parametrize("path", sorted((EXAMPLES / "invalid").glob("*.json")), ids=lambda p: p.name)
def test_invalid_examples_have_expected_reason(path: pathlib.Path) -> None:
    assert path.name in EXPECTED_REASON, f"add {path.name} to EXPECTED_REASON"
    result = validate_envelope(json.loads(path.read_text()))
    expected = EXPECTED_REASON[path.name]
    if expected is None:
        assert result.ok
    else:
        assert not result.ok
        assert result.reason == expected


def test_non_object_message_is_rejected_as_wrong_type() -> None:
    result = validate_envelope(["not", "an", "object"])  # type: ignore[arg-type]
    assert not result.ok and result.reason == "wrong_type"


def test_street_rider_with_train_trip_id_is_undeclared_field() -> None:
    msg = json.loads((EXAMPLES / "valid" / "rider_arrival.json").read_text())
    msg["payload"]["origin"] = "street"  # keeps train_trip_id -> forbidden
    result = validate_envelope(msg)
    assert not result.ok and result.reason == "undeclared_field"
