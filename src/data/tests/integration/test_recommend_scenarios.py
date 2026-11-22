"""006 T026 — what the model publishes on the four scenarios, through a `run_cycle` loop (SC-003 to SC-006).

Forced mode (seed 42, fixed duration, no wall clock). The loop runs a cycle every 15 simulated seconds and collects
`gold.mpc_evaluation` after each one, because the table holds the latest cycle only. Whether a candidate reaches the
15 s threshold is reported, never asserted (research R13); no parameter is tuned to make it so.
"""
from __future__ import annotations

import pytest
from jsonschema import Draft202012Validator, FormatChecker
import json
from pathlib import Path

import psycopg

from src.data.rules.holds import MAX_HOLD_S
from src.data.tests.fixtures.mpc_runs import Cycle, replay
from src.pulsoflota.models.read.recommendation import RecommendationV110

SCHEMA = json.loads((Path(__file__).resolve().parents[4] / "contracts" / "read" / "recommendation.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
DURATION = 2700
LAST_STOP = "P-900"


@pytest.fixture(scope="module")
def runs(module_db_dsn):
    """Each run is built once for the module and shared (plain data)."""
    cache: dict[tuple, list[Cycle]] = {}
    conn = psycopg.connect(module_db_dsn)

    def get(scenario: str | None, scale: float = 1.0, duration: int = DURATION) -> list[Cycle]:
        key = (scenario, scale, duration)
        if key not in cache:
            cache[key] = replay(conn, scenario, duration, demand_scale=scale)
        return cache[key]

    yield get
    conn.close()


def _bunching_cycles(cycles: list[Cycle]) -> list[Cycle]:
    """Cycles whose snapshot has a live bunched follower with at least one stop left to act on."""
    out = []
    for c in cycles:
        followers = [b for b in c.buses.values() if b["state"] == "bunched" and b["quality"] == "live"
                     and b["next_stop"] not in (None, LAST_STOP)]
        if followers:
            out.append(c)
    return out


def _types(c: Cycle) -> set[str]:
    return {e["action"]["type"] for e in c.evaluation}


def _all_rows(cycles: list[Cycle]) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for c in cycles:
        for r in c.recs:
            rows[r["rec_id"]] = r
    return rows


def _assert_valid(row: dict) -> None:
    RecommendationV110.model_validate(row["doc"])
    errors = [e.message for e in VALIDATOR.iter_errors(row["doc"])]
    assert not errors, errors
    assert row["doc"]["status"] == row["status"] and row["doc"]["horizon_s"] == 600
    assert row["doc"]["reason"].strip() and row["doc"]["lineage"]["model_version"] == "1.0.0"


def test_c1_evaluates_hold_slow_down_and_reserve_in_every_bunching_cycle(runs) -> None:
    cycles = runs("c1_bunching")
    bunching = _bunching_cycles(cycles)
    assert len(bunching) >= 5, "C1 must have bunching cycles"
    for c in bunching:
        assert {"hold", "slow_down", "reserve_dispatch"} <= _types(c), (c.t, _types(c))
        live = [r for r in c.recs if r["status"] == "proposed" and not r["stale"]]
        assert len(live) <= 3, (c.t, len(live))  # only the current top 3 count (SC-003)
        ranks = sorted(r["doc"]["rank"] for r in live)
        assert ranks == list(range(1, len(ranks) + 1))
    for row in _all_rows(cycles).values():
        _assert_valid(row)
    published = sum(1 for e in (e for c in bunching for e in c.evaluation) if e["recommended"])
    best = max((float(e["saving_s_per_rider"]) for c in bunching for e in c.evaluation), default=0.0)
    print(f"C1 seed 42, scale 1: {len(bunching)} bunching cycles, {len(_all_rows(cycles))} rows, "
          f"{published} recommended evaluations, best saving {best:.1f} s per rider")


def test_c1_slow_down_rows_carry_the_configured_intensity(runs) -> None:
    for scale in (1.0, 3.0):
        for row in _all_rows(runs("c1_bunching", scale)).values():
            a = row["doc"]["action"]
            if a["type"] == "slow_down":
                assert a["speed_reduction_pct"] in (10, 20) and a["duration_s"] == 300
            else:
                assert "speed_reduction_pct" not in a


def test_c5_evaluates_a_reserve_while_a_reserve_and_a_driver_are_free(runs) -> None:
    cycles = runs("c5_breakdown")
    broken = [c for c in cycles if any(b["state"] == "broken_down" for b in c.buses.values())
              and c.reserve_free and c.drivers_free > 0]
    assert len(broken) >= 3, "the C5 fixture must have breakdown cycles with a free reserve"
    for c in broken:
        assert "reserve_dispatch" in _types(c), (c.t, _types(c))
    for row in _all_rows(cycles).values():
        _assert_valid(row)
        if row["doc"]["action"]["type"] == "reserve_dispatch":
            assert row["doc"]["case"] == "C5" and row["doc"]["ewt_saving_s"] >= 15
    shown = [e for c in broken for e in c.evaluation if e["action"]["type"] == "reserve_dispatch"]
    print(f"C5: {len(broken)} breakdown cycles, best reserve saving "
          f"{max((float(e['saving_s_per_rider']) for e in shown), default=0):.1f} s per rider (after the 900 s cost)")


def test_a_normal_snapshot_has_no_candidate_and_no_row(runs) -> None:
    """SC-005: no bunched, gap or broken bus and no queue above 20 means nothing is evaluated."""
    cycles = runs(None)
    calm = [c for c in cycles if not c.trouble]
    assert len(calm) >= 20, "the normal run must have calm cycles"
    for c in calm:
        assert c.evaluation == [], (c.t, [e["action"] for e in c.evaluation])
    print(f"normal run: {len(calm)} calm cycles of {len(cycles)}, 0 candidates in all of them; "
          f"{len(_all_rows(cycles))} rows over the whole run")


def test_d1_no_row_and_no_candidate_targets_an_estimated_bus(runs) -> None:
    cycles = runs("d1_silence")
    seen: set[str] = set()
    silent = [c for c in cycles if c.sources_down]
    assert silent, "the D1 fixture must silence a bus"
    for c in cycles:
        down = set(c.sources_down) | {b for b, v in c.buses.items() if v["quality"] == "estimated"}
        for e in c.evaluation:
            assert e["action"].get("bus_id") not in down, (c.t, e["action"])
        for r in c.recs:
            if r["rec_id"] not in seen:  # a row is created with a live target
                seen.add(r["rec_id"])
                assert r["doc"]["action"]["bus_id"] not in down, (c.t, r["doc"]["action"])


def test_no_hold_above_the_cap_and_horizon_is_600_on_every_row_of_every_run(runs) -> None:
    for scenario, scale in (("c1_bunching", 1.0), ("c1_bunching", 3.0), ("c5_breakdown", 1.0), (None, 1.0),
                            ("d1_silence", 1.0)):
        cycles = runs(scenario, scale)
        for row in _all_rows(cycles).values():
            assert row["doc"]["horizon_s"] == 600
            if row["doc"]["action"]["type"] == "hold":
                assert 0 <= row["doc"]["action"]["duration_s"] <= MAX_HOLD_S
        for c in cycles:
            for e in c.evaluation:
                if e["action"]["type"] == "hold":
                    assert e["action"]["duration_s"] <= MAX_HOLD_S


def test_demo_demand_has_an_evaluated_candidate_in_every_bunching_cycle(runs) -> None:
    """Scale 3, as the data owner's prototype (research R13). Reported, not asserted: whether one reaches 15 s."""
    cycles = runs("c1_bunching", 3.0)
    bunching = _bunching_cycles(cycles)
    assert len(bunching) >= 5
    for c in bunching:
        assert len(c.evaluation) >= 1, c.t
    rows = _all_rows(cycles)
    best = max((float(e["saving_s_per_rider"]) for c in bunching for e in c.evaluation), default=0.0)
    print(f"C1 seed 42, SIM_DEMAND_SCALE=3: {len(bunching)} bunching cycles, {len(rows)} recommendation rows, "
          f"best saving {best:.1f} s per rider")
    for row in rows.values():
        _assert_valid(row)
