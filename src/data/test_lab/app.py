"""Data flow viewer: follow the data and the decisions from raw events to the dispatcher's answer.

A read-only console for the data team (not product code). For one stack it shows, live, the
seven stages of the decision loop and what each one holds:

  1 raw          simulator events as they arrive (bronze.events, source = simulator)
  2 bronze       the immutable landing table and its rejections
  3 silver       per-bus state, stop visits, incidents
  4 gold         the snapshot: corridor_now, service_metric (EWT), source_status
  5 decision     gold.decision_inputs and the model's output, gold.recommendation
  6 front        what the api serves the dispatcher console (/api/v1/corridor/{id}/now) and the
                 recommendation documents it will show
  7 response     the dispatcher's `decision` event (command door, bronze), the status it moves the
                 recommendation to, and gold.instruction_status (hold executed or not)

It can also trace one recommendation end to end (GET /api/trace/{target}/{rec_id}): the raw events
up to the bronze id it was computed from, the snapshot and inputs it used, the document, and the
answer that came back. Every query is a SELECT in a read-only transaction.

Targets come from the environment (see compose.lab.yml):
    LAB_MAIN_DSN / LAB_MAIN_API     the default stack
    LAB_PFSIM_DSN / LAB_PFSIM_API   the sim-console stack `pfsim` (optional)
"""
from __future__ import annotations

import json
import os
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from psycopg.rows import dict_row

from src.data.test_lab import whatif

HERE = Path(__file__).resolve().parent
PORT = int(os.environ.get("LAB_PORT", "8085"))
CORRIDOR_ID = os.environ.get("LAB_CORRIDOR_ID", "C6-008")

TARGETS: dict[str, dict[str, str]] = {}
if os.environ.get("LAB_PFSIM_DSN"):
    TARGETS["pfsim"] = {"dsn": os.environ["LAB_PFSIM_DSN"], "api": os.environ.get("LAB_PFSIM_API", "")}
if os.environ.get("LAB_MAIN_DSN"):
    TARGETS["principal"] = {"dsn": os.environ["LAB_MAIN_DSN"], "api": os.environ.get("LAB_MAIN_API", "")}


def _connect(target: str) -> psycopg.Connection:
    if target not in TARGETS:
        raise HTTPException(404, f"unknown target {target!r}")
    try:
        conn = psycopg.connect(TARGETS[target]["dsn"], connect_timeout=3, row_factory=dict_row)
    except psycopg.Error as exc:
        raise HTTPException(503, f"database unreachable: {str(exc).splitlines()[0]}") from exc
    conn.read_only = True
    return conn


def _q(conn: psycopg.Connection, sql: str, params: dict[str, Any] | None = None, one: bool = False) -> Any:
    """Run one SELECT; a missing table (old volume) gives None instead of breaking the page."""
    try:
        cur = conn.execute(sql, params or {})
        return cur.fetchone() if one else cur.fetchall()
    except psycopg.Error:
        conn.rollback()
        return None


def _api_get(target: str, path: str) -> dict[str, Any]:
    base = TARGETS[target]["api"]
    if not base:
        return {"ok": False, "error": "api not configured"}
    try:
        with urllib.request.urlopen(f"{base}{path}", timeout=3) as resp:  # noqa: S310 (base URL from env)
            return {"ok": True, "status": resp.status, "url": path, "body": json.loads(resp.read())}
    except Exception as exc:
        return {"ok": False, "url": path, "error": type(exc).__name__}


# ------------------------------------------------------------------------------- overview
def overview(target: str) -> dict[str, Any]:
    with _connect(target) as conn:
        raw_types = _q(conn, """
            SELECT event_type, source, count(*) AS total,
                   count(*) FILTER (WHERE arrival_ts > clock_timestamp() - interval '60 seconds') AS last_60s,
                   max(id) AS last_id
            FROM bronze.events GROUP BY event_type, source ORDER BY total DESC""") or []
        raw_latest = _q(conn, """
            SELECT id, source, event_type, to_char(event_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS sim_ts,
                   round(extract(epoch FROM clock_timestamp() - arrival_ts)::numeric, 1) AS age_s, payload
            FROM bronze.events WHERE source = 'simulator' ORDER BY id DESC LIMIT 8""") or []
        bronze = _q(conn, """
            SELECT (SELECT count(*) FROM bronze.events) AS events,
                   (SELECT max(id) FROM bronze.events) AS max_id,
                   (SELECT count(*) FROM bronze.rejections) AS rejections""", one=True)
        rejections = _q(conn, "SELECT reason, count(*) AS n FROM bronze.rejections GROUP BY reason ORDER BY n DESC") or []
        silver_buses = _q(conn, """
            SELECT bus_id, operational_status, data_quality, prev_stop_id, next_stop_id,
                   round(distance_along_m) AS distance_m, occupancy,
                   to_char(last_report_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS last_report
            FROM silver.bus_current_state ORDER BY bus_id""") or []
        silver_counts = _q(conn, """
            SELECT (SELECT count(*) FROM silver.position_history) AS position_history,
                   (SELECT count(*) FROM silver.stop_visits) AS stop_visits,
                   (SELECT count(*) FROM silver.incidents) AS incidents""", one=True)
        snap = _q(conn, """
            SELECT s.snapshot_id, to_char(s.as_of_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS sim_ts, s.rules_version,
                   s.max_bronze_id, round(extract(epoch FROM clock_timestamp() - c.committed_at)::numeric, 1) AS age_s
            FROM gold.snapshots s JOIN gold.snapshot_commits c USING (snapshot_id)
            ORDER BY c.committed_at DESC LIMIT 1""", one=True)
        gold: dict[str, Any] = {"snapshot": snap, "n_snapshots": (_q(conn, "SELECT count(*) AS n FROM gold.snapshots", one=True) or {}).get("n")}
        decision: dict[str, Any] = {}
        if snap:
            sid = {"sid": snap["snapshot_id"]}
            corridor = _q(conn, "SELECT doc FROM gold.corridor_now WHERE snapshot_id = %(sid)s", sid, one=True)
            gold["corridor_now"] = corridor["doc"] if corridor else None
            gold["service_metric"] = _q(conn, """
                SELECT n_headways, round(mean_wait_s) AS mean_wait_s, round(scheduled_wait_s) AS scheduled_wait_s,
                       round(ewt_s) AS ewt_s, computable FROM gold.service_metric WHERE snapshot_id = %(sid)s""", sid, one=True)
            status = _q(conn, "SELECT doc FROM gold.source_status WHERE snapshot_id = %(sid)s", sid, one=True)
            gold["source_status"] = status["doc"] if status else None
            inputs = _q(conn, "SELECT doc FROM gold.decision_inputs WHERE snapshot_id = %(sid)s", sid, one=True)
            decision["inputs"] = _inputs_summary(inputs["doc"]) if inputs else None
            decision["evaluated"] = _q(conn, """
                SELECT action, "case", round(score_s, 1) AS score_s, round(saving_s_per_rider, 1) AS saving_s,
                       recommended, reason_not FROM gold.mpc_evaluation ORDER BY seq LIMIT 12""")
        decision["by_status"] = _q(conn, "SELECT status, count(*) AS n FROM gold.recommendation GROUP BY status ORDER BY status")
        recs = _q(conn, """
            SELECT rec_id, status, stale, "case", doc,
                   to_char(proposed_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS proposed,
                   to_char(close_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS closed
            FROM gold.recommendation ORDER BY proposed_ts DESC, (doc->>'rank')::int LIMIT 30""")
        decision["recommendations"] = recs
        front = {
            "corridor_now": _api_get(target, f"/api/v1/corridor/{CORRIDOR_ID}/now"),
            "source_status": _api_get(target, f"/api/v1/corridor/{CORRIDOR_ID}/source-status"),
            "open_recommendations": [r["doc"] for r in (recs or []) if r["status"] == "proposed" and not r["stale"]],
        }
        responses = _q(conn, """
            SELECT e.id AS bronze_id, e.source, e.payload->>'action' AS action, e.payload->>'user_id' AS user_id,
                   e.payload->>'rec_id' AS rec_id, e.payload->>'reason' AS reason,
                   to_char(e.event_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS sim_ts,
                   r.status AS rec_status, r.doc->'action'->>'type' AS action_type, r.doc->'action'->>'bus_id' AS bus_id,
                   i.status AS instruction, i.observed_dwell_s, i.hold_s
            FROM bronze.events e
            LEFT JOIN gold.recommendation r ON r.rec_id::text = e.payload->>'rec_id'
            LEFT JOIN gold.instruction_status i ON i.rec_id::text = e.payload->>'rec_id'
            WHERE e.event_type = 'decision' ORDER BY e.id DESC LIMIT 15""")
    return {
        "target": target, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw": {"types": raw_types, "latest": raw_latest},
        "bronze": {"totals": bronze, "rejections": rejections},
        "silver": {"buses": silver_buses, "counts": silver_counts},
        "gold": gold, "decision": decision, "front": front, "response": responses,
    }


def _inputs_summary(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "snapshot_id": doc.get("snapshot_id"), "as_of_ts": doc.get("as_of_ts"),
        "summary": doc.get("summary"), "resources": doc.get("resources"),
        "active_incidents": doc.get("active_incidents"), "action_cost": doc.get("action_cost"),
        "buses": [{k: b.get(k) for k in ("bus_id", "bus_state", "headway_ahead_s", "headway_planned_s",
                                         "next_stop_id", "data_quality")} for b in doc.get("buses", [])],
        "keys": sorted(doc.keys()),
    }


# ---------------------------------------------------------------------------------- trace
def trace(target: str, rec_id: uuid.UUID) -> dict[str, Any]:
    with _connect(target) as conn:
        rec = _q(conn, """
            SELECT rec_id, doc, status, stale, "case", first_snapshot_id, max_bronze_id, rules_version,
                   to_char(proposed_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS proposed,
                   to_char(expires_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS expires,
                   to_char(close_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS closed, params
            FROM gold.recommendation WHERE rec_id = %(r)s""", {"r": rec_id}, one=True)
        if rec is None:
            raise HTTPException(404, "unknown recommendation")
        sid = {"sid": rec["first_snapshot_id"]}
        snap = _q(conn, """SELECT snapshot_id, to_char(as_of_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS sim_ts,
                                  max_bronze_id, rules_version FROM gold.snapshots WHERE snapshot_id = %(sid)s""", sid, one=True)
        bronze_cut = snap["max_bronze_id"] if snap else rec["max_bronze_id"]
        raw = _q(conn, """
            SELECT id, event_type, to_char(event_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS sim_ts, payload
            FROM bronze.events WHERE id <= %(cut)s AND source = 'simulator'
              AND event_type IN ('bus_position', 'stop_arrival', 'stop_departure', 'incident_report')
            ORDER BY id DESC LIMIT 12""", {"cut": bronze_cut}) or []
        n_raw = _q(conn, "SELECT count(*) AS n FROM bronze.events WHERE id <= %(cut)s", {"cut": bronze_cut}, one=True)
        visits = _q(conn, """
            SELECT bus_id, stop_id, to_char(arrival_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS arrival,
                   to_char(departure_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS departure, round(dwell_s) AS dwell_s,
                   boarded, alighted
            FROM silver.stop_visits v, gold.snapshots s
            WHERE s.snapshot_id = %(sid)s AND v.arrival_ts <= s.as_of_ts
            ORDER BY v.arrival_ts DESC LIMIT 10""", sid) or []
        corridor = _q(conn, "SELECT doc FROM gold.corridor_now WHERE snapshot_id = %(sid)s", sid, one=True)
        metric = _q(conn, """SELECT n_headways, round(ewt_s) AS ewt_s, round(mean_wait_s) AS mean_wait_s,
                                    round(scheduled_wait_s) AS scheduled_wait_s, computable
                             FROM gold.service_metric WHERE snapshot_id = %(sid)s""", sid, one=True)
        inputs = _q(conn, "SELECT doc FROM gold.decision_inputs WHERE snapshot_id = %(sid)s", sid, one=True)
        answers = _q(conn, """
            SELECT id AS bronze_id, source, to_char(event_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS sim_ts,
                   to_char(arrival_ts AT TIME ZONE 'UTC', 'HH24:MI:SS') AS arrival_utc, payload
            FROM bronze.events WHERE event_type = 'decision' AND payload->>'rec_id' = %(r)s ORDER BY id""",
                     {"r": str(rec_id)}) or []
        instruction = _q(conn, "SELECT * FROM gold.instruction_status WHERE rec_id = %(r)s", {"r": rec_id}, one=True)
    return {
        "rec": {k: rec[k] for k in ("rec_id", "status", "stale", "case", "proposed", "expires", "closed", "rules_version")},
        "steps": {
            "raw": {"bronze_cut": bronze_cut, "events_before": (n_raw or {}).get("n"), "latest": raw},
            "silver": {"stop_visits": visits},
            "gold": {"snapshot": snap, "corridor_now": corridor["doc"] if corridor else None, "service_metric": metric},
            "decision": {"inputs": _inputs_summary(inputs["doc"]) if inputs else None, "params": rec["params"]},
            "front": {"document": rec["doc"]},
            "response": {"decision_events": answers, "status": rec["status"], "closed": rec["closed"],
                         "instruction_status": instruction},
        },
    }


# ---------------------------------------------------------------------------------- app
app = FastAPI(title="PulsoFlota data flow viewer", docs_url=None, redoc_url=None)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(HERE / "index.html")


@app.get("/api/targets")
def targets() -> list[str]:
    return list(TARGETS)


@app.get("/api/flow/{target}")
def flow(target: str) -> dict[str, Any]:
    return overview(target)


@app.get("/api/trace/{target}/{rec_id}")
def trace_rec(target: str, rec_id: uuid.UUID) -> dict[str, Any]:
    return trace(target, rec_id)


@app.get("/api/whatif/{target}/base")
def whatif_base(target: str) -> dict[str, Any]:
    """The editable inputs of the newest snapshot and what the model proposes from them, unchanged."""
    with _connect(target) as conn:
        sid, inp, facts = whatif.load_base(conn, target)
    return {"inputs": whatif.describe(sid, inp, facts), "result": whatif.run(inp, facts)}


@app.post("/api/whatif/{target}/run")
def whatif_run(target: str, scenario: whatif.Scenario) -> dict[str, Any]:
    """The model on the edited inputs, next to the unchanged run. Nothing is written."""
    with _connect(target) as conn:
        sid, inp, facts = whatif.load_base(conn, target)
    new_inp, new_facts = whatif.apply(inp, facts, scenario)
    return {"snapshot_id": sid, "original": whatif.run(inp, facts), "scenario": whatif.run(new_inp, new_facts)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")  # noqa: S104 (inside its container)
