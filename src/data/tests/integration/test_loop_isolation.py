"""T035 — isolation of the hold loop (004 FR-017, FR-028, SC-011; Principle III).

Offline part: with the database unreachable, the simulator with `--holds on` keeps producing every event
of its duration and exits only when the duration ends; the poller logs one failure line per outage.
Live part (`-m live`, host only, dedicated project `pulsoflota-verify` only): with `api`, `refresh` and
the poller side stopped, `bronze.events` keeps growing. Every compose call passes `-p pulsoflota-verify`.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import psycopg
import pytest

from src.data.simulator.engine import run
from src.data.simulator.main import main

ROOT = Path(__file__).resolve().parents[4]
PROJECT = "pulsoflota-verify"
DEAD_DSN = "postgresql://nobody:never-used@127.0.0.1:1/none"


def _digest(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def test_database_down_does_not_delay_or_shorten_the_stream(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", DEAD_DSN)
    monkeypatch.setenv("SIM_HOLD_POLL_S", "0.05")
    monkeypatch.delenv("SIM_SCENARIO_FILE", raising=False)
    buf = io.StringIO()
    started = time.monotonic()
    # 120 steps at 10 ms each: about 1.2 s of wall time, so the poller thread retries about 20 times
    main(["--seed", "42", "--duration", "600", "--holds", "on", "--pace", "0.01"], out=buf)
    elapsed = time.monotonic() - started
    expected = [json.dumps(e, sort_keys=True) for e in run(42, 600)]
    assert buf.getvalue().splitlines() == expected  # every event, none delayed out of the run
    assert 0.5 < elapsed < 30
    err = capsys.readouterr().err
    failed = [x for x in err.splitlines() if "hold_poll_failed" in x]
    assert len(failed) == 1  # one line per outage, not one per retry
    assert "never-used" not in err and "Traceback" not in err and "127.0.0.1" not in err


def test_stream_with_the_poller_stopped_is_the_same_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", DEAD_DSN)
    monkeypatch.delenv("SIM_SCENARIO_FILE", raising=False)
    on, off = io.StringIO(), io.StringIO()
    main(["--seed", "7", "--duration", "900", "--holds", "on"], out=on)
    main(["--seed", "7", "--duration", "900", "--holds", "off"], out=off)
    assert _digest(on.getvalue().splitlines()) == _digest(off.getvalue().splitlines())


def test_ingestion_code_never_imports_the_backend_or_the_poller() -> None:
    """Ingestion does not depend on the backend or on the hold loop (static)."""
    for path in (ROOT / "src" / "data" / "ingestion").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "scenarios.holds" not in text and "src.api" not in text and "gold.instruction_status" not in text, path


def _compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", "-p", PROJECT, *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=120, check=False)


def _count(dsn: str) -> int:
    with psycopg.connect(dsn, autocommit=True, connect_timeout=3) as c:
        return c.execute("SELECT count(*) FROM bronze.events").fetchone()[0]


@pytest.mark.live
def test_bronze_keeps_growing_with_api_refresh_and_poller_stopped(request: pytest.FixtureRequest, db_dsn) -> None:
    if "live" not in (request.config.getoption("-m") or ""):
        pytest.skip("live isolation check: run it explicitly with `-m live`")
    if Path("/.dockerenv").exists() or shutil.which("docker") is None:
        pytest.skip("host only: needs the docker CLI outside the tests container")
    if os.environ.get("COMPOSE_PROJECT_NAME") != PROJECT:
        pytest.skip(f"set COMPOSE_PROJECT_NAME={PROJECT}; never runs against the default stack")

    _compose("stop", "api", "refresh")  # the dedicated project only (-p on this very line)
    running = _compose("ps", "--services", "--filter", "status=running").stdout.split()
    assert "api" not in running and "refresh" not in running and "ingestion" in running
    first = _count(db_dsn)
    assert first > 0, "the stack must already be ingesting"
    time.sleep(12)
    assert _count(db_dsn) > first + 5, "bronze did not grow with the backend side stopped"
