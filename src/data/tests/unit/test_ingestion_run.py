"""Unit tests for src/data/ingestion/run.py without a database (T013).

`consume` and `main` are exercised with fake ingest functions and fake connections, so the
stdin -> ingest -> retry -> counts wiring is covered offline.
"""
from __future__ import annotations

import io
import json
from unittest.mock import MagicMock

import psycopg
import pytest

from src.data.ingestion import run as ingestion_run
from src.data.ingestion.bronze import IngestResult
from src.data.ingestion.retry import AuthFailed, Retrier, RetryExhausted, RetryPolicy


def _fast_retrier(total: float = 30.0) -> tuple[Retrier, io.StringIO]:
    out = io.StringIO()
    return Retrier(RetryPolicy(1, 5, total), clock=_Clock(), sleep=lambda s: None, stream=out), out


class _Clock:
    """Advances 1 s per reading, so the window ends without real waiting."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def test_consume_counts_accepted_and_reasons_and_skips_blank() -> None:
    results = {"a": IngestResult(True, bronze_id=1), "b": IngestResult(False, "wrong_type"), "": None}
    counts = ingestion_run.consume(["a", "b", "a", ""], lambda line: results[line])
    assert counts == {"accepted": 2, "wrong_type": 1}


def test_duplicates_are_counted_apart_from_rejections() -> None:
    results = {
        "ok": IngestResult(True, bronze_id=1),
        "bad": IngestResult(False, "wrong_type"),
        "dup": IngestResult(False, "duplicate_event"),
    }
    counts = ingestion_run.consume(["ok", "bad", "bad", "dup", "dup", "dup", "ok"], lambda line: results[line])
    summary = ingestion_run.summarize(counts)
    assert summary["accepted"] == 2
    assert summary["rejected"] == 2
    assert summary["duplicates"] == 3
    assert summary["by_reason"] == {"wrong_type": 2}
    assert "duplicate_event" not in summary["by_reason"]
    assert summary["rejection_rate"] == pytest.approx(2 / 4)


def test_rejection_rate_is_none_when_denominator_is_zero() -> None:
    assert ingestion_run.summarize({})["rejection_rate"] is None
    only_dups = ingestion_run.consume(["d", "d"], lambda line: IngestResult(False, "duplicate_event"))
    summary = ingestion_run.summarize(only_dups)
    assert summary["rejection_rate"] is None and summary["duplicates"] == 2


def test_main_wires_stdin_to_ingest(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@localhost:1/z")
    fake_conn = MagicMock()
    monkeypatch.setattr(ingestion_run.psycopg, "connect", MagicMock(return_value=fake_conn))
    monkeypatch.setattr(
        ingestion_run,
        "ingest_line",
        lambda conn, line: IngestResult(True, bronze_id=1) if line.strip() else None,
    )
    counts = ingestion_run.main(io.StringIO('{"a":1}\n\n{"b":2}\n'))
    assert counts == {"accepted": 2}
    fake_conn.close.assert_called_once()
    assert ingestion_run.psycopg.connect.call_args.kwargs["connect_timeout"] == 3


def _run_main(monkeypatch, lines: list[str], behaviour, retrier=None):
    """Run `main` with a fake `ingest_line`; `behaviour(i, line)` may raise or return a result."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:secretpw@dbhost:1/z")
    conns: list[MagicMock] = []

    def connect(*a, **kw):
        c = MagicMock()
        conns.append(c)
        return c

    monkeypatch.setattr(ingestion_run.psycopg, "connect", connect)
    calls: list[str] = []

    def fake_ingest(conn, line):
        calls.append(line.strip())
        return behaviour(len(calls), line)

    monkeypatch.setattr(ingestion_run, "ingest_line", fake_ingest)
    if retrier is None:
        retrier, _ = _fast_retrier()
    counts = ingestion_run.main(io.StringIO("".join(f"{x}\n" for x in lines)), retrier=retrier)
    return counts, calls, conns


def test_failed_line_is_retried_before_the_next_line_is_read(monkeypatch) -> None:
    seen_failures: list[str] = []

    def behaviour(n: int, line: str):
        if line.strip() == "c" and not seen_failures:
            seen_failures.append(line)
            raise psycopg.errors.lookup("57P01")("terminating")
        return IngestResult(True, bronze_id=n)

    counts, calls, conns = _run_main(monkeypatch, ["a", "b", "c", "d"], behaviour)
    assert calls == ["a", "b", "c", "c", "d"]  # same line again, nothing skipped or reordered
    assert counts == {"accepted": 4}
    assert len(conns) == 2  # one reconnect
    conns[0].close.assert_called_once()


def test_non_retryable_error_exits_unchanged(monkeypatch) -> None:
    def behaviour(n: int, line: str):
        raise psycopg.errors.lookup("42P01")("no table")

    with pytest.raises(psycopg.errors.ProgrammingError):
        _run_main(monkeypatch, ["a", "b"], behaviour)


def test_auth_failure_is_not_retried_and_leaks_nothing(monkeypatch) -> None:
    retrier, out = _fast_retrier(total=120)
    attempts: list[int] = []

    def behaviour(n: int, line: str):
        attempts.append(n)
        raise psycopg.OperationalError(
            'connection failed: connection to server at "dbhost" (10.0.0.1), port 5432 failed: '
            'FATAL:  password authentication failed for user "u" secretpw'
        )

    with pytest.raises(AuthFailed):
        _run_main(monkeypatch, ["a", "b"], behaviour, retrier=retrier)
    assert attempts == [1]
    lines = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [x["event"] for x in lines] == ["db_auth_failed"] and lines[0]["reason"] == "db_auth_failed"
    for forbidden in ("secretpw", "dbhost", "10.0.0.1", "password", "FATAL"):
        assert forbidden not in out.getvalue()


def test_exhaustion_raises_after_one_exhausted_line(monkeypatch) -> None:
    retrier, out = _fast_retrier(total=5)

    def behaviour(n: int, line: str):
        raise psycopg.OperationalError("connection refused to dbhost with secretpw")

    with pytest.raises(RetryExhausted):
        _run_main(monkeypatch, ["a", "b"], behaviour, retrier=retrier)
    events = [json.loads(x)["event"] for x in out.getvalue().splitlines()]
    assert events.count("db_retry_exhausted") == 1 and events[-1] == "db_retry_exhausted"
    assert "secretpw" not in out.getvalue()


def test_invalid_retry_settings_stop_before_any_line_is_read(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@localhost:1/z")
    monkeypatch.setenv("INGESTION_RETRY_TOTAL_S", "abc")
    connect = MagicMock()
    monkeypatch.setattr(ingestion_run.psycopg, "connect", connect)
    stdin = io.StringIO("a\n")
    with pytest.raises(RuntimeError):
        ingestion_run.main(stdin)
    connect.assert_not_called()
    assert stdin.tell() == 0
