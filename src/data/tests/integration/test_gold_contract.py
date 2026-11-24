"""T041 — stored gold documents validate against the read schemas (SC-001, SC-008, FR-016-FR-019, FR-025, FR-037, FR-040)."""
from __future__ import annotations

from datetime import datetime

import pytest

import src.data.pipeline.gold as gold_module
from src.data.pipeline.cycle import CycleError
from src.data.rules import RULES_VERSION
from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import count, cycle, docs, validator
from src.data.tests.fixtures.silver_support import dump

LINEAGE_TABLES = ("snapshots", "source_status", "corridor_now", "decision_inputs", "service_metric")


def _errors(schema: str, doc: dict) -> list[str]:
    return [e.message for e in validator(schema).iter_errors(doc)]


@pytest.mark.parametrize("timeline", [bb.normal, bb.c1_bunching, bb.d1_source_outage, bb.c2_gap, bb.c5_breakdown])
def test_every_stored_doc_validates_and_ids_agree(gold_conn, timeline) -> None:
    tl = timeline()
    bb.ingest_all(gold_conn, tl.events)
    as_of = (datetime.fromisoformat(tl.as_of) - bb.T0).total_seconds()
    result = cycle(gold_conn, as_of)
    stored = docs(gold_conn, result.snapshot_id)
    assert _errors("source_status", stored["source_status"]) == []
    assert _errors("corridor_now", stored["corridor_now"]) == []
    row = gold_conn.execute("SELECT snapshot_id::text, as_of_ts FROM gold.snapshots").fetchone()
    for name, doc in stored.items():
        assert doc["snapshot_id"] == row[0] == str(result.snapshot_id), name
        assert datetime.fromisoformat(doc["as_of_ts"]) == row[1], name
    status = gold_conn.execute("SELECT status FROM gold.source_status").fetchone()[0]
    assert status == stored["source_status"]["status"]


def test_every_gold_row_of_a_cycle_has_lineage_and_shares_the_snapshot_id(gold_conn) -> None:
    bb.ingest_all(gold_conn, bb.normal().events)
    result = cycle(gold_conn, 3000)
    max_id = gold_conn.execute("SELECT max(id) FROM bronze.events").fetchone()[0]
    for table in ("snapshots", "source_status", "corridor_now", "service_metric"):
        rows = gold_conn.execute(
            f"SELECT snapshot_id, rules_version, max_bronze_id FROM gold.{table}").fetchall()  # noqa: S608
        assert rows == [(result.snapshot_id, RULES_VERSION, max_id)], table
    assert result.max_bronze_id == max_id


def _regular_visits() -> list[dict]:
    """Three buses leave P-884, P-885 and P-886 every 600 s (1,800 / 2,400 / 3,000 s)."""
    b = bb.Builder("regular-visits")
    for bus, depart in (("B-103", 1800), ("B-102", 2400), ("B-101", 3000)):
        for stop in ("P-884", "P-885", "P-886"):
            b.stop_visit(bus, bb.trip_id(bus), stop, depart - 10, depart)
    return b.events


def test_service_metric_is_stored_with_the_cycle(gold_conn) -> None:
    """Stop-based (005 US3): two headways of 600 s at each of three stops in the trailing 15 minutes."""
    bb.ingest_all(gold_conn, bb.normal().events + _regular_visits())
    cycle(gold_conn, 3000)
    n, mean, sched, ewt, ok = gold_conn.execute(
        "SELECT n_headways, mean_wait_s, scheduled_wait_s, ewt_s, computable FROM gold.service_metric").fetchone()
    assert (n, ok) == (6, True)
    # planned 420 s since issue #42 (scheduled wait 210 s); the crafted departures stay 600 s apart (mean wait 300 s)
    assert float(sched) == 210.0 and float(mean) == pytest.approx(300.0, abs=0.01)
    assert float(ewt) == pytest.approx(90.0, abs=0.01)  # 300 - 210: the crafted service is worse than the 420 s plan


def test_service_metric_is_not_computable_without_stop_departures(gold_conn) -> None:
    """Positions alone give no stop headway: the row exists, `computable` is false, values are NULL, not 0."""
    bb.ingest_all(gold_conn, bb.normal().events)
    cycle(gold_conn, 3000)
    assert gold_conn.execute(
        "SELECT n_headways, mean_wait_s, scheduled_wait_s, ewt_s, computable FROM gold.service_metric").fetchone() == (
        0, None, None, None, False)


def test_empty_bronze_gives_no_data_and_an_empty_corridor(gold_conn) -> None:
    result = cycle(gold_conn, 100)
    stored = docs(gold_conn, result.snapshot_id)
    assert stored["source_status"]["status"] == "no_data" and stored["source_status"]["sources_down"] == []
    assert stored["corridor_now"]["buses"] == []
    assert stored["corridor_now"]["summary"] == {"buses_in_service": 0, "n_bunched": 0, "n_gaps": 0}
    assert result.max_bronze_id == 0 and result.status == "no_data"
    assert _errors("corridor_now", stored["corridor_now"]) == []
    computable = gold_conn.execute("SELECT computable, n_headways FROM gold.service_metric").fetchone()
    assert computable == (False, 0)


def test_a_failure_while_building_rolls_everything_back(gold_conn, monkeypatch) -> None:
    bb.ingest_all(gold_conn, bb.normal().events)
    silver_before = dump(gold_conn)
    original = gold_module.build_snapshot

    def failing(*args, **kwargs):
        original(*args, **kwargs)       # rows are written inside the transaction ...
        raise RuntimeError("boom /secret/path")  # ... and then the cycle fails

    monkeypatch.setattr(gold_module, "build_snapshot", failing)
    with pytest.raises(CycleError) as exc:
        cycle(gold_conn, 3000)
    assert "boom" not in str(exc.value) and "/secret/path" not in str(exc.value)
    assert "Traceback" not in str(exc.value)
    assert exc.value.correlation_id
    for table in LINEAGE_TABLES:
        assert count(gold_conn, f"gold.{table}") == 0, table
    assert dump(gold_conn) == silver_before                      # silver rebuild rolled back too

    monkeypatch.setattr(gold_module, "build_snapshot", original)  # the next cycle runs normally
    assert cycle(gold_conn, 3000).created is True
