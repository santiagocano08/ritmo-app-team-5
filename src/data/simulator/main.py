"""Simulator CLI (T023): JSON-lines envelopes on stdout.

    python -m src.data.simulator.main --seed S --duration D [--pace P] [--start-hour H]
        [--scenario-file PATH] [--truth-path PATH] [--holds {on,off}]

`--scenario-file` (or SIM_SCENARIO_FILE) turns scenario injectors on (004); an invalid file exits
non-zero before any event. The hidden truth goes to `--truth-path` (or SIM_TRUTH_PATH), else stderr.

`--holds on` (or SIM_HOLDS=on) turns the hold loop on (004 Phase 2): an initial synchronous poll of the
backend `decision` rows, then a read-only daemon thread. With it off (the default) the simulator never
touches the database. With it on and an empty bronze the stream is byte-identical to the baseline.

`SIM_DEMAND_SCALE` (006, demo setting, default 1.0 = the reference demand; accepted 0.1 to 10, anything else exits
before the first event) scales how many riders the simulator creates. It is not a field of any message.

`--start-hour` (or SIM_START_HOUR; demo setting, default 17 = the evening peak every reference run uses; an integer
from 0 to 23, anything else exits before the first event) is the local Medellin hour the simulated day starts at.
Congestion, street demand and metro trains follow that hour; event timestamps move with it.

`--pace` only throttles output in wall-clock seconds per 5 s sim step so a
long-running container produces a steady stream; it never changes the bytes.

`SIM_WARMUP_S` (demo setting, default 0) emits the first N simulated seconds without the pace, so a paced demo starts
with the corridor already full of buses and with history for the metrics and the decision model. Like the pace it
never changes the bytes, only when they are written.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import timedelta
from typing import TextIO

from src.data.simulator.engine import run, sim_start
from src.data.simulator.model import STEP_S
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.config import ScenarioConfigError, load_scenarios
from src.data.simulator.scenarios.truth import TruthSink
from src.data.simulator.scenarios.actions import ActionBoard
from src.data.simulator.scenarios.holds import HoldBoard, HoldPoller
from src.pulsoflota.config import (get_db_dsn, get_sim_hold_noncompliance, get_sim_hold_poll_s, get_sim_holds,
                                   get_sim_scenario_file, get_sim_truth_path)


DEMAND_SCALE_MIN, DEMAND_SCALE_MAX = 0.1, 10.0


def get_demand_scale() -> float:
    """SIM_DEMAND_SCALE: unset or empty is 1.0; a number from 0.1 to 10; anything else is an error."""
    raw = os.environ.get("SIM_DEMAND_SCALE")
    if raw is None or raw.strip() == "":
        return 1.0
    try:
        value = float(raw)
    except ValueError:
        raise RuntimeError(f"SIM_DEMAND_SCALE must be a number, got: {raw!r}") from None
    if not math.isfinite(value) or not DEMAND_SCALE_MIN <= value <= DEMAND_SCALE_MAX:
        raise RuntimeError(f"SIM_DEMAND_SCALE must be between {DEMAND_SCALE_MIN} and {DEMAND_SCALE_MAX}, got: {raw!r}")
    return value


START_HOUR_DEFAULT = 17


def get_warmup_s() -> int:
    """SIM_WARMUP_S: unset or empty is 0; an integer from 0 to 14400 simulated seconds; anything else is an error."""
    raw = os.environ.get("SIM_WARMUP_S")
    if raw is None or raw.strip() == "":
        return 0
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"SIM_WARMUP_S must be an integer, got: {raw!r}") from None
    if not 0 <= value <= 14400:
        raise RuntimeError(f"SIM_WARMUP_S must be between 0 and 14400, got: {raw!r}")
    return value


def get_start_hour(raw: str | None = None) -> int:
    """SIM_START_HOUR (or `raw` from the CLI): unset or empty is 17; an integer from 0 to 23; anything else is an error."""
    raw = os.environ.get("SIM_START_HOUR") if raw is None else raw
    if raw is None or raw.strip() == "":
        return START_HOUR_DEFAULT
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"SIM_START_HOUR must be an integer, got: {raw!r}") from None
    if not 0 <= value <= 23:
        raise RuntimeError(f"SIM_START_HOUR must be between 0 and 23, got: {raw!r}")
    return value


def main(argv: list[str] | None = None, out: TextIO | None = None) -> None:
    parser = argparse.ArgumentParser(description="PulsoFlota base simulator (corridor C6-008, direction 1)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--duration", type=int, default=3600, help="Simulated seconds")
    parser.add_argument("--pace", type=float, default=0.0,
                        help="Wall-clock seconds to wait per simulated 5 s step (0 = as fast as possible)")
    parser.add_argument("--start-hour", default=None,
                        help="Local hour (0-23) the simulated day starts at (default: SIM_START_HOUR, else 17)")
    parser.add_argument("--scenario-file", default=None,
                        help="JSON scenario file (default: SIM_SCENARIO_FILE; unset = no scenario)")
    parser.add_argument("--truth-path", default=None,
                        help="Where to write the hidden scenario truth (default: SIM_TRUTH_PATH, else stderr)")
    parser.add_argument("--holds", choices=("on", "off"), default=None,
                        help="Hold loop: poll approved holds from bronze, read-only (default: SIM_HOLDS, else off)")
    args = parser.parse_args(argv)
    out = out or sys.stdout
    try:
        demand_scale = get_demand_scale()
    except RuntimeError as exc:
        print(f"demand scale rejected: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    try:
        start_hour = get_start_hour(args.start_hour)
    except RuntimeError as exc:
        print(f"start hour rejected: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    try:
        warmup_s = get_warmup_s()
    except RuntimeError as exc:
        print(f"warm-up rejected: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    try:
        scenarios = load_scenarios(args.scenario_file or get_sim_scenario_file())
    except ScenarioConfigError as exc:
        print(f"scenario file rejected: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    truth = TruthSink(scenarios, path=args.truth_path or get_sim_truth_path())
    board = poller = actions = None
    try:
        holds_on = (args.holds == "on") if args.holds else get_sim_holds()
        if holds_on:
            start = sim_start(start_hour)

            def when(t: int) -> str:
                return (start + timedelta(seconds=t)).strftime("%Y-%m-%dT%H:%M:%SZ")

            actions = ActionBoard(truth=truth, when=when)
            board = HoldBoard(args.seed, get_sim_hold_noncompliance(), truth=truth, when=when, actions=actions)
            poller = HoldPoller(get_db_dsn(), board, start, get_sim_hold_poll_s())
    except RuntimeError as exc:
        print(f"hold loop rejected: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    if poller is not None:
        poller.poll_once()  # the only blocking call (2 s timeouts): decisions already written are known from step 0
        poller.start()
    events = scenario_events(scenarios, args.seed, args.duration, truth, start_hour=start_hour, holds=board,
                             demand_scale=demand_scale, actions=actions) \
        if scenarios or board else run(args.seed, args.duration, start_hour=start_hour, demand_scale=demand_scale)
    last_ts = None
    # Simulated second from which the pace applies (the warm-up before it is written as fast as possible).
    paced_from = (sim_start(start_hour) + timedelta(seconds=warmup_s)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        for event in events:
            if args.pace > 0 and last_ts is not None and event["event_ts"] != last_ts and event["event_ts"] > paced_from:
                out.flush()
                time.sleep(args.pace / STEP_S * _delta(last_ts, event["event_ts"]))
            last_ts = event["event_ts"]
            out.write(json.dumps(event, sort_keys=True) + "\n")
        out.flush()
    finally:
        if poller is not None:
            poller.stop()
        truth.close()


def _delta(a: str, b: str) -> float:
    from datetime import datetime
    f = "%Y-%m-%dT%H:%M:%SZ"
    return max((datetime.strptime(b, f) - datetime.strptime(a, f)).total_seconds(), 0.0)


if __name__ == "__main__":
    main()
