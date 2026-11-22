"""Gold snapshot builder (feature 002, US2; data-model G1-G4, research R5, R8).

Orchestration only: it reads silver and `config`, calls the pure rules in `src/data/rules/`, builds
the read objects through the generated Pydantic models (contract `contracts/read/*.schema.json`)
and stores them. No threshold or planned headway lives here. The caller owns the transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from src.pulsoflota.models.read.corridor_now import CorridorNowV100
from src.pulsoflota.models.read.decision_inputs import DecisionInputsV100
from src.pulsoflota.models.read.source_status import SourceStatusV100
from src.data.rules import RULES_VERSION
from src.data.rules.classify import classify_buses, corridor_status, summarize
from src.data.rules.headway import BusObs, compute_headways, order_buses
from src.data.rules.service_metric import service_metric
from src.data.rules.snapshot_id import snapshot_id as make_snapshot_id
from src.data.rules.timebands import local_hour_band, m2_band, next_window

SQL_DIR = Path(__file__).resolve().parents[1] / "rules" / "sql"

SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class SnapshotResult:
    snapshot_id: UUID
    status: str
    created: bool


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def rebuild_baselines(conn: psycopg.Connection, as_of_ts: datetime, max_bronze_id: int) -> None:
    """Replace `gold.m1_baseline` and `gold.m2_baseline` for this cycle (FR-027..FR-031).

    Runs after the silver rebuild, in the caller's transaction. The thresholds (minimum sample
    count, M2 stop) are read from `config` by the SQL, never from literals here.
    """
    params = {"as_of_ts": _utc(as_of_ts), "max_bronze_id": max_bronze_id, "rules_version": RULES_VERSION}
    with conn.cursor() as cur:
        for table, sql_file in (("m1_baseline", "gold_m1_baseline.sql"), ("m2_baseline", "gold_m2_baseline.sql")):
            cur.execute(f"DELETE FROM gold.{table}")  # noqa: S608 - fixed table names
            cur.execute((SQL_DIR / sql_file).read_text(encoding="utf-8"), params)


def build_snapshot(conn: psycopg.Connection, as_of_ts: datetime, max_bronze_id: int) -> SnapshotResult:
    """Insert the snapshot and its gold rows from the silver tables built for this cycle.

    A snapshot with the same identity (R5) is left untouched and `created` is False.
    """
    as_of = _utc(as_of_ts)
    sid = make_snapshot_id(as_of, RULES_VERSION, max_bronze_id)
    with conn.cursor(row_factory=dict_row) as cur:
        inserted = cur.execute(
            "INSERT INTO gold.snapshots (snapshot_id, as_of_ts, rules_version, max_bronze_id) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING snapshot_id",
            (sid, as_of, RULES_VERSION, max_bronze_id)).fetchone()
        if inserted is None:
            existing = cur.execute("SELECT status FROM gold.source_status WHERE snapshot_id = %s",
                                   (sid,)).fetchone()
            return SnapshotResult(sid, existing["status"] if existing else "no_data", False)

        settings = cur.execute(
            "SELECT corridor_id, direction, headway_planned_s, drivers_free, hold_penalty_s, "
            "early_departure_penalty_s FROM config.corridor_settings").fetchone()
        planned = float(settings["headway_planned_s"])
        state_rows = cur.execute(
            "SELECT bus_id, distance_along_m, position_ts, prev_stop_id, next_stop_id, last_report_ts, "
            "data_quality, operational_status, on_corridor, waiting FROM silver.bus_current_state ORDER BY bus_id"
        ).fetchall()
        history_rows = cur.execute(
            "SELECT h.bus_id, h.event_ts, h.distance_along_m FROM silver.position_history h "
            "JOIN silver.bus_current_state s ON s.bus_id = h.bus_id AND s.position_trip_id = h.trip_id "
            "WHERE s.on_corridor ORDER BY h.bus_id, h.event_ts, h.bronze_id").fetchall()

        history: dict[str, list[tuple[datetime, float]]] = {}
        for r in history_rows:
            history.setdefault(r["bus_id"], []).append((_utc(r["event_ts"]), float(r["distance_along_m"])))

        # Departure from the first stop on the trip each bus is positioned on (US2, research R3): a bus waiting at
        # the terminal reports the same distance until it leaves, so the headway counts from the departure.
        origin = cur.execute("SELECT distance_along_m FROM config.ref_stops WHERE stop_seq = 1").fetchone()
        origin_m = float(origin["distance_along_m"]) if origin else 0.0
        departure_rows = cur.execute(
            "SELECT s.bus_id, v.departure_ts FROM silver.bus_current_state s "
            "JOIN silver.stop_visits v ON v.bus_id = s.bus_id AND v.trip_id = s.position_trip_id "
            "JOIN config.ref_stops r ON r.stop_id = v.stop_id AND r.stop_seq = 1 WHERE s.on_corridor").fetchall()
        first_departure = {r["bus_id"]: _utc(r["departure_ts"]) for r in departure_rows}

        on_corridor = [r for r in state_rows if r["on_corridor"] and r["distance_along_m"] is not None]
        by_id = {r["bus_id"]: r for r in on_corridor}
        ordered = order_buses([
            BusObs(bus_id=r["bus_id"], distance_along_m=float(r["distance_along_m"]),
                   position_ts=_utc(r["position_ts"]), history=tuple(history.get(r["bus_id"], ())),
                   estimated=r["data_quality"] == "estimated",
                   broken_down=r["operational_status"] == "broken_down",
                   departure_ts=first_departure.get(r["bus_id"]))
            for r in on_corridor])
        headways = compute_headways(ordered, origin_m)
        states = classify_buses(ordered, headways, planned)
        in_service, n_bunched, n_gaps = summarize(states)

        # A silent waiting bus is still a silent source (R7); a bus that finished its trip is not.
        sources_down = [{"bus_id": r["bus_id"], "since": _utc(r["last_report_ts"])}
                        for r in state_rows
                        if (r["on_corridor"] or r["waiting"]) and r["data_quality"] == "estimated"]
        status = corridor_status(bool(state_rows), len(sources_down))

        source_status = SourceStatusV100.model_validate({
            "schema_version": SCHEMA_VERSION, "snapshot_id": sid, "as_of_ts": as_of,
            "status": status, "sources_down": sources_down})
        corridor_now = CorridorNowV100.model_validate({
            "schema_version": SCHEMA_VERSION, "snapshot_id": sid, "as_of_ts": as_of,
            "corridor_id": settings["corridor_id"], "direction": settings["direction"],
            "buses": [{
                "bus_id": b.bus_id, "direction": settings["direction"],
                "prev_stop_id": by_id[b.bus_id]["prev_stop_id"] or by_id[b.bus_id]["next_stop_id"],
                "next_stop_id": by_id[b.bus_id]["next_stop_id"] or by_id[b.bus_id]["prev_stop_id"],
                "distance_along_m": b.distance_along_m,
                "headway_ahead_s": headways[b.bus_id].seconds,
                "headway_planned_s": planned,
                "bus_state": states[b.bus_id],
                "data_quality": by_id[b.bus_id]["data_quality"],
                "ts": b.position_ts} for b in ordered],
            "summary": {"buses_in_service": in_service, "n_bunched": n_bunched, "n_gaps": n_gaps}})

        metric = service_metric([h.seconds for h in headways.values() if h.seconds is not None], planned)

        decision_inputs = _decision_inputs(cur, sid, as_of, settings, corridor_now,
                                           {r["bus_id"] for r in on_corridor})

        lineage = (RULES_VERSION, max_bronze_id)
        cur.execute(
            "INSERT INTO gold.source_status (snapshot_id, status, doc, rules_version, max_bronze_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (sid, status, Jsonb(source_status.model_dump(mode="json")), *lineage))
        cur.execute(
            "INSERT INTO gold.corridor_now (snapshot_id, doc, rules_version, max_bronze_id) "
            "VALUES (%s, %s, %s, %s)",
            (sid, Jsonb(corridor_now.model_dump(mode="json")), *lineage))
        cur.execute(
            "INSERT INTO gold.decision_inputs (snapshot_id, doc, rules_version, max_bronze_id) "
            "VALUES (%s, %s, %s, %s)",
            (sid, Jsonb(decision_inputs.model_dump(mode="json")), *lineage))
        cur.execute(
            "INSERT INTO gold.service_metric (snapshot_id, n_headways, mean_wait_s, scheduled_wait_s, ewt_s, "
            "computable, rules_version, max_bronze_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (sid, metric.n_headways, metric.mean_wait_s, metric.scheduled_wait_s, metric.ewt_s,
             metric.computable, *lineage))
    return SnapshotResult(sid, status, True)


def _decision_inputs(cur, sid: UUID, as_of: datetime, settings: dict, corridor_now: CorridorNowV100,
                     on_corridor_ids: set[str]) -> DecisionInputsV100:
    """Build the decision_inputs object (FR-032..FR-035). `buses` and `summary` are taken from the
    very `corridor_now` object of this snapshot, so the two cannot differ."""
    shared = corridor_now.model_dump(mode="json")
    forecast = cur.execute(
        "SELECT segment_id, forecast_travel_s FROM gold.m1_baseline WHERE hour_band = %s ORDER BY segment_id",
        (local_hour_band(as_of),)).fetchall()
    window_start, window_end = next_window(as_of)
    demand = cur.execute("SELECT arrivals_forecast FROM gold.m2_baseline WHERE band = %s",
                         (m2_band(window_start),)).fetchone()
    reserve = [r["bus_id"] for r in cur.execute(
        "SELECT bus_id FROM config.fleet_roster WHERE role = 'reserve' ORDER BY bus_id").fetchall()
        if r["bus_id"] not in on_corridor_ids]
    incidents = [r["inc_id"] for r in cur.execute(
        "SELECT inc_id FROM silver.incidents WHERE start_ts <= %s AND end_ts > %s ORDER BY inc_id",
        (as_of, as_of)).fetchall()]
    stops = [r["stop_id"] for r in cur.execute("SELECT stop_id FROM config.enabled_stops ORDER BY stop_id").fetchall()]
    return DecisionInputsV100.model_validate({
        "schema_version": SCHEMA_VERSION, "snapshot_id": sid, "as_of_ts": as_of,
        "corridor_id": settings["corridor_id"], "direction": settings["direction"],
        "buses": shared["buses"], "summary": shared["summary"],
        "travel_time_forecast": [{"segment_id": r["segment_id"], "forecast_travel_s": float(r["forecast_travel_s"])}
                                 for r in forecast],
        "demand_15min": {"window_start_ts": window_start, "window_end_ts": window_end,
                         "arrivals_forecast": demand["arrivals_forecast"]},
        "resources": {"reserve_free": reserve, "drivers_free": settings["drivers_free"]},
        "action_cost": {"hold_penalty_s": float(settings["hold_penalty_s"]),
                        "early_departure_penalty_s": float(settings["early_departure_penalty_s"])},
        "active_incidents": incidents, "enabled_stops": stops})
