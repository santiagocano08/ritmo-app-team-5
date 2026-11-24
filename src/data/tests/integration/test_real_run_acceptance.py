"""Acceptance on a real simulator run (data owner decision 2026-11-20, research R7, R14).

The base run (seed 42, 3,600 s, five buses 600 s apart, re-dispatched every 5 min) goes through
the real ingestion boundary into a throwaway database, and a cycle runs every 5 minutes. Waiting
buses (0 m, not yet departed) must never show up as bunched, as gaps or as a "bus ahead".
"""
from __future__ import annotations

import pytest

from src.data.ingestion.bronze import ingest
from src.data.simulator.engine import run
from src.data.tests.fixtures.gold_support import cycle, docs

SEED, DURATION_S = 42, 3600


def test_base_run_has_no_bunching_gaps_or_out_of_range_headways(gold_conn) -> None:
    for event in run(SEED, DURATION_S):
        assert ingest(gold_conn, event).accepted

    seen_headways: list[float] = []
    for minute in range(5, 61, 5):
        result = cycle(gold_conn, minute * 60)
        corridor = docs(gold_conn, result.snapshot_id)["corridor_now"]
        assert corridor["summary"]["n_bunched"] == 0, minute
        assert corridor["summary"]["n_gaps"] == 0, minute
        assert corridor["summary"]["buses_in_service"] == len(corridor["buses"]), minute
        for bus in corridor["buses"]:
            assert bus["bus_state"] not in ("bunched", "gap"), (minute, bus["bus_id"])
            if bus["headway_ahead_s"] is not None:
                seen_headways.append(bus["headway_ahead_s"])
                # 0.5x to 1.5x the planned 420 s (issue #42; 300 to 900 s with the old 600 s)
                assert 210 <= bus["headway_ahead_s"] <= 630, (minute, bus["bus_id"], bus["headway_ahead_s"])
    assert seen_headways, "the run produced no headway at all"
    print(f"\nacceptance: {len(seen_headways)} headways, min {min(seen_headways):.1f} s, "
          f"max {max(seen_headways):.1f} s")
