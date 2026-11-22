"""T048 (US6, FR-060 to FR-064, SC-013): one future-dated event no longer moves the data clock.

C1 seed 42 streamed event by event through the real ingestion boundary; every few events one refresh step
runs exactly as the refresh loop does (`resolve_clock` then `run_cycle` with the untrusted buses).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.data.ingestion.bronze import ingest
from src.data.pipeline.cycle import run_cycle
from src.data.refresh import run as refresh
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.config import load_scenarios
from src.data.simulator.scenarios.truth import TruthSink
from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import docs
from src.data.tests.integration.test_scenarios_gold import FIXTURES, SEED, T0

FUTURE = datetime(2030, 1, 1, tzinfo=timezone.utc)
DAY_START = datetime(2026, 11, 24, 22, 0, tzinfo=timezone.utc)
INJECT_AT_S = 1300  # B-101 is on the corridor (it finishes its trip at about 1,550 s)
EVERY = 25
WALL = datetime(2027, 6, 1, 12, 0, tzinfo=timezone.utc)


def _events(duration: int = 2700):
    scenarios = load_scenarios(FIXTURES / "c1_bunching.json")
    return scenario_events(scenarios, SEED, duration, TruthSink(scenarios))


def _step(conn):
    decision = refresh.resolve_clock(conn, "data", lambda: WALL)
    result = run_cycle(conn, decision.as_of, notify=False, untrusted_buses=decision.untrusted)
    return decision, result


def _future_event(bus: str = "B-101", tag: str = "future") -> dict:
    env = bb.Builder(tag).position(bus, bb.trip_id(bus), 0, 1000.0)
    env["event_ts"] = FUTURE.isoformat().replace("+00:00", "Z")
    return env


def _stream(conn, inject: bool):
    """Yield (decision, result, injected_now) after every EVERY events; inject the 2030 event once."""
    injected = False
    n = 0
    for event in _events():
        ts = datetime.fromisoformat(event["event_ts"].replace("Z", "+00:00"))
        ingest(conn, event)
        n += 1
        if inject and not injected and ts >= T0 + timedelta(seconds=INJECT_AT_S):
            assert ingest(conn, _future_event()).accepted is True
            injected = True
            yield (*_step(conn), True)
        elif injected and n % EVERY == 0:
            yield (*_step(conn), False)
        elif not inject and n % EVERY == 0:
            yield (*_step(conn), False)


def _buses(conn, snapshot_id) -> dict:
    return {b["bus_id"]: b for b in docs(conn, snapshot_id)["corridor_now"]["buses"]}


def test_the_clock_stays_in_the_simulated_day_and_only_the_bad_bus_is_estimated(gold_conn) -> None:
    conn = gold_conn
    steps = list(_stream(conn, inject=True))
    first_decision, first_result, first = steps[0]
    assert first
    # on the unfixed code resolve_clock does not exist and resolve_as_of returns 2030-01-01
    assert DAY_START <= first_decision.as_of < FUTURE
    assert first_decision.as_of.year == 2026
    assert first_decision.untrusted == frozenset({"B-101"})

    snap = docs(conn, first_result.snapshot_id)
    assert first_result.as_of_ts == first_decision.as_of
    assert "B-101" in {d["bus_id"] for d in snap["source_status"]["sources_down"]}
    buses = _buses(conn, first_result.snapshot_id)
    assert buses["B-101"]["data_quality"] == "estimated"
    assert buses["B-101"]["bus_state"] in {"regular", "leader"}  # never bunched or gap: no alert (classify.py)
    others = {k: v for k, v in buses.items() if k != "B-101"}
    assert others and all(b["data_quality"] == "live" for b in others.values())
    targeting = conn.execute("SELECT count(*) FROM gold.incident WHERE snapshot_id = %s AND doc::text LIKE '%%B-101%%'",
                             (first_result.snapshot_id,)).fetchone()[0]
    assert targeting == 0


def test_the_other_buses_stay_live_in_every_cycle_after_the_injection(gold_conn) -> None:
    conn = gold_conn
    checked = 0
    for decision, result, _ in _stream(conn, inject=True):
        assert DAY_START <= decision.as_of < FUTURE
        buses = _buses(conn, result.snapshot_id)
        for bus, row in buses.items():
            if bus != "B-101":
                assert row["data_quality"] == "live", (bus, decision.as_of)
        checked += 1
    assert checked >= 10


def test_a_later_valid_report_returns_the_bus_and_the_2030_event_stays_in_bronze(gold_conn) -> None:
    conn = gold_conn
    last = None
    for _, result, _ in _stream(conn, inject=True):
        last = result
    decision = refresh.resolve_clock(conn, "data", lambda: WALL)
    assert decision.untrusted == frozenset()  # B-101 reported again after the injection (US6.4)
    assert last is not None
    kept = conn.execute("SELECT count(*) FROM bronze.events WHERE event_ts = %s", (FUTURE,)).fetchone()[0]
    assert kept == 1


def test_one_bus_alone_uses_its_own_latest_report(gold_conn) -> None:
    ingest(gold_conn, _future_event())
    decision = refresh.resolve_clock(gold_conn, "data", lambda: WALL)
    assert decision.as_of == FUTURE and decision.untrusted == frozenset()  # documented limit (US6.5)


def test_no_bus_falls_back_to_the_wall_clock(gold_conn) -> None:
    decision = refresh.resolve_clock(gold_conn, "data", lambda: WALL)
    assert decision.as_of == WALL and decision.untrusted == frozenset()
    assert refresh.resolve_as_of(gold_conn, "data", lambda: WALL) == WALL


def test_two_buses_the_guard_already_applies(gold_conn) -> None:
    b = bb.Builder("two")
    b.position("B-101", bb.trip_id("B-101"), 0, 100.0)
    bb.ingest_all(gold_conn, b.events)
    ingest(gold_conn, _future_event("B-102", "two-future"))
    decision = refresh.resolve_clock(gold_conn, "data", lambda: WALL)
    assert decision.untrusted == frozenset({"B-102"}) and decision.as_of == DAY_START + timedelta(seconds=0)


def test_the_simulator_at_its_normal_pace_has_no_untrusted_bus_in_any_cycle(gold_conn) -> None:
    steps = list(_stream(gold_conn, inject=False))
    assert len(steps) > 50
    assert all(d.untrusted == frozenset() for d, _, _ in steps)


def test_with_no_bad_event_the_clock_equals_the_old_newest_report(gold_conn) -> None:
    for event in _events(1200):
        ingest(gold_conn, event)
    newest = gold_conn.execute(refresh._NEWEST_BUS_REPORT).fetchone()[0]
    gold_conn.rollback()
    decision = refresh.resolve_clock(gold_conn, "data", lambda: WALL)
    assert decision.untrusted == frozenset() and decision.as_of == newest


def test_wall_mode_is_unchanged(gold_conn) -> None:
    ingest(gold_conn, _future_event())
    decision = refresh.resolve_clock(gold_conn, "wall", lambda: WALL)
    assert decision.as_of == WALL and decision.untrusted == frozenset()
