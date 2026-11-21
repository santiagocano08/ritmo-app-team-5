"""Simulator CLI (T023): JSON-lines envelopes on stdout.

    python -m src.data.simulator.main --seed S --duration D [--pace P]
        [--scenario-file PATH] [--truth-path PATH]

`--scenario-file` (or SIM_SCENARIO_FILE) turns scenario injectors on (004); an invalid file exits
non-zero before any event. The hidden truth goes to `--truth-path` (or SIM_TRUTH_PATH), else stderr.

`--pace` only throttles output in wall-clock seconds per 5 s sim step so a
long-running container produces a steady stream; it never changes the bytes.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import TextIO

from src.data.simulator.engine import run
from src.data.simulator.model import STEP_S
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.config import ScenarioConfigError, load_scenarios
from src.data.simulator.scenarios.truth import TruthSink
from src.pulsoflota.config import get_sim_scenario_file, get_sim_truth_path


def main(argv: list[str] | None = None, out: TextIO | None = None) -> None:
    parser = argparse.ArgumentParser(description="PulsoFlota base simulator (corridor C6-008, direction 1)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--duration", type=int, default=3600, help="Simulated seconds")
    parser.add_argument("--pace", type=float, default=0.0,
                        help="Wall-clock seconds to wait per simulated 5 s step (0 = as fast as possible)")
    parser.add_argument("--scenario-file", default=None,
                        help="JSON scenario file (default: SIM_SCENARIO_FILE; unset = no scenario)")
    parser.add_argument("--truth-path", default=None,
                        help="Where to write the hidden scenario truth (default: SIM_TRUTH_PATH, else stderr)")
    args = parser.parse_args(argv)
    out = out or sys.stdout
    try:
        scenarios = load_scenarios(args.scenario_file or get_sim_scenario_file())
    except ScenarioConfigError as exc:
        print(f"scenario file rejected: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    truth = TruthSink(scenarios, path=args.truth_path or get_sim_truth_path())
    events = scenario_events(scenarios, args.seed, args.duration, truth) if scenarios \
        else run(args.seed, args.duration)
    last_ts = None
    try:
        for event in events:
            if args.pace > 0 and last_ts is not None and event["event_ts"] != last_ts:
                out.flush()
                time.sleep(args.pace / STEP_S * _delta(last_ts, event["event_ts"]))
            last_ts = event["event_ts"]
            out.write(json.dumps(event, sort_keys=True) + "\n")
        out.flush()
    finally:
        truth.close()


def _delta(a: str, b: str) -> float:
    from datetime import datetime
    f = "%Y-%m-%dT%H:%M:%SZ"
    return max((datetime.strptime(b, f) - datetime.strptime(a, f)).total_seconds(), 0.0)


if __name__ == "__main__":
    main()
