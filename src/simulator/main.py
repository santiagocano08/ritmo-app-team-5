"""
Simulator entry point — STUB for US-2 container bring-up.

The real implementation is in US-4 (T021–T023).  This stub runs an infinite
loop that emits nothing, so the ingestion container stays up and the isolation
test (T009) can verify that stopping the API does not stop ingestion.
"""
from __future__ import annotations

import argparse
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="PulsoFlota base simulator (stub)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--duration",
        type=int,
        default=3600,
        help="Simulation duration in seconds",
    )
    args = parser.parse_args()

    # Stub: emit nothing yet; just sleep so the container stays alive.
    # The real implementation (US-4) replaces this body with deterministic
    # event generation (see T021–T023).
    end_time = time.monotonic() + args.duration
    while time.monotonic() < end_time:
        time.sleep(5)
    # EOF: no events emitted — ingestion will read nothing but won't crash.
    sys.stdout.flush()


if __name__ == "__main__":
    main()
