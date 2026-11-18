"""
Unit tests for src/simulator/main.py (US-2 stub).
Verifies the stub accepts --seed and --duration arguments and exits without
error.  The real implementation (US-4) replaces the body; these tests cover
the module-level code so coverage is counted.
"""
from __future__ import annotations

import sys
import time
from unittest.mock import patch

import pytest

from src.simulator import main as simulator_main


def test_main_exits_after_duration() -> None:
    """main() must complete when duration elapses (use a 0-second duration)."""
    # Patch time.monotonic to simulate instant expiry.
    start = 1000.0
    calls = iter([start, start, start + 1])  # start, loop check, loop check → expire
    with patch("src.simulator.main.time.monotonic", side_effect=calls):
        with patch("src.simulator.main.time.sleep"):
            with patch("sys.argv", ["simulator", "--seed", "42", "--duration", "0"]):
                simulator_main.main()  # should return without raising


def test_main_accepts_seed_and_duration_args() -> None:
    """main() must parse --seed and --duration without error."""
    start = 1000.0
    calls = iter([start, start + 10])
    with patch("src.simulator.main.time.monotonic", side_effect=calls):
        with patch("src.simulator.main.time.sleep"):
            with patch("sys.argv", ["simulator", "--seed", "7", "--duration", "1"]):
                simulator_main.main()
