"""T055 — decision_inputs: schema, equality with corridor_now, M1/M2 inputs, resources, incidents (FR-032..FR-035)."""
from __future__ import annotations

import pytest

from tests.fixtures import bronze_builders as bb
from tests.fixtures.gold_support import count, cycle, validator


pytestmark = pytest.mark.usefixtures("config_reset")


def _stored(conn, snapshot_id) -> dict:
    return conn.execute("SELECT doc FROM gold.decision_inputs WHERE snapshot_id = %s", (snapshot_id,)).fetchone()[0]


def _corridor(conn, snapshot_id) -> dict:
    return conn.execute("SELECT doc FROM gold.corridor_now WHERE snapshot_id = %s", (snapshot_id,)).fetchone()[0]


def _run(conn, events: list[dict], as_of_s: float) -> tuple:
    assert all(r.accepted for r in bb.ingest_all(conn, events))
    conn.commit()
    result = cycle(conn, as_of_s)
    return result, _stored(conn, result.snapshot_id)


def test_decision_inputs_validate_and_equal_corridor_now(gold_conn) -> None:
    result, doc = _run(gold_conn, bb.normal().events, 3000)
    errors = list(validator("decision_inputs").iter_errors(doc))
    assert not errors, errors[:3]
    corridor = _corridor(gold_conn, result.snapshot_id)
    assert doc["buses"] == corridor["buses"] and doc["summary"] == corridor["summary"]
    assert doc["buses"], "the normal timeline has buses on the corridor"
    assert doc["snapshot_id"] == corridor["snapshot_id"] == str(result.snapshot_id)
    assert doc["as_of_ts"] == corridor["as_of_ts"]
    assert (doc["corridor_id"], doc["direction"]) == (corridor["corridor_id"], corridor["direction"])


def test_empty_bronze_still_gives_a_valid_decision_inputs(gold_conn) -> None:
    result = cycle(gold_conn, 100)
    doc = _stored(gold_conn, result.snapshot_id)
    assert not list(validator("decision_inputs").iter_errors(doc))
    assert doc["buses"] == [] and doc["summary"] == {"buses_in_service": 0, "n_bunched": 0, "n_gaps": 0}


def test_travel_time_forecast_is_the_m1_of_the_local_hour_of_as_of(gold_conn) -> None:
    result, doc = _run(gold_conn, bb.normal().events, 3000)       # 22:50Z = 17:50 local
    forecast = doc["travel_time_forecast"]
    assert [f["segment_id"] for f in forecast] == list(range(1, 18))
    rows = gold_conn.execute("SELECT segment_id, forecast_travel_s FROM gold.m1_baseline "
                             "WHERE hour_band = 17 ORDER BY segment_id").fetchall()
    assert [(f["segment_id"], f["forecast_travel_s"]) for f in forecast] == [(r[0], float(r[1])) for r in rows]


def test_demand_15min_is_the_next_aligned_window_at_or_after_as_of(gold_conn) -> None:
    result, doc = _run(gold_conn, bb.normal().events, 3000)       # 22:50Z -> window 23:00-23:15Z (band 72)
    d = doc["demand_15min"]
    assert d["window_start_ts"] == "2026-11-24T23:00:00Z" and d["window_end_ts"] == "2026-11-24T23:15:00Z"
    expected = gold_conn.execute("SELECT arrivals_forecast FROM gold.m2_baseline WHERE band = 72").fetchone()[0]
    assert d["arrivals_forecast"] == expected


def test_demand_window_on_an_exact_boundary_is_that_window(gold_conn) -> None:
    result = cycle(gold_conn, 3600)                                # exactly 23:00:00Z
    d = _stored(gold_conn, result.snapshot_id)["demand_15min"]
    assert d["window_start_ts"] == "2026-11-24T23:00:00Z"


def test_demand_window_across_the_local_midnight_uses_band_zero(gold_conn) -> None:
    result = cycle(gold_conn, 7 * 3600 - 1)                        # 04:59:59Z next day = 23:59:59 local
    d = _stored(gold_conn, result.snapshot_id)["demand_15min"]
    assert d["window_start_ts"] == "2026-11-25T05:00:00Z"
    expected = gold_conn.execute("SELECT arrivals_forecast FROM gold.m2_baseline WHERE band = 0").fetchone()[0]
    assert d["arrivals_forecast"] == expected
    hour_23 = gold_conn.execute("SELECT forecast_travel_s FROM gold.m1_baseline WHERE segment_id = 1 "
                                "AND hour_band = 23").fetchone()[0]
    assert _stored(gold_conn, result.snapshot_id)["travel_time_forecast"][0]["forecast_travel_s"] == float(hour_23)


def test_reserve_free_loses_a_dispatched_reserve_bus(gold_conn) -> None:
    result, doc = _run(gold_conn, bb.normal().events, 3000)
    assert doc["resources"] == {"reserve_free": ["B-106", "B-107"], "drivers_free": 2}
    assert doc["action_cost"] == {"hold_penalty_s": 0, "early_departure_penalty_s": 0}
    assert doc["enabled_stops"] == [f"P-{n}" for n in range(883, 901)]

    b = bb.Builder("reserve-dispatched")
    b.drive("B-106", 2000, 3000)
    assert all(r.accepted for r in bb.ingest_all(gold_conn, b.events))
    gold_conn.commit()
    result2 = cycle(gold_conn, 3000)
    doc2 = _stored(gold_conn, result2.snapshot_id)
    assert doc2["resources"]["reserve_free"] == ["B-107"]
    assert "B-106" in {x["bus_id"] for x in doc2["buses"]}


def test_active_incidents_are_ordered_by_id_and_drop_when_elapsed(gold_conn) -> None:
    b = bb.Builder("incidents")
    ids = [b.incident("bus_breakdown", "B-104", at=2900, duration_min=5.0)["event_id"],
           b.incident("stop_closed", "P-885", at=2950, duration_min=10.0)["event_id"],
           b.incident("bus_breakdown", "B-102", at=2800, duration_min=0)["event_id"]]   # never active
    b.incident("bus_breakdown", "B-103", at=100, duration_min=1.0)                      # long over
    assert all(r.accepted for r in bb.ingest_all(gold_conn, b.events))
    gold_conn.commit()
    during = _stored(gold_conn, cycle(gold_conn, 3000).snapshot_id)
    assert during["active_incidents"] == sorted(ids[:2])
    after_first = _stored(gold_conn, cycle(gold_conn, 3250).snapshot_id)   # 2900 s + 5 min = 3200 s
    assert after_first["active_incidents"] == [ids[1]]
    after_all = _stored(gold_conn, cycle(gold_conn, 3600).snapshot_id)     # 2950 s + 10 min = 3550 s
    assert after_all["active_incidents"] == []
    for doc in (during, after_first, after_all):
        assert not list(validator("decision_inputs").iter_errors(doc))


def test_a_config_change_changes_the_output_without_code_change(gold_conn) -> None:
    result, base = _run(gold_conn, bb.normal().events, 3000)
    gold_conn.execute("UPDATE config.corridor_settings SET drivers_free = 1, hold_penalty_s = 12.5, "
                      "early_departure_penalty_s = 7")
    gold_conn.execute("DELETE FROM config.enabled_stops WHERE stop_id IN ('P-883', 'P-900')")
    gold_conn.execute("DELETE FROM config.fleet_roster WHERE bus_id = 'B-107'")
    gold_conn.commit()
    result2 = cycle(gold_conn, 3000 + 5)
    changed = _stored(gold_conn, result2.snapshot_id)
    assert changed["resources"] == {"reserve_free": ["B-106"], "drivers_free": 1}
    assert changed["action_cost"] == {"hold_penalty_s": 12.5, "early_departure_penalty_s": 7}
    assert changed["enabled_stops"] == [f"P-{n}" for n in range(884, 900)]
    assert base["enabled_stops"] != changed["enabled_stops"]
    assert not list(validator("decision_inputs").iter_errors(changed))


def test_the_five_gold_rows_of_a_snapshot_share_one_id_and_lineage(gold_conn) -> None:
    result, _ = _run(gold_conn, bb.normal().events, 3000)
    for table in ("source_status", "corridor_now", "decision_inputs", "service_metric"):
        rows = gold_conn.execute(f"SELECT snapshot_id, rules_version, max_bronze_id FROM gold.{table}").fetchall()  # noqa: S608
        assert rows == [(result.snapshot_id, "1.0.0", result.max_bronze_id)], table
    assert count(gold_conn, "gold.snapshots") == 1
    for table in ("m1_baseline", "m2_baseline"):
        lineage = gold_conn.execute(f"SELECT DISTINCT rules_version, max_bronze_id FROM gold.{table}").fetchall()  # noqa: S608
        assert lineage == [("1.0.0", result.max_bronze_id)], table
