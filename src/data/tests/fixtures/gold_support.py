"""Helpers shared by the gold integration tests (002, Phase 2).

`cycle` runs one snapshot cycle at `T0 + seconds`; `docs` reads the three stored documents of a
snapshot; `validator` returns a draft 2020-12 validator with format checks for a read schema
(research R9); `fixture` loads a scenario fixture of `contracts/read/fixtures/`.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import psycopg
from jsonschema import Draft202012Validator, FormatChecker

from src.data.pipeline.cycle import CycleResult, run_cycle
from src.data.tests.fixtures.silver_support import at

READ_DIR = Path(__file__).resolve().parents[4] / "contracts" / "read"

__all__ = ["at", "cycle", "docs", "validator", "fixture", "clear_all", "count"]


def cycle(conn: psycopg.Connection, as_of_s: float, notify: bool = False) -> CycleResult | None:
    """Run one cycle. `run_cycle` owns its transaction, so end the test's own read transaction first."""
    if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
        conn.commit()
    return run_cycle(conn, at(as_of_s), notify=notify)


@lru_cache(maxsize=None)
def validator(schema_name: str) -> Draft202012Validator:
    schema = json.loads((READ_DIR / f"{schema_name}.schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def fixture(scenario: str, name: str) -> dict:
    return json.loads((READ_DIR / "fixtures" / scenario / f"{name}.json").read_text(encoding="utf-8"))


def docs(conn: psycopg.Connection, snapshot_id) -> dict[str, dict]:
    out = {}
    for table in ("source_status", "corridor_now"):
        out[table] = conn.execute(
            f"SELECT doc FROM gold.{table} WHERE snapshot_id = %s", (snapshot_id,)).fetchone()[0]  # noqa: S608
    return out


def count(conn: psycopg.Connection, table: str) -> int:
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]  # noqa: S608 - fixed names


def clear_all(conn: psycopg.Connection) -> None:
    """Empty bronze, silver and the gold tables of one throwaway database."""
    conn.execute("TRUNCATE bronze.events, bronze.rejections RESTART IDENTITY")
    for table in ("segment_traversals", "stop_visits", "bus_current_state", "incidents", "position_history"):
        conn.execute(f"DELETE FROM silver.{table}")  # noqa: S608 - fixed names
    for table in ("incident", "service_metric", "decision_inputs", "corridor_now", "source_status", "snapshots"):
        conn.execute(f"DELETE FROM gold.{table}")  # noqa: S608 - fixed names
    conn.commit()
