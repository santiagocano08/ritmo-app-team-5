"""Local time bands for M1 and M2 (FR-026, FR-030, FR-032, research R7, R13).

Local time is America/Bogota, a fixed UTC-5 offset with no daylight saving, so a constant offset
is used instead of a time-zone database. The SQL side uses the same offset
(`AT TIME ZONE 'UTC' - interval '5 hours'`); `tests/integration/test_timebands_sql.py` checks that
both agree at the boundary instants.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

LOCAL_OFFSET = timedelta(hours=-5)
WINDOW = timedelta(minutes=15)
BANDS_PER_HOUR = 4


def _utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return ts.astimezone(timezone.utc)


def _local(ts: datetime) -> datetime:
    return _utc(ts) + LOCAL_OFFSET


def local_date(ts: datetime) -> date:
    return _local(ts).date()


def local_hour_band(ts: datetime) -> int:
    """Local hour of day, 0..23 (M1 band of a traversal departure; band of `as_of_ts`)."""
    return _local(ts).hour


def m2_band(ts: datetime) -> int:
    """Local 15-minute band index, `local_hour * 4 + local_minute div 15`, 0..95."""
    local = _local(ts)
    return local.hour * BANDS_PER_HOUR + local.minute // 15


def next_window(as_of: datetime) -> tuple[datetime, datetime]:
    """First clock-aligned 15-minute window with `start >= as_of` (UTC start and end).

    The offset is a whole number of hours, so UTC and local windows coincide.
    """
    ts = _utc(as_of)
    floor = ts.replace(minute=ts.minute - ts.minute % 15, second=0, microsecond=0)
    start = floor if floor >= ts else floor + WINDOW
    return start, start + WINDOW
