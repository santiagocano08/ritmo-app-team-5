"""T032 — the read-only decision poller against a throwaway database (004 FR-017, FR-028, SC-011; AC7)."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest

from src.data.simulator.scenarios import holds as holds_module
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.holds import HoldBoard, HoldPoller, connect_read_only, fetch_decisions
from src.data.simulator.scenarios.truth import TruthSink
from src.data.tests.fixtures.bronze_builders import Builder, insert_backend_commands, iso
from src.data.tests.fixtures.rec_support import insert_seed_like

START = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
REC1 = "11111111-1111-4111-8111-111111111111"
REC2 = "22222222-2222-4222-8222-222222222222"


def decision(rec_id: str, action: str = "apply", at: float = 0, tag: str = "poller") -> dict:
    b = Builder(f"{tag}-{rec_id}-{action}-{at}")
    return b._command("decision", at, {"rec_id": rec_id, "action": action, "user_id": "dispatcher-01", "ts": iso(at)})


@pytest.fixture
def conn(module_db_dsn):
    with psycopg.connect(module_db_dsn) as c:
        c.execute("TRUNCATE bronze.events, bronze.rejections RESTART IDENTITY")
        c.execute("DELETE FROM gold.recommendation")
        c.commit()
        insert_seed_like(c)  # 006 R4: the recommendations the old seed file held, as `gold.recommendation` rows
        yield c


def test_the_session_is_read_only(module_db_dsn, conn) -> None:
    ro = connect_read_only(module_db_dsn)
    try:
        assert ro.execute("SELECT count(*) FROM bronze.events").fetchone()[0] == 0
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            ro.execute("INSERT INTO bronze.rejections (reason, received_ts) VALUES ('duplicate_event', now())")
    finally:
        ro.close()


def test_new_decisions_appear_in_id_order_and_only_once(module_db_dsn, conn) -> None:
    insert_backend_commands(conn, [decision(REC2, at=1), decision(REC1, at=2)])
    board = HoldBoard(seed=42, noncompliance=0.0)
    poller = HoldPoller(module_db_dsn, board, START, 1.0)
    poller.poll_once()
    assert [o.rec_id for o in board.pending_orders()] == [REC2, REC1]
    insert_backend_commands(conn, [decision("44444444-4444-4444-8444-444444444444", at=3)])
    poller.poll_once()
    poller.poll_once()
    assert len(board.pending_orders()) == 2  # the 120 s hold is refused; the first two are not repeated
    assert poller.last_id == 3
    poller.stop()


def test_the_poller_resolves_a_rec_id_from_the_recommendation_table(module_db_dsn, conn) -> None:
    """006 R4: `SELECT rec_id, doc, params FROM gold.recommendation` through the read-only session."""
    insert_backend_commands(conn, [decision(REC1)])
    board = HoldBoard(seed=42, noncompliance=0.0)
    poller = HoldPoller(module_db_dsn, board, START, 1.0)
    poller.poll_once()
    (o,) = board.pending_orders()
    assert (o.rec_id, o.bus_id, o.stop_id, o.hold_s, o.until_s) == (REC1, "B-103", "P-887", 90.0, 2100.0)
    assert poller.unresolved_ids() == []
    poller.stop()


def test_a_decision_whose_row_does_not_exist_yet_is_retried(module_db_dsn, conn) -> None:
    late = "88888888-8888-4888-8888-888888888888"
    insert_backend_commands(conn, [decision(late)])
    board = HoldBoard(seed=42, noncompliance=0.0)
    poller = HoldPoller(module_db_dsn, board, START, 1.0)
    poller.poll_once()
    assert board.pending_orders() == [] and poller.unresolved_ids() == [late]
    from src.data.tests.fixtures.rec_support import insert_recommendation
    insert_recommendation(conn, late, bus="B-104", stop="P-888", duration_s=60, expires="2026-11-24T22:40:00Z")
    poller.poll_once()
    assert [o.rec_id for o in board.pending_orders()] == [late] and poller.unresolved_ids() == []
    poller.stop()


def test_decided_at_sim_is_the_newest_bus_report_with_a_smaller_id(module_db_dsn, conn) -> None:
    insert_backend_commands(conn, [decision(REC1, at=0)])  # before every report: null
    b = Builder("poller-reports")
    b.position("B-101", "C6-008-B-101-001", 50, 10.0)
    b.position("B-102", "C6-008-B-102-001", 40, 10.0)  # older event_ts, larger id: not the newest by time
    for e in b.events:
        conn.execute(
            "INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload) "
            "VALUES (%s, %s, %s, %s, %s, now(), %s::jsonb)",
            (e["source"], e["event_id"], e["schema_version"], e["event_type"], e["event_ts"],
             json.dumps(e["payload"])))
    conn.commit()
    insert_backend_commands(conn, [decision(REC2, at=999)])  # backend report must not count either
    rows = fetch_decisions(conn, 0)
    assert [r.rec_id for r in rows] == [REC1, REC2]
    assert rows[0].decided_at is None
    assert rows[1].decided_at == datetime(2026, 11, 24, 22, 0, 50, tzinfo=timezone.utc)


def test_decisions_of_other_sources_and_types_are_ignored(conn) -> None:
    other = decision(REC1)
    other["event_type"] = "confirmation"
    other["payload"] = {"inst_id": REC1, "status": "received", "ts": iso(0)}
    insert_backend_commands(conn, [other])
    assert fetch_decisions(conn, 0) == []


def test_database_down_does_not_raise_or_block() -> None:
    board = HoldBoard(seed=42, noncompliance=0.0)
    poller = HoldPoller("postgresql://nobody:x@127.0.0.1:1/none", board, START, 1.0)
    started = time.monotonic()
    poller.poll_once()
    assert time.monotonic() - started < 5 and poller.failed


def test_poller_module_has_select_only() -> None:
    code = Path(holds_module.__file__).read_text(encoding="utf-8")
    assert not re.search(r"\b(INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|TRUNCATE|CREATE\s+TABLE|DROP\s+)", code, re.I)


def test_pre_written_decision_is_on_the_board_before_the_first_event(module_db_dsn, conn) -> None:
    """The initial synchronous poll: the daemon thread is not started, the run is still deterministic."""
    insert_backend_commands(conn, [decision(REC1)])
    board = HoldBoard(seed=42, noncompliance=0.0)
    poller = HoldPoller(module_db_dsn, board, START, 1.0)
    poller.poll_once()  # what main() does before the first simulated event
    assert poller.thread is None
    events = list(scenario_events([], 42, 2400, TruthSink([]), holds=board))
    arr = next(e for e in events if e["event_type"] == "stop_arrival" and e["payload"]["bus_id"] == "B-103"
               and e["payload"]["stop_id"] == "P-887")
    dep = next(e for e in events if e["event_type"] == "stop_departure" and e["payload"]["bus_id"] == "B-103"
               and e["payload"]["stop_id"] == "P-887")
    assert (arr["event_ts"], dep["event_ts"]) == ("2026-11-24T22:27:45Z", "2026-11-24T22:29:15Z")


def test_the_thread_polls_and_stops(module_db_dsn, conn) -> None:
    board = HoldBoard(seed=42, noncompliance=0.0)
    poller = HoldPoller(module_db_dsn, board, START, 0.05)
    poller.start()
    insert_backend_commands(conn, [decision(REC1)])
    deadline = time.monotonic() + 5
    while not board.pending_orders() and time.monotonic() < deadline:
        time.sleep(0.05)
    poller.stop()
    assert board.pending_orders() and not poller.thread.is_alive()
