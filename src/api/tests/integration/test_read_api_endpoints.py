"""Integration tests for the read endpoints against a gold-seeded database.

Three states per endpoint: healthy (live), source outage (estimated) and no-data
(empty gold), plus the unknown-corridor path. Needs a real database and skips when
DATABASE_URL is unset.
"""
from __future__ import annotations

from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import cycle
from src.data.tests.integration.test_gold_fixtures import _as_of_seconds


def _seed(gold_conn, timeline: bb.Timeline):
    assert all(r.accepted for r in bb.ingest_all(gold_conn, timeline.events))
    return cycle(gold_conn, _as_of_seconds(timeline))


# --- US-05.1 /now ----------------------------------------------------------

def test_now_healthy_reflects_latest_snapshot(client, gold_conn) -> None:
    result = _seed(gold_conn, bb.normal())

    resp = client.get("/api/v1/corridor/C6-008/now")

    assert resp.status_code == 200
    body = resp.json()
    assert body["snapshot_id"] == str(result.snapshot_id)
    assert body["buses"], "expected at least one bus on the corridor"
    assert body["buses"][0]["bus_state"] == "leader"
    summary = body["summary"]
    assert {"buses_in_service", "n_bunched", "n_gaps"} <= summary.keys()


def test_now_empty_gold_returns_no_data_envelope(client, gold_conn) -> None:
    resp = client.get("/api/v1/corridor/C6-008/now")

    assert resp.status_code == 200
    assert resp.json() == {"status": "no_data", "corridor_id": "C6-008"}


def test_now_unknown_corridor_returns_no_data_echoing_id(client, gold_conn) -> None:
    _seed(gold_conn, bb.normal())

    resp = client.get("/api/v1/corridor/C6-999/now")

    assert resp.status_code == 200
    assert resp.json() == {"status": "no_data", "corridor_id": "C6-999"}


# --- US-05.2 /source-status ------------------------------------------------

def test_source_status_healthy_is_live(client, gold_conn) -> None:
    _seed(gold_conn, bb.normal())

    resp = client.get("/api/v1/corridor/C6-008/source-status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "live"
    assert body["sources_down"] == []


def test_source_status_stale_bus_is_estimated_without_alert(client, gold_conn) -> None:
    _seed(gold_conn, bb.d1_source_outage())

    resp = client.get("/api/v1/corridor/C6-008/source-status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "estimated"
    down = {s["bus_id"]: s for s in body["sources_down"]}
    assert "B-103" in down
    assert "since" in down["B-103"]


def test_source_status_empty_gold_returns_no_data_envelope(client, gold_conn) -> None:
    resp = client.get("/api/v1/corridor/C6-008/source-status")

    assert resp.status_code == 200
    assert resp.json() == {"status": "no_data", "corridor_id": "C6-008", "sources_down": []}


def test_source_status_unknown_corridor_returns_no_data_echoing_id(client, gold_conn) -> None:
    _seed(gold_conn, bb.normal())

    resp = client.get("/api/v1/corridor/C6-999/source-status")

    assert resp.status_code == 200
    assert resp.json() == {"status": "no_data", "corridor_id": "C6-999", "sources_down": []}


# --- FR-005 read-only safety (T018) ----------------------------------------

def test_endpoints_do_not_write_any_gold_or_bronze_row(client, gold_conn) -> None:
    _seed(gold_conn, bb.normal())

    def counts() -> dict[str, int]:
        tables = (
            "bronze.events",
            "gold.snapshots",
            "gold.corridor_now",
            "gold.source_status",
        )
        return {t: gold_conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}  # noqa: S608

    before = counts()
    client.get("/api/v1/corridor/C6-008/now")
    client.get("/api/v1/corridor/C6-008/source-status")
    gold_conn.rollback()
    assert counts() == before
