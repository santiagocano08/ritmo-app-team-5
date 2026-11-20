"""T066 — a failed refresh cycle publishes nothing, logs a safe error line, and the next cycle works."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import psycopg
import pytest

from src.refresh import run as refresh

T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)


def test_forced_failure_leaves_no_snapshot_no_notification_and_recovers(
        gold_conn, module_db_dsn, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    with psycopg.connect(module_db_dsn, autocommit=True) as listener:
        listener.execute("LISTEN gold_snapshot")

        def boom(*args, **kwargs):
            raise ValueError("internal detail /secret/path")

        with monkeypatch.context() as m:
            m.setattr("src.pipeline.gold.build_snapshot", boom)
            with caplog.at_level(logging.INFO):
                refresh.refresh_once(gold_conn, "wall", now_fn=lambda: T0)
        assert gold_conn.execute("SELECT count(*) FROM gold.snapshots").fetchone()[0] == 0
        gold_conn.rollback()  # run_cycle needs an idle connection
        assert list(listener.notifies(timeout=0.5, stop_after=1)) == []

        lines = [json.loads(r.getMessage()) for r in caplog.records if r.getMessage().startswith("{")]
        errors = [x for x in lines if x.get("event") == "refresh_cycle" and x.get("status") == "error"]
        assert len(errors) == 1
        assert errors[0]["error_class"] == "CycleError" and errors[0]["correlation_id"]
        cycle_failed = [x for x in lines if x.get("event") == "cycle_failed"]
        assert cycle_failed and cycle_failed[0]["error_class"] == "ValueError"
        text = " ".join(r.getMessage() for r in caplog.records)
        assert "Traceback" not in text and "/secret/path" not in text
        assert all(r.exc_info is None for r in caplog.records)

        refresh.refresh_once(gold_conn, "wall", now_fn=lambda: T0)
        assert gold_conn.execute("SELECT count(*) FROM gold.snapshots").fetchone()[0] == 1
        assert len(list(listener.notifies(timeout=2, stop_after=1))) == 1
