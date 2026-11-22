"""Parameters of the decision model (006 FR-010, FR-018; data-model M1).

Pure data, no I/O. Defaults equal the defaults of `config.decision_model`; `pipeline/recommend.py` builds
this object from the table row (phase 2), and a test keeps both in step. The projector and the candidate
rules read every number from here, never from a literal. Owner of every value: the data owner (declared in
the spec Clarifications of 2026-11-21 and 2026-11-22) unless a comment says otherwise.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MpcParams:
    scoring_window_s: int = 1800  # FR-005: projection and scoring window (data owner, 2026-11-21)
    horizon_s: int = 600  # FR-018, ADR-0007: decision horizon published in recommendations
    step_s: int = 5  # simulator STEP_S: grid on which arrival and departure times are rounded up
    capacity: int = 40  # simulator CAPACITY, FR-005
    threshold_s_per_rider: float = 15  # FR-012: minimum saving per rider to publish
    top_n: int = 3  # FR-012: at most this many recommendations per cycle
    reserve_ready_s: int = 120  # declared assumption (data owner): reserve reaches P-883 this late
    reserve_cost_s: float = 900  # declared (data owner): passenger-seconds charged per dispatch
    slow_duration_s: int = 300  # declared (data owner): length of a slow-down
    slow_shares: tuple[float, ...] = (0.10, 0.20)  # FR-008: published as speed_reduction_pct 10 and 20
    hold_options_s: tuple[int, ...] = (30, 60, 90)  # FR-008, each <= MAX_HOLD_S
    adjust_options_s: tuple[int, ...] = (-120, -60, 60, 120)  # FR-008: shift of the next terminal slot
    skip_reach_stops: int = 4  # prototype reach, declared here
    queue_trigger_riders: int = 20  # FR-008: half a bus
    proposal_ttl_s: int = 120  # FR-030
    rest_s: int = 300  # FR-030
    freshness_max_s: int = 15  # FR-017, ADR-0006
    rate_window_s: int = 1800  # FR-003: observation window of the rider arrival rate (30 minutes)
    train_share: float = 0.80  # data/reference/SOURCES.md assumption (data owner)
    walk_mean_s: int = 120  # mean of the simulator's walk (60 to 180 s)
    model_version: str = "1.0.0"  # lineage.model_version
