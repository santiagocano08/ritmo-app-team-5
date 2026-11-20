"""T068 — SC-009 live cadence. Needs the compose stack up with `REFRESH_CLOCK=data`.

Run: `pytest tests/integration/test_refresh_live.py -m live` (about 10 minutes). Listens on the
compose database; it never writes to it.
"""
from __future__ import annotations

import os
import time

import psycopg
import pytest

pytestmark = pytest.mark.live

DURATION_S = float(os.environ.get("LIVE_CADENCE_DURATION_S", "600"))


def test_notifications_arrive_every_5_s_and_are_readable(request: pytest.FixtureRequest, db_dsn) -> None:
    if "live" not in (request.config.getoption("-m") or ""):
        pytest.skip("10-minute live check: run it explicitly with `-m live`")
    times: list[float] = []
    with psycopg.connect(db_dsn, autocommit=True) as listener, psycopg.connect(db_dsn) as reader:
        listener.execute("LISTEN gold_snapshot")
        end = time.monotonic() + DURATION_S
        while time.monotonic() < end:
            for note in listener.notifies(timeout=1, stop_after=1):
                times.append(time.monotonic())
                sid = note.payload and __import__("json").loads(note.payload)["snapshot_id"]
                assert reader.execute("SELECT 1 FROM gold.corridor_now WHERE snapshot_id = %s",
                                      (sid,)).fetchone() is not None
                reader.rollback()
    assert len(times) >= 2, "no notifications: is the refresh service running?"
    intervals = [b - a for a, b in zip(times, times[1:])]
    ok = sum(1 for i in intervals if 4.0 <= i <= 6.0)
    print(f"notifications={len(times)} intervals: min={min(intervals):.2f} max={max(intervals):.2f} "
          f"within_5s±1s={ok}/{len(intervals)}")
    assert ok / len(intervals) >= 0.95
