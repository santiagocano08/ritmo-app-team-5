"""006 T021 — assembly of the projector `Inputs` from one snapshot (FR-001, FR-003; research R1, R13).

The snapshot is built by a real `run_cycle` on crafted bronze; `recommend.load_inputs` then reads exactly what the
model reads. Hand values come from the reference data (633.92 riders/day, shape 0.104833 at 17 h).
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.data.pipeline import recommend
from src.data.rules.timebands import LOCAL_OFFSET
from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import cycle

REF = Path(__file__).resolve().parents[4] / "data" / "reference"
DAILY = 633.92
SHAPE = {int(r["hour"]): float(r["metro_line_a_shape"]) for r in csv.DictReader((REF / "demand_params.csv").open())}


def _run(conn, b: bb.Builder, as_of_s: float):
    assert all(r.accepted for r in bb.ingest_all(conn, b.events))
    res = cycle(conn, as_of_s)
    params = recommend.load_params(conn)
    inp, facts = recommend.load_inputs(conn, res.snapshot_id, res.as_of_ts, res.max_bronze_id, params)
    conn.rollback()
    return inp, facts, res


def test_reference_rates_at_17h(gold_conn) -> None:
    """Prado: 633.92 x 0.8 x 0.104833 = 53.2 riders/h in trains; a street stop 0.83 riders/h."""
    inp, facts, _ = _run(gold_conn, bb.Builder("inputs-ref"), 0)
    street = DAILY * 0.2 * SHAPE[17] / 16
    assert street == pytest.approx(0.8307, abs=1e-3)
    assert inp.stops[1].rate_by_hour[17] == pytest.approx(street)
    assert inp.stops[1].rate_by_hour[18] == pytest.approx(DAILY * 0.2 * SHAPE[18] / 16)
    assert inp.stops[0].rate_by_hour == (0.0,) * 24 and inp.stops[17].rate_by_hour == (0.0,) * 24
    sod = 17 * 3600
    with (REF / "train_arrivals.csv").open() as fh:
        secs = []
        for r in csv.DictReader(fh):
            h, m, s = (int(x) for x in r["arrival_time"].split(":"))
            secs.append(h * 3600 + m * 60 + s)
    per_hour = {h: sum(1 for s in secs if s // 3600 == h) for h in range(24)}
    # a train of 16:58 or 16:59 still has riders walking at 17:00: the simulator sizes its batch with its own hour
    expected = sorted((s + 120 - sod, DAILY * 0.8 * SHAPE[s // 3600] / per_hour[s // 3600])
                      for s in secs if 0 < s + 120 - sod <= 1800)
    batches = inp.stops[0].train_batches
    assert [t for t, _ in batches] == [t for t, _ in expected] and len(expected) > 15
    assert [n for _, n in batches] == pytest.approx([n for _, n in expected])
    assert sum(1 for t, n in batches if n == pytest.approx(DAILY * 0.8 * SHAPE[17] / 40)) >= len(batches) - 3
    assert DAILY * 0.8 * SHAPE[17] == pytest.approx(53.2, abs=0.05)
    assert DAILY * 0.8 * SHAPE[17] / 40 == pytest.approx(1.33, abs=0.01)


def test_observed_rate_replaces_the_reference_only_with_enough_events(gold_conn) -> None:
    b = bb.Builder("inputs-obs")
    for t in (100, 200, 300, 400, 500):  # 5 events = min_sample_count: observed
        b.rider_arrival("P-886", t, "P-890")
    for t in (100, 200, 300, 400):  # 4 events: reference
        b.rider_arrival("P-887", t, "P-890")
    b.rider_arrival("P-886", 1500, "P-890")  # after as_of: never read
    inp, _, _ = _run(gold_conn, b, 1000)
    assert inp.stops[3].rate_by_hour[17] == pytest.approx(5 / 1800 * 3600)
    assert inp.stops[3].rate_by_hour[18] == pytest.approx(5 / 1800 * 3600 * SHAPE[18] / SHAPE[17])
    assert inp.stops[4].rate_by_hour[17] == pytest.approx(DAILY * 0.2 * SHAPE[17] / 16)
    assert inp.stops[3].queue == 5 and inp.stops[4].queue == 4  # the queue of M3, no arrival seen at either


def test_buses_open_visits_slots_breakdown_and_resources(gold_conn) -> None:
    b = bb.Builder("inputs-buses")
    t1 = bb.trip_id("B-101")
    b.drive("B-101", 0, 995)  # 1.2 m/s: 1,194 m at 995 s
    b.position("B-101", t1, 1000, 1200.0, occupancy=12)
    b.incident("bus_breakdown", "B-101", at=900, duration_min=2.0)  # ends at 1,020 s
    t2 = bb.trip_id("B-102")
    b.stop_arrival("B-102", t2, "P-886", 980, boarded=2, alighted=1, rejected=0, occupancy=8)
    b.position("B-102", t2, 990, 1991.0, occupancy=9)
    b.position("B-102", t2, 1000, 1991.0, occupancy=9)
    b.stop_visit("B-105", bb.trip_id("B-105"), "P-883", 880, 900)  # last terminal departure: 900 s
    b.position("B-105", bb.trip_id("B-105"), 1000, 100.0)
    inp, facts, res = _run(gold_conn, b, 1000)
    buses = {x.bus_id: x for x in inp.buses}
    b101, b102 = buses["B-101"], buses["B-102"]
    assert b101.kind == "service" and b101.distance_m == pytest.approx(1200.0) and b101.occupancy == 12
    assert b101.next_stop_idx == 2 and b101.at_stop is None
    assert b101.broken_until == pytest.approx(20.0)
    assert b102.at_stop == (-20.0, 18.0) and b102.next_stop_idx == 4 and b102.occupancy == 9  # dwell 10+3*2+2*1
    # B-103 and B-104 never reported: the next terminal slots are the last departure + 600 s, +600 s each
    waiting = sorted(x.bus_id for x in inp.buses if x.kind == "waiting")
    assert waiting == ["B-103", "B-104"]
    assert inp.next_departures == (500.0, 1100.0)
    assert sorted(x.bus_id for x in inp.buses if x.kind == "reserve") == ["B-106", "B-107"]
    assert facts.drivers_free == 2 and len(facts.enabled_stops) == 18 and facts.snapshot_id == str(res.snapshot_id)
    assert dict(facts.bus_states)["B-101"] == "broken_down"
    assert len(inp.stops) == 18 and len(inp.m1) == 24 and all(len(r) == 17 for r in inp.m1)
    assert inp.alight_share[0] == pytest.approx(1 / 18) and inp.alight_share[17] == 1.0
    assert inp.as_of == res.as_of_ts and inp.params.horizon_s == 600


def test_m1_covers_all_24_bands_with_the_reference_formula(gold_conn) -> None:
    inp, _, _ = _run(gold_conn, bb.Builder("inputs-m1"), 0)
    cf17 = float(gold_conn.execute("SELECT congestion_factor FROM config.ref_congestion_factor WHERE hour = 17")
                 .fetchone()[0])
    assert inp.m1[17][0] == pytest.approx(834.0 / (60.0 / 3.6) / cf17)
    assert inp.trend == (1.0,) * 17


def test_local_hour_crosses_the_boundary(gold_conn) -> None:
    """At 17:55 local the 1,800 s window reaches hour 18: both hours' values are present (FR-003)."""
    inp, _, _ = _run(gold_conn, bb.Builder("inputs-boundary"), 3300)
    local = inp.as_of + LOCAL_OFFSET
    assert (local.hour, local.minute) == (17, 55)
    assert inp.stops[1].rate_by_hour[17] != inp.stops[1].rate_by_hour[18]
    assert inp.m1[17][3] != inp.m1[18][3]


def test_buses_waiting_at_the_terminal_leave_first_and_are_not_projected_as_departing_now(gold_conn) -> None:
    """Found by the projection-error check of T048a: a bus that reports position 0 and has not left P-883 is
    waiting for its scheduled departure, not a bus that leaves now. Waiters at the terminal take the first slots
    (by id), then buses back from their trip or never seen (by id); the tuple is in bus-id order."""
    b = bb.Builder("inputs-queue")
    b.stop_visit("B-102", bb.trip_id("B-102"), "P-883", 880, 900)  # the last departure: 900 s
    b.position("B-102", bb.trip_id("B-102"), 1000, 100.0)
    for t in range(0, 1001, 5):
        b.position("B-103", bb.trip_id("B-103"), t, 0.0, speed_kmh=0.0)  # waits at the terminal, reporting
    b.stop_arrival("B-101", bb.trip_id("B-101"), "P-900", 960)  # finished its trip: back in layover
    b.stop_departure("B-101", bb.trip_id("B-101"), "P-900", 970)
    inp, _, _ = _run(gold_conn, b, 1000)
    waiting = {x.bus_id for x in inp.buses if x.kind == "waiting"}
    assert waiting == {"B-101", "B-103", "B-104", "B-105"}
    assert {x.bus_id for x in inp.buses if x.kind == "service"} == {"B-102"}
    # last departure 900 s: slots at 500, 1100, 1700, 2300 s; B-103 (at the terminal) first, then B-101, B-104, B-105
    by_id = dict(zip(sorted(waiting), inp.next_departures))
    assert by_id == {"B-103": 500.0, "B-101": 1100.0, "B-104": 1700.0, "B-105": 2300.0}
