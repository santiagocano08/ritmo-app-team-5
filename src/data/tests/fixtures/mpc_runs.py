"""Replay of a simulator run through the real cycle, collecting what the model published (006 T026, T027).

`replay` ingests a forced-mode run (fixed seed, fixed duration, no wall clock) into the connection's database and
runs `run_cycle` every `step_s` simulated seconds. After each cycle it reads, in the cycle's own state, the snapshot
(bus states), the latest `gold.mpc_evaluation` (which holds the latest cycle only) and every
`gold.recommendation` row. The result is plain data, so one run serves many assertions.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from src.data.ingestion.bronze import ingest
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.config import load_scenarios
from src.data.simulator.scenarios.truth import TruthSink
from src.data.tests.fixtures.gold_support import clear_all, cycle

SCENARIOS = Path(__file__).resolve().parent / "scenarios"


@dataclass
class Cycle:
    t: int
    snapshot_id: str
    buses: dict[str, dict]  # bus_id -> {state, quality, next_stop, prev_stop}
    sources_down: list[str]
    evaluation: list[dict]
    recs: list[dict]
    drivers_free: int = 2
    reserve_free: list[str] = field(default_factory=list)

    @property
    def bunched(self) -> bool:
        return any(b["state"] == "bunched" for b in self.buses.values())

    @property
    def trouble(self) -> bool:
        return any(b["state"] in ("bunched", "gap", "broken_down") for b in self.buses.values())


def ingest_run(conn: psycopg.Connection, scenario: str | None, duration: int, seed: int = 42,
               demand_scale: float = 1.0) -> None:
    scenarios = load_scenarios(SCENARIOS / f"{scenario}.json") if scenario else []
    truth = TruthSink(scenarios)
    for event in scenario_events(scenarios, seed, duration, truth, demand_scale=demand_scale):
        ingest(conn, event)
    truth.close()


def _snapshot(conn: psycopg.Connection, snapshot_id) -> tuple[dict, list[str], int, list[str]]:
    doc = conn.execute("SELECT doc FROM gold.decision_inputs WHERE snapshot_id = %s", (snapshot_id,)).fetchone()[0]
    status = conn.execute("SELECT doc FROM gold.source_status WHERE snapshot_id = %s", (snapshot_id,)).fetchone()[0]
    buses = {b["bus_id"]: {"state": b["bus_state"], "quality": b["data_quality"], "next_stop": b["next_stop_id"],
                           "prev_stop": b["prev_stop_id"]} for b in doc["buses"]}
    return (buses, [s["bus_id"] for s in status["sources_down"]], doc["resources"]["drivers_free"],
            doc["resources"]["reserve_free"])


def collect(conn: psycopg.Connection) -> tuple[list[dict], list[dict]]:
    conn.rollback()
    with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        ev = cur.execute("SELECT action, \"case\", score_s, saving_s_per_rider, recommended, reason_not "
                         "FROM gold.mpc_evaluation ORDER BY seq").fetchall()
        recs = cur.execute("SELECT rec_id::text AS rec_id, key, status, stale, proposed_ts, expires_ts, close_ts, "
                           "doc, params, lineage_detail FROM gold.recommendation ORDER BY proposed_ts, rec_id"
                           ).fetchall()
    conn.rollback()
    return ev, recs


def replay(conn: psycopg.Connection, scenario: str | None, duration: int, *, start_s: int = 300, step_s: int = 15,
           seed: int = 42, demand_scale: float = 1.0) -> list[Cycle]:
    clear_all(conn)
    ingest_run(conn, scenario, duration, seed, demand_scale)
    out: list[Cycle] = []
    for t in range(start_s, duration, step_s):
        res = cycle(conn, t)
        buses, down, drivers, reserve = _snapshot(conn, res.snapshot_id)
        conn.rollback()
        ev, recs = collect(conn)
        out.append(Cycle(t, str(res.snapshot_id), buses, down, ev, recs, drivers, reserve))
    return out
