"""T016 — live outage check. Host only, dedicated compose project only.

Run: `COMPOSE_PROJECT_NAME=pulsoflota-verify uv run pytest src/data/tests/integration/test_ingestion_outage_live.py -m live`
It stops and starts `db` of the dedicated project `pulsoflota-verify`; it refuses to run against any
other project, inside the `tests` container, or without `-m live`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psycopg
import pytest

pytestmark = pytest.mark.live
ROOT = Path(__file__).resolve().parents[4]
PROJECT = "pulsoflota-verify"
OUTAGE_S = 30


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=120, check=check)


def _inspect(fmt: str) -> str:
    cid = _compose("ps", "-q", "ingestion").stdout.strip()
    return subprocess.run(["docker", "inspect", "-f", fmt, cid], capture_output=True, text=True,
                          timeout=30, check=True).stdout.strip()


def test_ingestion_survives_a_30_s_database_outage(request: pytest.FixtureRequest, db_dsn) -> None:
    if "live" not in (request.config.getoption("-m") or ""):
        pytest.skip("live outage check: run it explicitly with `-m live`")
    if Path("/.dockerenv").exists() or shutil.which("docker") is None:
        pytest.skip("host only: needs the docker CLI outside the tests container")
    if os.environ.get("COMPOSE_PROJECT_NAME") != PROJECT:
        pytest.skip(f"set COMPOSE_PROJECT_NAME={PROJECT}; never runs against the default stack")

    restarts = _inspect("{{.RestartCount}}")
    started = _inspect("{{.State.StartedAt}}")
    sim_pid = _compose("exec", "-T", "ingestion", "sh", "-c", "pgrep -f src.data.simulator.main | head -1").stdout.strip()
    with psycopg.connect(db_dsn, autocommit=True) as c:
        before = c.execute("SELECT coalesce(max(id),0) FROM bronze.events").fetchone()[0]
    assert before > 0, "the stack must already be ingesting"

    _compose("stop", "db")
    try:
        time.sleep(OUTAGE_S)
    finally:
        _compose("start", "db")

    deadline = time.monotonic() + 60
    after = before
    while time.monotonic() < deadline:
        time.sleep(2)
        try:
            with psycopg.connect(db_dsn, autocommit=True, connect_timeout=3) as c:
                after = c.execute("SELECT coalesce(max(id),0) FROM bronze.events").fetchone()[0]
        except psycopg.OperationalError:
            continue
        if after > before + 5:
            break
    assert after > before + 5, "bronze did not grow again after the outage"

    assert _inspect("{{.RestartCount}}") == restarts
    assert _inspect("{{.State.StartedAt}}") == started
    assert _compose("exec", "-T", "ingestion", "sh", "-c", "pgrep -f src.data.simulator.main | head -1").stdout.strip() == sim_pid

    with psycopg.connect(db_dsn) as c:
        ids = [str(r[0]) for r in c.execute("SELECT event_id FROM bronze.events ORDER BY id")]
    seed = os.environ.get("SIM_SEED", "42")
    sim = subprocess.run([sys.executable, "-m", "src.data.simulator.main", "--seed", seed, "--duration", "3600", "--pace", "0"],
                         cwd=ROOT, capture_output=True, text=True, timeout=120, check=True,
                         env={**os.environ, "PYTHONPATH": str(ROOT)})
    expected = [json.loads(x)["event_id"] for x in sim.stdout.splitlines() if x.strip()][: len(ids)]
    assert ids == expected, "stored event order differs from the seeded stream (gap, replay or restart)"

    logs = _compose("logs", "--no-color", "ingestion").stdout
    retry_lines = [x[x.index("{"):] for x in logs.splitlines() if '"event": "db_retry"' in x or '"event":"db_retry"' in x]
    assert retry_lines, "no db_retry lines in the ingestion logs"
    for raw in retry_lines:
        data = json.loads(raw)
        assert data["event"] == "db_retry" and data["reason"] in {
            "db_unreachable", "db_connection_lost", "db_shutting_down", "db_starting"}
    for secret_marker in ("postgresql://", "password", os.environ.get("POSTGRES_PASSWORD", "\0")):
        assert secret_marker not in "\n".join(retry_lines)
    assert re.search(r'"event": ?"db_recovered"', logs)
