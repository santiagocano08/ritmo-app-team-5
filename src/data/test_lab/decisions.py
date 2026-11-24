"""Decisions tab of the data flow viewer: was each recommendation decided, how many in the last X minutes.

The one place where the viewer writes, and only on the `pfsim` target (the isolated sim-console stack):
approve/discard inserts a `decision` event into `bronze.events` through the command door (data contract §4.2),
validated against `contracts/read/command_event.schema.json` — the same message the backend and the sim console
write. The principal stack stays read-only.

The report itself (`src/data/sim_console/report.py`) is shared with the sim console and works on simulated time.
Saved runs live in `src/data/sim_console/runs/archive/` (mounted into the container): the sim console saves a run
before every reset, and the "Guardar" button here saves the current run on demand.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import psycopg
from fastapi import HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel

from src.data.sim_console import outcomes, report

WRITABLE_TARGET = "pfsim"
USER_ID = "test-lab"
COMMAND_SCHEMA = Path(os.environ.get("LAB_COMMAND_SCHEMA", "/contracts/command_event.schema.json"))
ARCHIVE_DIR = Path(os.environ.get("LAB_ARCHIVE_DIR", "/archive"))
# The simulated clock has stopped when no simulator event has arrived for this long (wall clock). A single silent
# bus (D1_SILENCE) does not trigger it: the other buses keep reporting.
SILENT_RUN_S = int(os.environ.get("LAB_RUN_SILENT_S", "30"))

Q_SNAPSHOT = """
SELECT s.as_of_ts FROM gold.snapshots s JOIN gold.snapshot_commits c USING (snapshot_id)
ORDER BY s.as_of_ts DESC, s.max_bronze_id DESC LIMIT 1"""
Q_RUN = """
SELECT min(event_ts) AS start_ts, min(arrival_ts) AS first_arrival,
       extract(epoch FROM clock_timestamp() - max(arrival_ts)) AS silent_s,
       extract(epoch FROM max(arrival_ts) - min(arrival_ts)) AS wall_s, max(event_ts) AS last_sim_ts
FROM bronze.events WHERE source = 'simulator'"""
# Simulated seconds per real second over the last 40 s: a warm-up writes its first minutes at once, so a longer
# window (or the whole run) would overstate the pace right after it.
Q_RECENT_PACE = """
SELECT extract(epoch FROM max(event_ts) - min(event_ts)) AS sim_s, extract(epoch FROM max(arrival_ts) - min(arrival_ts)) AS wall_s
FROM bronze.events WHERE source = 'simulator' AND arrival_ts > clock_timestamp() - interval '40 seconds'"""
Q_RECS = """
SELECT rec_id::text AS rec_id, status, stale, "case", proposed_ts, expires_ts, close_ts,
       (doc->>'rank')::int AS rank, doc->'action'->>'type' AS action,
       doc->'action'->>'bus_id' AS bus_id, doc->'action'->>'stop_id' AS stop_id,
       (doc->>'ewt_saving_s')::float AS saving_s, doc->>'reason' AS reason_text, doc
FROM gold.recommendation"""
Q_DECISIONS = """
SELECT id AS bronze_id, lower(payload->>'rec_id') AS rec_id, payload->>'action' AS action,
       payload->>'user_id' AS user_id, event_ts AS decided_at
FROM bronze.events WHERE event_type = 'decision' ORDER BY id"""


def check_command(event: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate a `decision` command event against the contract file, without jsonschema (dev-only dependency,
    not in the prod image). Reads every rule from the schema: required keys, no extra keys, the enums and consts of
    the envelope, and the decision payload branch of `oneOf`. Raises ValueError with the first broken rule."""
    props = schema["properties"]
    if missing := set(schema["required"]) - event.keys():
        raise ValueError(f"missing {sorted(missing)}")
    if extra := event.keys() - props.keys():
        raise ValueError(f"undeclared {sorted(extra)}")
    for k, rule in props.items():
        if "enum" in rule and event[k] not in rule["enum"]:
            raise ValueError(f"{k}={event[k]!r} not in {rule['enum']}")
        if "const" in rule and event[k] != rule["const"]:
            raise ValueError(f"{k} must be {rule['const']!r}")
    branch = next(b for b in schema["oneOf"] if b["properties"]["event_type"].get("const") == event["event_type"])
    pay, rules = event["payload"], branch["properties"]["payload"]
    if missing := set(rules["required"]) - pay.keys():
        raise ValueError(f"payload missing {sorted(missing)}")
    if rules.get("additionalProperties") is False and (extra := pay.keys() - rules["properties"].keys()):
        raise ValueError(f"payload undeclared {sorted(extra)}")
    for k, rule in rules["properties"].items():
        if k in pay and "enum" in rule and pay[k] not in rule["enum"]:
            raise ValueError(f"payload.{k}={pay[k]!r} not in {rule['enum']}")
        if k in pay and rule.get("format") == "uuid":
            uuid.UUID(pay[k])
    uuid.UUID(event["event_id"])
    datetime.fromisoformat(event["event_ts"].replace("Z", "+00:00"))


class Decision(BaseModel):
    rec_id: uuid.UUID
    action: Literal["apply", "discard"]


def build(conn: psycopg.Connection, window_s: int | None, with_docs: bool = False) -> dict[str, Any]:
    """The decision report of the run in this database. Raises 409 when there is no data yet."""
    try:
        snap = conn.execute(Q_SNAPSHOT).fetchone()
        run = conn.execute(Q_RUN).fetchone()
        if snap is None or run is None or run["start_ts"] is None:
            raise HTTPException(409, "sin datos todavía: no hay snapshot ni eventos del simulador")
        recs = conn.execute(Q_RECS).fetchall()
        events = conn.execute(Q_DECISIONS).fetchall()
        recent = conn.execute(Q_RECENT_PACE).fetchone()
    except psycopg.errors.UndefinedTable as exc:
        raise HTTPException(409, "este stack no tiene el modelo de decisión (falta la migración 009)") from exc
    as_of, start = snap["as_of_ts"], run["start_ts"]
    run_over = float(run["silent_s"] or 0) > SILENT_RUN_S
    rows = report.rows(recs, events, as_of, run_over)
    # Simulated seconds per real second (pace 1 = 5), over the last 40 s: turns a countdown in simulated time into
    # real seconds.
    wall = float((recent or {}).get("wall_s") or 0)
    sim_per_real = round(float(recent["sim_s"]) / wall, 2) if wall > 20 else None
    docs = {r["rec_id"]: r["doc"] for r in recs}
    for r in rows:
        if with_docs:
            r["doc"] = docs.get(r["rec_id"])
        r["reason_text"] = r.get("reason_text") or ""
    return {
        "run_key": report.run_key(run["first_arrival"]), "start_ts": start, "as_of_ts": as_of,
        "run_over": run_over, "silent_s": round(float(run["silent_s"] or 0), 1), "sim_per_real": sim_per_real,
        "window": report.summary(rows, as_of, start, window_s),
        "total": report.summary(rows, as_of, start, None),
        "buckets": report.buckets(rows, as_of, start),
        "rows": rows, "decisions": events if with_docs else None,
        "can_decide": False, "archive_ready": ARCHIVE_DIR.is_dir(),
    }


def decide(dsn: str, d: Decision) -> dict[str, Any]:
    """Write the dispatcher's answer for one open recommendation (pfsim only)."""
    with psycopg.connect(dsn, connect_timeout=3, row_factory=dict_row) as conn:
        snap = conn.execute(Q_SNAPSHOT).fetchone()
        run = conn.execute(Q_RUN).fetchone()
        if snap is None:
            raise HTTPException(409, "sin snapshot todavía")
        rec = conn.execute("SELECT status, expires_ts FROM gold.recommendation WHERE rec_id = %(r)s",
                           {"r": d.rec_id}).fetchone()
        if rec is None:
            raise HTTPException(404, "recomendación desconocida")
        if rec["status"] != "proposed":
            raise HTTPException(409, f"la recomendación ya está {rec['status']}")
        # Simulated time decides, never the wall clock. Past expires_ts the next cycle marks it expired; a decision
        # written now would overturn that, because the pipeline lets the first decision win.
        if snap["as_of_ts"] > rec["expires_ts"]:
            raise HTTPException(409, "la recomendación venció (la hora simulada pasó su expires_ts)")
        if run and float(run["silent_s"] or 0) > SILENT_RUN_S:
            raise HTTPException(409, "la corrida terminó: la recomendación quedó expirada al detenerse el reloj simulado")
        if conn.execute("SELECT 1 FROM bronze.events WHERE event_type = 'decision' AND payload->>'rec_id' = %(r)s",
                        {"r": str(d.rec_id)}).fetchone():
            raise HTTPException(409, "ya hay una decisión para esta recomendación (se refleja en el siguiente ciclo)")
        sim_now = snap["as_of_ts"].astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        event = {"source": "backend", "event_id": str(uuid.uuid4()), "schema_version": "1.0.0",
                 "event_type": "decision", "event_ts": sim_now,
                 "payload": {"rec_id": str(d.rec_id), "action": d.action, "user_id": USER_ID, "ts": sim_now}}
        try:
            check_command(event, json.loads(COMMAND_SCHEMA.read_text()))
        except FileNotFoundError as exc:
            raise HTTPException(503, f"no encuentro el contrato {COMMAND_SCHEMA} (monta contracts/read)") from exc
        except (ValueError, KeyError, StopIteration) as exc:
            raise HTTPException(422, f"command_event schema: {exc}") from exc
        row = conn.execute(
            """INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload)
               VALUES ('backend', %(event_id)s, '1.0.0', 'decision', %(ts)s, clock_timestamp(), %(payload)s)
               ON CONFLICT (source, event_id) DO NOTHING RETURNING id""",
            {"event_id": event["event_id"], "ts": snap["as_of_ts"],
             "payload": psycopg.types.json.Jsonb(event["payload"])}).fetchone()
        conn.commit()
    return {"bronze_id": row["id"] if row else None, "event_id": event["event_id"], "sim_ts": sim_now}


def save(conn: psycopg.Connection, target: str) -> dict[str, Any]:
    """Save the current run to the shared archive folder."""
    if not ARCHIVE_DIR.is_dir():
        raise HTTPException(503, f"carpeta de archivo no montada ({ARCHIVE_DIR})")
    rep = build(conn, None, with_docs=True)
    if rep["run_key"] is None:
        raise HTTPException(409, "sin datos para guardar")
    rep["outcomes"] = outcomes.build(outcomes.collect(conn), rep["rows"], rep["as_of_ts"], rep["run_over"],
                                     rep["start_ts"])
    doc = {"run_key": rep["run_key"], "archived_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "trigger": "manual", "saved_by": f"test-lab ({target})", "config": None,
           **{k: rep[k] for k in ("start_ts", "as_of_ts", "run_over", "total", "buckets", "rows", "decisions",
                                  "outcomes")}}
    report.write_archive(ARCHIVE_DIR, rep["run_key"], doc)
    return {"run_key": rep["run_key"]}


def saved_runs() -> list[dict[str, Any]]:
    return report.list_archives(ARCHIVE_DIR) if ARCHIVE_DIR.is_dir() else []


def saved_file(key: str, name: str) -> tuple[bytes, str]:
    if not report.valid_key(key) or name not in ("report.json", "recommendations.csv"):
        raise HTTPException(404, "corrida desconocida")
    f = ARCHIVE_DIR / key / name
    if not f.exists():
        raise HTTPException(404, "corrida desconocida")
    return f.read_bytes(), "application/json" if name.endswith(".json") else "text/csv"
