"""Freshness healthcheck of the refresh service (`python -m src.data.refresh.health`).

Exit 0 when a gold snapshot was committed in the last REFRESH_HEALTH_MAX_AGE_S seconds of
wall-clock time (default 30), else exit 1. In `REFRESH_CLOCK=data` mode a whole-feed stop
stops new snapshots, so this turns unhealthy: the declared M3 limitation is made visible.
Prints no connection detail.
"""
from __future__ import annotations

import os
import sys

import psycopg

from src.pulsoflota.config import get_db_dsn

DEFAULT_MAX_AGE_S = 30.0


def get_max_age_s() -> float:
    raw = os.environ.get("REFRESH_HEALTH_MAX_AGE_S")
    if raw is None or raw == "":
        return DEFAULT_MAX_AGE_S
    try:
        value = float(raw)
    except ValueError:
        raise RuntimeError("REFRESH_HEALTH_MAX_AGE_S must be a number") from None
    if value <= 0:
        raise RuntimeError("REFRESH_HEALTH_MAX_AGE_S must be greater than 0")
    return value


def snapshot_age_s(conn: psycopg.Connection) -> float | None:
    """Seconds since the newest snapshot was written (database clock); None if there is none."""
    row = conn.execute(
        "SELECT extract(epoch FROM clock_timestamp() - max(committed_at)) FROM gold.snapshot_commits").fetchone()
    conn.rollback()
    return None if row[0] is None else float(row[0])


def is_healthy(conn: psycopg.Connection, max_age_s: float) -> bool:
    age = snapshot_age_s(conn)
    return age is not None and age <= max_age_s


def main() -> int:
    try:
        max_age = get_max_age_s()
        with psycopg.connect(get_db_dsn(), connect_timeout=3) as conn:
            healthy = is_healthy(conn, max_age)
    except Exception:  # noqa: BLE001 - any failure means unhealthy; never print details
        print("unhealthy: check failed")
        return 1
    print("healthy" if healthy else f"unhealthy: no snapshot in the last {max_age:g} s")
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
