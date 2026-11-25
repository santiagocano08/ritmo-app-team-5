"""Unit tests for the Q0 (with age_s) and Q13 reads, using a recording fake connection."""
from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from src.api.reads import gold_reads


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def fetchone(self) -> dict[str, Any] | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeConn:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, Any]] = []

    def execute(self, query: str, params: Any = None) -> _Result:
        self.calls.append((query, params))
        return _Result(self.rows)


def _normalized(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip().lower()


def test_snapshot_with_age_returns_id_and_age() -> None:
    snapshot_id = uuid4()
    conn = _FakeConn([{"snapshot_id": snapshot_id, "age_s": 3.2}])

    result = gold_reads.latest_snapshot_with_age(conn)  # type: ignore[arg-type]

    assert result == (snapshot_id, 3.2)


def test_snapshot_with_age_none_when_no_snapshot() -> None:
    assert gold_reads.latest_snapshot_with_age(_FakeConn([])) is None  # type: ignore[arg-type]


def test_snapshot_age_uses_wall_clock_not_as_of_ts() -> None:
    conn = _FakeConn([])
    gold_reads.latest_snapshot_with_age(conn)  # type: ignore[arg-type]

    sql = _normalized(conn.calls[0][0])
    assert "clock_timestamp()" in sql
    assert "committed_at" in sql
    assert "gold.snapshot_commits" in sql
    assert "order by s.as_of_ts desc, s.max_bronze_id desc" in sql
    assert "limit 1" in sql


def test_recommendation_read_is_proposed_only_ranked_limited_and_read_only() -> None:
    doc = {"rec_id": "x"}
    conn = _FakeConn([{"doc": doc}])

    docs = gold_reads.proposed_recommendation_docs(conn)  # type: ignore[arg-type]

    assert docs == [doc]
    sql = _normalized(conn.calls[0][0])
    assert sql.startswith("select doc from gold.recommendation")
    assert "doc->>'status' = %(status)s" in sql
    assert "order by (doc->>'rank')::int" in sql
    assert "limit 3" in sql
    assert conn.calls[0][1] == {"status": "proposed"}
    for write in ("insert", "update", "delete", "truncate"):
        assert write not in sql.split()


def test_recommendation_read_returns_empty_list_without_rows() -> None:
    assert gold_reads.proposed_recommendation_docs(_FakeConn([])) == []  # type: ignore[arg-type]
