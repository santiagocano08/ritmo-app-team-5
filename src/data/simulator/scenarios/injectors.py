"""World injectors C1, C2 and C5 (004 FR-002, FR-005, FR-006, FR-007; research R1).

`ScenarioHooks` is passed to `engine.run(hooks=...)`. The engine calls it at four fixed points, each
guarded by `if hooks is not None`, so with no hooks the baseline statements run unchanged. The hooks
read no clock and draw no random number of their own; time is the engine's simulated second `t`.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

from src.data.simulator.scenarios.truth import TruthSink

BUNCHED_BELOW_S = 300  # same quantity the rule uses: 0.5 x planned headway (002 FR-022)


class ScenarioHooks:
    def __init__(self, scenarios: Sequence, truth: TruthSink) -> None:
        self._truth = truth
        self._c1 = [s for s in scenarios if s.type == "C1"]
        self._c2 = [s for s in scenarios if s.type == "C2"]
        self._c5 = [s for s in scenarios if s.type == "C5"]
        self._halted_until: dict[str, float] = {}
        self._c1_departure: dict[str, int | None] = {}  # scenario id -> departure of the delayed bus
        self._c1_done: set[str] = set()
        self._when: Callable[[int], str] = lambda ts: ""

    @property
    def active(self) -> bool:
        return bool(self._c1 or self._c2 or self._c5)

    def bind(self, when: Callable[[int], str]) -> None:
        """`when(t)` formats simulated second `t` as an event time (the engine owns the date)."""
        self._when = when

    # -- engine call points -------------------------------------------------------
    def on_step(self, t: int, buses: list, out: list[dict], env: Callable) -> None:
        """Start of the bus phase of step `t`: fire C2 and C5."""
        by_id = {b.bus_id: b for b in buses}
        for s in self._c2:
            if t < s.start_s or self._truth.record(s.id)["fired"]:
                continue
            b = by_id[s.bus]
            if b.phase == "waiting" and b.start_at > t:
                b.start_at += s.delay_s
            elif b.phase == "layover" and b.phase_end > t:
                b.phase_end += s.delay_s
            else:
                continue
            self._truth.fire(s.id, self._when(t))
        for s in self._c5:
            if t < s.start_s or self._truth.record(s.id)["fired"]:
                continue
            if by_id[s.bus].phase != "driving":
                continue
            self._halted_until[s.bus] = t + s.duration_s
            out.append(env("incident_report", t, {
                "incident_type": "bus_breakdown", "target_id": s.bus,
                "duration_min": s.duration_s / 60, "reported_by": "script"}))
            self._truth.fire(s.id, self._when(t))

    def halted(self, bus, t: int) -> bool:
        return t < self._halted_until.get(bus.bus_id, -1)

    def dwell_extra(self, bus, t: int, stop_id: str) -> float:
        """Extra dwell seconds for this arrival (C1: the first arrival at the stop at or after `start_s`)."""
        for s in self._c1:
            if s.bus == bus.bus_id and s.stop == stop_id and t >= s.start_s \
                    and not self._truth.record(s.id)["fired"]:
                self._truth.fire(s.id, self._when(t))
                self._c1_departure[s.id] = None
                return s.extra_s
        return 0

    def on_departure(self, bus, t: int, stop_id: str) -> None:
        """C1 measurement: gap between the delayed bus and the next bus leaving the same stop."""
        for s in self._c1:
            if s.id in self._c1_done or s.id not in self._c1_departure or s.stop != stop_id:
                continue
            delayed = self._c1_departure[s.id]
            if bus.bus_id == s.bus:
                if delayed is None:
                    self._c1_departure[s.id] = t
            elif delayed is not None:
                rec = self._truth.record(s.id)
                rec["follower_gap_s"] = t - delayed
                rec["target_reached"] = (t - delayed) < BUNCHED_BELOW_S
                self._c1_done.add(s.id)
