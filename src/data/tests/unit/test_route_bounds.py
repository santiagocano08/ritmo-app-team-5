"""T045 (US5, FR-050, FR-051): the route-end bound read by ingestion. FakeConn, no database."""
from __future__ import annotations

import json

import psycopg
import pytest

from src.data.ingestion.route_bounds import REASON, RETRY_AFTER_S, RouteBounds


class Cursor:
    def __init__(self, value) -> None:
        self.value = value

    def fetchone(self):
        return (self.value,)


class FakeConn:
    """`execute` answers from a script: a value, or an exception to raise."""

    def __init__(self, *script, autocommit: bool = True) -> None:
        self.script = list(script)
        self.queries: list[str] = []
        self.rollbacks = 0
        self.autocommit = autocommit

    def execute(self, query, params=None):
        self.queries.append(query)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, BaseException):
            raise item
        return Cursor(item)

    def rollback(self) -> None:
        self.rollbacks += 1


class Clock:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


def make(clock: Clock | None = None, stream=None) -> tuple[RouteBounds, Clock, list[str]]:
    clock = clock or Clock()
    lines: list[str] = []
    return RouteBounds(now_fn=clock, emit=lines.append), clock, lines


def test_reads_the_maximum_distance_of_the_reference_stops() -> None:
    bounds, _, _ = make()
    conn = FakeConn(5119.4)
    assert bounds.get(conn) == 5119.4
    assert "max(distance_along_m)" in conn.queries[0] and "config.ref_stops" in conn.queries[0]


def test_numeric_value_is_returned_as_float() -> None:
    from decimal import Decimal

    bounds, _, _ = make()
    value = bounds.get(FakeConn(Decimal("5119.4")))
    assert value == 5119.4 and isinstance(value, float)


def test_non_empty_read_is_cached_and_not_queried_again() -> None:
    bounds, clock, _ = make()
    conn = FakeConn(5119.4)
    assert bounds.get(conn) == 5119.4
    clock.t += 1000
    assert bounds.get(conn) == 5119.4
    assert len(conn.queries) == 1


def test_empty_table_accepts_and_logs_once_per_outage() -> None:
    bounds, clock, lines = make()
    conn = FakeConn(None)
    assert bounds.get(conn) is None
    assert bounds.get(conn) is None  # inside the 5 s window: no new query, no new line
    assert len(conn.queries) == 1
    clock.t += RETRY_AFTER_S + 0.1
    assert bounds.get(conn) is None  # retried, still down: still the same outage
    assert len(conn.queries) == 2
    assert len(lines) == 1
    line = json.loads(lines[0])
    assert line["event"] == REASON == "route_bound_unavailable"
    assert set(line) <= {"event", "level", "ts"}


def test_retry_is_not_earlier_than_five_seconds() -> None:
    assert RETRY_AFTER_S == 5
    bounds, clock, _ = make()
    conn = FakeConn(None, 5119.4)
    assert bounds.get(conn) is None
    clock.t += 4.9
    assert bounds.get(conn) is None and len(conn.queries) == 1
    clock.t += 0.2
    assert bounds.get(conn) == 5119.4 and len(conn.queries) == 2


def test_undefined_table_accepts_and_rolls_back_a_transaction() -> None:
    bounds, _, lines = make()
    conn = FakeConn(psycopg.errors.UndefinedTable("relation config.ref_stops does not exist"), autocommit=False)
    assert bounds.get(conn) is None
    assert conn.rollbacks == 1  # a failed statement aborts a non-autocommit transaction
    assert len(lines) == 1 and "ref_stops" not in lines[0]


def test_a_new_outage_logs_again_after_a_recovery_is_not_needed_once_cached() -> None:
    bounds, clock, lines = make()
    conn = FakeConn(None, 5119.4)
    bounds.get(conn)
    clock.t += 6
    bounds.get(conn)  # recovers and caches
    clock.t += 1000
    bounds.get(conn)
    assert len(lines) == 1 and len(conn.queries) == 2


def test_operational_error_propagates_for_the_retry_layer() -> None:
    bounds, _, lines = make()
    conn = FakeConn(psycopg.OperationalError("server closed the connection"))
    with pytest.raises(psycopg.OperationalError):
        bounds.get(conn)
    assert lines == []


def test_log_line_has_no_connection_data() -> None:
    bounds, _, lines = make()
    bounds.get(FakeConn(None))
    text = lines[0].lower()
    for forbidden in ("postgres", "password", "host", "dsn", "user"):
        assert forbidden not in text
