"""T028 — silver rebuild equality and bronze untouched (FR-001, FR-002, FR-005, US1 scenario 6, R2)."""
from __future__ import annotations

import hashlib
import re

import psycopg

from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.silver_support import build, dump
from src.data.pipeline.silver import SILVER_TABLES


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
    """Drop every silver table and recreate it from 004_silver.sql, 008 (005) and 009 (006) (idempotent)."""
    for table in SILVER_TABLES:
        conn.execute(f"DROP TABLE silver.{table}")  # noqa: S608 - fixed names
    from src.data.tests.db_helpers import INIT_DIR
    conn.execute((INIT_DIR / "004_silver.sql").read_text(encoding="utf-8"))
    conn.execute((INIT_DIR / "008_data_fixes_metrics.sql").read_text(encoding="utf-8"))
    conn.execute((INIT_DIR / "009_decision_mpc.sql").read_text(encoding="utf-8"))  # silver.stop_queue, occupancy
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

    root = Path(__file__).resolve().parents[4] / "src" / "data"
    for p in list((root / "pipeline").rglob("*.py")) + list((root / "rules").rglob("*.sql")):
        assert not re.search(r"\bTRUNCATE\s+(TABLE\s+)?\w+\.", p.read_text(encoding="utf-8"), re.IGNORECASE), p


def test_the_rebuild_is_atomic_a_failure_leaves_the_previous_silver(silver_conn) -> None:
    _prepare(silver_conn)
    build(silver_conn, 3000)
    before = dump(silver_conn)
    # A bad reference time type makes the rebuild fail part-way; the caller's rollback restores it.
    try:
        from src.data.pipeline.silver import rebuild_silver
        rebuild_silver(silver_conn, "not-a-timestamp", 10**9)  # type: ignore[arg-type]
    except psycopg.Error:
        silver_conn.rollback()
    else:  # pragma: no cover
        raise AssertionError("expected the rebuild to fail")
    assert dump(silver_conn) == before


# -- T057: SC-005 after a replay (US3) ---------------------------------------------------
def test_dropping_silver_and_gold_and_recomputing_gives_the_same_snapshot(gold_conn, module_db_dsn, monkeypatch) -> None:
    """After a replay, drop silver and gold, recompute at the last as_of: same silver, M1/M2, snapshot, id."""
    from src.data.ingestion.bronze import ingest
    from src.data.pipeline.compute import main
    from src.data.simulator.engine import run
    from src.data.tests.db_helpers import INIT_DIR
    from src.data.tests.fixtures.gold_support import cycle

    for event in run(42, 1800):
        assert ingest(gold_conn, event).accepted
    gold_conn.commit()
    monkeypatch.setenv("DATABASE_URL", module_db_dsn)
    assert main(["--from", "2026-11-24T22:01:00Z", "--to", "2026-11-24T22:30:00Z", "--step", "60",
                 "--no-notify"]) == 0

    gold_tables = ("snapshots", "source_status", "corridor_now", "decision_inputs", "service_metric")
    baselines = ("m1_baseline", "m2_baseline")

    def last_state() -> dict:
        snap = gold_conn.execute("SELECT snapshot_id FROM gold.snapshots ORDER BY as_of_ts DESC LIMIT 1").fetchone()[0]
        out = {"silver": dump(gold_conn)}
        for t in gold_tables:
            key = "snapshot_id"
            out[t] = [tuple(repr(v) for v in r) for r in gold_conn.execute(
                f"SELECT * FROM gold.{t} WHERE {key} = %s ORDER BY 1", (snap,)).fetchall()]  # noqa: S608
        for t in baselines:
            out[t] = [tuple(repr(v) for v in r) for r in gold_conn.execute(
                f"SELECT * FROM gold.{t} ORDER BY 1, 2").fetchall()]  # noqa: S608
        for t in ("service_metric_stop", "stop_ewt_band", "stop_boarding_band"):  # 005: all rows of the snapshot / of the closed bands
            out[t] = sorted(tuple(repr(v) for v in r) for r in gold_conn.execute(
                f"SELECT * FROM gold.{t}" + (" WHERE snapshot_id = %s" if t == "service_metric_stop" else ""),  # noqa: S608
                (snap,) if t == "service_metric_stop" else ()).fetchall())
        out["incident"] = [tuple(repr(v) for v in r) for r in gold_conn.execute(
            "SELECT * FROM gold.incident WHERE snapshot_id = %s ORDER BY 1, 2", (snap,)).fetchall()]
        return out

    before = last_state()
    assert all(before[t] for t in gold_tables + baselines + ("service_metric_stop", "stop_ewt_band", "stop_boarding_band"))
    last_as_of_s = 30 * 60

    gold_conn.commit()
    # 004: gold.incident references gold.snapshots, so it goes first and its init script is replayed
    gold_conn.execute("DROP VIEW gold.incident_current")
    gold_conn.execute("DROP TABLE gold.incident")
    gold_conn.execute("DROP TABLE gold.service_metric_stop")  # 005: references gold.snapshots
    gold_conn.execute("DROP TABLE gold.stop_ewt_band")
    gold_conn.execute("DROP VIEW gold.stop_boarding_band_v")
    gold_conn.execute("DROP TABLE gold.stop_boarding_band")
    for t in baselines + tuple(reversed(gold_tables)):
        gold_conn.execute(f"DROP TABLE gold.{t}")  # noqa: S608 - fixed names
    for t in SILVER_TABLES:
        gold_conn.execute(f"DROP TABLE silver.{t}")  # noqa: S608 - fixed names
    gold_conn.execute((INIT_DIR / "004_silver.sql").read_text(encoding="utf-8"))
    gold_conn.execute((INIT_DIR / "005_gold.sql").read_text(encoding="utf-8"))
    gold_conn.execute((INIT_DIR / "007_scenarios.sql").read_text(encoding="utf-8"))
    gold_conn.execute((INIT_DIR / "008_data_fixes_metrics.sql").read_text(encoding="utf-8"))
    gold_conn.execute((INIT_DIR / "009_decision_mpc.sql").read_text(encoding="utf-8"))  # 006: silver.stop_queue, gold.recommendation
    gold_conn.commit()

    result = cycle(gold_conn, last_as_of_s)
    assert result is not None and result.created
    assert last_state() == before
