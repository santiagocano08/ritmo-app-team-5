"""T039 — D1 source outage in gold (SC-003, FR-010, FR-011)."""
from __future__ import annotations

from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import cycle, docs

LAST_REPORT = 2875      # B-103 last report before the outage
RESUMES = 3005          # first report after the outage


def _outage_timeline() -> bb.Builder:
    b = bb.Builder("d1_replay")
    starts = {"B-105": 0, "B-104": 600, "B-103": 1200, "B-102": 1800, "B-101": 2400}
    for bus_id, start in starts.items():
        t = start
        while t <= 3100:
            silent = bus_id == "B-103" and LAST_REPORT < t < RESUMES
            if not silent:
                b.position(bus_id, bb.trip_id(bus_id), t, (t - start) * bb.SPEED_MPS)
            t += 5
    return b


def test_estimated_after_more_than_120_s_and_live_again_after_the_next_report(gold_conn) -> None:
    bb.ingest_all(gold_conn, _outage_timeline().events)
    per_snapshot = {}
    for as_of in range(2860, 3101, 5):
        result = cycle(gold_conn, as_of)
        per_snapshot[as_of] = docs(gold_conn, result.snapshot_id)

    def b103(as_of: int) -> dict:
        return next(b for b in per_snapshot[as_of]["corridor_now"]["buses"] if b["bus_id"] == "B-103")

    estimated = [t for t in per_snapshot if b103(t)["data_quality"] == "estimated"]
    assert estimated[0] - LAST_REPORT > 120
    assert estimated[0] - LAST_REPORT <= 125                 # SC-003: first snapshot at most 125 s later
    assert b103(LAST_REPORT + 120)["data_quality"] == "live"  # exactly 120 s is still live
    assert estimated == list(range(estimated[0], RESUMES, 5))  # estimated until the next report
    assert b103(RESUMES)["data_quality"] == "live"

    for as_of in estimated:
        ss = per_snapshot[as_of]["source_status"]
        assert ss["status"] == "estimated"
        assert [s["bus_id"] for s in ss["sources_down"]] == ["B-103"]
        by_id = {b["bus_id"]: b for b in per_snapshot[as_of]["corridor_now"]["buses"]}
        assert by_id["B-103"]["bus_state"] == "regular" and by_id["B-102"]["bus_state"] == "regular"
    assert per_snapshot[RESUMES]["source_status"]["status"] == "live"
    assert per_snapshot[RESUMES]["source_status"]["sources_down"] == []

    for as_of, d in per_snapshot.items():
        states = {b["bus_state"] for b in d["corridor_now"]["buses"]}
        assert not states & {"bunched", "gap", "broken_down"}, as_of
        assert d["corridor_now"]["summary"]["n_bunched"] == 0
        assert d["corridor_now"]["summary"]["n_gaps"] == 0
    assert gold_conn.execute("SELECT count(*) FROM silver.incidents").fetchone()[0] == 0
