"""
Unit tests for src/ingestion/run.py (US-2 stub).
Verifies the stub reads stdin without crashing and discards lines gracefully.
The real implementation (US-3) will replace the stub body; these tests cover
the module-level code so coverage is counted.
"""
from __future__ import annotations

import io
import sys
from unittest.mock import patch

from src.ingestion import run as ingestion_run


def test_main_reads_empty_stdin_without_error() -> None:
    """main() must handle an empty stdin stream without raising."""
    with patch("sys.stdin", io.StringIO("")):
        ingestion_run.main()  # should not raise


def test_main_reads_blank_lines_without_error() -> None:
    """main() must handle blank / whitespace-only lines without raising."""
    fake_stdin = io.StringIO("\n   \n\n")
    with patch("sys.stdin", fake_stdin):
        ingestion_run.main()  # should not raise


def test_main_reads_json_lines_without_error() -> None:
    """main() must consume JSON-line input without raising (stub discards)."""
    lines = '{"event_type": "bus_position"}\n{"event_type": "stop_arrival"}\n'
    fake_stdin = io.StringIO(lines)
    with patch("sys.stdin", fake_stdin):
        ingestion_run.main()  # should not raise
