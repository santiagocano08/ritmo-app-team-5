"""Service outcome of a simulator run (src/data/sim_console/outcomes.py): effects, groups, boarding, run summary."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.data.sim_console import outcomes

T0 = datetime(2026, 11, 24, 22, 0, tzinfo=timezone.utc)


def at(s: float) -> datetime:
    return T0 + timedelta(seconds=s)


def point(s, wait, ok=True, in_service=4, bunched=0):
    return {"as_of_ts": at(s), "mean_wait_s": wait, "scheduled_wait_s": 300.0, "ewt_s": wait - 300.0,
            "computable": ok, "in_service": in_service, "bunched": bunched}


SERIES = [point(0, 320), point(600, 340, bunched=1), point(1200, 300), point(1500, 290),
          point(2100, 330), point(2400, 9999, ok=False)]


def closed(rid, outcome, t, reason=None):
    return {"rec_id": rid, "outcome": outcome, "reason": reason, "close_ts": at(t), "action": "hold",
            "bus_id": "B-102", "stop_id": "P-884", "case": "C1", "saving_s": 10.0}


def test_effect_reads_the_two_non_overlapping_15_min_windows():
    e = outcomes.effects([closed("a", "applied", 600)], SERIES, at(2400))[0]
    assert (e["wait_before_s"], e["wait_after_s"], e["delta_wait_s"], e["verdict"]) == (340, 290, -50.0, "better")
    assert e["delta_ewt_s"] == -50.0


def test_effect_worse_same_and_measuring():
    series = SERIES + [point(2700, 333)]
    effs = outcomes.effects([closed("w", "expired", 1200, "time"), closed("s", "discarded", 2100),
                             closed("m", "applied", 2700), {"rec_id": "o", "outcome": "open", "close_ts": None}],
                            series, at(3000))
    by = {e["rec_id"]: e for e in effs}
    assert by["w"]["verdict"] == "worse" and by["w"]["delta_wait_s"] == 30.0   # 300 -> 330 at 2100
    # after = newest computable snapshot at or before close + 15 min (2400 is not computable, 2700 is)
    assert by["s"]["verdict"] == "same" and by["s"]["delta_wait_s"] == 3.0     # 330 -> 333
    assert by["m"]["verdict"] == "measuring" and by["m"]["wait_before_s"] == 333
    assert "o" not in by


def test_no_data_before_the_first_computable_snapshot():
    e = outcomes.effects([closed("a", "applied", 600)], [point(0, 300, ok=False), point(1500, 300)], at(1600))[0]
    assert e["verdict"] == "no_data"


def test_groups_compare_applied_with_not_applied():
    effs = outcomes.effects([closed("a", "applied", 600), closed("b", "expired", 1200, "time")], SERIES, at(2400))
    g = {x["group"]: x for x in outcomes.compare_groups(effs)}
    assert (g["applied"]["better"], g["applied"]["median_delta_wait_s"]) == (1, -50.0)
    assert (g["not_applied"]["worse"], g["not_applied"]["median_delta_wait_s"]) == (1, 30.0)


def test_boarding_is_weighted_by_riders():
    b = outcomes.boarding_summary([{"stop_id": "P-883", "riders": 30, "le5": 8, "le10": 30, "le15": 30},
                                   {"stop_id": "P-890", "riders": 10, "le5": 0, "le10": 2, "le15": 5}])
    assert (b["riders"], b["p5"], b["p10"], b["p15"]) == (40, 20.0, 80.0, 87.5)
    assert b["per_stop"][1]["p10"] == 20.0
    assert outcomes.boarding_summary([])["p10"] is None


def test_run_summary_skips_non_computable_snapshots():
    r = outcomes.run_summary(SERIES, {"p10": 80.0})
    assert r["avg_wait_s"] == 316.0 and r["max_in_service"] == 4 and r["p_board_10"] == 80.0
    assert r["snapshots_bunched_pct"] == round(100 / 6, 1)


def test_run_over_before_the_after_window_is_ended_not_measuring():
    e = outcomes.effects([closed("a", "applied", 1500)], SERIES, at(2100), run_over=True)[0]
    assert e["verdict"] == "ended" and e["wait_before_s"] == 290


def test_build_drops_snapshots_before_the_run_start():
    raw = {"series": [point(-80000, 999)] + SERIES, "boarding": []}
    out = outcomes.build(raw, [], at(2400), start=T0)
    assert out["series"][0]["as_of_ts"] == T0 and out["run"]["snapshots"] == len(SERIES)
