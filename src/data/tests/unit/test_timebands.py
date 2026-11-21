"""T051 — local time bands with the fixed UTC-5 offset (FR-026, FR-030, FR-032, R7, R13)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from src.data.rules import timebands


def utc(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def test_no_zoneinfo_is_used() -> None:
    source = timebands.__loader__.get_source(timebands.__name__)  # type: ignore[union-attr]
    assert "zoneinfo" not in source and "pytz" not in source


@pytest.mark.parametrize("ts,hour", [
    ("2026-11-24T22:00:00Z", 17),      # simulator start = 17:00 local
    ("2026-11-25T04:59:59Z", 23),      # last second of the local day
    ("2026-11-25T05:00:00Z", 0),       # local midnight
    ("2026-11-24T19:00:00Z", 14),
    ("2026-11-24T05:00:00Z", 0),
])
def test_local_hour_band(ts: str, hour: int) -> None:
    assert timebands.local_hour_band(utc(ts)) == hour


@pytest.mark.parametrize("ts,band", [
    ("2026-11-25T05:00:00Z", 0),       # 00:00 local
    ("2026-11-25T05:14:59Z", 0),       # 00:14
    ("2026-11-25T05:15:00Z", 1),       # 00:15
    ("2026-11-25T04:59:59Z", 95),      # 23:59 previous local day
    ("2026-11-24T19:00:00Z", 56),      # 14:00 local
    ("2026-11-24T22:07:30Z", 68),      # 17:07 local -> 17 * 4 + 0
    ("2026-11-24T22:15:00Z", 69),
])
def test_m2_band_index(ts: str, band: int) -> None:
    assert timebands.m2_band(utc(ts)) == band


def test_m2_band_covers_exactly_96_values() -> None:
    start = utc("2026-11-25T05:00:00Z")
    bands = [timebands.m2_band(start + timedelta(minutes=15 * i)) for i in range(96)]
    assert bands == list(range(96))


def test_local_date_changes_at_05_utc() -> None:
    assert timebands.local_date(utc("2026-11-25T04:59:59Z")) == date(2026, 11, 24)
    assert timebands.local_date(utc("2026-11-25T05:00:00Z")) == date(2026, 11, 25)


def test_previous_local_day_and_new_local_day_pair() -> None:
    before, after = utc("2026-11-25T04:59:59Z"), utc("2026-11-25T05:00:00Z")
    assert (timebands.local_date(before), timebands.local_hour_band(before), timebands.m2_band(before)) == (
        date(2026, 11, 24), 23, 95)
    assert (timebands.local_date(after), timebands.local_hour_band(after), timebands.m2_band(after)) == (
        date(2026, 11, 25), 0, 0)


@pytest.mark.parametrize("as_of,start", [
    ("2026-11-24T22:00:00Z", "2026-11-24T22:00:00Z"),      # exactly on a boundary: that boundary
    ("2026-11-24T22:00:01Z", "2026-11-24T22:15:00Z"),
    ("2026-11-24T22:14:59Z", "2026-11-24T22:15:00Z"),
    ("2026-11-24T22:15:00Z", "2026-11-24T22:15:00Z"),
    ("2026-11-25T04:59:59Z", "2026-11-25T05:00:00Z"),      # crosses the local midnight
    ("2026-11-24T23:50:00Z", "2026-11-25T00:00:00Z"),
])
def test_next_window_is_first_aligned_window_at_or_after_as_of(as_of: str, start: str) -> None:
    got_start, got_end = timebands.next_window(utc(as_of))
    assert got_start == utc(start)
    assert got_end == utc(start) + timedelta(minutes=15)
    assert got_start.tzinfo is not None and got_start.utcoffset() == timedelta(0)


def test_subsecond_as_of_rounds_up_to_the_next_window() -> None:
    start, _ = timebands.next_window(utc("2026-11-24T22:00:00Z") + timedelta(microseconds=1))
    assert start == utc("2026-11-24T22:15:00Z")


def test_non_utc_input_is_converted() -> None:
    bogota = datetime(2026, 11, 24, 17, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
    assert timebands.local_hour_band(bogota) == 17
    assert timebands.next_window(bogota)[0] == utc("2026-11-24T22:00:00Z")


def test_naive_datetimes_are_rejected() -> None:
    naive = datetime(2026, 11, 24, 22, 0, 0)
    for fn in (timebands.local_hour_band, timebands.m2_band, timebands.local_date, timebands.next_window):
        with pytest.raises(ValueError):
            fn(naive)
