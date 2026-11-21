"""T030 — live freshness check. Host only, dedicated compose project only.

Run: `COMPOSE_PROJECT_NAME=pulsoflota-verify uv run pytest src/data/tests/integration/test_ingestion_feed_live.py -m live -s`
Freezes the simulator with SIGSTOP inside the `ingestion` container of the dedicated project and
checks the view and the Docker health transitions. Never touches the default stack.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

import psycopg
import pytest

pytestmark = pytest.mark.live
ROOT = Path(__file__).resolve().parents[4]
PROJECT = "pulsoflota-verify"
THRESHOLD_S, INTERVAL_S = 15, 5


def _compose(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args], cwd=ROOT, input=stdin, capture_output=True,
                          text=True, timeout=60, check=True)


def _control(action: str) -> None:
    script = (ROOT / "scripts" / "drill" / "feed_control.py").read_text(encoding="utf-8")
    _compose("exec", "-T", "ingestion", "python", "-", action, stdin=script)


def _inspect(fmt: str) -> str:
    cid = _compose("ps", "-q", "ingestion").stdout.strip()
    return subprocess.run(["docker", "inspect", "-f", fmt, cid], capture_output=True, text=True,
                          timeout=30, check=True).stdout.strip()


def _health() -> dict:
    return json.loads(_inspect("{{json .State.Health}}"))


def _parse(ts: str) -> datetime:
    head, _, rest = ts.partition(".")
    frac = "".join(ch for ch in rest if ch.isdigit())[:6]
    return datetime.fromisoformat(f"{head}.{frac or '0'}+00:00")


def _view(dsn: str) -> dict:
    with psycopg.connect(dsn) as c:
        cur = c.execute("SELECT * FROM ops.ingestion_health")
        row = cur.fetchone()
        return dict(zip([d.name for d in cur.description], row))


def test_freezing_the_feed_turns_ingestion_unhealthy_and_resuming_recovers(request, db_dsn) -> None:
    if "live" not in (request.config.getoption("-m") or ""):
        pytest.skip("live freshness check: run it explicitly with `-m live`")
    if Path("/.dockerenv").exists() or shutil.which("docker") is None:
        pytest.skip("host only: needs the docker CLI outside the tests container")
    if os.environ.get("COMPOSE_PROJECT_NAME") != PROJECT:
        pytest.skip(f"set COMPOSE_PROJECT_NAME={PROJECT}; never runs against the default stack")

    view = _view(db_dsn)
    assert view["last_insert_age_s"] is not None and view["last_insert_age_s"] < THRESHOLD_S
    assert view["events_60s"] > 0
    assert view["rejection_rate_60s"] is None or view["rejection_rate_60s"] >= 0
    assert _health()["Status"] == "healthy"

    restarts, started = _inspect("{{.RestartCount}}"), _inspect("{{.State.StartedAt}}")
    with psycopg.connect(db_dsn) as c:
        last_insert = c.execute("SELECT max(arrival_ts) FROM bronze.events").fetchone()[0]

    _control("stop")
    first_failed_end = None
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and first_failed_end is None:
            time.sleep(1)
            for entry in _health().get("Log", []):
                if entry["ExitCode"] != 0:
                    end = _parse(entry["End"])
                    if end >= last_insert:
                        first_failed_end = end
                        probe_s = (_parse(entry["End"]) - _parse(entry["Start"])).total_seconds()
                        break
        assert first_failed_end is not None, "ingestion never became unhealthy"
        assert _health()["Status"] == "unhealthy"
        delay = (first_failed_end - last_insert).total_seconds()
        print(f"unhealthy after {delay:.1f}s (bound {THRESHOLD_S}+{INTERVAL_S}+probe {probe_s:.2f}s)")
        assert delay <= THRESHOLD_S + INTERVAL_S + probe_s + 1.0
    finally:
        _control("resume")

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and _health()["Status"] != "healthy":
        time.sleep(1)
    assert _health()["Status"] == "healthy"
    assert _inspect("{{.RestartCount}}") == restarts
    assert _inspect("{{.State.StartedAt}}") == started
