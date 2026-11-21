"""Helpers shared by the silver integration tests (002, Phase 1).

`at(t)` turns seconds after the simulated start into a UTC datetime; `build` runs the silver
rebuild with `M = max(bronze.events.id)` the way the cycle does (research R4); `dump` returns an
ordered, comparable copy of every silver table.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import psycopg

from src.data.pipeline.silver import SILVER_TABLES, rebuild_silver
from src.data.tests.fixtures.bronze_builders import T0

__all__ = ["at", "max_id", "build", "dump", "state", "visits", "traversals", "incidents"]


def at(t: float) -> datetime:
    return T0 + timedelta(seconds=t)


def max_id(conn: psycopg.Connection) -> int:
    return conn.execute("SELECT coalesce(max(id), 0) FROM bronze.events").fetchone()[0]


def build(conn: psycopg.Connection, as_of_s: float, max_bronze_id: int | None = None) -> None:
    """Rebuild silver at `T0 + as_of_s`, reading bronze rows with id <= max_bronze_id (default: all)."""
    m = max_id(conn) if max_bronze_id is None else max_bronze_id
    rebuild_silver(conn, at(as_of_s), m)
    conn.commit()


def dump(conn: psycopg.Connection) -> dict[str, list[tuple]]:
    """Every silver table, rows ordered by all columns (text cast so mixed types sort)."""
    out = {}
    for table in SILVER_TABLES:
        rows = conn.execute(f"SELECT * FROM silver.{table} ORDER BY 1, 2, 3, 4, 5").fetchall()  # noqa: S608
        out[table] = sorted(rows, key=repr)
    return out


def _dicts(conn: psycopg.Connection, query: str) -> list[dict]:
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        return cur.execute(query).fetchall()


def state(conn: psycopg.Connection) -> dict[str, dict]:
    rows = _dicts(conn, "SELECT * FROM silver.bus_current_state ORDER BY bus_id")
    return {r["bus_id"]: r for r in rows}


def visits(conn: psycopg.Connection) -> list[dict]:
    return _dicts(conn, "SELECT * FROM silver.stop_visits ORDER BY bus_id, trip_id, arrival_ts")


def traversals(conn: psycopg.Connection) -> list[dict]:
    return _dicts(conn, "SELECT * FROM silver.segment_traversals ORDER BY bus_id, trip_id, segment_id")


def incidents(conn: psycopg.Connection) -> list[dict]:
    return _dicts(conn, "SELECT * FROM silver.incidents ORDER BY start_ts, inc_id")
