"""006 T027 — status derived by data, immutable columns, freshness, rollback and the model switch (FR-014, FR-017,
FR-019 to FR-021, FR-030; SC-001, SC-006, SC-007).

Rows are made with `rec_support` (validated against the 1.1.0 schema); decisions are inserted the way the backend
writes them. The proposal clock is simulated: T0 is 22:00:00Z.
"""
from __future__ import annotations

import json
import logging

import pytest

from src.data.pipeline import cycle as cycle_module
from src.data.pipeline import recommend
from src.data.refresh import run as refresh
from src.data.tests.fixtures.bronze_builders import Builder, ingest_all, insert_backend_commands, iso, trip_id
from src.data.tests.fixtures.gold_support import cycle
from src.data.tests.fixtures.mpc_runs import collect, ingest_run
from src.data.tests.fixtures.rec_support import insert_recommendation

R_APPLY, R_DISCARD, R_NONE, R_PASSED, R_LIVE = (f"{n}{n}{n}{n}{n}{n}{n}{n}-0000-4000-8000-000000000000" for n in "abcde")
IMMUTABLE = "rec_id, key, proposed_ts, expires_ts, first_snapshot_id, params"


def decision(rec_id: str, action: str = "apply", at_s: float = 0) -> dict:
    return Builder(f"life-{rec_id}-{action}")._command(
        "decision", at_s, {"rec_id": rec_id, "action": action, "user_id": "dispatcher-01", "ts": iso(at_s)})


def status_of(conn) -> dict[str, str]:
    conn.rollback()
    return {r[0]: r[1] for r in conn.execute("SELECT rec_id::text, status FROM gold.recommendation")}


def rows_snapshot(conn) -> list[tuple]:
    conn.rollback()
    return conn.execute("SELECT rec_id::text, key, status, stale, proposed_ts, expires_ts, close_ts, "
                        "first_snapshot_id, params, doc, rules_version FROM gold.recommendation "
                        "ORDER BY rec_id").fetchall()


@pytest.fixture
def conn(gold_conn):
    insert_recommendation(gold_conn, R_APPLY, bus="B-103", stop="P-887", duration_s=60, expires="2026-11-24T22:30:00Z",
                          proposed="2026-11-24T22:00:00Z")
    insert_recommendation(gold_conn, R_DISCARD, bus="B-104", stop="P-887", duration_s=60,
                          expires="2026-11-24T22:30:00Z", proposed="2026-11-24T22:00:00Z")
    insert_recommendation(gold_conn, R_NONE, bus="B-102", stop="P-888", duration_s=60, expires="2026-11-24T22:02:00Z",
                          proposed="2026-11-24T22:00:00Z")
    insert_recommendation(gold_conn, R_PASSED, bus="B-105", stop="P-889", duration_s=30,
                          expires="2026-11-24T22:30:00Z", proposed="2026-11-24T22:00:00Z")
    insert_recommendation(gold_conn, R_LIVE, bus="B-101", stop="P-890", duration_s=30, expires="2026-11-24T22:30:00Z",
                          proposed="2026-11-24T22:00:00Z")
    return gold_conn


def reports(conn) -> None:
    b = Builder("life-reports")
    b.drive("B-103", 0, 200)
    b.stop_visit("B-105", trip_id("B-105"), "P-889", 60, 80)  # B-105 passes P-889 after the proposal
    ingest_all(conn, b.events)


def test_each_status_comes_from_a_fact(conn) -> None:
    reports(conn)
    insert_backend_commands(conn, [decision(R_APPLY, "apply", 100), decision(R_DISCARD, "discard", 100)])
    cycle(conn, 130)
    got = status_of(conn)
    assert got == {R_APPLY: "applied", R_DISCARD: "discarded", R_NONE: "expired", R_PASSED: "expired",
                   R_LIVE: "proposed"}
    docs = {r[0]: r[1] for r in conn.execute("SELECT rec_id::text, doc->>'status' FROM gold.recommendation")}
    assert docs == got  # the column and the document cannot differ


def test_a_decision_that_arrives_after_the_expiry_still_wins(conn) -> None:
    reports(conn)
    cycle(conn, 200)
    assert status_of(conn)[R_NONE] == "expired"
    insert_backend_commands(conn, [decision(R_NONE, "apply", 205)])
    cycle(conn, 210)
    assert status_of(conn)[R_NONE] == "applied"


def test_nothing_is_applied_without_a_decision_fact(conn) -> None:
    """SC-007, Principle IV: the model never writes a decision and no status is invented."""
    reports(conn)
    for t in (10, 60, 130, 700, 2000):
        cycle(conn, t)
    assert set(status_of(conn).values()) <= {"proposed", "expired"}
    assert conn.execute("SELECT count(*) FROM bronze.events WHERE event_type = 'decision'").fetchone()[0] == 0


def test_the_first_decision_by_bronze_id_wins(conn) -> None:
    reports(conn)
    insert_backend_commands(conn, [decision(R_LIVE, "discard", 50)])
    insert_backend_commands(conn, [Builder("life-second")._command(
        "decision", 60, {"rec_id": R_LIVE, "action": "apply", "user_id": "dispatcher-02", "ts": iso(60)})])
    cycle(conn, 100)
    assert status_of(conn)[R_LIVE] == "discarded"


def test_immutable_columns_never_change_and_a_rerun_gives_identical_rows(conn) -> None:
    reports(conn)
    before = conn.execute(f"SELECT {IMMUTABLE} FROM gold.recommendation ORDER BY rec_id").fetchall()  # noqa: S608
    cycle(conn, 130)
    first = rows_snapshot(conn)
    cycle(conn, 135)
    cycle(conn, 130)  # the same instant again: same snapshot, same rows
    cycle(conn, 130)
    after = conn.execute(f"SELECT {IMMUTABLE} FROM gold.recommendation ORDER BY rec_id").fetchall()  # noqa: S608
    assert after == before
    assert [r[:7] for r in rows_snapshot(conn)] == [r[:7] for r in first]  # status, stale, close_ts as at 130 s


def test_reingesting_the_same_batch_leaves_the_table_unchanged(conn) -> None:
    b = Builder("life-reports")
    b.drive("B-103", 0, 200)
    ingest_all(conn, b.events)
    cycle(conn, 130)
    first = rows_snapshot(conn)
    ingest_all(conn, b.events)  # duplicates are dropped at the boundary
    cycle(conn, 130)
    assert rows_snapshot(conn) == first


def test_a_rolled_back_cycle_leaves_no_row_and_no_status_change(conn, monkeypatch: pytest.MonkeyPatch) -> None:
    reports(conn)
    before = rows_snapshot(conn)
    real = recommend.run_model

    def run_then_fail(*a, **kw):
        real(*a, **kw)
        raise RuntimeError("boom after the writes")

    monkeypatch.setattr(cycle_module.recommend, "run_model", run_then_fail)
    with pytest.raises(cycle_module.CycleError):
        cycle(conn, 130)
    assert rows_snapshot(conn) == before


def test_status_is_still_derived_when_the_model_is_off(conn, monkeypatch: pytest.MonkeyPatch) -> None:
    reports(conn)
    monkeypatch.setenv("MPC_ENABLED", "off")
    cycle(conn, 130)
    assert status_of(conn)[R_NONE] == "expired" and status_of(conn)[R_LIVE] == "proposed"
    conn.rollback()
    assert conn.execute("SELECT count(*) FROM gold.mpc_evaluation").fetchone()[0] == 0


def test_a_snapshot_older_than_fifteen_seconds_creates_no_row_but_keeps_deriving(conn) -> None:
    """FR-017: age counted from `gold.snapshot_commits.committed_at`; existing rows keep deriving."""
    ingest_run(conn, "c1_bunching", 1960)
    for t in range(1300, 1960, 30):  # the first cycle with a bunched follower (as in test_scenarios_gold)
        res = cycle(conn, t)
        ev, recs = collect(conn)
        if ev:
            break
    assert len(ev) > 0, "a fresh snapshot with a bunched follower evaluates candidates"
    n_before = len(recs)
    params = recommend.load_params(conn)
    conn.rollback()
    for age, fresh in ((14.0, True), (20.0, False)):  # 15.0 exactly is the unit test's job (a probe ages by ms)
        conn.execute("UPDATE gold.snapshot_commits SET committed_at = clock_timestamp() - make_interval(secs => %s) "
                     "WHERE snapshot_id = %s", (age, res.snapshot_id))
        conn.commit()
        assert recommend.snapshot_age_s(conn, res.snapshot_id) == pytest.approx(age, abs=2.0)
        recommend.run_model(conn, res.snapshot_id, res.as_of_ts, res.max_bronze_id)
        conn.commit()
        ev, recs = collect(conn)
        assert (len(ev) > 0) is fresh, age
        if not fresh:
            assert len(recs) == n_before
    assert params.freshness_max_s == 15


def test_refresh_log_line_carries_model_ms(conn, caplog: pytest.LogCaptureFixture) -> None:
    reports(conn)
    conn.commit()
    with caplog.at_level(logging.INFO, logger="pulsoflota.refresh"):
        refresh.refresh_once(conn, "data")
    line = json.loads([r.getMessage() for r in caplog.records if '"refresh_cycle"' in r.getMessage()][0])
    assert isinstance(line["model_ms"], (int, float)) and line["model_ms"] >= 0 and line["status"] != "error"


def test_the_model_writes_gold_only(conn) -> None:
    reports(conn)
    n = conn.execute("SELECT count(*) FROM bronze.events").fetchone()[0]
    conn.rollback()
    cycle(conn, 130)
    conn.rollback()
    assert conn.execute("SELECT count(*) FROM bronze.events").fetchone()[0] == n
