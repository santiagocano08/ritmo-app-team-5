"""Unit tests for src/data/ingestion/retry.py (T011, T012): policy, classification, backoff, log lines.

No database and no real sleeping: a fake clock advances when the code "sleeps".
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import psycopg
import pytest
from jsonschema import Draft202012Validator

from src.data.ingestion import retry
from src.data.ingestion.retry import (
    REASONS,
    AuthFailed,
    Retrier,
    RetryExhausted,
    RetryPolicy,
    classify,
    is_auth_failure,
)
from src.pulsoflota import config

ROOT = Path(__file__).resolve().parents[4]
SCHEMA = json.loads(
    (ROOT / "specs/003-ops-ci-reliability/contracts/ingestion-retry-log.schema.json").read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator(SCHEMA)

ENV_NAMES = ("INGESTION_RETRY_INITIAL_S", "INGESTION_RETRY_MAX_WAIT_S", "INGESTION_RETRY_TOTAL_S")


def _err(sqlstate: str | None, message: str = "boom") -> Exception:
    if sqlstate is None:
        return psycopg.OperationalError(message)
    return psycopg.errors.lookup(sqlstate)(message)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _retrier(total: float = 120, initial: float = 1, max_wait: float = 5):
    clock = FakeClock()
    out = io.StringIO()
    r = Retrier(RetryPolicy(initial, max_wait, total), clock=clock, sleep=clock.sleep, stream=out)
    return r, clock, out


def _lines(out: io.StringIO) -> list[dict]:
    return [json.loads(x) for x in out.getvalue().splitlines()]


# -- config ---------------------------------------------------------------------------------

def test_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    assert config.get_ingestion_retry_initial_s() == 1
    assert config.get_ingestion_retry_max_wait_s() == 5
    assert config.get_ingestion_retry_total_s() == 120
    policy = RetryPolicy.from_env()
    assert (policy.initial_s, policy.max_wait_s, policy.total_s) == (1, 5, 120)
    assert policy.total_s >= 31  # the drill outage (SC-004)


@pytest.mark.parametrize("value", ["abc", "0", "-1", "nan", "inf", ""])
@pytest.mark.parametrize("name", ENV_NAMES)
def test_invalid_single_value_raises(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        RetryPolicy.from_env()


@pytest.mark.parametrize(
    "env",
    [
        {"INGESTION_RETRY_INITIAL_S": "10", "INGESTION_RETRY_MAX_WAIT_S": "5"},
        {"INGESTION_RETRY_MAX_WAIT_S": "200", "INGESTION_RETRY_TOTAL_S": "120"},
    ],
)
def test_inconsistent_values_raise(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with pytest.raises(RuntimeError):
        RetryPolicy.from_env()


# -- classification ---------------------------------------------------------------------------

@pytest.mark.parametrize("sqlstate", [None, "08000", "08006", "08001", "57P01", "57P02", "57P03"])
def test_retryable(sqlstate: str | None) -> None:
    assert classify(_err(sqlstate)) in REASONS


def test_interface_error_is_retryable() -> None:
    assert classify(psycopg.InterfaceError("closed")) == "db_connection_lost"


@pytest.mark.parametrize(
    "exc",
    [
        psycopg.errors.lookup("22003")("x"),  # DataError
        psycopg.errors.lookup("23505")("x"),  # IntegrityError
        psycopg.errors.lookup("42P01")("x"),  # ProgrammingError
        psycopg.errors.lookup("53100")("x"),  # disk full (OperationalError, not retried)
        psycopg.errors.lookup("57014")("x"),  # query canceled
        ValueError("x"),
    ],
)
def test_not_retryable(exc: Exception) -> None:
    assert classify(exc) is None


def test_reason_vocabulary_is_fixed() -> None:
    assert set(REASONS) == {"db_unreachable", "db_connection_lost", "db_shutting_down", "db_starting"}
    assert classify(_err(None)) == "db_unreachable"
    assert classify(_err("57P01")) == "db_shutting_down"
    assert classify(_err("57P03")) == "db_starting"
    assert classify(_err("08006")) == "db_connection_lost"


# -- backoff ----------------------------------------------------------------------------------

def test_wait_sequence_and_last_attempt_at_window_end() -> None:
    r, clock, out = _retrier(total=17)
    calls = 0

    def op() -> None:
        nonlocal calls
        calls += 1
        raise _err("57P01")

    with pytest.raises(RetryExhausted):
        r.run(op)
    assert clock.sleeps == [1, 2, 4, 5, 5]
    assert calls == 6  # first try + one after each wait; the last falls at 17 s


def test_last_wait_is_shortened_to_the_window() -> None:
    r, clock, _ = _retrier(total=14)
    with pytest.raises(RetryExhausted):
        r.run(lambda: (_ for _ in ()).throw(_err(None)))
    assert clock.sleeps == [1, 2, 4, 5, 2]
    assert sum(clock.sleeps) == 14


def test_non_retryable_is_raised_unchanged_without_logs() -> None:
    r, clock, out = _retrier()
    exc = psycopg.errors.lookup("22003")("x")
    with pytest.raises(type(exc)) as info:
        r.run(lambda: (_ for _ in ()).throw(exc))
    assert info.value is exc
    assert clock.sleeps == [] and out.getvalue() == ""


def test_reconnect_runs_before_each_new_attempt_and_can_fail() -> None:
    r, clock, out = _retrier()
    events: list[str] = []
    state = {"down": 3}

    def reconnect() -> None:
        events.append("reconnect")
        if state["down"] > 0:
            state["down"] -= 1
            raise _err(None)

    def op() -> str:
        events.append("op")
        if not events.count("op") > 1:
            raise _err("57P01")
        return "stored"

    assert r.run(op, reconnect=reconnect) == "stored"
    assert events == ["op", "reconnect", "reconnect", "reconnect", "reconnect", "op"]
    assert [x["event"] for x in _lines(out)] == ["db_retry"] * 4 + ["db_recovered"]


# -- log lines (T012) -------------------------------------------------------------------------

def test_one_valid_retry_line_per_failed_attempt_and_one_recovered() -> None:
    r, clock, out = _retrier()
    n = {"c": 0}

    def op() -> str:
        n["c"] += 1
        if n["c"] <= 3:
            raise _err("57P03")
        return "ok"

    r.run(op)
    lines = _lines(out)
    assert [x["event"] for x in lines] == ["db_retry", "db_retry", "db_retry", "db_recovered"]
    for line in lines:
        VALIDATOR.validate(line)
    assert [x["attempt"] for x in lines[:3]] == [1, 2, 3]
    assert [x["wait_s"] for x in lines[:3]] == [1, 2, 4]
    assert lines[0]["reason"] == "db_starting" and lines[0]["sqlstate"] == "57P03"
    assert lines[-1]["attempts"] == 3 and lines[-1]["outage_s"] == 7
    # the outage state resets after recovery: a later success logs nothing
    r.run(lambda: "ok")
    assert len(_lines(out)) == 4


def test_exhaustion_line() -> None:
    r, clock, out = _retrier(total=3)
    with pytest.raises(RetryExhausted):
        r.run(lambda: (_ for _ in ()).throw(_err(None)))
    lines = _lines(out)
    assert [x["event"] for x in lines] == ["db_retry", "db_retry", "db_retry_exhausted"]
    for line in lines:
        VALIDATOR.validate(line)
    last = lines[-1]
    assert last["window_s"] == 3 and last["attempts"] == 3 and last["sqlstate"] is None


def test_log_lines_never_carry_secrets_or_exception_text() -> None:
    secret = "host=secret-db.internal user=admin password=hunter2 postgresql://admin:hunter2@secret-db.internal/pf"
    r, clock, out = _retrier(total=5)
    with pytest.raises(RetryExhausted) as info:
        r.run(lambda: (_ for _ in ()).throw(psycopg.OperationalError(secret)))
    text = out.getvalue() + str(info.value)
    for forbidden in ("hunter2", "secret-db", "admin", "postgresql://", "password"):
        assert forbidden not in text


def test_schema_rejects_crafted_invalid_lines() -> None:
    good = {"ts": "2026-11-21T05:00:00.000Z", "level": "warning", "event": "db_retry", "attempt": 1,
            "wait_s": 1, "elapsed_s": 0, "reason": "db_unreachable", "sqlstate": None}
    VALIDATOR.validate(good)
    for bad in (
        {**good, "reason": "connection to 10.0.0.1 refused"},
        {**good, "dsn": "postgresql://x"},
        {**good, "ts": "2026-11-21T05:00:00+00:00"},
        {k: v for k, v in good.items() if k != "attempt"},
    ):
        assert not VALIDATOR.is_valid(bad)


def test_module_uses_no_exception_text() -> None:
    source = Path(retry.__file__).read_text(encoding="utf-8")
    assert "str(exc" not in source and "%s\" % exc" not in source


# -- authentication failure at connect: never retried ---------------------------------------------

# Real psycopg message shape (libpq text): sqlstate is None on a failed connect.
AUTH_MESSAGE = (
    'connection failed: connection to server at "secret-db.internal" (10.9.8.7), port 5432 failed: '
    'FATAL:  password authentication failed for user "admin"'
)


@pytest.mark.parametrize(
    "exc",
    [
        psycopg.OperationalError(AUTH_MESSAGE),
        psycopg.OperationalError("FATAL:  authentication failed"),
        psycopg.errors.lookup("28P01")("x"),
        psycopg.errors.lookup("28000")("x"),
    ],
)
def test_auth_failure_is_detected_and_not_classified_as_retryable(exc: Exception) -> None:
    assert is_auth_failure(exc)
    assert classify(exc) is None


def test_plain_unreachable_is_not_an_auth_failure() -> None:
    assert not is_auth_failure(psycopg.OperationalError("connection refused"))


def test_auth_failure_stops_at_once_with_one_clean_line() -> None:
    r, clock, out = _retrier(total=120)
    calls = []

    def op():
        calls.append(1)
        raise psycopg.OperationalError(AUTH_MESSAGE)

    with pytest.raises(AuthFailed) as info:
        r.run(op)
    assert len(calls) == 1 and clock.sleeps == []
    lines = _lines(out)
    assert len(lines) == 1
    VALIDATOR.validate(lines[0])
    assert lines[0]["event"] == "db_auth_failed" and lines[0]["reason"] == "db_auth_failed"
    text = out.getvalue() + str(info.value)
    for forbidden in ("secret-db", "10.9.8.7", "admin", "password", "authentication", "FATAL", "5432"):
        assert forbidden not in text
