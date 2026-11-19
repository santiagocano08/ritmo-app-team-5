"""T028 — silver rebuild equality and bronze untouched (FR-001, FR-002, FR-005, US1 scenario 6, R2)."""
from __future__ import annotations

import hashlib
import re

import psycopg

from tests.fixtures import bronze_builders as bb
from tests.fixtures.silver_support import build, dump
from src.pipeline.silver import SILVER_TABLES


def _bronze_fingerprint(conn: psycopg.Connection) -> tuple[int, str]:
    rows = conn.execute(
        "SELECT id, source, event_id::text, event_type, event_ts::text, arrival_ts::text, payload::text "
        "FROM bronze.events ORDER BY id").fetchall()
    return len(rows), hashlib.sha256(repr(rows).encode()).hexdigest()


def _rich_timeline() -> list[dict]:
    """Positions, visits, traversals and incidents in one deterministic batch."""
    b = bb.Builder("rich")
    events = list(bb.normal().events)
    trip = bb.trip_id("B-101")
    for seg in range(1, 6):
        b.traversal("B-101", trip, seg, depart=2500 + seg * 100, arrive=2500 + seg * 100 + 60)
    b.stop_visit("B-102", bb.trip_id("B-102"), "P-885", 2000, 2030, boarded=4, alighted=2)
    b.incident("bus_breakdown", "B-103", at=2900, duration_min=30.0)
    return events + b.events


def _prepare(conn) -> None:
    assert all(r.accepted for r in bb.ingest_all(conn, _rich_timeline()))


def _recreate_silver(conn: psycopg.Connection) -> None:
    """Drop every silver table and recreate it from db/init/004_silver.sql."""
    for table in SILVER_TABLES:
        conn.execute(f"DROP TABLE silver.{table}")  # noqa: S608 - fixed names
    from tests.db_helpers import INIT_DIR
    conn.execute((INIT_DIR / "004_silver.sql").read_text(encoding="utf-8"))
    conn.commit()


def test_rebuild_from_scratch_equals_the_cycle_by_cycle_result(silver_conn) -> None:
    _prepare(silver_conn)
    build(silver_conn, 3000)
    before = dump(silver_conn)
    assert all(before[t] for t in SILVER_TABLES), {t: len(r) for t, r in before.items()}

    _recreate_silver(silver_conn)
    assert all(silver_conn.execute(f"SELECT count(*) FROM silver.{t}").fetchone()[0] == 0  # noqa: S608
               for t in SILVER_TABLES)
    build(silver_conn, 3000)
    assert dump(silver_conn) == before


def test_building_twice_in_a_row_gives_identical_silver(silver_conn) -> None:
    _prepare(silver_conn)
    build(silver_conn, 3000)
    first = dump(silver_conn)
    build(silver_conn, 3000)
    assert dump(silver_conn) == first


def test_reingesting_the_same_batch_changes_nothing(silver_conn) -> None:
    _prepare(silver_conn)
    build(silver_conn, 3000)
    first = dump(silver_conn)
    results = bb.ingest_all(silver_conn, _rich_timeline())
    assert not any(r.accepted for r in results)  # all duplicates
    build(silver_conn, 3000)
    assert dump(silver_conn) == first


def test_a_build_leaves_bronze_untouched(silver_conn) -> None:
    _prepare(silver_conn)
    before = _bronze_fingerprint(silver_conn)
    build(silver_conn, 3000)
    build(silver_conn, 2500)
    assert _bronze_fingerprint(silver_conn) == before
    assert before[0] > 0


def test_rebuild_uses_delete_and_does_not_block_a_concurrent_reader(silver_conn, module_db_dsn) -> None:
    _prepare(silver_conn)
    build(silver_conn, 3000)
    expected = silver_conn.execute("SELECT count(*) FROM silver.position_history").fetchone()[0]
    with psycopg.connect(module_db_dsn, autocommit=False) as reader:
        reader.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        assert reader.execute("SELECT count(*) FROM silver.position_history").fetchone()[0] == expected
        # A rebuild in another session must neither block on the reader nor wait for it.
        silver_conn.execute("SET lock_timeout = '2s'")
        build(silver_conn, 3000)
        assert reader.execute("SELECT count(*) FROM silver.position_history").fetchone()[0] == expected
        reader.rollback()
    silver_conn.execute("RESET lock_timeout")


def test_rebuild_source_does_not_use_truncate() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src"
    for p in list((root / "pipeline").rglob("*.py")) + list((root / "rules").rglob("*.sql")):
        assert not re.search(r"\bTRUNCATE\s+(TABLE\s+)?\w+\.", p.read_text(encoding="utf-8"), re.IGNORECASE), p


def test_the_rebuild_is_atomic_a_failure_leaves_the_previous_silver(silver_conn) -> None:
    _prepare(silver_conn)
    build(silver_conn, 3000)
    before = dump(silver_conn)
    # A bad reference time type makes the rebuild fail part-way; the caller's rollback restores it.
    try:
        from src.pipeline.silver import rebuild_silver
        rebuild_silver(silver_conn, "not-a-timestamp", 10**9)  # type: ignore[arg-type]
    except psycopg.Error:
        silver_conn.rollback()
    else:  # pragma: no cover
        raise AssertionError("expected the rebuild to fail")
    assert dump(silver_conn) == before
