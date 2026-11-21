"""Freshness healthcheck of the ingestion service (`python -m src.data.ingestion.health`).

Exit 0 when the newest bronze insert is at most INGESTION_HEALTH_MAX_AGE_S seconds old (default 15,
database clock), else exit 1. Reads only `ops.ingestion_health.last_insert_age_s`. Depends on the
database only. Prints no connection detail and no exception text.
"""
from __future__ import annotations

import os
import sys

import psycopg

from src.pulsoflota.config import get_db_dsn

DEFAULT_MAX_AGE_S = 15.0


def get_max_age_s() -> float:
    raw = os.environ.get("INGESTION_HEALTH_MAX_AGE_S")
    if raw is None or raw == "":
        return DEFAULT_MAX_AGE_S
    try:
        value = float(raw)
    except ValueError:
        raise RuntimeError("INGESTION_HEALTH_MAX_AGE_S must be a number") from None
    if value <= 0:
        raise RuntimeError("INGESTION_HEALTH_MAX_AGE_S must be greater than 0")
    return value


def last_insert_age_s(conn: psycopg.Connection) -> float | None:
    """Seconds since the last bronze insert (database clock); None when bronze is empty."""
    row = conn.execute("SELECT last_insert_age_s FROM ops.ingestion_health").fetchone()
    conn.rollback()
    return None if row is None or row[0] is None else float(row[0])


def is_healthy(conn: psycopg.Connection, max_age_s: float) -> bool:
    age = last_insert_age_s(conn)
    return age is not None and age <= max_age_s


def main() -> int:
    try:
        max_age = get_max_age_s()
        with psycopg.connect(get_db_dsn(), connect_timeout=3) as conn:
            healthy = is_healthy(conn, max_age)
    except Exception:  # noqa: BLE001 - any failure means unhealthy; never print details
        print("unhealthy: check failed")
        return 1
    print("healthy" if healthy else f"unhealthy: no insert in the last {max_age:g} s")
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
