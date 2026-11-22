"""006 T020 — `silver.stop_queue` (FR-004, data-model M3, research R3).

queue(stop) = `rejected` of the newest `stop_arrival` at the stop (any bus) + `rider_arrival` events at the stop
after that arrival; both bounded by the 30-minute window and by `id <= M`.
"""
from __future__ import annotations

import pytest

from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.silver_support import at, build, max_id


def _queue(conn) -> dict[str, tuple]:
    rows = conn.execute("SELECT stop_id, queue_riders, basis_ts, basis_bronze_id, as_of_ts FROM silver.stop_queue "
                        "ORDER BY stop_id").fetchall()
    return {r[0]: r[1:] for r in rows}


def _load(conn, b: bb.Builder) -> list[int]:
    assert all(r.accepted for r in bb.ingest_all(conn, b.events))
    return [r[0] for r in conn.execute("SELECT id FROM bronze.events ORDER BY id").fetchall()]


def test_queue_is_rejected_at_the_newest_arrival_plus_riders_since(silver_conn) -> None:
    b = bb.Builder("queue-basic")
    b.stop_arrival("B-101", bb.trip_id("B-101"), "P-885", 100, rejected=4)
    b.rider_arrival("P-885", 100, "P-890")  # same second as the arrival: already in `rejected`, not counted twice
    b.rider_arrival("P-885", 110, "P-890")
    b.rider_arrival("P-885", 120, "P-890")
    b.rider_arrival("P-885", 90, "P-890")  # before the arrival: boarded or rejected, not counted
    ids = _load(silver_conn, b)
    build(silver_conn, 200)
    q = _queue(silver_conn)
    assert len(q) == 18
    assert q["P-885"][0] == 6 and q["P-885"][1] == at(100)
    assert q["P-885"][2] == ids[3]  # the largest bronze id used: the rider at 120 s
    assert q["P-885"][3] == at(200)


def test_newest_arrival_of_any_bus_is_the_basis(silver_conn) -> None:
    b = bb.Builder("queue-two-buses")
    b.stop_arrival("B-101", bb.trip_id("B-101"), "P-887", 50, rejected=9)
    b.rider_arrival("P-887", 150, "P-890")
    b.stop_arrival("B-102", bb.trip_id("B-102"), "P-887", 200, rejected=2)
    b.rider_arrival("P-887", 210, "P-890")
    _load(silver_conn, b)
    build(silver_conn, 300)
    assert _queue(silver_conn)["P-887"][:2] == (3, at(200))


def test_stop_without_an_arrival_counts_the_riders_of_the_window_and_has_no_basis(silver_conn) -> None:
    b = bb.Builder("queue-no-arrival")
    for t in (10, 20, 30):
        b.rider_arrival("P-886", t, "P-890")
    ids = _load(silver_conn, b)
    build(silver_conn, 100)
    q = _queue(silver_conn)
    assert q["P-886"][:2] == (3, None) and q["P-886"][2] == ids[-1]
    assert q["P-883"][:3] == (0, None, 0)  # nothing at all: empty queue, no bronze id


def test_both_look_backs_stop_at_thirty_minutes(silver_conn) -> None:
    b = bb.Builder("queue-window")
    b.stop_arrival("B-101", bb.trip_id("B-101"), "P-888", 100, rejected=8)  # 1,900 s before as_of: out of the window
    b.rider_arrival("P-888", 150, "P-890")  # also out
    b.rider_arrival("P-888", 1900, "P-890")
    b.rider_arrival("P-888", 1950, "P-890")
    _load(silver_conn, b)
    build(silver_conn, 2000)
    assert _queue(silver_conn)["P-888"][:2] == (2, None)


def test_rows_after_as_of_or_after_m_are_ignored(silver_conn) -> None:
    b = bb.Builder("queue-bounds")
    b.stop_arrival("B-101", bb.trip_id("B-101"), "P-889", 100, rejected=1)
    b.rider_arrival("P-889", 120, "P-890")
    b.rider_arrival("P-889", 900, "P-890")  # after as_of
    _load(silver_conn, b)
    first = max_id(silver_conn)
    late = bb.Builder("queue-bounds-late")
    late.rider_arrival("P-889", 130, "P-890")  # inside the window but ingested after M
    _load(silver_conn, late)
    build(silver_conn, 200, max_bronze_id=first)
    assert _queue(silver_conn)["P-889"][0] == 2
    build(silver_conn, 200)
    assert _queue(silver_conn)["P-889"][0] == 3


def test_rebuild_is_delete_plus_insert_and_idempotent(silver_conn) -> None:
    b = bb.Builder("queue-idem")
    b.stop_arrival("B-101", bb.trip_id("B-101"), "P-885", 100, rejected=4)
    _load(silver_conn, b)
    build(silver_conn, 200)
    first = _queue(silver_conn)
    build(silver_conn, 200)
    assert _queue(silver_conn) == first
    assert silver_conn.execute("SELECT count(*) FROM silver.stop_queue").fetchone()[0] == 18


@pytest.mark.parametrize("stop", ["P-883", "P-900"])
def test_every_stop_has_a_row(silver_conn, stop) -> None:
    build(silver_conn, 10)
    assert stop in _queue(silver_conn)
