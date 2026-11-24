"""Local simulation control console (data team test harness, not part of the product).

Starts and stops simulator runs on an isolated compose project (`pfsim`) and shows the run's
state (simulated time, data age, source, services) and the countdown of the scenario's events.
The other tabs (Flujo, Modelo, Decisiones, Resultados) are the data flow viewer of
`src/data/test_lab`, mounted at /lab/. Approve/discard goes through the command door of the data
contract (§4.1–§4.2): a `decision` event INSERTed into `bronze.events`, validated against
`contracts/read/command_event.schema.json`.

Safety rules:
- binds to 127.0.0.1 by default; `SIM_CONSOLE_HOST=0.0.0.0` is an explicit opt-in to expose the
  harness to the LAN (only on a trusted network: approve/discard has no authentication);
- runs only fixed `docker compose` argument lists on project `pfsim` (no shell, no free text);
- every run parameter is validated against an allow-list or a numeric range;
- never touches the default stack or its `db_data` volume.

Run from the repository root:
    cp src/data/sim_console/.pfsim.env.example src/data/sim_console/.pfsim.env   # once
    uv run --frozen --extra dev python -m src.data.sim_console.app   # then open http://127.0.0.1:8090
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
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from src.data.sim_console import db_config, outcomes, report

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".pfsim.env"
RUNS_DIR = HERE / "runs"
ARCHIVE_DIR = RUNS_DIR / "archive"  # one folder per run: report.json + recommendations.csv (git-ignored)
SCENARIO_DIR = ROOT / "src/data/tests/fixtures/scenarios"
COMMAND_SCHEMA = ROOT / "contracts/read/command_event.schema.json"
PROJECT = "pfsim"
COMPOSE = ["docker", "compose", "-p", PROJECT, "--env-file", str(ENV_FILE),
           "-f", str(ROOT / "docker-compose.yml"), "-f", str(HERE / "compose.sim.yml")]
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

# The containers use DATABASE_URL with host `db` (compose network). This process runs on the host,
# so resolve a host-reachable DSN from the same .pfsim.env credentials (see db_config.py).
DSN = db_config.dsn_for("pfsim")
LAST_DB_ERROR: str | None = None

# Bind address of this harness. Shell env wins over .pfsim.env so the launcher .bat can opt in
# to LAN access without editing the env file. Default stays local-only.
HOST = os.environ.get("SIM_CONSOLE_HOST", ENV.get("SIM_CONSOLE_HOST", "127.0.0.1"))
PORT = int(os.environ.get("SIM_CONSOLE_PORT", ENV.get("SIM_CONSOLE_PORT", "8090")))


def scenarios() -> list[str]:
    return ["none"] + sorted(p.stem for p in SCENARIO_DIR.glob("*.json"))


class RunConfig(BaseModel):
    scenario: str = "c1_bunching"
    demand_scale: float = Field(5.0, ge=0.1, le=10.0)
    seed: int = Field(42, ge=0, le=2**31 - 1)
    duration_s: int = Field(2700, ge=300, le=14400)
    start_hour: int = Field(17, ge=0, le=23)  # local Medellin hour the simulated day starts at
    warmup_s: int = Field(0, ge=0, le=7200)  # simulated seconds written without the pace (corridor full at the start)
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
            "SIM_START_HOUR": str(cfg.start_hour),
            "SIM_WARMUP_S": str(cfg.warmup_s),
            "SIM_SCENARIO_FILE": "" if cfg.scenario == "none" else f"/scn/{cfg.scenario}.json",
            "SIM_HOLDS": "on" if cfg.holds else "off",
            "MPC_ENABLED": "on" if cfg.mpc else "off",
        }
        _set("starting", "saving the previous run's recommendations")
        archive("before_reset")
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
        record = {"started_at": STATE["started_at"], **cfg.model_dump(), "env": sim_env, "requested_by": STATE.get("requested_by")}
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


def _restore_state() -> None:
    """After a console restart, pick up the run that is still going (last line of runs/history.jsonl) so the page keeps
    its countdown. Nothing is restored when the simulator is not running."""
    history = RUNS_DIR / "history.jsonl"
    if not history.exists():
        return
    sim = next((x for x in _services() if x["service"] == "ingestion"), None)
    if sim is None or sim["state"] != "running":
        return
    try:
        last = json.loads(history.read_text().strip().splitlines()[-1])
        cfg = RunConfig(**{k: last[k] for k in RunConfig.model_fields if k in last})
    except (OSError, ValueError, IndexError):
        return
    STATE.update(phase="running", message="simulator running (restored after a console restart)",
                 config=cfg.model_dump(), started_at=last.get("started_at"))


# ------------------------------------------------------------------------------- db reads
Q_SNAPSHOT = """
SELECT s.snapshot_id, s.as_of_ts, s.rules_version,
       extract(epoch FROM clock_timestamp() - c.committed_at) AS age_s
FROM gold.snapshots s JOIN gold.snapshot_commits c USING (snapshot_id)
ORDER BY s.as_of_ts DESC, s.max_bronze_id DESC LIMIT 1"""


def _connect() -> psycopg.Connection:
    return psycopg.connect(DSN, connect_timeout=2, row_factory=dict_row)


def _db_status() -> dict[str, Any] | None:
    global LAST_DB_ERROR
    try:
        with _connect() as conn:
            LAST_DB_ERROR = None
            snap = conn.execute(Q_SNAPSHOT).fetchone()
            out: dict[str, Any] = {
                "bronze_events": conn.execute("SELECT count(*) AS n FROM bronze.events").fetchone()["n"],
                "snapshot": snap,
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
    except psycopg.Error as exc:
        LAST_DB_ERROR = str(exc).strip()
        return None


# --------------------------------------------------------------------- decision report
Q_REPORT_RECS = """
SELECT rec_id::text AS rec_id, status, stale, "case", proposed_ts, expires_ts, close_ts,
       (doc->>'rank')::int AS rank, doc->'action'->>'type' AS action,
       doc->'action'->>'bus_id' AS bus_id, doc->'action'->>'stop_id' AS stop_id,
       (doc->>'ewt_saving_s')::float AS saving_s, doc->>'reason' AS reason_text, doc
FROM gold.recommendation"""
Q_DECISIONS = """
SELECT id AS bronze_id, lower(payload->>'rec_id') AS rec_id, payload->>'action' AS action,
       payload->>'user_id' AS user_id, event_ts AS decided_at, arrival_ts
FROM bronze.events WHERE event_type = 'decision' ORDER BY id"""
Q_RUN = """
SELECT min(event_ts) AS start_ts, min(arrival_ts) AS first_arrival
FROM bronze.events WHERE source = 'simulator'"""
ARCHIVE_LOCK = threading.Lock()
ARCHIVED: set[str] = set()  # run keys auto-archived when the run ended (one write per run)


def _run_over(services: list[dict[str, str]]) -> bool:
    """The simulated clock has stopped: the simulator was stopped or finished its day (it runs once, restart no)."""
    if STATE["phase"] == "starting":
        return False
    if STATE["phase"] == "stopped":
        return True
    sim = next((s for s in services if s["service"] == "ingestion"), None)
    return sim is None or sim["state"] not in ("running", "restarting", "created")


def _report(conn: psycopg.Connection, run_over: bool, window_s: int | None, with_docs: bool = False
            ) -> dict[str, Any] | None:
    snap = conn.execute(Q_SNAPSHOT).fetchone()
    run = conn.execute(Q_RUN).fetchone()
    if snap is None or run is None or run["start_ts"] is None:
        return None
    as_of, start = snap["as_of_ts"], run["start_ts"]
    recs = conn.execute(Q_REPORT_RECS).fetchall()
    events = conn.execute(Q_DECISIONS).fetchall()
    rows = report.rows(recs, events, as_of, run_over)
    if with_docs:
        docs = {r["rec_id"]: r["doc"] for r in recs}
        for r in rows:
            r["doc"] = docs.get(r["rec_id"])
    return {"run_key": report.run_key(run["first_arrival"]), "start_ts": start, "as_of_ts": as_of, "run_over": run_over,
            "window": report.summary(rows, as_of, start, window_s),
            "total": report.summary(rows, as_of, start, None),
            "buckets": report.buckets(rows, as_of, start), "rows": rows, "decisions": events}


def archive(trigger: str, services: list[dict[str, str]] | None = None) -> str | None:
    """Save the run's recommendations and decisions to runs/archive/<run_key>/ before they can be lost.

    Called before every reset (`down -v`), on stop, when the run ends, and from the "Guardar" button. The same run
    always writes the same folder, so a later save only adds what happened since. Returns the run key, or None when
    there is nothing to save (no pfsim database or no data yet)."""
    with ARCHIVE_LOCK:
        try:
            with _connect() as conn:
                rep = _report(conn, _run_over(services if services is not None else _services()), None, with_docs=True)
                if rep is not None:
                    rep["outcomes"] = outcomes.build(outcomes.collect(conn), rep["rows"], rep["as_of_ts"],
                                                     rep["run_over"], rep["start_ts"])
        except psycopg.Error:
            return None
        if rep is None or rep["run_key"] is None:
            return None
        # a run reset within its first simulated minutes, with nothing proposed, is not worth keeping
        if rep["total"]["proposed"] == 0 and (rep["as_of_ts"] - rep["start_ts"]).total_seconds() < 300:
            return None
        doc = {"run_key": rep["run_key"], "archived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "trigger": trigger, "saved_by": "sim-console", "config": STATE.get("config"),
               "console_started_at": STATE.get("started_at"),
               **{k: rep[k] for k in ("start_ts", "as_of_ts", "run_over", "total", "buckets", "rows", "decisions",
                                  "outcomes")}}
        report.write_archive(ARCHIVE_DIR, rep["run_key"], doc)
        return rep["run_key"]


# ---------------------------------------------------------------------------------- app
app = FastAPI(title="PulsoFlota simulation console", docs_url=None, redoc_url=None)

# One app on 8090: the data flow viewer (src/data/test_lab: Flujo, ¿Qué pasa si…?, Decisiones, Resultados) is mounted
# at /lab/ and reads this console's pfsim stack. Its 8085 container stays optional, for the principal stack.
from src.data.test_lab import app as lab  # noqa: E402 (after the env is read)
from src.data.test_lab import decisions as lab_decisions  # noqa: E402

lab.TARGETS.clear()
lab.TARGETS["pfsim"] = {"dsn": DSN, "api": f"http://127.0.0.1:{ENV.get('API_HOST_PORT', '58100')}"}
lab_decisions.ARCHIVE_DIR = ARCHIVE_DIR
lab_decisions.COMMAND_SCHEMA = COMMAND_SCHEMA
lab_decisions.USER_ID = USER_ID
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/lab", lab.app)
_restore_state()


@app.get("/lab", include_in_schema=False)
def lab_root() -> RedirectResponse:
    return RedirectResponse("/lab/")


@app.get("/")
def index() -> FileResponse:
    # no-store: after an update the browser must load the new page (with the tabs), not a cached one
    return FileResponse(HERE / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/options")
def options() -> dict[str, Any]:
    return {"scenarios": scenarios(), "defaults": RunConfig().model_dump()}


@app.get("/api/status")
def status(window_min: int = 15) -> dict[str, Any]:
    """`window_min`: simulated minutes of the decision report window; 0 = the whole run."""
    services = _services()
    run_over = _run_over(services)
    rep = None
    try:
        with _connect() as conn:
            rep = _report(conn, run_over, window_min * 60 if window_min > 0 else None)
    except psycopg.Error:
        pass
    # the run ended: save it once, without a click
    if rep and run_over and rep["run_key"] not in ARCHIVED and archive("run_ended", services):
        ARCHIVED.add(rep["run_key"])
    if rep:
        rep.pop("decisions")
    return {"run": STATE, "services": services, "db": _db_status(), "db_error": LAST_DB_ERROR,
            "report": rep, "now": datetime.now(timezone.utc).isoformat(timespec="seconds")}


@app.get("/api/db-check")
def db_check() -> dict[str, Any]:
    """Diagnostic for the host-side DB connection (password masked)."""
    ok, error = db_config.probe(DSN)
    return {"dsn": db_config.mask_dsn(DSN), "port_open": db_config.port_open(DSN),
            "ok": ok, "error": error or LAST_DB_ERROR}


@app.post("/api/archive")
def archive_now() -> dict[str, Any]:
    key = archive("manual")
    if key is None:
        raise HTTPException(409, "nothing to save: no pfsim database or no data yet")
    return {"run_key": key, "folder": str((ARCHIVE_DIR / key).relative_to(ROOT))}


@app.get("/api/runs")
def runs() -> list[dict[str, Any]]:
    return report.list_archives(ARCHIVE_DIR)


@app.get("/api/runs/{run_key}/{name}")
def run_file(run_key: str, name: Literal["report.json", "recommendations.csv"]) -> Response:
    if not report.valid_key(run_key):
        raise HTTPException(404, "unknown run")
    f = ARCHIVE_DIR / run_key / name
    if not f.exists():
        raise HTTPException(404, "unknown run")
    media = "application/json" if name.endswith(".json") else "text/csv"
    return Response(f.read_bytes(), media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="pfsim-{run_key}-{name}"'})


@app.post("/api/run", status_code=202)
def run(cfg: RunConfig, request: Request) -> dict[str, Any]:
    # Every start resets pfsim (down -v): log who asked, so an unexpected reset can be traced.
    who = {"referer": request.headers.get("referer"), "user_agent": (request.headers.get("user-agent") or "")[:120]}
    print(json.dumps({"event": "run_requested", "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                      "phase_before": STATE["phase"], "scenario": cfg.scenario, **who}), flush=True)
    if cfg.scenario not in scenarios():
        raise HTTPException(422, f"unknown scenario {cfg.scenario!r}")
    if not LOCK.acquire(blocking=False):
        raise HTTPException(409, "another start or stop is in progress")
    STATE.update(config=cfg.model_dump(), started_at=None, requested_by=who)
    threading.Thread(target=_start_run, args=(cfg,), daemon=True).start()
    return {"accepted": True}


@app.post("/api/stop")
def stop() -> dict[str, Any]:
    if not LOCK.acquire(blocking=False):
        raise HTTPException(409, "another start or stop is in progress")
    try:
        _compose("stop", "ingestion", timeout=60)
        _set("stopped", "simulator stopped; data kept until the next start")
        archive("stopped")
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
        archive("before_teardown")
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
        rec = conn.execute("SELECT status, stale, expires_ts FROM gold.recommendation WHERE rec_id = %(r)s",
                           {"r": d.rec_id}).fetchone()
        if rec is None:
            raise HTTPException(404, "unknown recommendation")
        if rec["status"] != "proposed":
            raise HTTPException(409, f"recommendation is already {rec['status']}")
        # Simulated time decides, not the wall clock: past expires_ts the next cycle marks it expired, and a
        # decision written now would overturn that (the pipeline lets the first decision win).
        if snap["as_of_ts"] > rec["expires_ts"]:
            raise HTTPException(409, "recommendation expired (simulated time is past expires_ts)")
        if _run_over(_services()):
            raise HTTPException(409, "the run is over: the recommendation expired when the simulated clock stopped")
        first = conn.execute("SELECT 1 FROM bronze.events WHERE event_type = 'decision' AND payload->>'rec_id' = %(r)s",
                             {"r": str(d.rec_id)}).fetchone()
        if first is not None:
            raise HTTPException(409, "recommendation already decided (waiting for the next cycle)")
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

    ok, error = db_config.probe(DSN)
    print(f"db: {db_config.mask_dsn(DSN)} port_open={db_config.port_open(DSN)} ok={ok}", flush=True)
    if not ok:
        print(f"db error: {error}", flush=True)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
