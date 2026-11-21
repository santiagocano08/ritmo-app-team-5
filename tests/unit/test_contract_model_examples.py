"""
Unit test: run every file in contracts/turn1-events/examples through the
EventEnvelopeRoot Pydantic model and assert:
  - valid/ examples pass
  - invalid/ examples (except 10_duplicate_event) fail with a ValidationError
  - 10_duplicate_event is structurally valid (duplicate detection happens at
    ingestion, not at the schema-validation layer)

This test is the regression guard for the strict-type defect fix: a numeric
string like "28.5" for speed_kmh must be rejected.
"""
from __future__ import annotations

import json
import pathlib

import pytest
from pydantic import ValidationError

from src.pulsoflota.models.turn1_events import EventEnvelopeRoot

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_EXAMPLES_DIR = pathlib.Path(__file__).parent.parent.parent / "contracts" / "turn1-events" / "examples"
_VALID_DIR = _EXAMPLES_DIR / "valid"
_INVALID_DIR = _EXAMPLES_DIR / "invalid"

# 10_duplicate_event.json is structurally valid — it passes schema validation;
# the duplicate is only detectable by the ingestion layer (source + event_id
# uniqueness check against bronze.events).
_SCHEMA_VALID_BUT_INGESTION_REJECTED = {"10_duplicate_event.json"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Valid examples — must all parse without error
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "example_path",
    sorted(_VALID_DIR.glob("*.json")),
    ids=lambda p: p.name,
)
def test_valid_example_passes(example_path: pathlib.Path) -> None:
    """Every example in examples/valid/ must be accepted by the model."""
    data = _load(example_path)
    # Should not raise
    envelope = EventEnvelopeRoot.model_validate(data)
    assert envelope is not None, f"model_validate returned None for {example_path.name}"


# ---------------------------------------------------------------------------
# Invalid examples — must all be rejected (except ingestion-only rejections)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "example_path",
    [
        p
        for p in sorted(_INVALID_DIR.glob("*.json"))
        if p.name not in _SCHEMA_VALID_BUT_INGESTION_REJECTED
    ],
    ids=lambda p: p.name,
)
def test_invalid_example_rejected(example_path: pathlib.Path) -> None:
    """Every example in examples/invalid/ (except ingestion-only ones) must
    raise ValidationError when parsed by the model."""
    data = _load(example_path)
    with pytest.raises(ValidationError):
        EventEnvelopeRoot.model_validate(data)


# ---------------------------------------------------------------------------
# Ingestion-layer rejections — structurally valid at the schema level
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "example_path",
    [
        p
        for p in sorted(_INVALID_DIR.glob("*.json"))
        if p.name in _SCHEMA_VALID_BUT_INGESTION_REJECTED
    ],
    ids=lambda p: p.name,
)
def test_ingestion_only_rejection_passes_schema(example_path: pathlib.Path) -> None:
    """10_duplicate_event.json is structurally valid — the model must accept it.
    The duplicate is caught by the ingestion layer (UNIQUE(source, event_id))."""
    data = _load(example_path)
    envelope = EventEnvelopeRoot.model_validate(data)
    assert envelope is not None


# ---------------------------------------------------------------------------
# Explicit regression test for the strict-type defect
# ---------------------------------------------------------------------------

def test_string_for_numeric_speed_is_rejected() -> None:
    """A JSON string value for speed_kmh ('28.5' instead of 28.5) must be
    rejected with ValidationError — not silently coerced to a float.

    This is the specific defect reported: the JSON Schema contract says
    speed_kmh must be type 'number'; a string is a schema violation.
    """
    with open(_INVALID_DIR / "02_wrong_type.json") as f:
        data = json.load(f)

    # Confirm the fixture actually has a string for speed_kmh
    assert isinstance(data["payload"]["speed_kmh"], str), (
        "Fixture 02_wrong_type.json must have a string value for speed_kmh"
    )

    with pytest.raises(ValidationError) as exc_info:
        EventEnvelopeRoot.model_validate(data)

    errors = exc_info.value.errors()
    # At least one error must reference speed_kmh
    speed_errors = [
        e for e in errors
        if any("speed_kmh" in str(loc) for loc in e.get("loc", []))
    ]
    assert speed_errors, (
        f"Expected a ValidationError for speed_kmh, got: {errors}"
    )
