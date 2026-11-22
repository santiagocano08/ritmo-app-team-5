"""One gold cycle in one transaction (feature 002; research R4, R5, R6; FR-004, FR-037, FR-038, FR-040).

`run_cycle(conn, as_of_ts)`: REPEATABLE READ, advisory lock (skip when held), `M = max(bronze id)`,
silver rebuild, gold snapshot, `pg_notify` only for a new snapshot, then COMMIT. PostgreSQL
delivers the notification at commit, so a reader never hears of an unreadable snapshot.
Any error rolls everything back and raises `CycleError`, whose message carries no internal detail.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

import psycopg
from psycopg import pq

from src.data.pipeline import gold
from src.data.pipeline.holds import build_instruction_status
from src.data.pipeline.incidents import build_incidents
from src.data.pipeline.silver import rebuild_silver
from src.data.pipeline.stop_metrics import rebuild_ewt_bands

CHANNEL = "gold_snapshot"
ADVISORY_LOCK_KEY = 7_203_002  # arbitrary constant: "pulsoflota 002 gold cycle"

logger = logging.getLogger("pulsoflota.cycle")


@dataclass(frozen=True)
class CycleResult:
    snapshot_id: UUID
    as_of_ts: datetime
    max_bronze_id: int
    status: str
    created: bool


class CycleError(RuntimeError):
    """A cycle failed and was rolled back. Safe to show: generic text plus a correlation id."""

    def __init__(self, correlation_id: str) -> None:
        super().__init__("gold cycle failed; see the logs with correlation_id " + correlation_id)
        self.correlation_id = correlation_id


def _log(level: int, **fields: object) -> None:
    logger.log(level, json.dumps(fields, sort_keys=True, default=str))


def run_cycle(conn: psycopg.Connection, as_of_ts: datetime, notify: bool = True) -> CycleResult | None:
    """Run one cycle at `as_of_ts` (timezone-aware). None when another cycle holds the lock.

    The connection must be idle and not in autocommit mode: the cycle owns the transaction.
    """
    if as_of_ts.tzinfo is None:
        raise ValueError("as_of_ts must be timezone-aware")
    if conn.autocommit or conn.info.transaction_status != pq.TransactionStatus.IDLE:
        raise ValueError("run_cycle needs an idle, non-autocommit connection")
    as_of = as_of_ts.astimezone(timezone.utc)
    try:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        if not conn.execute("SELECT pg_try_advisory_xact_lock(%s)", (ADVISORY_LOCK_KEY,)).fetchone()[0]:
            conn.rollback()
            _log(logging.INFO, event="cycle_skipped", reason="lock_held", as_of_ts=as_of.isoformat())
            return None
        max_id = conn.execute("SELECT coalesce(max(id), 0) FROM bronze.events").fetchone()[0]
        rebuild_silver(conn, as_of, max_id)
        gold.rebuild_baselines(conn, as_of, max_id)
        rebuild_ewt_bands(conn, as_of, max_id)  # 005: closed 15-minute bands, replaced every cycle
        snap = gold.build_snapshot(conn, as_of, max_id)
        if snap.created:
            build_incidents(conn, snap.snapshot_id, as_of, max_id)
        build_instruction_status(conn, as_of, max_id)  # 004: rebuilt every cycle, not per snapshot
        if snap.created and notify:
            conn.execute("SELECT pg_notify(%s, %s)", (CHANNEL, json.dumps({"snapshot_id": str(snap.snapshot_id)})))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        correlation_id = uuid.uuid4().hex
        _log(logging.ERROR, event="cycle_failed", error_class=type(exc).__name__,
             correlation_id=correlation_id, as_of_ts=as_of.isoformat())
        raise CycleError(correlation_id) from None
    _log(logging.INFO, event="cycle_done", snapshot_id=str(snap.snapshot_id), created=snap.created,
         max_bronze_id=max_id, as_of_ts=as_of.isoformat())
    return CycleResult(snap.snapshot_id, as_of, max_id, snap.status, snap.created)
