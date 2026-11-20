"""T076 — the SQL time bands equal src/rules/timebands.py at the boundary instants (FR-026, FR-030, R7).

The SQL paths are exercised for real: the hour band comes from silver.segment_traversals (T032) and
the 15-minute band from the M2 baseline SQL (T060), with the minimum sample count lowered to 1 in the
throwaway database so a single rider shows up as an `observed` row.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.rules import timebands
from tests.fixtures import bronze_builders as bb
from tests.fixtures.gold_support import clear_all
from src.pipeline.cycle import run_cycle

pytestmark = pytest.mark.usefixtures("config_reset")

INSTANTS = [
    "2026-11-25T04:59:59Z", "2026-11-25T05:00:00Z", "2026-11-25T05:14:59Z",
    "2026-11-25T05:15:00Z", "2026-11-24T19:00:00Z", "2026-11-26T04:59:00Z",
]


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _env(builder: bb.Builder, etype: str, ts: datetime, payload: dict, source: str = "simulator") -> None:
    builder.events.append({"schema_version": "1.0.0", "event_id": builder._eid(), "event_type": etype,
                           "source": source, "event_ts": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "payload": payload})


@pytest.mark.parametrize("instant", INSTANTS)
def test_sql_hour_band_and_m2_band_match_python(gold_conn, instant: str) -> None:
    clear_all(gold_conn)
    gold_conn.execute("UPDATE config.corridor_settings SET min_sample_count = 1")
    gold_conn.commit()
    t = utc(instant)
    trip = bb.trip_id("B-101")
    b = bb.Builder("sqlbands:" + instant)
    # Hour band: a traversal of segment 1 that departs at the instant.
    _env(b, "stop_departure", t, {"bus_id": "B-101", "trip_id": trip, "stop_id": "P-883",
                                  "boarded": 0, "alighted": 0, "rejected": 0, "occupancy": 0})
    _env(b, "stop_arrival", t + timedelta(seconds=60), {"bus_id": "B-101", "trip_id": trip, "stop_id": "P-884",
                                                        "boarded": 0, "alighted": 0, "rejected": 0, "occupancy": 0})
    # M2 band: the simulator is running at the instant and one rider arrives at P-883.
    _env(b, "bus_position", t, {"bus_id": "B-101", "operator": bb.OPERATOR, "trip_id": trip, "direction": 1,
                                "distance_along_m": 0.0, "speed_kmh": 0.0, "schedule_deviation_s": 0,
                                "doors_open": False, "occupancy": 0})
    _env(b, "rider_arrival", t, {"stop_id": "P-883", "direction": 1, "origin": "street",
                                 "destination_stop_id": "P-890"})
    assert all(r.accepted for r in bb.ingest_all(gold_conn, b.events))
    gold_conn.commit()

    as_of = t + timedelta(days=1)  # every band of the instant's day has ended
    assert run_cycle(gold_conn, as_of, notify=False) is not None

    hour_band = gold_conn.execute("SELECT hour_band FROM silver.segment_traversals").fetchone()[0]
    assert hour_band == timebands.local_hour_band(t)

    rows = gold_conn.execute("SELECT band FROM gold.m2_baseline WHERE n_samples >= 1 AND source = 'observed' "
                             "AND arrivals_forecast >= 1").fetchall()
    assert [r[0] for r in rows] == [timebands.m2_band(t)]
