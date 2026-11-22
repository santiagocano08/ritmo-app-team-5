"""Silver rebuild runner (feature 002, US1; research R1, R2, R4).

Deletes and rebuilds every silver table from bronze + `config` inside the caller's
transaction, by running the SQL files of `src/data/rules/sql/` in dependency order. Orchestration
only: no rule or threshold lives here. Parameterized statements only; bronze is read, never
written (FR-002). `DELETE` (not `TRUNCATE`) keeps concurrent readers unblocked (MVCC).

The caller owns the transaction (the cycle runs it REPEATABLE READ and passes `M`), and
commits or rolls back.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

import psycopg

from src.data.rules import ESTIMATED_AFTER_S

SQL_DIR = Path(__file__).resolve().parents[1] / "rules" / "sql"

# Dependency order: bus_current_state and traversals read silver.incidents.
_BUILD_ORDER = (
    ("position_history", "silver_position_history.sql"),
    ("incidents", "silver_incidents.sql"),
    ("bus_current_state", "silver_bus_current_state.sql"),
    ("stop_visits", "silver_stop_visits.sql"),
    ("segment_traversals", "silver_segment_traversals.sql"),
    ("stop_queue", "silver_stop_queue.sql"),  # 006: last, it reads only bronze and config
)
SILVER_TABLES = tuple(table for table, _ in _BUILD_ORDER)


def rebuild_silver(conn: psycopg.Connection, as_of_ts: datetime, max_bronze_id: int,
                   untrusted_buses: Iterable[str] = ()) -> None:
    """Rebuild all silver tables for `as_of_ts`, reading bronze rows with id <= max_bronze_id.

    `untrusted_buses` (005 US6): buses the clock guard distrusts; they are Estimated in `bus_current_state`.
    """
    params = {"as_of_ts": as_of_ts, "max_bronze_id": max_bronze_id,
              "estimated_after_s": ESTIMATED_AFTER_S, "untrusted_buses": sorted(untrusted_buses)}
    with conn.cursor() as cur:
        for table in reversed(SILVER_TABLES):
            cur.execute(f"DELETE FROM silver.{table}")  # noqa: S608 - fixed table names
        for _, filename in _BUILD_ORDER:
            cur.execute((SQL_DIR / filename).read_text(encoding="utf-8"), params)
