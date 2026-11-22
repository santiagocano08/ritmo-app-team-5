"""US2 (FR-020, FR-022, SC-003, SC-004): the bus leaving the terminal is measured from the leader's departure.

C1 seed 42 through the real ingestion boundary into a throwaway database. The leader waits at the first
stop; before the fix the headway counted from the moment it started waiting (1,240 / 1,835 / 2,440 s).
"""
from __future__ import annotations

import pytest

from src.data.tests.fixtures.gold_support import cycle, docs
from src.data.tests.integration.test_scenarios_gold import load_run

# as_of seconds after 22:00:00Z and the headway of the bus that has just left the terminal.
EXPECTED = [(1240, 615.0), (1835, 595.0), (2440, 605.0)]


@pytest.mark.parametrize(("as_of_s", "expected"), EXPECTED)
def test_terminal_headway_is_measured_from_the_leader_departure(gold_conn, as_of_s, expected) -> None:
    load_run(gold_conn, "c1_bunching", duration=2700)
    result = cycle(gold_conn, as_of_s)
    buses = docs(gold_conn, result.snapshot_id)["corridor_now"]["buses"]
    nearest = min((b for b in buses if b.get("headway_ahead_s") is not None), key=lambda b: b["distance_along_m"])
    assert nearest["headway_ahead_s"] == pytest.approx(expected, abs=1.0)
    assert 300 <= nearest["headway_ahead_s"] <= 900
    assert nearest["bus_state"] != "gap"
    ewt = gold_conn.execute("SELECT ewt_s FROM gold.service_metric WHERE snapshot_id = %s",
                            (result.snapshot_id,)).fetchone()[0]
    # Stop-based EWT arrives in Phase 2; here only the spatial artefacts of the terminal wait must be gone.
    assert ewt is None or round(float(ewt)) not in (211, 467, 731)
