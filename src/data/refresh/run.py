"""Refresh loop (`python -m src.data.refresh.run`): recompute the gold snapshot every tick (FR-036).

One process, one thread: cycles cannot overlap. A tick that falls inside a slow cycle is skipped,
never queued (FR-039). A failed cycle is logged and the next tick runs normally (FR-040).
`REFRESH_CLOCK=wall|data` selects the reference time (research R3). Logs are JSON lines.
"""
from __future__ import annotations

import json
import logging
import math
import os
import sys
import time
from datetime import datetime, timezone
from typing import Callable

import psycopg

from src.data.pipeline.cycle import CycleError, run_cycle
from src.data.pipeline.reference import load_reference
from src.data.rules import ESTIMATED_AFTER_S
from src.data.rules.clock import ClockDecision, trusted_clock
from src.pulsoflota.config import get_db_dsn, get_log_level

log = logging.getLogger("pulsoflota.refresh")

DEFAULT_INTERVAL_S = 5.0
_NEWEST_BUS_REPORT = (
    "SELECT max(event_ts) FROM bronze.events "
    "WHERE event_type IN ('bus_position', 'stop_arrival', 'stop_departure') AND source <> 'backend'")
# 005 US6: per bus, the event_ts of its newest report by arrival (largest bronze id).
_LATEST_BY_BUS = (
    "SELECT DISTINCT ON (payload->>'bus_id') payload->>'bus_id' AS bus_id, event_ts FROM bronze.events "
    "WHERE event_type IN ('bus_position', 'stop_arrival', 'stop_departure') AND source <> 'backend' "
    "ORDER BY payload->>'bus_id', id DESC")
# What the last cycle logged as untrusted, so the clock_guard WARNING is written only when the set changes.
_GUARD_STATE: dict = {"untrusted": frozenset()}


class JsonFormatter(logging.Formatter):
    """One JSON object per line. Messages that already are JSON pass through; no tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if message.startswith("{"):
            return message
        return json.dumps({"level": record.levelname, "logger": record.name, "message": message})


def _event(level: int, **fields: object) -> None:
    log.log(level, json.dumps(fields, sort_keys=True, default=str))


def get_interval_s() -> float:
    raw = os.environ.get("REFRESH_INTERVAL_S")
    if raw is None or raw == "":
        return DEFAULT_INTERVAL_S
    try:
        value = float(raw)
    except ValueError:
        raise RuntimeError("REFRESH_INTERVAL_S must be a number") from None
    if value <= 0:
        raise RuntimeError("REFRESH_INTERVAL_S must be greater than 0")
    return value


def get_clock_mode() -> str:
    mode = os.environ.get("REFRESH_CLOCK", "wall").strip().lower() or "wall"
    if mode not in ("wall", "data"):
        raise RuntimeError("REFRESH_CLOCK must be 'wall' or 'data'")
    return mode


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_clock(conn, mode: str, now_fn: Callable[[], datetime] = utc_now) -> ClockDecision:
    """Reference time and untrusted buses of this cycle (contracts/guards.md G3).

    `data`: the newest report among trusted buses; wall clock if no bus ever reported. `wall`: the wall clock.
    """
    if mode == "data":
        rows = conn.execute(_LATEST_BY_BUS).fetchall()
        conn.rollback()
        decision = trusted_clock({bus_id: ts for bus_id, ts in rows}, ESTIMATED_AFTER_S)
        if decision.as_of is not None:
            return decision
    return ClockDecision(now_fn(), frozenset())


def resolve_as_of(conn, mode: str, now_fn: Callable[[], datetime] = utc_now) -> datetime:
    """Reference time of this cycle (see `resolve_clock`)."""
    return resolve_clock(conn, mode, now_fn).as_of


def next_tick(now: float, interval_s: float) -> float:
    """The next interval boundary strictly after `now`."""
    return (math.floor(now / interval_s) + 1) * interval_s


def connect_with_retry(dsn: str, attempts: int = 30, wait_s: float = 2.0,
                       sleep_fn: Callable[[float], None] = time.sleep) -> psycopg.Connection:
    """Open a (non-autocommit) connection, retrying while the database starts."""
    for attempt in range(attempts):
        try:
            return psycopg.connect(dsn)
        except psycopg.OperationalError:
            if attempt < attempts - 1:
                sleep_fn(wait_s)
    raise RuntimeError(f"could not connect to the database after {attempts} attempts") from None


def refresh_once(conn, mode: str, time_fn: Callable[[], float] = time.monotonic,
                 now_fn: Callable[[], datetime] = utc_now, guard_state: dict | None = None) -> None:
    """One cycle with its one log line. CycleError is logged here and swallowed (FR-040)."""
    guard_state = _GUARD_STATE if guard_state is None else guard_state
    started = time_fn()
    decision = resolve_clock(conn, mode, now_fn)
    as_of, untrusted = decision.as_of, sorted(decision.untrusted)
    if decision.untrusted != guard_state["untrusted"]:
        guard_state["untrusted"] = decision.untrusted
        _event(logging.WARNING, event="clock_guard", untrusted_buses=untrusted)
    try:
        result = run_cycle(conn, as_of, untrusted_buses=decision.untrusted)
    except CycleError as exc:
        _event(logging.ERROR, event="refresh_cycle", status="error", error_class=type(exc).__name__,
               correlation_id=exc.correlation_id, as_of_ts=as_of.isoformat(), snapshot_id=None,
               max_bronze_id=None, untrusted_buses=untrusted, duration_ms=round((time_fn() - started) * 1000))
        return
    duration_ms = round((time_fn() - started) * 1000)
    if result is None:
        _event(logging.INFO, event="refresh_cycle", status="skipped", snapshot_id=None,
               as_of_ts=as_of.isoformat(), max_bronze_id=None, untrusted_buses=untrusted,
               duration_ms=duration_ms)
        return
    _event(logging.INFO, event="refresh_cycle", status=result.status, snapshot_id=str(result.snapshot_id),
           as_of_ts=result.as_of_ts.isoformat(), max_bronze_id=result.max_bronze_id, untrusted_buses=untrusted,
           duration_ms=duration_ms, model_ms=round(getattr(result, "model_ms", 0.0), 1))


def run_loop(cycle: Callable[[], None], interval_s: float, time_fn: Callable[[], float] = time.time,
             sleep_fn: Callable[[float], None] = time.sleep, max_ticks: int | None = None) -> None:
    """Run `cycle` on interval boundaries; after a slow cycle, wait for the next future boundary."""
    ticks = 0
    target = next_tick(time_fn(), interval_s)
    while max_ticks is None or ticks < max_ticks:
        sleep_fn(max(0.0, target - time_fn()))
        try:
            cycle()
        except Exception as exc:  # noqa: BLE001 - the loop must survive any cycle failure (FR-040)
            _event(logging.ERROR, event="loop_error", error_class=type(exc).__name__)
        ticks += 1
        target = next_tick(time_fn(), interval_s)


def main() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=get_log_level(), handlers=[handler], force=True)
    interval = get_interval_s()
    mode = get_clock_mode()
    dsn = get_db_dsn()
    conn = connect_with_retry(dsn)
    load_reference(conn)
    conn.commit()
    _event(logging.INFO, event="refresh_started", clock=mode, interval_s=interval)

    def cycle() -> None:
        nonlocal conn
        if conn.closed:
            conn = connect_with_retry(dsn)
        refresh_once(conn, mode)

    run_loop(cycle, interval)


if __name__ == "__main__":
    main()
