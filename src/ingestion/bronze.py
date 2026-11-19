"""Insert-only writes to the bronze layer (T016, ADR-0001).

- valid event   -> INSERT into bronze.events, arrival_ts stamped here (any value
                   sent by the producer is ignored)
- invalid event -> INSERT into bronze.rejections with its reason and the
                   original message as received
- duplicate     -> the UNIQUE (source, event_id) constraint rejects it; it goes
                   to bronze.rejections with reason duplicate_event
Only INSERT statements, always parameterized.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from src.ingestion.validate import validate_envelope

_INSERT_EVENT = """
INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload)
VALUES (%(source)s, %(event_id)s, %(schema_version)s, %(event_type)s, %(event_ts)s, now(), %(payload)s)
ON CONFLICT ON CONSTRAINT bronze_events_unique DO NOTHING
RETURNING id
"""

_INSERT_REJECTION = """
INSERT INTO bronze.rejections (original_message, reason, received_ts)
VALUES (%(original_message)s, %(reason)s, now())
"""


@dataclass(frozen=True)
class IngestResult:
    accepted: bool
    reason: str | None = None
    bronze_id: int | None = None


def _reject(conn: psycopg.Connection, message: Any, reason: str) -> IngestResult:
    original = message if isinstance(message, (dict, list)) else {"raw": message}
    with conn.cursor() as cur:
        cur.execute(_INSERT_REJECTION, {"original_message": Jsonb(original), "reason": reason})
    if not conn.autocommit:
        conn.commit()
    return IngestResult(False, reason)


def ingest(conn: psycopg.Connection, message: Any) -> IngestResult:
    """Validate one decoded message and land it in bronze or bronze.rejections."""
    result = validate_envelope(message)
    if not result.ok:
        return _reject(conn, message, result.reason or "wrong_type")

    env = result.envelope.root  # type: ignore[union-attr]
    params = {
        "source": env.source,
        "event_id": env.event_id,
        "schema_version": env.schema_version.value,
        "event_type": env.event_type,
        "event_ts": env.event_ts,
        # store the payload exactly as received (validated, not re-serialized)
        "payload": Jsonb(message["payload"]),
    }
    with conn.cursor() as cur:
        cur.execute(_INSERT_EVENT, params)
        row = cur.fetchone()
    if not conn.autocommit:
        conn.commit()
    if row is None:  # ON CONFLICT DO NOTHING -> same source + event_id already in bronze
        return _reject(conn, message, "duplicate_event")
    return IngestResult(True, bronze_id=row[0])


def ingest_line(conn: psycopg.Connection, line: str) -> IngestResult | None:
    """Decode one JSON line and ingest it; blank lines are ignored."""
    line = line.strip()
    if not line:
        return None
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return _reject(conn, line, "wrong_type")
    return ingest(conn, message)
