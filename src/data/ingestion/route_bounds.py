"""Route-end bound for the ingestion range check (feature 005, US5, FR-050, FR-051; contracts/guards.md G1).

The bound is `max(distance_along_m)` of `config.ref_stops`, read on the ingestion connection and cached
after the first non-empty read. While it cannot be read (table empty, schema missing) the event is
accepted, the read is retried no earlier than `RETRY_AFTER_S` later, and one fixed-vocabulary line is
written per outage: it carries no connection data. A connection-level error is not swallowed here: the
retry layer of feature 003 reconnects and stores the same line again.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from typing import Callable

import psycopg

REASON = "route_bound_unavailable"
RETRY_AFTER_S = 5

_QUERY = "SELECT max(distance_along_m) FROM config.ref_stops"


def _emit_stderr(line: str) -> None:
    print(line, file=sys.stderr, flush=True)


class RouteBounds:
    """The cached route end. One instance per ingestion process (`DEFAULT`); tests build their own."""

    def __init__(self, now_fn: Callable[[], float] = time.monotonic,
                 emit: Callable[[str], None] = _emit_stderr) -> None:
        self._now = now_fn
        self._emit = emit
        self._bound: float | None = None
        self._next_try: float = 0.0
        self._outage_logged = False

    def get(self, conn) -> float | None:
        """The route end in meters, or None while it is unreadable (the event is then accepted)."""
        if self._bound is not None:
            return self._bound
        now = self._now()
        if now < self._next_try:
            return None
        try:
            value = conn.execute(_QUERY).fetchone()[0]
        except psycopg.errors.UndefinedTable:
            if not getattr(conn, "autocommit", True):
                conn.rollback()  # a failed statement aborts the open transaction
            value = None
        if value is None:
            self._next_try = now + RETRY_AFTER_S
            if not self._outage_logged:
                self._outage_logged = True
                ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                self._emit(json.dumps({"ts": ts, "level": "warning", "event": REASON},
                                      separators=(", ", ": ")))
            return None
        self._bound = float(value)
        self._outage_logged = False
        return self._bound


DEFAULT = RouteBounds()
