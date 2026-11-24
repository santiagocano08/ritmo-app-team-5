"""006 T058 — an approved reserve shows in `corridor_now` and takes a free reserve out of `decision_inputs` (FR-023, FR-026).

The events come from the simulator with a reserve order on the action board (decision at 600 s, ready after 120 s) and
go through the real ingestion boundary and the cycle path.
"""
from __future__ import annotations

import pytest

from src.data.ingestion.bronze import ingest
from src.data.simulator.engine import run
from src.data.simulator.scenarios.actions import ActionBoard
from src.data.tests.fixtures.gold_support import cycle

REC = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DURATION = 1500


def _board() -> ActionBoard:
    board = ActionBoard()
    board.add_reserve(REC, "B-108", 600.0, 120)
    return board


def _doc(conn, table: str, snapshot_id) -> dict:
    return conn.execute(f"SELECT doc FROM gold.{table} WHERE snapshot_id = %s", (snapshot_id,)).fetchone()[0]  # noqa: S608


def test_reserve_events_pass_the_boundary_and_b108_is_in_corridor_now(gold_conn) -> None:
    for event in run(42, DURATION, actions=_board()):
        assert ingest(gold_conn, event).accepted
    gold_conn.commit()
    before = cycle(gold_conn, 700)
    assert "B-108" not in {b["bus_id"] for b in _doc(gold_conn, "corridor_now", before.snapshot_id)["buses"]}
    assert _doc(gold_conn, "decision_inputs", before.snapshot_id)["resources"]["reserve_free"] == ["B-108", "B-109", "B-110", "B-111"]
    after = cycle(gold_conn, 900)
    corridor = _doc(gold_conn, "corridor_now", after.snapshot_id)
    assert "B-108" in {b["bus_id"] for b in corridor["buses"]}
    assert _doc(gold_conn, "decision_inputs", after.snapshot_id)["resources"]["reserve_free"] == ["B-109", "B-110", "B-111"]


@pytest.mark.parametrize("bus", ["B-108"])
def test_a_reserve_is_not_a_target_while_it_has_no_history(gold_conn, bus) -> None:
    """Right after the start the reserve is one live bus at P-883 like the others; no candidate may point at an
    `estimated` bus, so the state of B-108 must be live at that cycle."""
    for event in run(42, DURATION, actions=_board()):
        ingest(gold_conn, event)
    gold_conn.commit()
    result = cycle(gold_conn, 760)
    buses = {b["bus_id"]: b for b in _doc(gold_conn, "corridor_now", result.snapshot_id)["buses"]}
    assert buses[bus]["data_quality"] == "live"


def test_approved_reserve_row_starts_b108_120_s_after_the_decision(gold_conn, monkeypatch, module_db_dsn, tmp_path) -> None:
    """The whole path: row in `gold.recommendation`, backend `decision` in bronze, poller, board, engine."""
    import io
    import json
    from datetime import datetime, timedelta, timezone

    from src.data.simulator.main import main
    from src.data.tests.fixtures.rec_support import insert_recommendation
    from src.data.tests.integration.test_hold_loop import decision, feed, write_decision

    baseline = list(run(42, DURATION))
    decided = datetime(2026, 11, 24, 22, 10, 0, tzinfo=timezone.utc)  # 600 s into the run
    feed(gold_conn, [e for e in baseline
                     if datetime.strptime(e["event_ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) <= decided])
    insert_recommendation(gold_conn, REC, type="reserve_dispatch", bus="B-108", stop="P-883", duration_s=None,
                          case="C5", ready_s=120, proposed="2026-11-24T22:09:30Z", expires="2026-11-24T22:11:30Z")
    write_decision(gold_conn, decision(REC, "apply", tag="reserve"))
    monkeypatch.setenv("DATABASE_URL", module_db_dsn)
    monkeypatch.setenv("SIM_TRUTH_PATH", str(tmp_path / "truth.jsonl"))
    monkeypatch.delenv("SIM_SCENARIO_FILE", raising=False)
    buf = io.StringIO()
    main(["--seed", "42", "--duration", str(DURATION), "--holds", "on"], out=buf)
    events = [json.loads(x) for x in buf.getvalue().splitlines()]
    first = next(e for e in events if e["payload"].get("bus_id") == "B-108")
    first_at = datetime.strptime(first["event_ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    assert timedelta(0) <= first_at - (decided + timedelta(seconds=120)) < timedelta(seconds=5)
    truth = [json.loads(x) for x in (tmp_path / "truth.jsonl").read_text().splitlines()]
    assert [(r["type"], r["rec_id"], r["bus"]) for r in truth] == [("RESERVE", REC, "B-108")]
