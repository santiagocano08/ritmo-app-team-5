"""Contract tests: the recommendations envelope and its items."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.routers.corridor_read import RecommendationsResponse
from src.data.tests.fixtures.gold_support import fixture, validator

CORRIDOR = "C6-008"


def _item() -> dict:
    return fixture("c1_bunching", "recommendation") | {"status": "proposed"}


def test_fixture_item_validates_against_schema_and_envelope() -> None:
    item = _item()
    validator("recommendation").validate(item)

    envelope = RecommendationsResponse.model_validate(
        {"status": "ok", "corridor_id": CORRIDOR, "recommendations": [item]}
    )

    assert envelope.recommendations[0].action.bus_id == "B-101"


def test_envelope_rejects_more_than_three_items() -> None:
    with pytest.raises(ValidationError):
        RecommendationsResponse.model_validate(
            {"status": "ok", "corridor_id": CORRIDOR, "recommendations": [_item()] * 4}
        )


@pytest.mark.parametrize("status", ["stale", "no_data"])
def test_envelope_rejects_items_when_not_ok(status: str) -> None:
    with pytest.raises(ValidationError):
        RecommendationsResponse.model_validate(
            {"status": status, "corridor_id": CORRIDOR, "recommendations": [_item()]}
        )


def test_envelope_rejects_unknown_status_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        RecommendationsResponse.model_validate(
            {"status": "live", "corridor_id": CORRIDOR, "recommendations": []}
        )
    with pytest.raises(ValidationError):
        RecommendationsResponse.model_validate(
            {"status": "ok", "corridor_id": CORRIDOR, "recommendations": [], "extra": 1}
        )
