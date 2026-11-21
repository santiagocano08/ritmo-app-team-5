"""Ingestion entry point (T017): JSON-lines on stdin -> bronze.

Used by the `ingestion` container as `simulator | python -m src.data.ingestion.run`.
Importable, so tests can feed crafted lines without the live simulator.
"""
from __future__ import annotations

import logging
import sys
import time
from collections import Counter
from typing import Callable, Iterable, TextIO

import psycopg

from src.data.ingestion.bronze import IngestResult, ingest_line
from src.pulsoflota.config import get_db_dsn, get_log_level

log = logging.getLogger("ingestion")


def connect_with_retry(dsn: str, attempts: int = 10, wait_s: float = 2.0) -> psycopg.Connection:
    """Open an autocommit connection, retrying while the database starts."""
    last: Exception | None = None
    for _ in range(attempts):
        try:
            return psycopg.connect(dsn, autocommit=True)
        except psycopg.OperationalError as exc:  # db not ready yet
            last = exc
            time.sleep(wait_s)
    raise RuntimeError(f"could not connect to the database after {attempts} attempts") from last


def consume(lines: Iterable[str], ingest_fn: Callable[[str], IngestResult | None]) -> Counter:
    """Ingest every line; return counts of accepted events and rejection reasons."""
    counts: Counter = Counter()
    for line in lines:
        result = ingest_fn(line)
        if result is None:
            continue
        counts["accepted" if result.accepted else result.reason or "rejected"] += 1
    return counts


def main(stdin: TextIO | None = None) -> Counter:
    logging.basicConfig(level=get_log_level(), format="%(asctime)s %(name)s %(levelname)s %(message)s")
    conn = connect_with_retry(get_db_dsn())
    try:
        counts = consume(stdin or sys.stdin, lambda line: ingest_line(conn, line))
    finally:
        conn.close()
    log.info("ingestion finished: %s", dict(counts))
    return counts


if __name__ == "__main__":
    main()
