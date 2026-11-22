"""006 T050 — an approved hold from `gold.recommendation` runs in the simulator and is reported (FR-019, FR-023, FR-026,
SC-008 hold part, SC-009).

C1 seed 42 in forced mode (fixed time and seed). The model never reached the 15 s threshold with a hold on this
scenario (verification.md, phase 2), so the recommendation row is made by `rec_support` in the shape the model
publishes (schema 1.1.0, `proposed`). The path under test is the same as in production: backend `decision` row in
bronze, the read-only poller, the board, the engine, then `gold.instruction_status`.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timedelta, timezone

import pytest

from src.data.simulator.main import main
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.config import load_scenarios
from src.data.simulator.scenarios.truth import TruthSink
from src.data.tests.fixtures.rec_support import insert_recommendation
from src.data.tests.integration.test_hold_loop import decision, feed, status_rows, write_decision
from src.data.tests.fixtures.mpc_runs import SCENARIOS

REC = "66666666-6666-4666-8666-666666666666"
BUS, STOP, HOLD_S = "B-103", "P-890", 60
DURATION = 2400
SCENARIO = SCENARIOS / "c1_bunching.json"


def _ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _stream(*, holds: bool, monkeypatch, dsn: str, tmp_path) -> list[dict]:
    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setenv("SIM_TRUTH_PATH", str(tmp_path / "truth.jsonl"))
    monkeypatch.setenv("SIM_HOLD_NONCOMPLIANCE", "0")
    monkeypatch.delenv("SIM_SCENARIO_FILE", raising=False)
    buf = io.StringIO()
    main(["--seed", "42", "--duration", str(DURATION), "--scenario-file", str(SCENARIO),
          "--holds", "on" if holds else "off"], out=buf)
    return [json.loads(x) for x in buf.getvalue().splitlines()]


@pytest.fixture
def baseline() -> list[dict]:
    truth = TruthSink(load_scenarios(SCENARIO))
    events = list(scenario_events(load_scenarios(SCENARIO), 42, DURATION, truth))
    truth.close()
    return [json.loads(json.dumps(e, sort_keys=True)) for e in events]


def _visit(events: list[dict]) -> tuple[str, str]:
    arrival = next(e for e in events if e["event_type"] == "stop_arrival"
                   and e["payload"]["bus_id"] == BUS and e["payload"]["stop_id"] == STOP)
    departure = next(e for e in events if e["event_type"] == "stop_departure"
                     and e["payload"]["bus_id"] == BUS and e["payload"]["stop_id"] == STOP)
    return arrival["event_ts"], departure["event_ts"]


def _publish_hold_and_decide(conn, baseline: list[dict], action: str | None) -> None:
    """Bronze holds the events up to 120 s before the bus arrives; the row is `proposed`; `action` is written as the
    backend would (None writes no decision)."""
    arrival_ts, _ = _visit(baseline)
    decided = _ts(arrival_ts) - timedelta(seconds=120)
    feed(conn, [e for e in baseline if _ts(e["event_ts"]) <= decided])
    insert_recommendation(conn, REC, bus=BUS, stop=STOP, duration_s=HOLD_S,
                          expires=_iso(_ts(arrival_ts) + timedelta(seconds=30)), proposed=_iso(decided))
    if action:
        write_decision(conn, decision(REC, action, tag="model"))


def _reset_bronze(conn) -> None:
    conn.execute("TRUNCATE bronze.events, bronze.rejections RESTART IDENTITY")
    conn.commit()


def test_approved_model_hold_is_executed_and_reported(gold_conn, baseline, monkeypatch, module_db_dsn, tmp_path) -> None:
    _publish_hold_and_decide(gold_conn, baseline, "apply")
    events = _stream(holds=True, monkeypatch=monkeypatch, dsn=module_db_dsn, tmp_path=tmp_path)
    arrival_ts, departure_ts = _visit(events)
    dwell = (_ts(departure_ts) - _ts(arrival_ts)).total_seconds()
    assert abs(dwell - HOLD_S) <= 15 and dwell <= 90
    base_arrival, base_departure = _visit(baseline)
    assert (_ts(base_departure) - _ts(base_arrival)).total_seconds() < HOLD_S  # the hold is what lengthened it

    _reset_bronze(gold_conn)
    write_decision(gold_conn, decision(REC, "apply", tag="model"))
    feed(gold_conn, events)
    from src.data.tests.fixtures.gold_support import cycle
    cycle(gold_conn, DURATION - 5)
    row = status_rows(gold_conn)[REC]
    assert row[1] == "executed" and abs(row[2] - HOLD_S) <= 15


@pytest.mark.parametrize("action", ["discard", None])
def test_discarded_or_proposed_hold_creates_no_order(gold_conn, baseline, monkeypatch, module_db_dsn, tmp_path,
                                                     action) -> None:
    _publish_hold_and_decide(gold_conn, baseline, action)
    events = _stream(holds=True, monkeypatch=monkeypatch, dsn=module_db_dsn, tmp_path=tmp_path)
    assert events == baseline


def test_no_approved_recommendation_gives_the_baseline_stream(gold_conn, baseline, monkeypatch, module_db_dsn,
                                                              tmp_path) -> None:
    events = _stream(holds=True, monkeypatch=monkeypatch, dsn=module_db_dsn, tmp_path=tmp_path)
    assert events == baseline
