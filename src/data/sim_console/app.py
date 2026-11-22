"""Local simulation control console (data team test harness, not part of the product).

Starts and stops simulator runs on an isolated compose project (`pfsim`) and shows what the
data platform produces: snapshots, corridor state, EWT, recommendations, holds and projection
accuracy. Approve/discard goes through the command door of the data contract (§4.1–§4.2):
a `decision` event INSERTed into `bronze.events`, validated against
`contracts/read/command_event.schema.json`.

Safety rules:
- binds to 127.0.0.1 only; never expose it on a network interface;
- runs only fixed `docker compose` argument lists on project `pfsim` (no shell, no free text);
- every run parameter is validated against an allow-list or a numeric range;
- never touches the default stack or its `db_data` volume.

Run from the repository root:
    cp src/data/sim_console/.pfsim.env.example src/data/sim_console/.pfsim.env   # once
    uv run --frozen python -m src.data.sim_console.app   # then open http://127.0.0.1:8090
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import jsonschema
import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".pfsim.env"
RUNS_DIR = HERE / "runs"
SCENARIO_DIR = ROOT / "src/data/tests/fixtures/scenarios"
COMMAND_SCHEMA = ROOT / "contracts/read/command_event.schema.json"
PROJECT = "pfsim"
COMPOSE = ["docker", "compose", "-p", PROJECT, "--env-file", str(ENV_FILE),
           "-f", str(ROOT / "docker-compose.yml"), "-f", str(HERE / "compose.sim.yml")]
HOST = "127.0.0.1"
PORT = int(os.environ.get("SIM_CONSOLE_PORT", "8090"))
USER_ID = "sim-console"


# ---------------------------------------------------------------------------------- config
def _read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        raise SystemExit(f"missing {ENV_FILE}: copy {ENV_FILE.name}.example next to it and set POSTGRES_PASSWORD")
    env: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


ENV = _read_env()
DSN = (f"postgresql://{ENV['POSTGRES_USER']}:{ENV['POSTGRES_PASSWORD']}@127.0.0.1:"
       f"{ENV.get('POSTGRES_PORT', '56432')}/{ENV['POSTGRES_DB']}")


def scenarios() -> list[str]:
    return ["none"] + sorted(p.stem for p in SCENARIO_DIR.glob("*.json"))


class RunConfig(BaseModel):
    scenario: str = "c1_bunching"
    demand_scale: float = Field(3.0, ge=0.1, le=10.0)
    seed: int = Field(42, ge=0, le=2**31 - 1)
    duration_s: int = Field(2700, ge=300, le=14400)
    pace_s: float = Field(1.0, ge=0.0, le=5.0)
    holds: bool = True
    mpc: bool = True


class Decision(BaseModel):
    rec_id: uuid.UUID
    action: Literal["apply", "discard"]


# ------------------------------------------------------------------------------ run control
STATE: dict[str, Any] = {"phase": "idle", "message": "", "config": None, "started_at": None}
LOCK = threading.Lock()


def _compose(*args: str, extra_env: dict[str, str] | None = None, timeout: int = 600) -> str:
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}  # shell would override the env file
    env.update(extra_env or {})
    out = subprocess.run([*COMPOSE, *args], cwd=ROOT, env=env, capture_output=True, text=True,
                         timeout=timeout, check=False)
    if out.returncode != 0:
        raise RuntimeError((out.stderr or out.stdout).strip()[-600:])
    return out.stdout


def _set(phase: str, message: str = "") -> None:
    STATE["phase"], STATE["message"] = phase, message


def _start_run(cfg: RunConfig) -> None:
    try:
        sim_env = {
            "SIM_SEED": str(cfg.seed),
            "SIM_DURATION_S": str(cfg.duration_s),
            "SIM_PACE_S": str(cfg.pace_s),
            "SIM_DEMAND_SCALE": str(cfg.demand_scale),
            "SIM_SCENARIO_FILE": "" if cfg.scenario == "none" else f"/scn/{cfg.scenario}.json",
            "SIM_HOLDS": "on" if cfg.holds else "off",
            "MPC_ENABLED": "on" if cfg.mpc else "off",
        }
        _set("starting", "resetting the pfsim database")
        _compose("down", "-v", "--remove-orphans")
        _set("starting", "starting db and refresh (first build can take a minute)")
        _compose("up", "-d", "--build", "db", "refresh", extra_env=sim_env)
        _set("starting", "starting the simulator")
        _compose("up", "-d", "--build", "ingestion", extra_env=sim_env)
        _set("starting", "starting the api and the dispatcher console (http://localhost:58080)")
        _compose("up", "-d", "--build", "api", "frontend", extra_env=sim_env)
        STATE["started_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        RUNS_DIR.mkdir(exist_ok=True)
        record = {"started_at": STATE["started_at"], **cfg.model_dump(), "env": sim_env}
        with (RUNS_DIR / "history.jsonl").open("a") as fh:
            fh.write(json.dumps(record) + "\n")
        _set("running", "simulator running")
    except Exception as exc:  # surfaced in the UI
        _set("error", str(exc))
    finally:
        LOCK.release()


def _services() -> list[dict[str, str]]:
    try:
        raw = _compose("ps", "-a", "--format", "json", timeout=20)
    except Exception:
        return []
    rows = [json.loads(line) for line in raw.splitlines() if line.strip().startswith("{")]
    return [{"service": r.get("Service", ""), "state": r.get("State", ""),
             "status": r.get("Status", ""), "health": r.get("Health", "")} for r in rows]


# ------------------------------------------------------------------------------- db reads
Q_SNAPSHOT = """
SELECT s.snapshot_id, s.as_of_ts, s.rules_version,
       extract(epoch FROM clock_timestamp() - c.committed_at) AS age_s
FROM gold.snapshots s JOIN gold.snapshot_commits c USING (snapshot_id)
ORDER BY s.as_of_ts DESC, s.max_bronze_id DESC LIMIT 1"""
Q_RECS = """
SELECT rec_id, status, stale, proposed_ts, expires_ts, close_ts,
       (doc->>'rank')::int AS rank, doc->'action'->>'type' AS action,
       doc->'action'->>'bus_id' AS bus_id, doc->'action'->>'stop_id' AS stop_id,
       (doc->>'ewt_saving_s')::numeric AS saving_s, doc->>'reason' AS reason
FROM gold.recommendation
ORDER BY (status = 'proposed' AND NOT stale) DESC, proposed_ts DESC, rank LIMIT 15"""
Q_HOLDS = """
SELECT rec_id, bus_id, stop_id, hold_s, observed_dwell_s, status
FROM gold.instruction_status ORDER BY max_bronze_id DESC LIMIT 10"""
Q_ACCURACY = """
SELECT b.lead_bucket, count(a.error_s) AS n_compared,
       round(avg(a.abs_error_s), 1) AS mae_s,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY a.abs_error_s))::numeric, 1) AS median_s,
       max(a.abs_error_s) AS worst_s, round(avg(a.error_s), 1) AS mean_error_s
FROM (VALUES ('0-5 min', 1), ('5-10 min', 2), ('10-30 min', 3)) AS b(lead_bucket, ord)
LEFT JOIN gold.v_projection_accuracy a
       ON a.lead_bucket = b.lead_bucket AND NOT a.affected_by_decision AND a.error_s IS NOT NULL
GROUP BY b.lead_bucket, b.ord ORDER BY b.ord"""


def _connect() -> psycopg.Connection:
    return psycopg.connect(DSN, connect_timeout=2, row_factory=dict_row)


def _db_status() -> dict[str, Any] | None:
    try:
        with _connect() as conn:
            snap = conn.execute(Q_SNAPSHOT).fetchone()
            out: dict[str, Any] = {
                "bronze_events": conn.execute("SELECT count(*) AS n FROM bronze.events").fetchone()["n"],
                "snapshot": snap,
                "recommendations": conn.execute(Q_RECS).fetchall(),
                "holds": conn.execute(Q_HOLDS).fetchall(),
                "accuracy": conn.execute(Q_ACCURACY).fetchall(),
            }
            if snap:
                sid = {"sid": snap["snapshot_id"]}
                row = conn.execute("SELECT doc FROM gold.corridor_now WHERE snapshot_id = %(sid)s", sid).fetchone()
                out["corridor"] = row["doc"] if row else None
                row = conn.execute("SELECT doc FROM gold.source_status WHERE snapshot_id = %(sid)s", sid).fetchone()
                out["source_status"] = row["doc"] if row else None
                out["service"] = conn.execute(
                    "SELECT n_headways, mean_wait_s, scheduled_wait_s, ewt_s, computable "
                    "FROM gold.service_metric WHERE snapshot_id = %(sid)s", sid).fetchone()
            return out
    except psycopg.Error:
        return None


# ---------------------------------------------------------------------------------- app
app = FastAPI(title="PulsoFlota simulation console", docs_url=None, redoc_url=None)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(HERE / "index.html")


@app.get("/api/options")
def options() -> dict[str, Any]:
    return {"scenarios": scenarios(), "defaults": RunConfig().model_dump()}


@app.get("/api/status")
def status() -> dict[str, Any]:
    return {"run": STATE, "services": _services(), "db": _db_status(),
            "now": datetime.now(timezone.utc).isoformat(timespec="seconds")}


@app.post("/api/run", status_code=202)
def run(cfg: RunConfig) -> dict[str, Any]:
    if cfg.scenario not in scenarios():
        raise HTTPException(422, f"unknown scenario {cfg.scenario!r}")
    if not LOCK.acquire(blocking=False):
        raise HTTPException(409, "another start or stop is in progress")
    STATE.update(config=cfg.model_dump(), started_at=None)
    threading.Thread(target=_start_run, args=(cfg,), daemon=True).start()
    return {"accepted": True}


@app.post("/api/stop")
def stop() -> dict[str, Any]:
    if not LOCK.acquire(blocking=False):
        raise HTTPException(409, "another start or stop is in progress")
    try:
        _compose("stop", "ingestion", timeout=60)
        _set("stopped", "simulator stopped; data kept until the next start")
    except Exception as exc:
        _set("error", str(exc))
    finally:
        LOCK.release()
    return {"phase": STATE["phase"]}


@app.post("/api/teardown")
def teardown() -> dict[str, Any]:
    if not LOCK.acquire(blocking=False):
        raise HTTPException(409, "another start or stop is in progress")
    try:
        _compose("down", "-v", "--remove-orphans", timeout=120)
        _set("idle", "pfsim stack removed")
    except Exception as exc:
        _set("error", str(exc))
    finally:
        LOCK.release()
    return {"phase": STATE["phase"]}


@app.post("/api/decision")
def decision(d: Decision) -> dict[str, Any]:
    with _connect() as conn:
        snap = conn.execute(Q_SNAPSHOT).fetchone()
        if snap is None:
            raise HTTPException(409, "no snapshot yet")
        rec = conn.execute("SELECT status, stale FROM gold.recommendation WHERE rec_id = %(r)s",
                           {"r": d.rec_id}).fetchone()
        if rec is None:
            raise HTTPException(404, "unknown recommendation")
        if rec["status"] != "proposed":
            raise HTTPException(409, f"recommendation is already {rec['status']}")
        sim_now = snap["as_of_ts"].astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        event = {
            "source": "backend", "event_id": str(uuid.uuid4()), "schema_version": "1.0.0",
            "event_type": "decision", "event_ts": sim_now,
            "payload": {"rec_id": str(d.rec_id), "action": d.action, "user_id": USER_ID, "ts": sim_now},
        }
        try:
            jsonschema.validate(event, json.loads(COMMAND_SCHEMA.read_text()))
        except jsonschema.ValidationError as exc:
            raise HTTPException(422, f"command_event schema: {exc.message}") from exc
        row = conn.execute(
            """INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload)
               VALUES ('backend', %(event_id)s, '1.0.0', 'decision', %(ts)s, clock_timestamp(), %(payload)s)
               ON CONFLICT (source, event_id) DO NOTHING RETURNING id""",
            {"event_id": event["event_id"], "ts": snap["as_of_ts"],
             "payload": psycopg.types.json.Jsonb(event["payload"])}).fetchone()
        conn.commit()
    return {"bronze_id": row["id"] if row else None, "event_id": event["event_id"], "sim_ts": sim_now}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
