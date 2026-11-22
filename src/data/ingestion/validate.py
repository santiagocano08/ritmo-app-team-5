"""Boundary validation of turn-1 event envelopes (T015, research R12).

Validates a decoded JSON message against the Pydantic V2 models derived from
contracts/turn1-events and maps the first failure to the contract's rejection
reason enum. Deterministic code: the rule judges the data, never an LLM.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from src.pulsoflota.models.turn1_events import EventEnvelopeRoot, EventType, SchemaVersion

SUPPORTED_SCHEMA_VERSIONS = {v.value for v in SchemaVersion}
KNOWN_EVENT_TYPES = {t.value for t in EventType}


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str | None = None
    envelope: EventEnvelopeRoot | None = None
    detail: str | None = None


def _reason_for(error: dict[str, Any]) -> str:
    """Map one Pydantic error dict to a rejection.schema.json reason."""
    etype: str = error.get("type", "")
    msg: str = error.get("msg", "")
    if etype == "missing":
        return "missing_required_field"
    if etype == "extra_forbidden":
        return "undeclared_field"
    if etype.startswith("uuid"):
        return "invalid_uuid"
    if etype.startswith(("datetime", "date_", "timezone", "time_")):
        return "invalid_timestamp"
    if etype == "union_tag_invalid":
        return "unknown_event_type"
    if etype == "value_error":
        # model_validator conditionals (rider_arrival.train_trip_id)
        if "required" in msg:
            return "missing_required_field"
        if "forbidden" in msg:
            return "undeclared_field"
        return "value_out_of_range"
    if etype.endswith("_type") or etype.endswith("_parsing") or etype in {"model_attributes_type", "dict_type"}:
        return "wrong_type"
    # greater_than*, less_than*, enum, literal_error, too_short, string_too_short, ...
    return "value_out_of_range"


def validate_envelope(message: Any, route_end_m: float | None = None) -> ValidationResult:
    """Validate one decoded message; never raises for bad input.

    `route_end_m` (005 US5): when given, a `bus_position` beyond it is rejected as `value_out_of_range`.
    None means the bound is unreadable and the event is accepted (contracts/guards.md G1).
    """
    if not isinstance(message, dict):
        return ValidationResult(False, "wrong_type", detail="message is not a JSON object")

    # Envelope-level checks first so the reason is the most specific one.
    version = message.get("schema_version")
    if version is not None and isinstance(version, str) and version not in SUPPORTED_SCHEMA_VERSIONS:
        return ValidationResult(False, "unsupported_schema_version", detail=f"schema_version={version!r}")
    event_type = message.get("event_type")
    if isinstance(event_type, str) and event_type not in KNOWN_EVENT_TYPES:
        return ValidationResult(False, "unknown_event_type", detail=f"event_type={event_type!r}")

    try:
        envelope = EventEnvelopeRoot.model_validate(message)
    except ValidationError as exc:
        first = exc.errors()[0]
        loc = ".".join(str(p) for p in first.get("loc", ()))
        return ValidationResult(False, _reason_for(first), detail=f"{loc}: {first.get('msg', '')}")
    root = envelope.root
    if route_end_m is not None and root.event_type == "bus_position" and root.payload.distance_along_m > route_end_m:
        return ValidationResult(False, "value_out_of_range", detail="payload.distance_along_m: beyond the route end")
    return ValidationResult(True, envelope=envelope)
