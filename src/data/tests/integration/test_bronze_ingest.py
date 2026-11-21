"""T013 — ingestion into bronze against a live PostgreSQL (DATABASE_URL).

- a valid envelope lands in bronze.events once, with arrival_ts stamped by ingestion
- each invalid envelope lands in bronze.rejections with the matching reason
- same source + event_id twice: first accepted, second -> duplicate_event,
  bronze.events unchanged
Each test uses fresh event_ids so it is independent of previous runs.
"""
from __future__ import annotations

import json
import pathlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.data.ingestion.bronze import ingest

EXAMPLES = pathlib.Path(__file__).resolve().parents[4] / "contracts" / "turn1-events" / "examples"


def _fresh(name: str, folder: str = "valid") -> dict:
    msg = json.loads((EXAMPLES / folder / name).read_text())
    if isinstance(msg.get("event_id"), str) and folder == "valid":
        msg["event_id"] = str(uuid.uuid4())
    return msg


def _count(conn, sql: str, *params) -> int:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()[0]


@pytest.fixture()
def conn(db_dsn):
    import psycopg
    with psycopg.connect(db_dsn, autocommit=True) as c:
        yield c


def test_valid_event_lands_once_with_ingestion_arrival_ts(conn) -> None:
    msg = _fresh("bus_position.json")
    msg["arrival_ts"] = "2000-01-01T00:00:00Z"  # must be overwritten
    before = datetime.now(timezone.utc) - timedelta(seconds=5)
    result = ingest(conn, msg)
    assert result.accepted, result.reason
    with conn.cursor() as cur:
        cur.execute(
            "SELECT event_type, arrival_ts, payload FROM bronze.events WHERE source=%s AND event_id=%s",
            (msg["source"], msg["event_id"]),
        )
        rows = cur.fetchall()
    assert len(rows) == 1
    event_type, arrival_ts, payload = rows[0]
    assert event_type == "bus_position"
    assert arrival_ts >= before, "arrival_ts must be stamped by ingestion, not taken from the message"
    assert payload == msg["payload"]


@pytest.mark.parametrize(
    "name,reason",
    [
        ("01_missing_field.json", "missing_required_field"),
        ("02_wrong_type.json", "wrong_type"),
        ("03_out_of_range.json", "value_out_of_range"),
        ("04_unknown_event_type.json", "unknown_event_type"),
        ("05_unsupported_schema_version.json", "unsupported_schema_version"),
        ("06_extra_undeclared_field.json", "undeclared_field"),
        ("07_invalid_uuid.json", "invalid_uuid"),
        ("08_invalid_timestamp.json", "invalid_timestamp"),
        ("09_rider_missing_train_trip_id.json", "missing_required_field"),
    ],
)
def test_invalid_event_goes_to_rejections_with_reason(conn, name: str, reason: str) -> None:
    msg = _fresh(name, folder="invalid")
    last_id = _count(conn, "SELECT coalesce(max(id), 0) FROM bronze.rejections")
    result = ingest(conn, msg)
    assert not result.accepted and result.reason == reason
    with conn.cursor() as cur:
        cur.execute(
            "SELECT reason, original_message FROM bronze.rejections WHERE id > %s ORDER BY id",
            (last_id,),
        )
        rows = cur.fetchall()
    assert len(rows) == 1, "exactly one rejection row per invalid event"
    assert rows[0][0] == reason
    assert rows[0][1] == msg, "original_message must be stored as received"


def test_duplicate_is_discarded_and_bronze_unchanged(conn) -> None:
    msg = _fresh("stop_arrival.json")
    key = (msg["source"], msg["event_id"])
    first = ingest(conn, msg)
    assert first.accepted
    n_events = _count(conn, "SELECT count(*) FROM bronze.events WHERE source=%s AND event_id=%s", *key)
    second = ingest(conn, dict(msg))
    assert not second.accepted and second.reason == "duplicate_event"
    assert _count(conn, "SELECT count(*) FROM bronze.events WHERE source=%s AND event_id=%s", *key) == n_events == 1
    assert _count(
        conn,
        "SELECT count(*) FROM bronze.rejections WHERE reason='duplicate_event' AND original_message->>'event_id'=%s",
        key[1],
    ) == 1
