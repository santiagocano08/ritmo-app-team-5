"""Simulator CLI (T023): JSON-lines envelopes on stdout.

    python -m src.data.simulator.main --seed S --duration D [--pace P]

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


def main(argv: list[str] | None = None, out: TextIO | None = None) -> None:
    parser = argparse.ArgumentParser(description="PulsoFlota base simulator (corridor C6-008, direction 1)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--duration", type=int, default=3600, help="Simulated seconds")
    parser.add_argument("--pace", type=float, default=0.0,
                        help="Wall-clock seconds to wait per simulated 5 s step (0 = as fast as possible)")
    args = parser.parse_args(argv)
    out = out or sys.stdout
    last_ts = None
    for event in run(args.seed, args.duration):
        if args.pace > 0 and last_ts is not None and event["event_ts"] != last_ts:
            out.flush()
            time.sleep(args.pace / STEP_S * _delta(last_ts, event["event_ts"]))
        last_ts = event["event_ts"]
        out.write(json.dumps(event, sort_keys=True) + "\n")
    out.flush()


def _delta(a: str, b: str) -> float:
    from datetime import datetime
    f = "%Y-%m-%dT%H:%M:%SZ"
    return max((datetime.strptime(b, f) - datetime.strptime(a, f)).total_seconds(), 0.0)


if __name__ == "__main__":
    main()
