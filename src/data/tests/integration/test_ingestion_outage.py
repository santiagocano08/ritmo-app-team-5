"""T015 — ingestion against a real PostgreSQL on a throwaway database (R10).

- a real 57P01 (pg_terminate_backend) between two lines: ingestion reconnects, order is kept, no gap
- a replayed line is stored once in bronze.events and once as `duplicate_event`, bronze unchanged
- contract rejections and duplicates are reported separately
"""
from __future__ import annotations

import io
import json
import pathlib
import uuid

import psycopg
import pytest

from src.data.ingestion import run as ingestion_run
from src.data.ingestion.retry import Retrier, RetryPolicy

EXAMPLES = pathlib.Path(__file__).resolve().parents[4] / "contracts" / "turn1-events" / "examples" / "valid"


def _event(n: int) -> str:
    msg = json.loads((EXAMPLES / "bus_position.json").read_text())
    msg["event_id"] = str(uuid.UUID(int=n))
    return json.dumps(msg)


@pytest.fixture()
def clean(module_db_dsn):
    with psycopg.connect(module_db_dsn, autocommit=True) as c:
        c.execute("TRUNCATE bronze.events, bronze.rejections RESTART IDENTITY")
    yield module_db_dsn


def _retrier() -> Retrier:
    return Retrier(RetryPolicy(0.05, 0.2, 10), stream=io.StringIO())


def _ids(dsn: str) -> list[str]:
    with psycopg.connect(dsn) as c:
        return [str(r[0]) for r in c.execute("SELECT event_id FROM bronze.events ORDER BY id")]


def test_backend_terminated_between_lines_keeps_order_and_leaves_no_gap(clean, monkeypatch) -> None:
    dsn = clean
    monkeypatch.setenv("DATABASE_URL", dsn)
    lines = [_event(i) for i in range(1, 9)]
    killer = psycopg.connect(dsn, autocommit=True)
    real_connect = psycopg.connect
    state = {"killed": 0}
    original = ingestion_run.ingest_line

    def ingest_and_kill(conn, line):
        result = original(conn, line)
        if json.loads(line)["event_id"] == str(uuid.UUID(int=4)) and not state["killed"]:
            pid = conn.info.backend_pid
            killer.execute("SELECT pg_terminate_backend(%s)", (pid,))
            state["killed"] = 1
        return result

    monkeypatch.setattr(ingestion_run, "ingest_line", ingest_and_kill)
    monkeypatch.setattr(ingestion_run.psycopg, "connect", real_connect)
    try:
        counts = ingestion_run.main(io.StringIO("\n".join(lines) + "\n"), retrier=_retrier())
    finally:
        killer.close()
    assert state["killed"] == 1
    assert counts["accepted"] == 8
    assert _ids(dsn) == [str(uuid.UUID(int=i)) for i in range(1, 9)]


def test_replayed_line_is_stored_once_and_recorded_as_duplicate(clean, monkeypatch) -> None:
    dsn = clean
    monkeypatch.setenv("DATABASE_URL", dsn)
    lines = [_event(1), _event(2), _event(1), "not json"]
    counts = ingestion_run.main(io.StringIO("\n".join(lines) + "\n"), retrier=_retrier())
    summary = ingestion_run.summarize(counts)
    assert summary["accepted"] == 2 and summary["duplicates"] == 1 and summary["rejected"] == 1
    assert summary["by_reason"] == {"wrong_type": 1}
    assert summary["rejection_rate"] == pytest.approx(1 / 3)
    with psycopg.connect(dsn) as c:
        assert c.execute("SELECT count(*) FROM bronze.events").fetchone()[0] == 2
        assert c.execute("SELECT count(*) FROM bronze.rejections WHERE reason='duplicate_event'").fetchone()[0] == 1
    # replay the whole batch: bronze.events is unchanged
    before = _ids(dsn)
    ingestion_run.main(io.StringIO("\n".join(lines) + "\n"), retrier=_retrier())
    assert _ids(dsn) == before
