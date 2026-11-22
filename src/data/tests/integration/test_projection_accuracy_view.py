"""006 T049d — `gold.v_projection_accuracy` on crafted rows (FR-036).

`as_of` is 2026-11-24T22:00:00Z for every projection; times below are seconds after it. Each case is a
`(bus, stop)` pair; `lead` is also the projected departure second. Real departures come from `silver.stop_visits`.

| case | bus/stop | lead | real departure (s) | error_s | bucket | affected |
|---|---|---|---|---|---|---|
| late | B-1/P-1 | 100 | 135 | +35 | 0-5 min | no |
| early, last second of bucket 1 | B-1/P-2 | 299 | 290 | -9 | 0-5 min | no |
| exact, first second of bucket 2 | B-1/P-3 | 300 | 300 | 0 (not NULL) | 5-10 min | no |
| last second of bucket 2 | B-1/P-4 | 599 | 650 | +51 | 5-10 min | no |
| first second of bucket 3 | B-1/P-5 | 600 | 700 | +100 | 10-30 min | no |
| window end, nothing yet | B-1/P-6 | 1800 | none | NULL | 10-30 min | no |
| first visit at or after as_of | B-2/P-1 | 90 | 80 (a visit at -60 and one at 1500 are ignored) | -10 | 0-5 min | no |
| first visit is estimated | B-2/P-2 | 60 | estimated at 50, a later one at 900 | NULL (not +840) | 0-5 min | no |
| applied on that bus at 100, before the departure | B-3/P-1 | 200 | 260 | +60 | 0-5 min | yes |
| applied at 300, after the departure | B-4/P-1 | 200 | 260 | +60 | 0-5 min | no |
| applied at -30, before as_of | B-5/P-1 | 200 | 260 | +60 | 0-5 min | no |
| discarded at 100 | B-6/P-1 | 200 | 260 | +60 | 0-5 min | no |
| applied for another bus (B-7) | B-8/P-1 | 200 | 260 | +60 | 0-5 min | no |
| applied at 500, no real departure yet | B-9/P-1 | 200 | none | NULL | 0-5 min | yes |
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg
import pytest
from psycopg.types.json import Jsonb

from src.data.tests.fixtures.gold_support import clear_all
from src.data.tests.fixtures.rec_support import make_row

A = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
SNAPSHOT = "bbbb0000-0000-4000-8000-00000000049d"


def ts(seconds: float) -> datetime:
    return A + timedelta(seconds=seconds)


@pytest.fixture()
def conn(module_db_dsn):
    with psycopg.connect(module_db_dsn) as c:
        clear_all(c)
        c.execute("INSERT INTO gold.snapshots (snapshot_id, as_of_ts, rules_version, max_bronze_id) "
                  "VALUES (%s, %s, 'test', 1)", (SNAPSHOT, A))
        yield c
        c.rollback()
        clear_all(c)


def project(conn, bus: str, stop: str, lead: float, snapshot: str = SNAPSHOT, as_of: datetime = A) -> None:
    conn.execute("INSERT INTO gold.mpc_projection VALUES (%s, %s, %s, %s, %s, %s, 'test', 1)",
                 (snapshot, bus, stop, as_of, as_of + timedelta(seconds=lead), lead))


def visit(conn, bus: str, stop: str, departure_s: float, *, trip: str = "T-1", estimated: bool = False) -> None:
    conn.execute("INSERT INTO silver.stop_visits (bus_id, trip_id, stop_id, arrival_ts, departure_ts, dwell_s, boarded, "
                 "alighted, rejected, estimated_at_departure) VALUES (%s, %s, %s, %s, %s, 10, 0, 0, 0, %s)",
                 (bus, trip, stop, ts(departure_s - 10), ts(departure_s), estimated))


def decide(conn, rec_id: str, bus: str, decided_s: float, status: str = "applied") -> None:
    r = make_row(rec_id, bus=bus, stop="P-1", status=status, validate=False)  # crafted bus ids are outside the contract enum
    conn.execute(
        "INSERT INTO gold.recommendation (rec_id, doc, key, \"case\", status, stale, proposed_ts, expires_ts, close_ts, "
        "first_snapshot_id, params, lineage_detail, rules_version, max_bronze_id) "
        "VALUES (%s, %s, %s, %s, %s, false, %s, %s, %s, %s, '{}', '{}', 'test', 1)",
        (rec_id, Jsonb(r["doc"]), r["key"], r["case"], status, r["proposed_ts"], r["expires_ts"], ts(decided_s),
         SNAPSHOT))


def view(conn) -> dict[tuple[str, str], dict]:
    cur = conn.execute("SELECT bus_id, stop_id, lead_bucket, actual_departure_ts, error_s, abs_error_s, "
                       "affected_by_decision FROM gold.v_projection_accuracy")
    cols = [d.name for d in cur.description]
    return {(r[0], r[1]): dict(zip(cols, r)) for r in cur.fetchall()}


def crafted(conn) -> None:
    for bus, stop, lead in (("B-1", "P-1", 100), ("B-1", "P-2", 299), ("B-1", "P-3", 300), ("B-1", "P-4", 599),
                            ("B-1", "P-5", 600), ("B-1", "P-6", 1800), ("B-2", "P-1", 90), ("B-2", "P-2", 60),
                            ("B-3", "P-1", 200), ("B-4", "P-1", 200), ("B-5", "P-1", 200), ("B-6", "P-1", 200),
                            ("B-8", "P-1", 200), ("B-9", "P-1", 200)):
        project(conn, bus, stop, lead)
    for bus, stop, dep in (("B-1", "P-1", 135), ("B-1", "P-2", 290), ("B-1", "P-3", 300), ("B-1", "P-4", 650),
                           ("B-1", "P-5", 700), ("B-3", "P-1", 260), ("B-4", "P-1", 260), ("B-5", "P-1", 260),
                           ("B-6", "P-1", 260), ("B-8", "P-1", 260)):
        visit(conn, bus, stop, dep)
    visit(conn, "B-2", "P-1", -60, trip="T-0")
    visit(conn, "B-2", "P-1", 80, trip="T-1")
    visit(conn, "B-2", "P-1", 1500, trip="T-2")
    visit(conn, "B-2", "P-2", 50, estimated=True)
    visit(conn, "B-2", "P-2", 900, trip="T-2")
    decide(conn, "d0000000-0000-4000-8000-000000000003", "B-3", 100)
    decide(conn, "d0000000-0000-4000-8000-000000000004", "B-4", 300)
    decide(conn, "d0000000-0000-4000-8000-000000000005", "B-5", -30)
    decide(conn, "d0000000-0000-4000-8000-000000000006", "B-6", 100, status="discarded")
    decide(conn, "d0000000-0000-4000-8000-000000000007", "B-7", 100)
    decide(conn, "d0000000-0000-4000-8000-000000000009", "B-9", 500)


def test_error_sign_buckets_and_nulls(conn) -> None:
    crafted(conn)
    v = view(conn)
    expect = {("B-1", "P-1"): (35, "0-5 min"), ("B-1", "P-2"): (-9, "0-5 min"), ("B-1", "P-3"): (0, "5-10 min"),
              ("B-1", "P-4"): (51, "5-10 min"), ("B-1", "P-5"): (100, "10-30 min"), ("B-2", "P-1"): (-10, "0-5 min"),
              ("B-3", "P-1"): (60, "0-5 min")}
    for key, (error, bucket) in expect.items():
        assert v[key]["error_s"] == Decimal(error) and v[key]["abs_error_s"] == abs(Decimal(error)), key
        assert v[key]["lead_bucket"] == bucket, key
    assert v[("B-1", "P-3")]["error_s"] is not None  # an exact forecast is 0, not NULL


def test_nothing_to_compare_gives_null_never_zero(conn) -> None:
    crafted(conn)
    v = view(conn)
    assert v[("B-1", "P-6")]["error_s"] is None and v[("B-1", "P-6")]["actual_departure_ts"] is None
    assert v[("B-1", "P-6")]["lead_bucket"] == "10-30 min"
    # the first visit at or after as_of is estimated: excluded, and the bus's next trip is not used instead
    assert v[("B-2", "P-2")]["actual_departure_ts"] is None and v[("B-2", "P-2")]["error_s"] is None
    assert v[("B-2", "P-2")]["abs_error_s"] is None


def test_the_real_departure_is_the_first_one_at_or_after_as_of(conn) -> None:
    crafted(conn)
    assert view(conn)[("B-2", "P-1")]["actual_departure_ts"] == ts(80)
    # a bus still dwelling at the stop at as_of (arrived before, leaves after) counts
    project(conn, "B-10", "P-1", 20)
    conn.execute("INSERT INTO silver.stop_visits (bus_id, trip_id, stop_id, arrival_ts, departure_ts, dwell_s, boarded, "
                 "alighted, rejected) VALUES ('B-10', 'T-1', 'P-1', %s, %s, 30, 0, 0, 0)", (ts(-10), ts(20)))
    assert view(conn)[("B-10", "P-1")]["error_s"] == Decimal(0)


def test_affected_by_decision(conn) -> None:
    crafted(conn)
    v = view(conn)
    assert v[("B-3", "P-1")]["affected_by_decision"] is True       # applied at 100, departure at 260
    assert v[("B-9", "P-1")]["affected_by_decision"] is True       # applied at 500, no real departure yet
    for key in (("B-4", "P-1"), ("B-5", "P-1"), ("B-6", "P-1"), ("B-8", "P-1"), ("B-1", "P-1")):
        assert v[key]["affected_by_decision"] is False, key        # after the departure / before as_of / discarded / other bus / none
    assert all(isinstance(r["affected_by_decision"], bool) for r in v.values())


def test_a_visit_that_arrives_later_fills_the_error_in(conn) -> None:
    project(conn, "B-1", "P-1", 100)
    assert view(conn)[("B-1", "P-1")]["error_s"] is None
    visit(conn, "B-1", "P-1", 120)
    assert view(conn)[("B-1", "P-1")]["error_s"] == Decimal(20)
