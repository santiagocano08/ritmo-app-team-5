"""Unit tests for the Q0 latest-snapshot resolver (offline, no DB).

Checks the resolver issues the mandated ordering and maps zero rows to the no-data
signal (None) rather than raising.
"""
from __future__ import annotations

from uuid import UUID, uuid4

from src.api.reads.gold_reads import latest_snapshot_id


class _FakeCursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _RecordingConn:
    def __init__(self, row):
        self._row = row
        self.executed_sql = ""

    def execute(self, sql, params=None):
        self.executed_sql = sql
        return _FakeCursor(self._row)


def test_resolver_orders_by_as_of_then_max_bronze_id_desc() -> None:
    conn = _RecordingConn({"snapshot_id": uuid4(), "as_of_ts": "2026-11-24T22:00:00Z"})

    latest_snapshot_id(conn)

    normalized = " ".join(conn.executed_sql.split()).lower()
    assert "order by as_of_ts desc, max_bronze_id desc" in normalized
    assert "limit 1" in normalized


def test_resolver_returns_snapshot_id_when_present() -> None:
    expected = uuid4()
    conn = _RecordingConn({"snapshot_id": expected, "as_of_ts": "2026-11-24T22:00:00Z"})

    result = latest_snapshot_id(conn)

    assert isinstance(result, UUID)
    assert result == expected


def test_resolver_returns_none_on_zero_rows() -> None:
    conn = _RecordingConn(None)

    assert latest_snapshot_id(conn) is None
