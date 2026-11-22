"""Contract tests: responses validate against the approved read JSON Schemas (SC-002).

Validating against the JSON Schema (not only the Pydantic model) proves "only
contract fields, nothing extra" independently of the model (research R5). These tests
need a gold-seeded database and skip when DATABASE_URL is unset.
"""
from __future__ import annotations

from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import cycle, validator
from src.data.tests.integration.test_gold_fixtures import _as_of_seconds


def _seed_normal(gold_conn) -> None:
    tl = bb.normal()
    assert all(r.accepted for r in bb.ingest_all(gold_conn, tl.events))
    cycle(gold_conn, _as_of_seconds(tl))


def test_corridor_now_validates_against_contract(client, gold_conn) -> None:
    _seed_normal(gold_conn)

    resp = client.get("/api/v1/corridor/C6-008/now")

    assert resp.status_code == 200
    body = resp.json()
    validator("corridor_now").validate(body)
    assert body["corridor_id"] == "C6-008"
    assert body["direction"] == 1


def test_source_status_validates_against_contract(client, gold_conn) -> None:
    _seed_normal(gold_conn)

    resp = client.get("/api/v1/corridor/C6-008/source-status")

    assert resp.status_code == 200
    validator("source_status").validate(resp.json())
