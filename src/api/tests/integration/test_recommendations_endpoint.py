"""Integration tests for GET /api/v1/corridor/{corridor_id}/recommendations."""
from __future__ import annotations

from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import cycle
from src.data.tests.fixtures.rec_support import insert_recommendation
from src.data.tests.integration.test_gold_fixtures import _as_of_seconds

URL = "/api/v1/corridor/C6-008/recommendations"
BUSES = ["B-101", "B-102", "B-103", "B-104", "B-105"]


def _seed_snapshot(gold_conn) -> None:
    timeline = bb.normal()
    assert all(r.accepted for r in bb.ingest_all(gold_conn, timeline.events))
    cycle(gold_conn, _as_of_seconds(timeline))
    gold_conn.execute("DELETE FROM gold.recommendation")
    gold_conn.commit()


def _rec(gold_conn, n: int, **kw) -> str:
    return insert_recommendation(gold_conn, f"cccc0012-0000-4000-8000-{n:012d}", **kw)


def _age_snapshot(gold_conn, seconds: int) -> None:
    gold_conn.execute(
        "UPDATE gold.snapshot_commits SET committed_at = committed_at - make_interval(secs => %s)",
        (seconds,),
    )
    gold_conn.commit()


def test_ok_returns_proposed_ordered_by_rank(client, gold_conn) -> None:
    _seed_snapshot(gold_conn)
    _rec(gold_conn, 2, rank=2, bus="B-102", type="reserve_dispatch", duration_s=None, case="C5")
    _rec(gold_conn, 1, rank=1)

    body = client.get(URL).json()

    assert body["status"] == "ok"
    assert body["corridor_id"] == "C6-008"
    assert [r["rank"] for r in body["recommendations"]] == [1, 2]
    assert all(r["status"] == "proposed" for r in body["recommendations"])


def test_ok_with_no_proposed_returns_empty_list(client, gold_conn) -> None:
    _seed_snapshot(gold_conn)

    resp = client.get(URL)

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "corridor_id": "C6-008", "recommendations": []}


def test_more_than_three_stored_returns_three(client, gold_conn) -> None:
    _seed_snapshot(gold_conn)
    for n in range(1, 5):
        _rec(gold_conn, n, rank=min(n, 3), bus=BUSES[n])

    body = client.get(URL).json()

    assert len(body["recommendations"]) == 3


def test_non_proposed_are_excluded(client, gold_conn) -> None:
    _seed_snapshot(gold_conn)
    _rec(gold_conn, 1, status="applied")
    _rec(gold_conn, 2, status="discarded", bus="B-102")
    _rec(gold_conn, 3, status="expired", bus="B-104")
    _rec(gold_conn, 4, status="proposed", bus="B-105", rank=2)

    body = client.get(URL).json()

    assert [r["rec_id"] for r in body["recommendations"]] == [f"cccc0012-0000-4000-8000-{4:012d}"]


def test_stale_when_snapshot_older_than_15_seconds(client, gold_conn) -> None:
    _seed_snapshot(gold_conn)
    _rec(gold_conn, 1)
    _age_snapshot(gold_conn, 30)

    resp = client.get(URL)

    assert resp.status_code == 200
    assert resp.json() == {"status": "stale", "corridor_id": "C6-008", "recommendations": []}


def test_no_data_without_snapshot(client, gold_conn) -> None:
    resp = client.get(URL)

    assert resp.status_code == 200
    assert resp.json() == {"status": "no_data", "corridor_id": "C6-008", "recommendations": []}


def test_no_data_for_other_corridor(client, gold_conn) -> None:
    _seed_snapshot(gold_conn)
    _rec(gold_conn, 1)

    resp = client.get("/api/v1/corridor/C6-999/recommendations")

    assert resp.status_code == 200
    assert resp.json() == {"status": "no_data", "corridor_id": "C6-999", "recommendations": []}


def test_non_get_methods_are_rejected(client, gold_conn) -> None:
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(URL).status_code == 405
