"""T024 — rec_id, stability, expiry, derived status, stale proposals and the rest rule (006 FR-014, FR-021, FR-030).

Pure: every cycle is a call of `derive_all` / `resting_keys` / `apply_picks` with the rows of the previous cycle.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from src.data.rules.mpc import (Candidate, CycleCtx, Decision, Evaluated, action_doc, action_key, derive_all,
                                make_rec_id, rank_candidates, resting_keys, apply_picks, to_existing)
from src.data.rules.mpc_params import MpcParams
from src.data.rules.projector import Action

STOPS = tuple(f"P-{n}" for n in range(883, 901))
P = MpcParams()
T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
SNAP1, SNAP2, SNAP3 = (f"00000000-0000-4000-8000-00000000000{i}" for i in (1, 2, 3))


def ev(bus="B-103", saving=20.0, s=60, stop=5):
    return Evaluated(Candidate(Action("hold", bus, stop, hold_s=s), "C1"), 1000.0, saving)


def ctx(t: float, snap: str = SNAP1) -> CycleCtx:
    return CycleCtx(snapshot_id=snap, as_of=T0 + timedelta(seconds=t), rules_version="1.6.0", model_version="1.0.0",
                    data_quality="live", params=P)


def picks(*evs):
    return rank_candidates(list(evs), P, STOPS).picks


def run(rows, t, evs, snap=SNAP1, decisions=None, passed=None):
    """One cycle: derive, rest, rank, apply. `evs=None` is a snapshot that is too old (no new row)."""
    c = ctx(t, snap)
    derived = derive_all(rows, decisions or {}, passed or {}, c.as_of, P)
    if evs is None:
        return apply_picks(derived, None, c)
    rest = resting_keys(derived, c.as_of, P.rest_s)
    return apply_picks(derived, rank_candidates(list(evs), P, STOPS, resting=rest).picks, c)


def existing(rows):
    return [to_existing(r) for r in rows]


def test_key_and_rec_id() -> None:
    k60 = action_key(action_doc(Action("hold", "B-103", 5, hold_s=60), STOPS))
    k90 = action_key(action_doc(Action("hold", "B-103", 5, hold_s=90), STOPS))
    ks = action_key(action_doc(Action("slow_down", "B-103", 5, share=0.2, duration_s=300), STOPS))
    kr = action_key(action_doc(Action("reserve_dispatch", "B-106", 0), STOPS))
    assert k60 == "hold|B-103|P-888|60|" and ks == "slow_down|B-103|P-888|300|20" and kr == "reserve_dispatch|B-106|P-883||"
    a = make_rec_id(k60, SNAP1, "1.0.0")
    assert a == make_rec_id(k60, SNAP1, "1.0.0")
    assert a != make_rec_id(k90, SNAP1, "1.0.0") and a != make_rec_id(k60, SNAP2, "1.0.0")
    assert a != make_rec_id(k60, SNAP1, "1.0.1")
    assert uuid.UUID(a).version == 4


def test_first_publication() -> None:
    (row,) = run([], 0, [ev()])
    assert row.status == "proposed" and not row.stale and row.is_new
    assert row.proposed_ts == T0 and row.expires_ts == T0 + timedelta(seconds=120)
    assert row.rec_id == make_rec_id(row.key, SNAP1, "1.0.0") and row.first_snapshot_id == SNAP1
    assert row.doc["status"] == "proposed" and row.doc["expires_ts"] == "2026-11-24T22:02:00Z"
    assert row.doc["lineage"]["snapshot_id"] == SNAP1 and row.params == {} and row.case == "C1"


def test_same_key_keeps_identity_and_refreshes_numbers() -> None:
    (r1,) = run([], 0, [ev(saving=20.0)])
    (r2,) = run(existing([r1]), 5, [ev(saving=24.5)], snap=SNAP2)
    assert (r2.rec_id, r2.proposed_ts, r2.expires_ts, r2.first_snapshot_id) == (
        r1.rec_id, r1.proposed_ts, r1.expires_ts, r1.first_snapshot_id)
    assert not r2.is_new
    assert r2.doc["ewt_saving_s"] == 24.5 and r2.doc["lineage"]["snapshot_id"] == SNAP2 and r2.doc["rank"] == 1
    assert r2.doc["reason"].endswith("saves 24.5 s per rider")


def test_a_reserve_row_carries_its_readiness_in_params() -> None:
    e = Evaluated(Candidate(Action("reserve_dispatch", "B-106", 0), "C5"), 1000.0, 30.0)
    (row,) = run([], 0, [e])
    assert row.params == {"ready_s": 120}


@pytest.mark.parametrize("decision,expected", [("apply", "applied"), ("discard", "discarded")])
def test_first_decision_wins_even_after_expiry(decision, expected) -> None:
    (r1,) = run([], 0, [ev()])
    d = {r1.rec_id: Decision(decision, T0 + timedelta(seconds=30))}
    (r2,) = run(existing([r1]), 10, [ev()], decisions=d)
    assert r2.status == expected and r2.doc["status"] == expected
    (r3,) = run(existing([r1]), 500, [], decisions=d)  # a decision that arrives after the expiry
    assert r3.status == expected


def test_expiry_by_time_and_by_passing_the_stop() -> None:
    (r1,) = run([], 0, [ev()])
    assert run(existing([r1]), 120, [ev()])[0].status == "proposed"  # now <= expires_ts
    (late,) = run(existing([r1]), 121, [])
    assert late.status == "expired" and late.close_ts == r1.expires_ts
    (passed,) = run(existing([r1]), 40, [], passed={r1.rec_id: T0 + timedelta(seconds=35)})
    assert passed.status == "expired" and passed.close_ts == T0 + timedelta(seconds=35)


def test_nothing_is_applied_or_discarded_without_a_decision() -> None:
    (row,) = run([], 0, [ev()])
    for t in (0, 5, 60, 120, 121, 900):
        (r,) = run(existing([row]), t, [])
        assert r.status in ("proposed", "expired")
        row = r


def test_a_proposal_that_leaves_the_top_is_stale_and_frozen_until_it_expires() -> None:
    (a,) = run([], 0, [ev("B-103", 20.0)])
    rows = run(existing([a]), 5, [ev("B-104", 30.0)], snap=SNAP2)
    by_bus = {r.doc["action"]["bus_id"]: r for r in rows}
    old, new = by_bus["B-103"], by_bus["B-104"]
    assert old.stale and old.status == "proposed" and old.rec_id == a.rec_id
    assert old.doc["ewt_saving_s"] == 20.0 and old.doc["rank"] == 1  # frozen numbers, last rank
    assert not new.stale and new.is_new
    live = [r for r in rows if r.status == "proposed" and not r.stale]
    assert len(live) <= 3
    gone = run(existing(rows), 130, [ev("B-104", 30.0)], snap=SNAP3)
    assert {r.doc["action"]["bus_id"]: r.status for r in gone}["B-103"] == "expired"


def test_a_stale_proposal_that_returns_to_the_top_is_refreshed_not_duplicated() -> None:
    (a,) = run([], 0, [ev("B-103", 20.0)])
    rows = run(existing([a]), 5, [ev("B-104", 30.0)], snap=SNAP2)
    rows = run(existing(rows), 10, [ev("B-103", 40.0), ev("B-104", 30.0)], snap=SNAP3)
    assert len(rows) == 2 and not any(r.stale for r in rows)
    assert {r.doc["action"]["bus_id"]: r.rec_id for r in rows}["B-103"] == a.rec_id


def test_no_new_row_from_an_old_snapshot_but_status_is_still_derived() -> None:
    (a,) = run([], 0, [ev()])
    rows = run(existing([a]), 200, None)
    assert len(rows) == 1 and rows[0].status == "expired" and not rows[0].is_new


@pytest.mark.parametrize("gap,resting", [(299, True), (300, False)])
def test_rest_after_expiry(gap, resting) -> None:
    (a,) = run([], 0, [ev()])
    rows = run(existing([a]), 121, [])  # expired at 120 s: close_ts = expires_ts
    rows = run(existing(rows), 120 + gap, [ev()], snap=SNAP2)
    again = [r for r in rows if r.is_new]
    assert bool(again) is (not resting)
    if again:
        assert again[0].rec_id != a.rec_id and again[0].first_snapshot_id == SNAP2


@pytest.mark.parametrize("gap,resting", [(299, True), (300, False)])
def test_rest_after_a_decision_counts_from_the_decision_time(gap, resting) -> None:
    (a,) = run([], 0, [ev()])
    d = {a.rec_id: Decision("discard", T0 + timedelta(seconds=40))}
    rows = run(existing([a]), 41, [], decisions=d)
    rows = run(existing(rows), 40 + gap, [ev()], snap=SNAP2, decisions=d)
    assert any(r.is_new for r in rows) is (not resting)


def test_close_ts_is_kept_once_set() -> None:
    (a,) = run([], 0, [ev()])
    d = {a.rec_id: Decision("apply", T0 + timedelta(seconds=40))}
    (b,) = run(existing([a]), 50, [], decisions=d)
    (c,) = run(existing([b]), 400, [], decisions=d)
    assert b.close_ts == c.close_ts == T0 + timedelta(seconds=40)


def test_conflicts_list_the_other_rec_ids() -> None:
    e2 = Evaluated(Candidate(Action("slow_down", "B-103", 5, share=0.2, duration_s=300), "C1"), 1000.0, 18.0)
    rows = run([], 0, [ev("B-103", 20.0), e2, ev("B-104", 19.0)])
    by = {r.doc["action"]["type"] + r.doc["action"]["bus_id"]: r for r in rows}
    h, s, o = by["holdB-103"], by["slow_downB-103"], by["holdB-104"]
    assert h.doc["conflicts_with"] == [s.rec_id] and s.doc["conflicts_with"] == [h.rec_id]
    assert o.doc["conflicts_with"] == []
