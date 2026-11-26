"""Gold-layer read queries for the read API (US-05).

Parameterized psycopg 3 SQL only, SELECT-only against gold. The latest snapshot is
resolved once per response (Q0) and its `snapshot_id` reused for the object read
(Q1/Q2), per docs/data-contract.md §3 rule 3. The gold `doc` is pre-validated against
the read contract by the pipeline; these functions return it as stored.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg

DictConnection = psycopg.Connection[dict[str, Any]]

# Q0: latest snapshot. Both ordering keys are mandatory (data-contract §3 rule 2).
_Q0_LATEST_SNAPSHOT = """
    SELECT snapshot_id, as_of_ts
    FROM gold.snapshots
    ORDER BY as_of_ts DESC, max_bronze_id DESC
    LIMIT 1
"""

# Q0 with data age: wall time since commit, never the simulated as_of_ts (data-contract §2.1).
_Q0_LATEST_SNAPSHOT_AGE = """
    SELECT s.snapshot_id,
           extract(epoch FROM clock_timestamp() - c.committed_at)::float8 AS age_s
    FROM gold.snapshots s
    JOIN gold.snapshot_commits c USING (snapshot_id)
    ORDER BY s.as_of_ts DESC, s.max_bronze_id DESC
    LIMIT 1
"""

# Q13: active recommendations for the console, at most the top 3.
_Q13_PROPOSED_RECOMMENDATIONS = """
    SELECT doc FROM gold.recommendation
    WHERE doc->>'status' = %(status)s
    ORDER BY (doc->>'rank')::int
    LIMIT 3
"""

# Q2: corridor_now document for a resolved snapshot.
_Q2_CORRIDOR_NOW = "SELECT doc FROM gold.corridor_now WHERE snapshot_id = %(snapshot_id)s"

# Q1: source_status document for a resolved snapshot.
_Q1_SOURCE_STATUS = "SELECT doc FROM gold.source_status WHERE snapshot_id = %(snapshot_id)s"


def latest_snapshot_id(conn: DictConnection) -> UUID | None:
    """Return the latest snapshot id, or None when no snapshot exists yet (no-data)."""
    row = conn.execute(_Q0_LATEST_SNAPSHOT).fetchone()
    if row is None:
        return None
    return row["snapshot_id"]


def corridor_now_doc(conn: DictConnection, snapshot_id: UUID) -> dict[str, Any] | None:
    """Return the stored corridor_now doc for the snapshot, or None if absent."""
    row = conn.execute(_Q2_CORRIDOR_NOW, {"snapshot_id": snapshot_id}).fetchone()
    if row is None:
        return None
    return row["doc"]


def source_status_doc(conn: DictConnection, snapshot_id: UUID) -> dict[str, Any] | None:
    """Return the stored source_status doc for the snapshot, or None if absent."""
    row = conn.execute(_Q1_SOURCE_STATUS, {"snapshot_id": snapshot_id}).fetchone()
    if row is None:
        return None
    return row["doc"]


def latest_snapshot_with_age(conn: DictConnection) -> tuple[UUID, float] | None:
    """Return the latest committed snapshot id and its wall-clock age in seconds, or None."""
    row = conn.execute(_Q0_LATEST_SNAPSHOT_AGE).fetchone()
    if row is None:
        return None
    return row["snapshot_id"], row["age_s"]


def proposed_recommendation_docs(conn: DictConnection) -> list[dict[str, Any]]:
    """Return the stored `proposed` recommendation docs by rank, as stored (Q13)."""
    rows = conn.execute(_Q13_PROPOSED_RECOMMENDATIONS, {"status": "proposed"}).fetchall()
    return [row["doc"] for row in rows]
