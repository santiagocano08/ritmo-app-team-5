"""T029 — seeded non-compliance draw of the hold executor (004 FR-014, SC-008; AC7, AC8).

The draw is `SHA-256("{seed}|hold|{rec_id}")` read as a fraction of 1 (first 8 bytes / 2**64); the
driver does not comply when it is below `SIM_HOLD_NONCOMPLIANCE`. It uses no shared generator.
"""
from __future__ import annotations

import random
import uuid

from src.data.simulator.scenarios.holds import HoldBoard, complies, compliance_draw
from src.data.simulator.scenarios.truth import TruthSink

N = 200
REC_IDS = [str(uuid.UUID(int=(i + 1) * 0x10001000100010001000100010001, version=4)) for i in range(N)]


def test_draw_is_reproducible_and_a_fraction() -> None:
    a = compliance_draw(42, REC_IDS[0])
    assert a == compliance_draw(42, REC_IDS[0])
    assert 0.0 <= a < 1.0
    assert a != compliance_draw(7, REC_IDS[0])
    assert a != compliance_draw(42, REC_IDS[1])


def test_probability_one_makes_all_non_compliant_and_zero_none() -> None:
    assert not any(complies(42, r, 1.0) for r in REC_IDS)
    assert all(complies(42, r, 0.0) for r in REC_IDS)


def test_the_draw_does_not_touch_the_global_random_state() -> None:
    random.seed(5)
    state = random.getstate()
    for r in REC_IDS:
        complies(42, r, 0.1)
    assert random.getstate() == state


def _apply_all(seed: int, p: float):
    truth = TruthSink([])
    board = HoldBoard(seed=seed, noncompliance=p, truth=truth, when=lambda t: f"t{t}")
    for i, rec in enumerate(REC_IDS):
        board.add_order(rec, f"B-{100 + i % 5}", f"S-{i}", 60, float("-inf"), 1000)
        assert board.dwell_end(f"B-{100 + i % 5}", 10, f"S-{i}", 20) in (20, 70)
    truth.close()
    return truth.records()


def test_batch_of_200_is_reproducible_and_matches_the_truth_records() -> None:
    first, second = _apply_all(42, 0.10), _apply_all(42, 0.10)
    assert first == second
    holds_truth = [r for r in first if r["type"] == "HOLD"]
    assert len(holds_truth) == N
    non_compliant = sum(1 for r in holds_truth if r["complied"] is False)
    assert non_compliant == sum(1 for r in REC_IDS if not complies(42, r, 0.10))
    assert 0 < non_compliant < N  # about 20 expected (reported in verification.md, not asserted exactly)


def test_forced_values_in_the_truth_records() -> None:
    assert all(r["complied"] is False for r in _apply_all(42, 1.0))
    assert all(r["complied"] is True for r in _apply_all(42, 0.0))
