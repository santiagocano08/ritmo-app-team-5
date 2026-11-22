"""T023 — threshold, top 3, ties, case, conflicts and reason text (006 FR-012, FR-013, FR-018, FR-022; R12).

The candidates are crafted `Evaluated` objects, so the expected order is read straight from the numbers.
"""
from __future__ import annotations

import pytest

from src.data.rules.mpc import Candidate, Evaluated, action_doc, build_doc, conflicts_for, rank_candidates
from src.data.rules.projector import Action
from src.data.tests.unit.projector_support import with_params
from src.data.rules.mpc_params import MpcParams

STOPS = tuple(f"P-{n}" for n in range(883, 901))
P = MpcParams()


def hold(bus="B-103", stop=5, s=60, saving=20.0, case="C1"):
    return Evaluated(Candidate(Action("hold", bus, stop, hold_s=s), case), 1000.0, saving)


def slow(bus="B-103", stop=5, share=0.2, saving=20.0, case="C1"):
    return Evaluated(Candidate(Action("slow_down", bus, stop, share=share, duration_s=300), case), 1000.0, saving)


def reserve(bus="B-106", saving=20.0, case="C5"):
    return Evaluated(Candidate(Action("reserve_dispatch", bus, 0), case), 1000.0, saving)


def adjust(bus="B-104", shift=60, saving=20.0, case="C2"):
    return Evaluated(Candidate(Action("adjust_departure", bus, 0, shift_s=shift), case), 1000.0, saving)


def skip(bus="B-102", stop=3, saving=20.0, case="C2"):
    return Evaluated(Candidate(Action("skip_stop", bus, stop), case), 1000.0, saving)


def test_threshold_is_fifteen_seconds_per_rider() -> None:
    r = rank_candidates([hold(saving=14.9), slow(saving=15.0)], P, STOPS)
    assert [p.candidate.action.type for p in r.picks] == ["slow_down"]
    assert r.not_picked[r_key(hold(saving=14.9))] == "below_threshold"


def r_key(ev) -> str:
    from src.data.rules.mpc import action_key
    return action_key(action_doc(ev.candidate.action, STOPS))


def test_threshold_comes_from_the_parameters() -> None:
    r = rank_candidates([hold(saving=14.9)], with_params(threshold_s_per_rider=10), STOPS)
    assert len(r.picks) == 1


def test_at_most_three_ranked_by_saving() -> None:
    evs = [hold(bus=f"B-10{i}", saving=20.0 + i) for i in range(1, 6)]
    r = rank_candidates(evs, P, STOPS)
    assert [p.rank for p in r.picks] == [1, 2, 3]
    assert [p.candidate.action.bus_id for p in r.picks] == ["B-105", "B-104", "B-103"]
    assert [p.saving_s for p in r.picks] == [25.0, 24.0, 23.0]
    assert sorted(v for v in r.not_picked.values()) == ["not_top_3", "not_top_3"]


def test_top_n_comes_from_the_parameters() -> None:
    evs = [hold(bus=f"B-10{i}", saving=20.0 + i) for i in range(1, 4)]
    assert len(rank_candidates(evs, with_params(top_n=1), STOPS).picks) == 1


def test_ties_break_by_catalog_order_then_bus_id() -> None:
    evs = [skip(), adjust(), hold(bus="B-104"), hold(bus="B-101"), slow(bus="B-105"), reserve()]
    r = rank_candidates(evs, with_params(top_n=3), STOPS)
    assert [(p.candidate.action.type, p.candidate.action.bus_id) for p in r.picks] == [
        ("reserve_dispatch", "B-106"), ("slow_down", "B-105"), ("hold", "B-101")]


def test_best_intensity_per_type_bus_and_stop_only() -> None:
    evs = [hold(s=30, saving=18.0), hold(s=60, saving=22.0), hold(s=90, saving=21.0), slow(share=0.1, saving=17.0)]
    r = rank_candidates(evs, P, STOPS)
    assert [(p.candidate.action.type, p.candidate.action.hold_s) for p in r.picks] == [("hold", 60), ("slow_down", 0)]


def test_resting_keys_are_skipped_and_the_next_candidate_fills_the_list() -> None:
    best = hold(bus="B-101", saving=40.0)
    evs = [best, hold(bus="B-102", saving=30.0), hold(bus="B-103", saving=20.0)]
    r = rank_candidates(evs, with_params(top_n=2), STOPS, resting=frozenset({r_key(best)}))
    assert [p.candidate.action.bus_id for p in r.picks] == ["B-102", "B-103"]
    assert r.not_picked[r_key(best)] == "resting"


def test_unsafe_targets_never_rank() -> None:
    r = rank_candidates([hold(bus="B-103", saving=90.0)], P, STOPS, unsafe_buses=frozenset({"B-103"}))
    assert r.picks == [] and r.not_picked[r_key(hold())] == "unsafe_target"


@pytest.mark.parametrize("ev,case", [(hold(case="C1"), "C1"), (skip(case="C2"), "C2"), (reserve(case="C5"), "C5")])
def test_case_follows_the_trigger_and_no_value_is_added(ev, case) -> None:
    pick = rank_candidates([ev], P, STOPS).picks[0]
    assert pick.case == case and pick.case in ("C1", "C2", "C5")


def test_conflicts_are_rows_on_the_same_bus() -> None:
    r = rank_candidates([hold(bus="B-103", saving=30), slow(bus="B-103", saving=25), reserve(saving=20),
                         hold(bus="B-104", stop=6, saving=19)], P, STOPS)
    conf = conflicts_for(r.picks)
    k_hold, k_slow = r.picks[0].key, r.picks[1].key
    assert conf[k_hold] == [k_slow] and conf[k_slow] == [k_hold]
    assert conf[r.picks[2].key] == []  # the reserve is another bus


def test_reason_names_action_bus_stop_and_saving() -> None:
    r = rank_candidates([hold(saving=22.0), slow(bus="B-103", saving=14.0 + 1.0), reserve(saving=33.0)], P, STOPS)
    reasons = {p.candidate.action.type: p.reason for p in r.picks}
    assert reasons["hold"] == "hold B-103 60 s at P-888 saves 22 s per rider"
    assert reasons["slow_down"] == "slow down B-103 by 20 % for 5 min at P-888 saves 15 s per rider"
    assert reasons["reserve_dispatch"] == "dispatch reserve B-106 saves 33 s per rider"
    adj = rank_candidates([adjust(shift=-60, saving=18.4), skip(saving=17.5)], P, STOPS).picks
    texts = {p.candidate.action.type: p.reason for p in adj}
    assert texts["adjust_departure"] == "advance the next departure from P-883 (B-104) by 60 s saves 18.4 s per rider"
    assert texts["skip_stop"] == "skip stops with an empty queue for B-102 from P-886 saves 17.5 s per rider"


def test_doc_has_horizon_600_and_lineage_and_validates() -> None:
    from datetime import datetime, timezone
    from src.pulsoflota.models.read.recommendation import RecommendationV110

    pick = rank_candidates([slow(saving=16.4)], with_params(scoring_window_s=1800), STOPS).picks[0]
    doc = build_doc(pick, rec_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", status="proposed",
                    expires_ts=datetime(2026, 11, 24, 22, 2, tzinfo=timezone.utc), conflicts=[],
                    snapshot_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", rules_version="1.6.0",
                    model_version="1.0.0", data_quality="live", horizon_s=P.horizon_s)
    assert doc["horizon_s"] == 600 and doc["schema_version"] == "1.1.0" and doc["rank"] == 1
    assert doc["lineage"] == {"model_version": "1.0.0", "rule_version": "1.6.0",
                              "snapshot_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"}
    assert doc["action"] == {"type": "slow_down", "bus_id": "B-103", "stop_id": "P-888", "duration_s": 300,
                             "speed_reduction_pct": 20}
    assert doc["expires_ts"] == "2026-11-24T22:02:00Z" and doc["ewt_saving_s"] == 16.4
    RecommendationV110.model_validate(doc)


@pytest.mark.parametrize("shares", [(0.10, 0.20), (0.07, 0.15)])
def test_speed_reduction_pct_is_the_configured_share_times_100(shares) -> None:
    for share in shares:
        doc = action_doc(Action("slow_down", "B-103", 5, share=share, duration_s=300), STOPS)
        assert doc["speed_reduction_pct"] in {round(s * 100, 6) for s in shares}
    assert action_doc(Action("hold", "B-103", 5, hold_s=60), STOPS) == {
        "type": "hold", "bus_id": "B-103", "stop_id": "P-888", "duration_s": 60}
    assert action_doc(Action("reserve_dispatch", "B-106", 0), STOPS)["duration_s"] is None
    assert "speed_reduction_pct" not in action_doc(Action("skip_stop", "B-102", 3), STOPS)
