"""Retry of the current line through a database outage (feature 003, FR-009 to FR-012).

Stdlib only. The retry wraps the single call that stores one line, so that line is stored again
after a reconnect and the next line is not read before. Log lines carry a fixed reason vocabulary,
the SQLSTATE and counters; they never carry the connection string, the host, the user, a password,
the exception text or any part of an event.
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, TextIO, TypeVar

import psycopg

from src.pulsoflota.config import (
    get_ingestion_retry_initial_s,
    get_ingestion_retry_max_wait_s,
    get_ingestion_retry_total_s,
)

T = TypeVar("T")

CONNECT_TIMEOUT_S = 3
REASONS = ("db_unreachable", "db_connection_lost", "db_shutting_down", "db_starting")


AUTH_REASON = "db_auth_failed"
_AUTH_SQLSTATES = ("28P01", "28000")
_AUTH_MARKERS = ("password authentication failed", "authentication failed")


class AuthFailed(Exception):
    """The database refused the credentials. Never retried; carries no connection data."""


class RetryExhausted(Exception):
    """The retry window ended with the database still unreachable. Carries no connection data."""


@dataclass(frozen=True)
class RetryPolicy:
    initial_s: float = 1.0
    max_wait_s: float = 5.0
    total_s: float = 120.0

    @classmethod
    def from_env(cls) -> "RetryPolicy":
        policy = cls(
            get_ingestion_retry_initial_s(),
            get_ingestion_retry_max_wait_s(),
            get_ingestion_retry_total_s(),
        )
        if policy.initial_s > policy.max_wait_s:
            raise RuntimeError("INGESTION_RETRY_INITIAL_S must be <= INGESTION_RETRY_MAX_WAIT_S")
        if policy.max_wait_s > policy.total_s:
            raise RuntimeError("INGESTION_RETRY_MAX_WAIT_S must be <= INGESTION_RETRY_TOTAL_S")
        return policy

    def wait_for(self, attempt: int) -> float:
        """Wait after failed attempt number `attempt` (>= 1): doubles, capped at max_wait_s."""
        return min(self.initial_s * 2 ** (attempt - 1), self.max_wait_s)


def is_auth_failure(exc: BaseException) -> bool:
    """True for a refused login. psycopg gives sqlstate None at connect, so the libpq text is matched.

    The text is only compared here; it is never stored, logged or re-raised.
    """
    if not isinstance(exc, (psycopg.OperationalError, psycopg.InterfaceError)):
        return False
    if getattr(exc, "sqlstate", None) in _AUTH_SQLSTATES:
        return True
    return any(
        marker in arg.lower() for arg in exc.args if isinstance(arg, str) for marker in _AUTH_MARKERS
    )


def classify(exc: BaseException) -> str | None:
    """Return the generic reason when `exc` is a connection-level failure, else None (do not retry)."""
    if not isinstance(exc, (psycopg.OperationalError, psycopg.InterfaceError)) or is_auth_failure(exc):
        return None
    state = getattr(exc, "sqlstate", None)
    if state is None:
        return "db_unreachable" if isinstance(exc, psycopg.OperationalError) else "db_connection_lost"
    if state == "57P01":
        return "db_shutting_down"
    if state == "57P03":
        return "db_starting"
    if state == "57P02" or state.startswith("08"):
        return "db_connection_lost"
    return None


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Retrier:
    """Runs one operation, retrying connection-level failures inside the policy window."""

    def __init__(
        self,
        policy: RetryPolicy,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        stream: TextIO | None = None,
    ) -> None:
        self.policy = policy
        self._clock = clock
        self._sleep = sleep
        self._stream = stream
        self._started: float | None = None
        self._attempts = 0

    def _emit(self, level: str, event: str, **fields: object) -> None:
        line = {"ts": _ts(), "level": level, "event": event, **fields}
        print(json.dumps(line, separators=(", ", ": ")), file=self._stream or sys.stderr, flush=True)

    def run(self, op: Callable[[], T], reconnect: Callable[[], None] | None = None) -> T:
        need_reconnect = False
        while True:
            try:
                if need_reconnect and reconnect is not None:
                    reconnect()
                result = op()
            except Exception as exc:
                if is_auth_failure(exc):
                    self._emit("error", "db_auth_failed", reason=AUTH_REASON,
                               sqlstate=getattr(exc, "sqlstate", None))
                    raise AuthFailed(AUTH_REASON) from None
                reason = classify(exc)
                if reason is None:
                    raise
                sqlstate = getattr(exc, "sqlstate", None)
                now = self._clock()
                if self._started is None:
                    self._started = now
                self._attempts += 1
                elapsed = now - self._started
                remaining = self.policy.total_s - elapsed
                if remaining <= 0:
                    self._emit("error", "db_retry_exhausted", attempts=self._attempts,
                               elapsed_s=round(elapsed, 3), window_s=self.policy.total_s,
                               reason=reason, sqlstate=sqlstate)
                    raise RetryExhausted(f"database unreachable for {round(elapsed, 1)} s ({reason})") from None
                wait = round(min(self.policy.wait_for(self._attempts), remaining), 6)
                self._emit("warning", "db_retry", attempt=self._attempts, wait_s=wait,
                           elapsed_s=round(elapsed, 3), reason=reason, sqlstate=sqlstate)
                self._sleep(wait)
                need_reconnect = True
                continue
            if self._started is not None:
                self._emit("info", "db_recovered", attempts=self._attempts,
                           outage_s=round(self._clock() - self._started, 3))
                self._started = None
                self._attempts = 0
            return result
