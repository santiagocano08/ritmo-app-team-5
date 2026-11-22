"""T003 — alighting share per stop (006 research R2, SC-010).

`alight_share(i, last) = 1 / (last - i + 1)`: a rider on board at stop `i` has a destination uniform on
`i..last`. The data owner's prototype uses `1 / (last - i)`, which alights everyone one stop early; the
comparison with the simulator below measures which one matches the world the projector predicts.
"""
from __future__ import annotations

from collections import defaultdict

import pytest

from src.data.rules.projector import alight_share
from src.data.simulator.engine import run

LAST = 17
MIN_SAMPLE = 30  # riders on board at a stop in the sample (R2: fewer than 30 are skipped, not forced)

# Largest absolute difference between the observed share and the formula, fixed in T013 from the first green
# run: observed value plus a recorded margin (research R2, verification.md). The runs are seeded, so the
# tolerance only guards against an engine edit that changes the destination model or the random sequence.
#   scale 1.0 (the spec's check): observed 0.0385 over 12 stops, margin 0.0215 -> 0.06
#   scale 10  (high power):       observed 0.0551 over 17 stops, margin 0.0449 -> 0.10
TOLERANCE_SCALE_1 = 0.06
TOLERANCE_SCALE_10 = 0.10


def prototype_share(i: int, last: int = LAST) -> float:
    return 1.0 / max(1, last - i)


def test_formula_values() -> None:
    assert alight_share(0) == pytest.approx(1 / 18)
    assert alight_share(16) == pytest.approx(0.5)
    assert alight_share(17) == 1.0
    assert alight_share(1, last=3) == pytest.approx(1 / 3)


def test_prototype_formula_is_different() -> None:
    assert prototype_share(16) == 1.0
    assert alight_share(16) != prototype_share(16)


def _observed(seed: int, demand_scale: float = 1.0) -> dict[int, tuple[int, int]]:
    """stop index -> (sum alighted, sum occupancy_in) from `stop_arrival` of a 3,600 s run."""
    ids = {}
    out: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for ev in run(seed, 3600, demand_scale=demand_scale):
        if ev["event_type"] != "stop_arrival":
            continue
        p = ev["payload"]
        i = ids.setdefault(p["stop_id"], len(ids))  # stops are first met in corridor order by bus 1
        out[i][0] += p["alighted"]
        out[i][1] += p["occupancy"]
    return {k: (v[0], v[1]) for k, v in out.items()}


def _largest_difference(formula, seeds=(42, 43), demand_scale: float = 1.0) -> tuple[float, int, int]:
    """Pooled over the seeds. Returns (largest |observed - formula|, stops compared, stops skipped)."""
    pooled: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for seed in seeds:
        for i, (alighted, occ_in) in _observed(seed, demand_scale).items():
            pooled[i][0] += alighted
            pooled[i][1] += occ_in
    worst, used, skipped = 0.0, 0, 0
    for i, (alighted, occ_in) in sorted(pooled.items()):
        if occ_in < MIN_SAMPLE:
            skipped += 1
            continue
        used += 1
        worst = max(worst, abs(alighted / occ_in - formula(i)))
    return worst, used, skipped


def test_formula_matches_the_simulator() -> None:
    worst, used, skipped = _largest_difference(alight_share)
    print(f"alight_share vs simulator (seeds 42, 43; 3,600 s): largest |diff| = {worst:.4f} over {used} stops "
          f"({skipped} skipped, fewer than {MIN_SAMPLE} riders)")
    assert used >= 3
    assert worst <= TOLERANCE_SCALE_1


def test_formula_matches_the_simulator_with_more_riders() -> None:
    """Same runs with `demand_scale=10` (a simulator argument, test only): many more riders per stop."""
    worst, used, skipped = _largest_difference(alight_share, demand_scale=10.0)
    print(f"alight_share vs simulator (scale 10): largest |diff| = {worst:.4f} over {used} stops ({skipped} skipped)")
    assert used >= 15
    assert worst <= TOLERANCE_SCALE_10


def test_prototype_formula_does_not_match_the_simulator() -> None:
    """At scale 1 the sample is too small to tell the two formulas apart (0.05 vs 0.0385); at scale 10 it is not."""
    worst_1, _, _ = _largest_difference(prototype_share)
    print(f"prototype formula vs simulator (scale 1): largest |diff| = {worst_1:.4f}")
    worst, used, _ = _largest_difference(prototype_share, demand_scale=10.0)
    print(f"prototype formula vs simulator (scale 10): largest |diff| = {worst:.4f} over {used} stops")
    assert worst > TOLERANCE_SCALE_10
