"""T064 — refresh loop: no overlap, skipped late ticks, clock selector, retry, failure survival.

All tests use an injected clock and fake cycles: no database, no real sleeping.
"""
from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import psycopg
import pytest

from src.pipeline.cycle import CycleError, CycleResult
from src.refresh import run as refresh


class FakeClock:
    def __init__(self, start: float) -> None:
        self.t = start
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


class FakeConn:
    """Answers `SELECT max(event_ts) ...` with a fixed value."""

    def __init__(self, value) -> None:
        self.value = value
        self.sql: list[str] = []

    def rollback(self) -> None:
        pass

    def execute(self, query, params=None):
        self.sql.append(query)
        cur = MagicMock()
        cur.fetchone.return_value = (self.value,)
        return cur


NOW = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)


# --- scheduling -----------------------------------------------------------------------------

def test_next_tick_is_the_next_future_boundary() -> None:
    assert refresh.next_tick(100.0, 5) == 105.0
    assert refresh.next_tick(101.2, 5) == 105.0
    assert refresh.next_tick(105.0, 5) == 110.0  # exactly on a boundary: the next one


def test_cycles_never_overlap_and_late_tick_is_skipped_not_queued() -> None:
    clock = FakeClock(start=0.5)
    starts: list[float] = []
    running = {"now": False, "overlap": False}
    durations = iter([7.0, 1.0, 1.0])  # first cycle outlasts one tick (boundary 10)

    def cycle() -> None:
        if running["now"]:
            running["overlap"] = True
        running["now"] = True
        starts.append(clock.time())
        clock.t += next(durations)
        running["now"] = False

    refresh.run_loop(cycle, interval_s=5, time_fn=clock.time, sleep_fn=clock.sleep, max_ticks=3)
    # cycle 1 at 5 (ends 12), tick 10 skipped, cycle 2 at 15 (ends 16), cycle 3 at 20
    assert starts == [5.0, 15.0, 20.0]
    assert running["overlap"] is False


def test_loop_sleeps_to_the_boundary() -> None:
    clock = FakeClock(start=1.0)
    refresh.run_loop(lambda: None, interval_s=5, time_fn=clock.time, sleep_fn=clock.sleep, max_ticks=2)
    assert clock.sleeps == [4.0, 5.0]


# --- failure survival (FR-040) --------------------------------------------------------------

def test_failed_cycle_is_logged_and_next_tick_runs(caplog: pytest.LogCaptureFixture) -> None:
    clock = FakeClock(start=0.0)
    calls = {"n": 0}

    def cycle() -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom with /internal/path")

    with caplog.at_level(logging.INFO, logger="pulsoflota.refresh"):
        refresh.run_loop(cycle, interval_s=5, time_fn=clock.time, sleep_fn=clock.sleep, max_ticks=2)
    assert calls["n"] == 2
    failures = [json.loads(r.getMessage()) for r in caplog.records if "loop_error" in r.getMessage()]
    assert len(failures) == 1
    assert failures[0]["error_class"] == "RuntimeError"
    assert "boom" not in json.dumps(failures[0]) and "Traceback" not in json.dumps(failures[0])
    assert all(r.exc_info is None for r in caplog.records)


# --- clock selector (R3) --------------------------------------------------------------------

def test_clock_mode_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REFRESH_CLOCK", raising=False)
    assert refresh.get_clock_mode() == "wall"
    monkeypatch.setenv("REFRESH_CLOCK", "data")
    assert refresh.get_clock_mode() == "data"
    monkeypatch.setenv("REFRESH_CLOCK", "WALL")
    assert refresh.get_clock_mode() == "wall"
    monkeypatch.setenv("REFRESH_CLOCK", "moon")
    with pytest.raises(RuntimeError):
        refresh.get_clock_mode()


def test_data_mode_uses_newest_non_backend_bus_report() -> None:
    newest = NOW - timedelta(hours=3)
    conn = FakeConn(newest)
    assert refresh.resolve_as_of(conn, "data", lambda: NOW) == newest
    query = conn.sql[0]
    assert "<> 'backend'" in query
    assert "bus_position" in query and "stop_arrival" in query and "stop_departure" in query
    assert "rider_arrival" not in query and "incident" not in query


def test_data_mode_without_bus_reports_falls_back_to_wall_clock() -> None:
    assert refresh.resolve_as_of(FakeConn(None), "data", lambda: NOW) == NOW


def test_wall_mode_uses_injected_clock_and_ignores_the_database() -> None:
    conn = FakeConn(NOW - timedelta(days=1))
    assert refresh.resolve_as_of(conn, "wall", lambda: NOW) == NOW
    assert conn.sql == []


# --- settings -------------------------------------------------------------------------------

def test_interval_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REFRESH_INTERVAL_S", raising=False)
    assert refresh.get_interval_s() == 5.0
    monkeypatch.setenv("REFRESH_INTERVAL_S", "2")
    assert refresh.get_interval_s() == 2.0
    for bad in ("0", "-1", "abc"):
        monkeypatch.setenv("REFRESH_INTERVAL_S", bad)
        with pytest.raises(RuntimeError):
            refresh.get_interval_s()


# --- connect with retry ---------------------------------------------------------------------

def test_connect_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = MagicMock()
    attempts = {"n": 0}

    def fake_connect(dsn: str, **kw):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise psycopg.OperationalError("down")
        return conn

    monkeypatch.setattr(refresh.psycopg, "connect", fake_connect)
    waits: list[float] = []
    assert refresh.connect_with_retry("postgresql://x", attempts=5, wait_s=2.0, sleep_fn=waits.append) is conn
    assert attempts["n"] == 3 and waits == [2.0, 2.0]


def test_connect_gives_up_with_a_generic_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_connect(dsn: str, **kw):
        raise psycopg.OperationalError("password=secret host=db")

    monkeypatch.setattr(refresh.psycopg, "connect", fake_connect)
    with pytest.raises(RuntimeError) as err:
        refresh.connect_with_retry("postgresql://x", attempts=2, wait_s=0, sleep_fn=lambda s: None)
    assert "secret" not in str(err.value)


# --- one cycle step and logging -------------------------------------------------------------

def test_refresh_once_logs_one_json_line_with_the_cycle_fields(
        monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    result = CycleResult(snapshot_id=__import__("uuid").UUID(int=7), as_of_ts=NOW, max_bronze_id=42,
                         status="ok", created=True)
    seen = {}
    monkeypatch.setattr(refresh, "run_cycle", lambda conn, as_of: seen.setdefault("as_of", as_of) and result)
    clock = FakeClock(start=100.0)
    with caplog.at_level(logging.INFO, logger="pulsoflota.refresh"):
        refresh.refresh_once(FakeConn(None), "wall", time_fn=clock.time, now_fn=lambda: NOW)
    assert seen["as_of"] == NOW
    line = json.loads([r.getMessage() for r in caplog.records if "refresh_cycle" in r.getMessage()][0])
    assert set(line) >= {"event", "snapshot_id", "as_of_ts", "max_bronze_id", "duration_ms", "status"}
    assert line["event"] == "refresh_cycle" and line["max_bronze_id"] == 42 and line["status"] == "ok"
    assert line["snapshot_id"] == str(result.snapshot_id)


def test_refresh_once_logs_skip_when_lock_is_held(
        monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(refresh, "run_cycle", lambda conn, as_of: None)
    with caplog.at_level(logging.INFO, logger="pulsoflota.refresh"):
        refresh.refresh_once(FakeConn(None), "wall", time_fn=lambda: 0.0, now_fn=lambda: NOW)
    line = json.loads([r.getMessage() for r in caplog.records if "refresh_cycle" in r.getMessage()][0])
    assert line["status"] == "skipped" and line["snapshot_id"] is None


def test_refresh_once_failure_logs_class_and_correlation_id_only(
        monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    def boom(conn, as_of):
        raise CycleError("abc123")

    monkeypatch.setattr(refresh, "run_cycle", boom)
    with caplog.at_level(logging.INFO, logger="pulsoflota.refresh"):
        refresh.refresh_once(FakeConn(None), "wall", time_fn=lambda: 0.0, now_fn=lambda: NOW)
    line = json.loads([r.getMessage() for r in caplog.records if "refresh_cycle" in r.getMessage()][0])
    assert line["status"] == "error" and line["error_class"] == "CycleError"
    assert line["correlation_id"] == "abc123"
    assert "Traceback" not in json.dumps(line)


def test_json_formatter_passes_json_through_and_wraps_text() -> None:
    fmt = refresh.JsonFormatter()
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, '{"event": "a"}', None, None)
    assert json.loads(fmt.format(rec)) == {"event": "a"}
    rec = logging.LogRecord("x", logging.WARNING, __file__, 1, "plain %s", ("text",), None)
    out = json.loads(fmt.format(rec))
    assert out["message"] == "plain text" and out["level"] == "WARNING"
    try:
        raise ValueError("x")
    except ValueError:
        import sys
        rec = logging.LogRecord("x", logging.ERROR, __file__, 1, "bad", None, sys.exc_info())
    assert "Traceback" not in fmt.format(rec)
    assert isinstance(io.StringIO(), io.StringIO)
