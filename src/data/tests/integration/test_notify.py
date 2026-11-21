"""T067 — one NOTIFY per new snapshot, payload valid against the notify schema, snapshot readable."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema
import psycopg

from src.data.refresh import run as refresh

ROOT = Path(__file__).resolve().parents[4]
SCHEMA = json.loads((ROOT / "specs/002-silver-gold-baselines/contracts/gold_snapshot_notify.schema.json")
                    .read_text(encoding="utf-8"))
T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)


def test_one_valid_notification_per_new_snapshot(gold_conn, module_db_dsn) -> None:
    validator = jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.FormatChecker())
    with psycopg.connect(module_db_dsn, autocommit=True) as listener:
        listener.execute("LISTEN gold_snapshot")
        times = [T0, T0 + timedelta(seconds=5), T0 + timedelta(seconds=10)]
        for t in times:
            refresh.refresh_once(gold_conn, "wall", now_fn=lambda t=t: t)
        refresh.refresh_once(gold_conn, "wall", now_fn=lambda: times[-1])  # same identity: no notify

        received = list(listener.notifies(timeout=2, stop_after=10))
        assert len(received) == 3
        for note in received:
            payload = json.loads(note.payload)
            validator.validate(payload)
            row = gold_conn.execute("SELECT 1 FROM gold.corridor_now WHERE snapshot_id = %s",
                                    (payload["snapshot_id"],)).fetchone()
            assert row is not None  # readable on receipt
        assert len({json.loads(n.payload)["snapshot_id"] for n in received}) == 3
