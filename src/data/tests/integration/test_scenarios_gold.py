"""T011 — shape and meaning of gold for each scenario (004 FR-001 to FR-010, SC-002 to SC-006).

The simulator runs with a fixture (seed 42) through the real ingestion boundary into a throwaway
database and gold is computed with the cycle path. Assertions are on shape and meaning, not bytes.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.data.ingestion.bronze import ingest
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.config import load_scenarios, parse_scenarios
from src.data.simulator.scenarios.truth import TruthSink
from src.data.tests.fixtures.gold_support import cycle, docs

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios"
T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
SEED, DURATION_S = 42, 3600


def secs(ts: str) -> int:
    return int((datetime.fromisoformat(ts.replace("Z", "+00:00")) - T0).total_seconds())


def load_run(conn, source, duration: int = DURATION_S):
    """Ingest a scenario run. `source` is a fixture name or a list of parsed scenarios. Returns the truth."""
    scenarios = load_scenarios(FIXTURES / f"{source}.json") if isinstance(source, str) else source
    truth = TruthSink(scenarios)
    for event in scenario_events(scenarios, SEED, duration, truth):
        ingest(conn, event)
    truth.close()
    return truth.records()


def snapshot(conn, as_of_s: int) -> dict:
    result = cycle(conn, as_of_s)
    d = docs(conn, result.snapshot_id)
    d["id"] = result.snapshot_id
    d["buses"] = {b["bus_id"]: b for b in d["corridor_now"]["buses"]}
    return d


def incidents(conn, snapshot_id) -> list[dict]:
    return [r[0] for r in conn.execute(
        "SELECT doc FROM gold.incident WHERE snapshot_id = %s ORDER BY inc_id", (snapshot_id,)).fetchall()]


def check_summary(snap: dict) -> None:
    """The summary agrees with the per-bus states of the same document."""
    states = [b["bus_state"] for b in snap["corridor_now"]["buses"]]
    s = snap["corridor_now"]["summary"]
    assert s["n_bunched"] == states.count("bunched")
    assert s["n_gaps"] == states.count("gap")
    assert s["buses_in_service"] == len(states) - states.count("broken_down")


def test_c1_bunches_the_follower(gold_conn) -> None:
    (truth,) = load_run(gold_conn, "c1_bunching")
    found = None
    for t in range(1300, 1960, 30):
        snap = snapshot(gold_conn, t)
        check_summary(snap)
        if snap["corridor_now"]["summary"]["n_bunched"] >= 1:
            found = snap
            break
    assert found is not None, "no snapshot with a bunched follower"
    bunched = [b for b in found["corridor_now"]["buses"] if b["bus_state"] == "bunched"]
    assert all(b["headway_ahead_s"] < 0.5 * b["headway_planned_s"] for b in bunched)
    assert any(b["bus_id"] == "B-103" for b in bunched)  # the bus behind the delayed B-102
    assert truth["bus"] == "B-102" and truth["fired"] is True and truth["target_reached"] is True


def test_c2_opens_a_gap(gold_conn) -> None:
    (truth,) = load_run(gold_conn, "c2_gap")
    found = None
    for t in range(1700, 1960, 20):
        snap = snapshot(gold_conn, t)
        check_summary(snap)
        if snap["corridor_now"]["summary"]["n_gaps"] >= 1:
            found = snap
            break
    assert found is not None, "no snapshot with a gap"
    gaps = [b for b in found["corridor_now"]["buses"] if b["bus_state"] == "gap"]
    assert all(b["headway_ahead_s"] > 1.5 * b["headway_planned_s"] for b in gaps) and gaps
    assert any(b["bus_id"] == "B-103" for b in gaps)  # the delayed bus is the one that trails
    assert truth["bus"] == "B-103" and truth["fired"] is True


def test_c5_breakdown_incident_bus_state_and_closing(gold_conn) -> None:
    (truth,) = load_run(gold_conn, "c5_breakdown")
    effective = secs(truth["effective_ts"])
    during = snapshot(gold_conn, effective + 60)
    check_summary(during)
    (inc,) = incidents(gold_conn, during["id"])
    assert inc["type"] == "bus_breakdown" and inc["target_id"] == "B-102" and inc["reported_by"] == "script"
    assert inc["until"] is None and inc["duration_s"] == 240 and inc["since"] == truth["effective_ts"]
    stopped = during["buses"]["B-102"]
    assert stopped["bus_state"] == "broken_down" and stopped["headway_ahead_s"] is None
    # excluded by rule, not by a fixed count
    assert during["corridor_now"]["summary"]["buses_in_service"] == len(during["buses"]) - 1
    # the follower measures its headway to the nearest operational bus, skipping the stopped one
    follower = during["buses"].get("B-103")
    leader = during["buses"].get("B-101")
    assert follower is not None and leader is not None  # three buses on the corridor
    assert follower["headway_ahead_s"] is not None
    assert follower["headway_ahead_s"] > 1.5 * follower["headway_planned_s"]
    assert follower["bus_state"] == "gap"
    # after the duration the incident is closed and the bus is back in service
    after = snapshot(gold_conn, effective + 240 + 60)
    (closed,) = incidents(gold_conn, after["id"])
    assert closed["until"] is not None and secs(closed["until"]) == effective + 240
    assert after["buses"]["B-102"]["bus_state"] != "broken_down"
    # truth and gold agree within one 5 s cycle
    first = next(t for t in range(effective - 20, effective + 60, 5)
                 if snapshot(gold_conn, t)["buses"].get("B-102", {}).get("bus_state") == "broken_down")
    assert abs(first - effective) <= 5


def test_d1_silence_makes_the_bus_estimated_without_alerts(gold_conn) -> None:
    (truth,) = load_run(gold_conn, "d1_silence")
    last_report = secs(truth["effective_ts"]) - 5
    estimated_at = []
    for t in range(240, 620, 5):
        snap = snapshot(gold_conn, t)
        if snap["source_status"]["status"] == "estimated":
            estimated_at.append(t)
            assert [s["bus_id"] for s in snap["source_status"]["sources_down"]] == ["B-101"]
            bus = snap["buses"]["B-101"]
            assert bus["data_quality"] == "estimated"
            assert bus["bus_state"] not in ("bunched", "gap", "broken_down")
            assert snap["corridor_now"]["summary"]["n_bunched"] == 0 == snap["corridor_now"]["summary"]["n_gaps"]
            assert incidents(gold_conn, snap["id"]) == []
        else:
            assert snap["source_status"]["sources_down"] == []
            if t >= 550:
                assert snap["buses"]["B-101"]["data_quality"] == "live"
    # more than 120 s after the last report, at most 125 s (within one 5 s cycle)
    assert estimated_at and last_report + 120 < estimated_at[0] <= last_report + 125
    assert estimated_at[-1] < 550 and estimated_at == list(range(estimated_at[0], estimated_at[-1] + 5, 5))
    assert truth["fired"] is True


def test_d1_silence_of_120_s_or_less_never_makes_the_bus_estimated(gold_conn) -> None:
    scenarios = parse_scenarios([{"id": "s", "type": "D1_SILENCE", "start_s": 250, "bus": "B-101",
                                  "duration_s": 120}])
    load_run(gold_conn, scenarios, duration=900)
    for t in range(240, 520, 5):
        snap = snapshot(gold_conn, t)
        assert snap["source_status"]["status"] == "live", t
        assert snap["buses"]["B-101"]["data_quality"] == "live", t


def _strip_bronze(value):
    if isinstance(value, dict):
        return {k: _strip_bronze(v) for k, v in value.items() if "bronze" not in k and k != "snapshot_id"}
    if isinstance(value, list):
        return [_strip_bronze(v) for v in value]
    return value


def _state(conn, as_of_s: int) -> dict:
    snap = snapshot(conn, as_of_s)
    silver = {}
    for table in ("position_history", "incidents", "bus_current_state", "stop_visits", "segment_traversals"):
        rows = conn.execute(f"SELECT to_jsonb(t) FROM silver.{table} t").fetchall()  # noqa: S608 - fixed names
        silver[table] = sorted(json.dumps(_strip_bronze(r[0]), sort_keys=True) for r in rows)
    return {"silver": silver, "corridor_now": _strip_bronze(snap["corridor_now"]),
            "source_status": _strip_bronze(snap["source_status"])}


def test_d1_duplicates_are_recorded_and_change_nothing(gold_conn) -> None:
    (truth,) = load_run(gold_conn, "d1_duplicates")
    dups = gold_conn.execute("SELECT count(*) FROM bronze.rejections WHERE reason = 'duplicate_event'").fetchone()[0]
    others = gold_conn.execute("SELECT count(*) FROM bronze.rejections WHERE reason <> 'duplicate_event'").fetchone()[0]
    assert dups == 20 == len(truth["event_ids"]) and others == 0  # duplicates are not in the rejection rate
    with_dups = _state(gold_conn, 1800)

    gold_conn.execute("TRUNCATE bronze.events, bronze.rejections RESTART IDENTITY")
    for table in ("incident", "service_metric", "service_metric_stop", "stop_ewt_band", "decision_inputs", "corridor_now",
                  "source_status", "snapshots"):
        gold_conn.execute(f"DELETE FROM gold.{table}")  # noqa: S608 - fixed names
    gold_conn.commit()
    load_run(gold_conn, "empty")
    assert gold_conn.execute("SELECT count(*) FROM bronze.rejections").fetchone()[0] == 0
    assert _state(gold_conn, 1800) == with_dups


def test_truth_never_changes_gold(gold_conn, tmp_path) -> None:
    path = tmp_path / "truth.jsonl"
    scenarios = load_scenarios(FIXTURES / "phase1_live.json")
    truth = TruthSink(scenarios, path=path)
    for event in scenario_events(scenarios, SEED, DURATION_S, truth):
        ingest(gold_conn, event)
    truth.close()
    assert path.exists()
    before = _state(gold_conn, 2500)
    path.unlink()  # delete, then alter, the truth: nothing the pipeline computes may move
    path.write_text("tampered\n", encoding="utf-8")
    for table in ("incident", "service_metric", "service_metric_stop", "stop_ewt_band", "decision_inputs", "corridor_now",
                  "source_status", "snapshots"):
        gold_conn.execute(f"DELETE FROM gold.{table}")  # noqa: S608 - fixed names
    gold_conn.commit()
    assert _state(gold_conn, 2500) == before


def test_empty_and_unset_scenarios_leave_the_base_stream(gold_conn) -> None:
    assert load_run(gold_conn, "empty") == []
    snap = snapshot(gold_conn, 1800)
    assert snap["corridor_now"]["summary"]["n_bunched"] == 0 == snap["corridor_now"]["summary"]["n_gaps"]
    assert incidents(gold_conn, snap["id"]) == []
