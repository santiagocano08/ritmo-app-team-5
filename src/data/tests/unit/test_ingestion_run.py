"""Unit tests for src/data/ingestion/run.py without a database (T017).

`consume` is exercised with a fake ingest function; `main` is exercised with a
fake connection so the stdin -> ingest -> counts wiring is covered offline.
"""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from src.data.ingestion import run as ingestion_run
from src.data.ingestion.bronze import IngestResult


def test_consume_counts_accepted_and_reasons_and_skips_blank() -> None:
    results = {"a": IngestResult(True, bronze_id=1), "b": IngestResult(False, "wrong_type"), "": None}
    counts = ingestion_run.consume(["a", "b", "a", ""], lambda line: results[line])
    assert counts == {"accepted": 2, "wrong_type": 1}


def test_main_wires_stdin_to_ingest(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@localhost:1/z")
    fake_conn = MagicMock()
    with patch.object(ingestion_run, "connect_with_retry", return_value=fake_conn), patch.object(
        ingestion_run,
        "ingest_line",
        side_effect=lambda conn, line: IngestResult(True, bronze_id=1) if line.strip() else None,
    ):
        counts = ingestion_run.main(io.StringIO('{"a":1}\n\n{"b":2}\n'))
    assert counts == {"accepted": 2}
    fake_conn.close.assert_called_once()


def test_connect_with_retry_gives_up(monkeypatch) -> None:
    import psycopg

    monkeypatch.setattr(ingestion_run.psycopg, "connect", MagicMock(side_effect=psycopg.OperationalError("down")))
    monkeypatch.setattr(ingestion_run.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="could not connect"):
        ingestion_run.connect_with_retry("postgresql://x", attempts=3, wait_s=0)
