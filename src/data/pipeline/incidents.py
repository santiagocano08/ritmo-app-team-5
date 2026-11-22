"""`gold.incident` builder (004 FR-021, FR-026, FR-027; research R6; data-model E6).

One row per incident per snapshot, built from `silver.incidents` of the same cycle (so the two
cannot differ). `duration_s`, `until` and `active` are computed in SQL behind `isfinite(end_ts)`:
an open-ended incident has `end_ts = 'infinity'`, which psycopg cannot load and PostgreSQL cannot
subtract, so the raw `end_ts` is never selected. The caller owns the transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.data.rules import RULES_VERSION
from src.pulsoflota.models.read.incident import IncidentV100

SCHEMA_VERSION = "1.0.0"

_SELECT = """
SELECT inc_id,
       incident_type AS type,
       target_id,
       CASE WHEN isfinite(end_ts) THEN extract(epoch FROM end_ts - start_ts)::float8 END AS duration_s,
       start_ts AS since,
       CASE WHEN isfinite(end_ts) AND end_ts <= %(as_of)s THEN end_ts END AS until,
       (start_ts <= %(as_of)s AND end_ts > %(as_of)s) AS active,
       reported_by
FROM silver.incidents
ORDER BY start_ts, inc_id
"""

_INSERT = ("INSERT INTO gold.incident (snapshot_id, inc_id, active, doc, rules_version, max_bronze_id) "
           "VALUES (%s, %s, %s, %s, %s, %s)")


def build_incidents(conn: psycopg.Connection, snapshot_id: UUID, as_of_ts: datetime, max_bronze_id: int) -> int:
    """Insert the incident rows of one new snapshot. Returns the number of rows."""
    as_of = as_of_ts.astimezone(timezone.utc)
    with conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(_SELECT, {"as_of": as_of}).fetchall()
        for r in rows:
            fields = {k: v for k, v in r.items() if k != "active"}  # `active` is a column, not a doc field
            doc = IncidentV100.model_validate({"schema_version": SCHEMA_VERSION, **fields})
            cur.execute(_INSERT, (snapshot_id, r["inc_id"], r["active"], Jsonb(doc.model_dump(mode="json")),
                                  RULES_VERSION, max_bronze_id))
    return len(rows)
