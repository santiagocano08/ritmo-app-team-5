"""Scenario injectors for the simulator (004). Off by default; see `config.py`."""
from __future__ import annotations

from collections.abc import Iterator, Sequence

from src.data.simulator.engine import run, sim_start
from src.data.simulator.scenarios.channel import apply_channel
from src.data.simulator.scenarios.injectors import ScenarioHooks
from src.data.simulator.scenarios.truth import TruthSink

WORLD = ("C1", "C2", "C5")


def scenario_events(scenarios: Sequence, seed: int, duration: int, truth: TruthSink | None = None,
                    start_hour: int = 17, holds=None) -> Iterator[dict]:
    """The simulator stream with the scenarios applied: world hooks in the engine, D1 in the channel.

    `holds` (004 Phase 2) is the hold board of an approved-hold run; `None` adds nothing."""
    truth = truth if truth is not None else TruthSink(scenarios)
    hooks = ScenarioHooks(scenarios, truth, holds)
    events = run(seed, duration, start_hour=start_hour, hooks=hooks if hooks.active else None, holds=holds)
    if any(s.type not in WORLD for s in scenarios):
        events = apply_channel(events, scenarios, sim_start(start_hour), truth)
    return events
