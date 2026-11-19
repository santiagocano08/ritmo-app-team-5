"""T027 — stop visits, segment traversals with exclusion flags, incidents (FR-012-FR-015, FR-026, R7)."""
from __future__ import annotations

from datetime import timedelta

import pytest

from tests.fixtures import bronze_builders as bb
from tests.fixtures.silver_support import at, build, incidents, state, traversals, visits

TRIP = bb.trip_id("B-101")


def _load(conn, b: bb.Builder) -> None:
    assert all(r.accepted for r in bb.ingest_all(conn, b.events))


# -- stop visits ------------------------------------------------------------------
def test_visit_pairs_arrival_and_departure_and_takes_counts_from_the_departure(silver_conn) -> None:
    b = bb.Builder("visit")
    b.stop_arrival("B-101", TRIP, "P-885", 100, boarded=0, alighted=0, rejected=0)
    b.stop_departure("B-101", TRIP, "P-885", 130, boarded=7, alighted=3, rejected=1)
    _load(silver_conn, b)
    build(silver_conn, 200)
    (v,) = visits(silver_conn)
    assert (v["bus_id"], v["trip_id"], v["stop_id"]) == ("B-101", TRIP, "P-885")
    assert (v["arrival_ts"], v["departure_ts"]) == (at(100), at(130))
    assert float(v["dwell_s"]) == 30.0
    assert (v["boarded"], v["alighted"], v["rejected"]) == (7, 3, 1)


def test_no_visit_row_until_both_events_exist(silver_conn) -> None:
    b = bb.Builder("half")
    b.stop_arrival("B-101", TRIP, "P-885", 100)
    b.stop_departure("B-102", bb.trip_id("B-102"), "P-885", 100)
    _load(silver_conn, b)
    build(silver_conn, 200)
    assert visits(silver_conn) == []
    b2 = bb.Builder("half2")
    b2.stop_departure("B-101", TRIP, "P-885", 150)
    _load(silver_conn, b2)
    build(silver_conn, 140)  # departure is in the future of this reference time
    assert visits(silver_conn) == []
    build(silver_conn, 200)
    assert len(visits(silver_conn)) == 1


def test_visits_are_per_bus_trip_and_stop(silver_conn) -> None:
    b = bb.Builder("visits")
    other = bb.trip_id("B-101", 2)
    b.stop_visit("B-101", TRIP, "P-885", 100, 120)
    b.stop_visit("B-101", TRIP, "P-886", 200, 215)
    b.stop_visit("B-101", other, "P-885", 900, 910)
    b.stop_visit("B-102", bb.trip_id("B-102"), "P-885", 100, 125)
    _load(silver_conn, b)
    build(silver_conn, 1000)
    assert {(v["bus_id"], v["trip_id"], v["stop_id"]) for v in visits(silver_conn)} == {
        ("B-101", TRIP, "P-885"), ("B-101", TRIP, "P-886"), ("B-101", other, "P-885"),
        ("B-102", bb.trip_id("B-102"), "P-885")}


def test_backend_stop_events_do_not_form_visits(silver_conn) -> None:
    b = bb.Builder("backend-visit")
    b.stop_arrival("B-101", TRIP, "P-885", 100)
    dep = b.stop_departure("B-101", TRIP, "P-885", 130)
    dep["source"] = "backend"
    _load(silver_conn, b)
    build(silver_conn, 200)
    assert visits(silver_conn) == []


# -- traversals ---------------------------------------------------------------------
def test_traversal_time_segment_and_band(silver_conn) -> None:
    b = bb.Builder("trav")
    b.traversal("B-101", TRIP, 3, depart=100, arrive=190)
    _load(silver_conn, b)
    build(silver_conn, 300)
    (t,) = traversals(silver_conn)
    assert (t["bus_id"], t["trip_id"], t["segment_id"]) == ("B-101", TRIP, 3)
    assert (t["departure_ts"], t["arrival_ts"]) == (at(100), at(190))
    assert float(t["travel_s"]) == 90.0
    assert t["hour_band"] == 17  # 22:01:40Z = 17:01:40 local
    assert t["travelled_while_estimated"] is False and t["broken_down"] is False


def test_no_traversal_until_the_arrival_at_the_next_stop_exists(silver_conn) -> None:
    b = bb.Builder("open")
    b.stop_departure("B-101", TRIP, "P-885", 100)           # segment 3 starts
    b.stop_arrival("B-101", TRIP, "P-887", 400)             # but arrival is two stops on
    b.stop_arrival("B-102", bb.trip_id("B-102"), "P-886", 400)  # other bus
    _load(silver_conn, b)
    build(silver_conn, 500)
    assert traversals(silver_conn) == []
    b2 = bb.Builder("open2")
    b2.stop_arrival("B-101", TRIP, "P-886", 250)
    _load(silver_conn, b2)
    build(silver_conn, 240)
    assert traversals(silver_conn) == []
    build(silver_conn, 500)
    assert [(t["segment_id"], float(t["travel_s"])) for t in traversals(silver_conn)] == [(3, 150.0)]


def test_every_segment_of_a_full_trip_is_a_traversal(silver_conn) -> None:
    b = bb.Builder("full")
    for seg in range(1, 18):
        b.traversal("B-101", TRIP, seg, depart=seg * 100, arrive=seg * 100 + 60)
    _load(silver_conn, b)
    build(silver_conn, 3000)
    assert [t["segment_id"] for t in traversals(silver_conn)] == list(range(1, 18))


@pytest.mark.parametrize("offset_s,band", [
    (6 * 3600 + 59 * 60 + 59, 23),   # 04:59:59Z = 23:59:59 local the day before
    (7 * 3600, 0),                   # 05:00:00Z = 00:00:00 local
    (21 * 3600, 14),                 # 19:00:00Z = 14:00:00 local
    (0, 17),                         # 22:00:00Z = 17:00:00 local
])
def test_hour_band_uses_the_fixed_utc_minus_5_offset(silver_conn, offset_s: int, band: int) -> None:
    b = bb.Builder(f"band{offset_s}")
    b.traversal("B-101", TRIP, 1, depart=offset_s, arrive=offset_s + 60)
    _load(silver_conn, b)
    build(silver_conn, offset_s + 100)
    (t,) = traversals(silver_conn)
    assert t["hour_band"] == band


# -- exclusion flags ----------------------------------------------------------------
def _flagged(conn, tag: str, reports: list[float], depart: float = 100, arrive: float = 400,
             incident=None) -> dict:
    """One traversal 100 -> 400 with extra bus reports at `reports`; returns its row."""
    b = bb.Builder(tag)
    for t in reports:
        b.position("B-101", TRIP, t, t)
    b.traversal("B-101", TRIP, 2, depart, arrive)
    if incident:
        incident(b)
    _load(conn, b)
    build(conn, arrive + 50)
    (t,) = traversals(conn)
    return t


@pytest.mark.parametrize("reports,expected", [
    ([220, 340], False),         # gaps 120, 120, 60 (departure 100 -> 220 -> 340 -> arrival 400): exactly 120 is fine
    ([221, 340], True),          # one gap of 121 s
    ([150, 300], True),          # 150 s gap between 150 and 300
    ([], True),                  # only the two ends, 300 s apart
    ([110, 220, 330], False),    # 10, 110, 110, 70
])
def test_travelled_while_estimated_is_a_gap_over_120_seconds_between_reports(silver_conn, reports, expected) -> None:
    row = _flagged(silver_conn, f"gap{expected}{len(reports)}{sum(reports)}", reports)
    assert row["travelled_while_estimated"] is expected


def test_both_ends_of_the_interval_count_as_reports(silver_conn) -> None:
    row = _flagged(silver_conn, "ends", [], depart=100, arrive=221)
    assert row["travelled_while_estimated"] is True
    row2 = _flagged_single(silver_conn, "ends2", 100, 220)
    assert row2["travelled_while_estimated"] is False


def _flagged_single(conn, tag: str, depart: float, arrive: float) -> dict:
    b = bb.Builder(tag)
    b.traversal("B-102", bb.trip_id("B-102"), 2, depart, arrive)
    _load(conn, b)
    build(conn, arrive + 50)
    return [t for t in traversals(conn) if t["bus_id"] == "B-102"][0]


def test_silence_outside_the_interval_does_not_flag_it(silver_conn) -> None:
    # a long silence before the departure and after the arrival is not travelled-while-estimated
    b = bb.Builder("outside")
    b.position("B-101", TRIP, 0, 0.0)
    b.traversal("B-101", TRIP, 2, depart=1000, arrive=1060)
    b.position("B-101", TRIP, 2000, 10.0)
    _load(silver_conn, b)
    build(silver_conn, 2100)
    (t,) = traversals(silver_conn)
    assert t["travelled_while_estimated"] is False


def test_other_buses_reports_do_not_fill_a_gap(silver_conn) -> None:
    b = bb.Builder("others")
    b.traversal("B-101", TRIP, 2, depart=100, arrive=400)
    b.drive("B-102", 100, 400)
    _load(silver_conn, b)
    build(silver_conn, 450)
    assert [t for t in traversals(silver_conn)][0]["travelled_while_estimated"] is True


def test_breakdown_overlapping_the_interval_sets_the_flag(silver_conn) -> None:
    row = _flagged(silver_conn, "bd-overlap", [150, 250, 350],
                   incident=lambda b: b.incident("bus_breakdown", "B-101", at=200, duration_min=1.0))
    assert row["broken_down"] is True


@pytest.mark.parametrize("start,duration,expected", [
    (0, 1.0, False),      # [0, 60) ended before the departure at 100
    (10, 1.5, False),     # [10, 100): ends exactly at the departure; half-open, so no overlap
    (10, 2.0, True),      # [10, 130) overlaps
    (400, 5.0, True),     # starts exactly at the arrival: overlaps the closed interval end
    (401, 5.0, False),    # starts after the arrival
    (200, 0.0, False),    # zero duration is never active
])
def test_breakdown_overlap_boundaries(silver_conn, start, duration, expected) -> None:
    row = _flagged(silver_conn, f"bd{start}-{duration}", [150, 250, 350],
                   incident=lambda b: b.incident("bus_breakdown", "B-101", at=start, duration_min=duration))
    assert row["broken_down"] is expected


def test_only_a_breakdown_of_this_bus_flags_the_traversal(silver_conn) -> None:
    def other(b: bb.Builder) -> None:
        b.incident("bus_breakdown", "B-102", at=200, duration_min=10.0)
        b.incident("stop_closed", "P-886", at=200, duration_min=10.0)
        b.incident("other", "B-101", at=200, duration_min=10.0)
    assert _flagged(silver_conn, "bd-other", [150, 250, 350], incident=other)["broken_down"] is False


def test_a_backend_breakdown_flags_the_traversal(silver_conn) -> None:
    b = bb.Builder("bd-backend")
    for t in (150, 250, 350):
        b.position("B-101", TRIP, t, t)
    b.traversal("B-101", TRIP, 2, 100, 400)
    _load(silver_conn, b)
    bb.insert_backend_commands(silver_conn, [b.command_incident(200, "B-101", duration_min=5.0)])
    build(silver_conn, 450)
    (t,) = traversals(silver_conn)
    assert t["broken_down"] is True


# -- incidents ------------------------------------------------------------------------
def test_incident_rows_use_event_id_and_the_half_open_interval(silver_conn) -> None:
    b = bb.Builder("inc")
    ev = b.incident("bus_breakdown", "B-101", at=100, duration_min=15.0, reported_by="dispatcher")
    _load(silver_conn, b)
    build(silver_conn, 200)
    (i,) = incidents(silver_conn)
    assert str(i["inc_id"]) == ev["event_id"]
    assert (i["incident_type"], i["target_id"], i["reported_by"], i["source"]) == (
        "bus_breakdown", "B-101", "dispatcher", "simulator")
    assert (i["start_ts"], i["end_ts"]) == (at(100), at(100) + timedelta(minutes=15))
    assert i["bronze_id"] == silver_conn.execute("SELECT id FROM bronze.events").fetchone()[0]


def test_backend_incidents_are_kept_and_later_ones_ignored(silver_conn) -> None:
    b = bb.Builder("inc2")
    b.incident("stop_closed", "P-886", at=100, duration_min=5.0)
    b.incident("other", "B-101", at=500, duration_min=5.0)  # after as_of
    _load(silver_conn, b)
    bb.insert_backend_commands(silver_conn, [b.command_incident(110, "B-102", duration_min=2.0)])
    build(silver_conn, 200)
    assert sorted((i["source"], i["incident_type"]) for i in incidents(silver_conn)) == [
        ("backend", "bus_breakdown"), ("simulator", "stop_closed")]


def test_zero_duration_incident_is_stored_but_never_makes_a_bus_broken_down(silver_conn) -> None:
    b = bb.Builder("inc0")
    b.position("B-101", TRIP, 100, 5.0)
    b.incident("bus_breakdown", "B-101", at=100, duration_min=0.0)
    _load(silver_conn, b)
    build(silver_conn, 100)
    (i,) = incidents(silver_conn)
    assert i["start_ts"] == i["end_ts"]
    assert state(silver_conn)["B-101"]["operational_status"] == "in_service"
