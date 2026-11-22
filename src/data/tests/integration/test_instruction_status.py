"""T033 — `gold.instruction_status`: rows, status times and pending rules (004 FR-015, FR-016, FR-019, FR-026, SC-007, SC-012).

Crafted bronze through the real boundary, decisions inserted the way the backend does, one gold cycle.
Seeds come from the fixture file (B-103 at P-887: 90 s, expires 22:35:00Z; B-102: 120 s; B-106: not a hold).
"""
from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from src.data.pipeline.seeds import load_seeds
from src.data.tests.fixtures.bronze_builders import Builder, ingest_all, insert_backend_commands, iso, trip_id
from src.data.tests.fixtures.gold_support import cycle, validator

SEEDS_FILE = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios" / "seed_recommendations.json"
REC = {n: f"{str(n) * 8}-{str(n) * 4}-4{str(n) * 3}-8{str(n) * 3}-{str(n) * 12}" for n in range(1, 6)}
TRIP = trip_id("B-103")
EXPIRES_1 = "2026-11-24T22:35:00Z"  # 2,100 s


def decision(n: int, action: str = "apply", tag: str = "is") -> dict:
    b = Builder(f"{tag}-{n}-{action}")
    return b._command("decision", 0, {"rec_id": REC[n], "action": action, "user_id": "dispatcher-01", "ts": iso(0)})


@pytest.fixture
def conn(gold_conn):
    load_seeds(gold_conn, SEEDS_FILE)
    gold_conn.commit()
    return gold_conn


def reports(conn, until: float = 1900, tag: str = "is-reports") -> None:
    b = Builder(tag)
    b.drive("B-103", 1235, until)
    b.drive("B-102", 635, until)
    ingest_all(conn, b.events)


def visit(conn, arrive: float, depart: float | None, tag: str = "is-visit") -> None:
    b = Builder(tag)
    b.stop_arrival("B-103", TRIP, "P-887", arrive)
    if depart is not None:
        b.stop_departure("B-103", TRIP, "P-887", depart)
    ingest_all(conn, b.events)


def rows(conn) -> dict[str, tuple]:
    out = conn.execute("SELECT rec_id::text, bus_id, stop_id, hold_s, observed_dwell_s, status, ts_by_status "
                       "FROM gold.instruction_status ORDER BY rec_id").fetchall()
    return {r[0]: r for r in out}


def test_executed_when_the_dwell_is_within_fifteen_seconds(conn) -> None:
    insert_backend_commands(conn, [decision(1)])
    reports(conn)
    visit(conn, 1650, 1740)
    cycle(conn, 1800)
    row = rows(conn)[REC[1]]
    assert row[1:4] == ("B-103", "P-887", 90) and row[4] == 90 and row[5] == "executed"
    assert row[6] == {"executed": iso(1740)}


def test_not_executed_when_the_dwell_is_the_natural_one(conn) -> None:
    insert_backend_commands(conn, [decision(1)])
    reports(conn)
    visit(conn, 1650, 1660)
    cycle(conn, 1800)
    row = rows(conn)[REC[1]]
    assert row[5] == "not_executed" and row[4] == 10 and row[6] == {"not_executed": iso(1660)}


def test_sixteen_seconds_off_is_not_executed(conn) -> None:
    insert_backend_commands(conn, [decision(1)])
    reports(conn)
    visit(conn, 1650, 1650 + 90 + 16)
    cycle(conn, 1800)
    assert rows(conn)[REC[1]][5] == "not_executed"


def test_no_row_while_pending(conn) -> None:
    insert_backend_commands(conn, [decision(1)])
    reports(conn, until=1600)
    cycle(conn, 1600)
    assert rows(conn) == {}  # window open, no visit
    visit(conn, 1650, None)
    reports(conn, until=1700, tag="is-reports-2")
    cycle(conn, 1700)
    assert rows(conn) == {}  # the bus is at the stop, not yet departed


def test_a_visit_still_open_after_the_window_is_pending_not_expired(conn) -> None:
    insert_backend_commands(conn, [decision(1)])
    visit(conn, 2090, None)  # arrived just before expires_ts and has not left at the reference time
    reports(conn, until=2150)
    cycle(conn, 2150)
    assert rows(conn) == {}


def test_expired_window_without_a_visit_is_not_executed_at_expires_ts(conn) -> None:
    insert_backend_commands(conn, [decision(1)])
    reports(conn, until=2200)
    cycle(conn, 2200)
    row = rows(conn)[REC[1]]
    assert row[5] == "not_executed" and row[4] is None and row[6] == {"not_executed": EXPIRES_1}


def test_silent_held_bus_ends_not_executed_at_expires_ts(conn) -> None:
    """A data fault: B-103 reports nothing during the visit (no arrival or departure at all)."""
    insert_backend_commands(conn, [decision(1)])
    b = Builder("is-fault")
    b.drive("B-102", 635, 2200)
    ingest_all(conn, b.events)
    cycle(conn, 2200)
    row = rows(conn)[REC[1]]
    assert row[5] == "not_executed" and row[6] == {"not_executed": EXPIRES_1}


def test_decision_written_after_the_bus_departed_is_not_executed(conn) -> None:
    reports(conn)
    visit(conn, 1650, 1740)
    insert_backend_commands(conn, [decision(1)])  # id after the visit: decided_at is at or after the arrival
    cycle(conn, 2200)
    row = rows(conn)[REC[1]]
    assert row[5] == "not_executed" and row[6] == {"not_executed": EXPIRES_1}


def test_breakdown_wins_over_a_matching_dwell(conn) -> None:
    insert_backend_commands(conn, [decision(1)])
    b = Builder("is-breakdown")
    b.incident("bus_breakdown", "B-103", at=1300, duration_min=2.0)
    ingest_all(conn, b.events)
    reports(conn)
    visit(conn, 1650, 1740)
    cycle(conn, 1800)
    row = rows(conn)[REC[1]]
    assert row[5] == "not_executed" and row[6] == {"not_executed": iso(1300)}


def test_hold_above_ninety_seconds_is_refused_and_reported_not_executed(conn) -> None:
    insert_backend_commands(conn, [decision(4)])
    reports(conn, until=1000)
    cycle(conn, 1000)  # window still open: the refusal does not wait
    row = rows(conn)[REC[4]]
    assert row[3] == 120 and row[5] == "not_executed" and row[6] == {"not_executed": "2026-11-24T22:25:00Z"}


def test_discard_unknown_and_non_hold_give_no_row(conn) -> None:
    unknown = Builder("is-unknown")._command("decision", 0, {"rec_id": "99999999-9999-4999-8999-999999999999",
                                                              "action": "apply", "user_id": "d", "ts": iso(0)})
    insert_backend_commands(conn, [decision(1, "discard"), unknown, decision(3)])
    reports(conn, until=2200)
    cycle(conn, 2200)
    assert rows(conn) == {}


def test_second_order_for_the_same_visit_is_a_conflict(conn) -> None:
    insert_backend_commands(conn, [decision(1), decision(5)])
    reports(conn)
    visit(conn, 1650, 1740)
    cycle(conn, 1800)
    out = rows(conn)
    assert out[REC[1]][5] == "executed" and out[REC[5]][5] == "not_executed"
    assert out[REC[5]][6] == {"not_executed": iso(1650)}


def test_same_decision_twice_gives_one_row(conn) -> None:
    insert_backend_commands(conn, [decision(1), decision(1, tag="is-again")])
    reports(conn)
    visit(conn, 1650, 1740)
    cycle(conn, 1800)
    assert len(rows(conn)) == 1


def test_rebuilt_each_cycle_and_stable_for_the_same_bronze(conn) -> None:
    insert_backend_commands(conn, [decision(1)])
    reports(conn)
    visit(conn, 1650, 1740)
    cycle(conn, 1800)
    first = rows(conn)
    cycle(conn, 1805)
    cycle(conn, 1810)
    assert rows(conn) == first
    conn.execute("DELETE FROM gold.instruction_status")
    conn.commit()
    cycle(conn, 1815)
    assert rows(conn) == first  # rebuilt from bronze, silver and config


def test_status_and_ts_by_status_validate_against_the_instruction_contract(conn) -> None:
    insert_backend_commands(conn, [decision(1), decision(4)])
    reports(conn)
    visit(conn, 1650, 1740)
    cycle(conn, 1800)
    v = validator("instruction")
    for rec, row in rows(conn).items():
        doc = {"schema_version": "1.0.0", "inst_id": rec, "rec_id": rec, "bus_id": row[1], "text": "hold",
               "status": row[5], "ts_by_status": row[6]}
        assert not list(v.iter_errors(doc)), doc
        assert list(row[6]) == [row[5]]  # exactly one key


def test_the_step_writes_nothing_to_bronze(conn) -> None:
    insert_backend_commands(conn, [decision(1)])
    reports(conn)
    visit(conn, 1650, 1740)
    before = conn.execute("SELECT count(*), max(id) FROM bronze.events").fetchone()
    cycle(conn, 1800)
    assert conn.execute("SELECT count(*), max(id) FROM bronze.events").fetchone() == before


def test_lineage_columns_and_table_shape(conn) -> None:
    insert_backend_commands(conn, [decision(1)])
    reports(conn)
    visit(conn, 1650, 1740)
    result = cycle(conn, 1800)
    rv, mx = conn.execute("SELECT rules_version, max_bronze_id FROM gold.instruction_status").fetchone()
    assert rv == "1.3.0" and mx == result.max_bronze_id
    pk = conn.execute("SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
                      "AND a.attnum = ANY(i.indkey) WHERE i.indrelid = 'gold.instruction_status'::regclass "
                      "AND i.indisprimary").fetchall()
    assert pk == [("rec_id",)]


def test_table_refuses_a_status_that_is_not_the_one_key(conn) -> None:
    for status, ts in (("executed", '{"not_executed": "2026-11-24T22:00:00Z"}'),
                       ("executed", '{"executed": "2026-11-24T22:00:00Z", "sent": "2026-11-24T22:00:00Z"}'),
                       ("sent", '{"sent": "2026-11-24T22:00:00Z"}')):
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "INSERT INTO gold.instruction_status (rec_id, bus_id, stop_id, hold_s, status, ts_by_status, "
                "rules_version, max_bronze_id) VALUES (gen_random_uuid(), 'B-103', 'P-887', 90, %s, %s::jsonb, "
                "'1.1.0', 1)", (status, ts))
        conn.rollback()
