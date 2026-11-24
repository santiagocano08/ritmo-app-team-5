"""T046 (US5, FR-050 to FR-053, SC-012): an impossible position never blinds the dispatcher.

G1: ingestion rejects `distance_along_m` above the route end with `value_out_of_range`.
G2: a row that is already in bronze (inserted straight) is ignored by silver; the cycle still writes a snapshot.
"""
from __future__ import annotations

import copy
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from psycopg.types.json import Jsonb

from src.data.ingestion.bronze import ingest
from src.data.ingestion.route_bounds import RouteBounds
from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import count, cycle, docs
from src.data.tests.fixtures.silver_support import at, build, state
from src.data.tests.integration.test_scenarios_gold import load_run

ROOT = Path(__file__).resolve().parents[4]
AS_OF = 2655
BAD_M = 99999.0
ROUTE_END_M = 5119.4


def _position(distance_m: float, at_s: float = 5, bus: str = "B-106", tag: str = "g") -> dict:
    return bb.Builder(tag).position(bus, bb.trip_id(bus), at_s, distance_m)


def _raw_insert(conn, env: dict) -> None:
    """Insert a bronze row the way a defect or an older version would (no validation of the range)."""
    env = copy.deepcopy(env)
    env["event_id"] = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload) "
        "VALUES (%s, %s, %s, %s, %s, now(), %s)",
        (env["source"], env["event_id"], env["schema_version"], env["event_type"], env["event_ts"],
         Jsonb(env["payload"])))
    conn.commit()


def _rejections(conn) -> list[tuple]:
    return conn.execute("SELECT reason, original_message FROM bronze.rejections ORDER BY id").fetchall()


# --- G1: ingestion -------------------------------------------------------------------------------

@pytest.mark.parametrize("distance_m", [BAD_M, 5119.5])
def test_ingestion_rejects_a_position_beyond_the_route_end(silver_conn, distance_m) -> None:
    msg = _position(distance_m)
    result = ingest(silver_conn, msg, bounds=RouteBounds())
    assert result.accepted is False and result.reason == "value_out_of_range"
    assert count(silver_conn, "bronze.events") == 0
    rows = _rejections(silver_conn)
    assert len(rows) == 1 and rows[0][0] == "value_out_of_range"
    assert rows[0][1] == msg  # the original message is kept


@pytest.mark.parametrize("distance_m", [0.0, ROUTE_END_M])
def test_ingestion_accepts_the_two_ends_of_the_route(silver_conn, distance_m) -> None:
    result = ingest(silver_conn, _position(distance_m), bounds=RouteBounds())
    assert result.accepted is True
    assert count(silver_conn, "bronze.events") == 1 and _rejections(silver_conn) == []


def test_the_range_check_applies_to_bus_position_only(silver_conn) -> None:
    arrival = bb.Builder("g").stop_arrival("B-106", bb.trip_id("B-106"), bb.TERMINUS, 5)
    assert ingest(silver_conn, arrival, bounds=RouteBounds()).accepted is True


def test_an_unreadable_bound_keeps_capturing_events(silver_conn) -> None:
    class Unreadable:
        def get(self, conn):
            return None

    result = ingest(silver_conn, _position(BAD_M), bounds=Unreadable())
    assert result.accepted is True and count(silver_conn, "bronze.events") == 1


# --- G2: silver and gold ------------------------------------------------------------------------

@pytest.fixture
def c1_run(gold_conn):
    load_run(gold_conn, "c1_bunching", duration=2700)
    return gold_conn


def _silver_others(conn) -> dict:
    rows = conn.execute(
        "SELECT bus_id, trip_id, distance_along_m, position_ts, prev_stop_id, next_stop_id, last_report_ts, "
        "data_quality, on_corridor, waiting, operational_status FROM silver.bus_current_state "
        "WHERE bus_id <> 'B-105' ORDER BY bus_id").fetchall()
    return {r[0]: r for r in rows}


def _by_bus(conn, snapshot_id) -> dict:
    return {b["bus_id"]: b for b in docs(conn, snapshot_id)["corridor_now"]["buses"]}


def test_a_99999_position_in_bronze_does_not_break_the_cycle(c1_run) -> None:
    conn = c1_run
    before = cycle(conn, AS_OF)
    base = _by_bus(conn, before.snapshot_id)
    assert "B-105" in base
    others = {k: v for k, v in base.items() if k != "B-105"}
    assert others  # the C1 stream has at most 3 buses on the corridor at once, so "the other in-service buses"
    silver_before = _silver_others(conn)
    assert len(silver_before) == 6  # the 6 other in-service buses of the 7 + 4 fleet that have reported (issue #42)

    bad = bb.Builder("bad").position("B-105", bb.trip_id("B-105"), AS_OF, BAD_M)
    _raw_insert(conn, bad)

    result = cycle(conn, AS_OF)  # on the unfixed code: CycleError (CorridorNowV100 rejects 99999)
    assert result is not None and result.created is True
    snap = docs(conn, result.snapshot_id)
    assert {d["bus_id"] for d in snap["source_status"]["sources_down"]} == {"B-105"}
    down = snap["source_status"]["sources_down"][0]
    assert down["since"].replace("Z", "+00:00") == at(AS_OF).isoformat()

    buses = _by_bus(conn, result.snapshot_id)
    assert buses["B-105"]["data_quality"] == "estimated"
    assert buses["B-105"]["distance_along_m"] == base["B-105"]["distance_along_m"]  # last valid position kept
    # its state is kept from the last valid position (leader in the 7 + 4 C1 stream; regular with 5 buses)
    assert buses["B-105"]["bus_state"] == base["B-105"]["bus_state"] == "leader"
    for bus, row in others.items():  # SC-012: the four other in-service buses keep their state
        assert buses[bus]["bus_state"] == row["bus_state"]
        assert buses[bus]["data_quality"] == "live"
        assert buses[bus]["distance_along_m"] == row["distance_along_m"]
    assert _silver_others(conn) == silver_before  # SC-012: the 4 other buses keep their silver state
    alerts = conn.execute("SELECT count(*) FROM gold.incident WHERE snapshot_id = %s "
                          "AND doc::text LIKE '%%B-105%%'", (result.snapshot_id,)).fetchone()[0]
    assert alerts == 0


def test_silver_ignores_the_impossible_row_and_keeps_the_valid_position(c1_run) -> None:
    conn = c1_run
    build(conn, AS_OF)
    valid = float(state(conn)["B-105"]["distance_along_m"])
    _raw_insert(conn, bb.Builder("bad").position("B-105", bb.trip_id("B-105"), AS_OF, BAD_M))
    build(conn, AS_OF)
    row = state(conn)["B-105"]
    assert float(row["distance_along_m"]) == valid and row["data_quality"] == "estimated"
    assert conn.execute("SELECT count(*) FROM silver.position_history WHERE distance_along_m > %s",
                        (ROUTE_END_M,)).fetchone()[0] == 0


def test_a_later_valid_position_returns_the_bus_to_live(c1_run) -> None:
    conn = c1_run
    _raw_insert(conn, bb.Builder("bad").position("B-105", bb.trip_id("B-105"), AS_OF, BAD_M))
    build(conn, AS_OF)
    assert state(conn)["B-105"]["data_quality"] == "estimated"
    later = bb.Builder("later").position("B-105", bb.trip_id("B-105"), AS_OF + 1, 4300.0)
    assert ingest(conn, later, bounds=RouteBounds()).accepted is True
    build(conn, AS_OF + 1)
    row = state(conn)["B-105"]
    assert row["data_quality"] == "live" and float(row["distance_along_m"]) == 4300.0


def test_a_bus_with_no_in_range_position_has_no_position_and_is_not_in_the_corridor(gold_conn) -> None:
    conn = gold_conn
    b = bb.Builder("none")
    b.stop_departure("B-106", bb.trip_id("B-106"), bb.STOPS[0], 0)
    b.drive("B-107", 0, 20)
    bb.ingest_all(conn, b.events)
    _raw_insert(conn, bb.Builder("bad").position("B-106", bb.trip_id("B-106"), 5, BAD_M))
    result = cycle(conn, 20)
    row = state(conn)["B-106"]
    assert row["distance_along_m"] is None and row["position_ts"] is None
    assert row["prev_stop_id"] is None and row["next_stop_id"] is None
    assert row["data_quality"] == "estimated"
    snap = docs(conn, result.snapshot_id)
    assert "B-106" not in {x["bus_id"] for x in snap["corridor_now"]["buses"]}
    assert "B-107" in {x["bus_id"] for x in snap["corridor_now"]["buses"]}
    assert "B-106" in {d["bus_id"] for d in snap["source_status"]["sources_down"]}


# --- FR-053 --------------------------------------------------------------------------------------

def test_no_contract_or_adr_changed() -> None:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("needs a git checkout")
    ref = subprocess.run(["git", "rev-parse", "--verify", "-q", "main"],
                         cwd=ROOT, capture_output=True, text=True)
    if ref.returncode != 0:
        pytest.skip("reference branch not available")
    # 006 FR-029 authorises exactly these contract files (recommendation 1.1.0, its README, two new fixtures);
    # every other contract file and every ADR must still be identical to main (the 004 branch it used to
    # compare with predates contract v0.3 and the team ADRs 0004/0005 that main now carries).
    # Issue #42 (contract v0.5) authorises the bus_id enums of every schema and the ADR-0002/0003 amendments.
    fleet = ("contracts/turn1-events", "contracts/read/corridor_now.schema.json", "contracts/read/source_status.schema.json",
             "contracts/read/decision_inputs.schema.json", "contracts/read/instruction.schema.json",
             "docs/adr/0002-turn1-event-contract.md", "docs/adr/0003-turn1-read-contract.md")
    allowed = [f":(exclude){p}" for p in ("contracts/read/recommendation.schema.json", "contracts/read/README.md",
                                          "contracts/read/fixtures/c1_slow_down", "contracts/read/fixtures/c2_skip_stop",
                                          *fleet)]
    diff = subprocess.run(["git", "diff", "main", "--", "contracts", "docs/adr", *allowed],
                          cwd=ROOT, capture_output=True, text=True)
    assert diff.stdout == ""
