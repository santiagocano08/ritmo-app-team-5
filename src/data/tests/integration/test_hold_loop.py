"""T034 — the closed loop for hold, offline (004 FR-012 to FR-016, FR-020, SC-007, SC-012; AC1 to AC9).

Crafted `decision` rows go into `bronze.events` as the backend writes them; the simulator runs with
`--holds on` against the same throwaway database (pace 0); its events go through the real ingestion
boundary; gold is computed with the cycle path. The recommendations are `gold.recommendation` rows made by
`rec_support` (B-103 at P-887 arrives at 1,650 s, expires at 2,100 s).
"""
from __future__ import annotations

import io
import json

import pytest
from psycopg.types.json import Jsonb

from src.data.ingestion.bronze import ingest
from src.data.simulator.engine import run
from src.data.simulator.main import main
from src.data.tests.fixtures.bronze_builders import Builder, iso
from src.data.tests.fixtures.gold_support import cycle
from src.data.tests.fixtures.rec_support import insert_seed_like

REC1 = "11111111-1111-4111-8111-111111111111"
REC4 = "44444444-4444-4444-8444-444444444444"
REC5 = "55555555-5555-4555-8555-555555555555"
DURATION = 2400


def decision(rec_id: str, action: str = "apply", tag: str = "loop") -> dict:
    return Builder(f"{tag}-{rec_id}-{action}")._command(
        "decision", 0, {"rec_id": rec_id, "action": action, "user_id": "dispatcher-01", "ts": iso(0)})


def write_decision(conn, cmd: dict) -> None:
    conn.execute(
        "INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload) "
        "VALUES (%s, %s, %s, %s, %s, now(), %s) ON CONFLICT (source, event_id) DO NOTHING",
        (cmd["source"], cmd["event_id"], cmd["schema_version"], cmd["event_type"], cmd["event_ts"],
         Jsonb(cmd["payload"])))
    conn.commit()


@pytest.fixture
def conn(gold_conn):
    insert_seed_like(gold_conn)
    return gold_conn


@pytest.fixture
def simulate(module_db_dsn, monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", module_db_dsn)
    monkeypatch.setenv("SIM_TRUTH_PATH", str(tmp_path / "truth.jsonl"))
    monkeypatch.delenv("SIM_SCENARIO_FILE", raising=False)

    def go(noncompliance: float = 0.0, holds: str = "on") -> list[dict]:
        monkeypatch.setenv("SIM_HOLD_NONCOMPLIANCE", str(noncompliance))
        buf = io.StringIO()
        main(["--seed", "42", "--duration", str(DURATION), "--holds", holds], out=buf)
        return [json.loads(x) for x in buf.getvalue().splitlines()]

    return go


def feed(conn, events: list[dict]) -> None:
    for e in events:
        ingest(conn, e)


def status_rows(conn) -> dict:
    return {r[0]: r for r in conn.execute(
        "SELECT rec_id::text, status, observed_dwell_s, ts_by_status FROM gold.instruction_status")}


def departure_after(events: list[dict], bus="B-103", stop="P-887") -> tuple[str, str]:
    arr = next(e for e in events if e["event_type"] == "stop_arrival" and e["payload"]["bus_id"] == bus
               and e["payload"]["stop_id"] == stop)
    dep = next(e for e in events if e["event_type"] == "stop_departure" and e["payload"]["bus_id"] == bus
               and e["payload"]["stop_id"] == stop)
    return arr["event_ts"], dep["event_ts"]


def test_forced_compliance_gives_executed(conn, simulate) -> None:
    write_decision(conn, decision(REC1))
    events = simulate(0.0)
    assert departure_after(events) == ("2026-11-24T22:21:35Z", "2026-11-24T22:23:05Z")
    feed(conn, events)
    cycle(conn, DURATION - 5)
    row = status_rows(conn)[REC1]
    assert row[1] == "executed" and abs(row[2] - 90) <= 15
    assert row[3] == {"executed": "2026-11-24T22:23:05Z"}


def test_forced_non_compliance_gives_not_executed(conn, simulate) -> None:
    write_decision(conn, decision(REC1))
    events = simulate(1.0)
    feed(conn, events)
    cycle(conn, DURATION - 5)
    assert status_rows(conn)[REC1][1] == "not_executed"


def test_discard_and_no_decision_run_no_hold(conn, simulate) -> None:
    baseline = [json.loads(json.dumps(e, sort_keys=True)) for e in run(42, DURATION)]
    assert simulate(0.0) == baseline  # no decision at all (Principle IV)
    write_decision(conn, decision(REC1, "discard"))
    assert simulate(0.0) == baseline
    feed(conn, baseline)
    cycle(conn, DURATION - 5)
    assert status_rows(conn) == {}


def test_seeded_hold_of_120_s_is_refused_and_reported(conn, simulate) -> None:
    write_decision(conn, decision(REC4))
    baseline = [json.loads(json.dumps(e, sort_keys=True)) for e in run(42, DURATION)]
    events = simulate(0.0)
    assert events == baseline  # the executor refused it: nothing changed
    feed(conn, events)
    cycle(conn, DURATION - 5)
    row = status_rows(conn)[REC4]
    assert row[1] == "not_executed" and row[3] == {"not_executed": "2026-11-24T22:25:00Z"}


def test_decision_written_after_the_bus_departed_does_not_hold(conn, simulate) -> None:
    baseline = simulate(0.0)  # first run with no decision
    feed(conn, baseline)
    write_decision(conn, decision(REC1))  # written after every report of the run
    again = simulate(0.0)
    assert again == baseline  # decided_at_sim is the end of the run: no arrival is strictly after it
    cycle(conn, DURATION - 5)
    row = status_rows(conn)[REC1]
    assert row[1] == "not_executed" and row[3] == {"not_executed": "2026-11-24T22:35:00Z"}


def test_same_decision_delivered_twice_runs_once(conn, simulate) -> None:
    cmd = decision(REC1)
    write_decision(conn, cmd)
    write_decision(conn, cmd)
    other = decision(REC1, tag="loop-second-event")  # same rec_id, another event id
    write_decision(conn, other)
    assert conn.execute("SELECT count(*) FROM bronze.events WHERE event_type = 'decision'").fetchone()[0] == 2
    events = simulate(0.0)
    assert departure_after(events)[1] == "2026-11-24T22:23:05Z"
    feed(conn, events)
    cycle(conn, DURATION - 5)
    assert len(status_rows(conn)) == 1


def test_reprocessing_the_same_bronze_leaves_the_rows_unchanged(conn, simulate) -> None:
    write_decision(conn, decision(REC1))
    feed(conn, simulate(0.0))
    cycle(conn, DURATION - 5)
    first = status_rows(conn)
    cycle(conn, DURATION)
    cycle(conn, DURATION - 5)
    assert status_rows(conn) == first and len(first) == 1


def test_two_orders_for_the_same_visit_run_the_first_only(conn, simulate) -> None:
    write_decision(conn, decision(REC1))
    write_decision(conn, decision(REC5))
    events = simulate(0.0)
    assert departure_after(events)[1] == "2026-11-24T22:23:05Z"  # 90 s from the first order, not 45 s
    feed(conn, events)
    cycle(conn, DURATION - 5)
    out = status_rows(conn)
    assert out[REC1][1] == "executed" and out[REC5][1] == "not_executed"


def test_hold_run_does_not_write_to_bronze_by_itself(conn, simulate) -> None:
    write_decision(conn, decision(REC1))
    before = conn.execute("SELECT count(*) FROM bronze.events").fetchone()[0]
    simulate(0.0)  # the simulator only prints events; the poller is read-only
    assert conn.execute("SELECT count(*) FROM bronze.events").fetchone()[0] == before
