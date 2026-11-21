"""Ingestion entry point (T017): JSON-lines on stdin -> bronze.

Used by the `ingestion` container as `simulator | python -m src.data.ingestion.run`.
Importable, so tests can feed crafted lines without the live simulator.
"""
from __future__ import annotations

import logging
import sys
from collections import Counter
from typing import Callable, Iterable, TextIO

import psycopg

from src.data.ingestion.bronze import IngestResult, ingest_line
from src.data.ingestion.retry import CONNECT_TIMEOUT_S, AuthFailed, Retrier, RetryExhausted, RetryPolicy
from src.pulsoflota.config import get_db_dsn, get_log_level

log = logging.getLogger("ingestion")

DUPLICATES = "duplicates"
_DUPLICATE_REASON = "duplicate_event"


def consume(lines: Iterable[str], ingest_fn: Callable[[str], IngestResult | None]) -> Counter:
    """Ingest every line, one at a time; return counts of accepted, duplicates and rejection reasons.

    A duplicate is not a contract rejection (FR-013): it is tallied under `duplicates`.
    The next line is read only after `ingest_fn` returned for the current one.
    """
    counts: Counter = Counter()
    for line in lines:
        result = ingest_fn(line)
        if result is None:
            continue
        if result.accepted:
            counts["accepted"] += 1
        elif result.reason == _DUPLICATE_REASON:
            counts[DUPLICATES] += 1
        else:
            counts[result.reason or "rejected"] += 1
    return counts


def summarize(counts: Counter | dict) -> dict:
    """Run summary (data-model E4). `rejection_rate` is None when nothing was accepted or rejected."""
    accepted = counts.get("accepted", 0)
    by_reason = {k: v for k, v in counts.items() if k not in ("accepted", DUPLICATES)}
    rejected = sum(by_reason.values())
    denominator = accepted + rejected
    return {
        "accepted": accepted,
        "rejected": rejected,
        "by_reason": by_reason,
        DUPLICATES: counts.get(DUPLICATES, 0),
        "rejection_rate": (rejected / denominator) if denominator else None,
    }


def _open(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn, autocommit=True, connect_timeout=CONNECT_TIMEOUT_S)


def main(stdin: TextIO | None = None, retrier: Retrier | None = None) -> Counter:
    logging.basicConfig(level=get_log_level(), format="%(asctime)s %(name)s %(levelname)s %(message)s")
    retrier = retrier or Retrier(RetryPolicy.from_env())  # invalid settings stop here, before any line
    dsn = get_db_dsn()
    holder: dict[str, psycopg.Connection | None] = {"conn": None}

    def reconnect() -> None:
        old, holder["conn"] = holder["conn"], None
        if old is not None:
            try:
                old.close()
            except Exception:  # the connection is already broken
                pass
        holder["conn"] = _open(dsn)

    def store(line: str) -> IngestResult | None:
        return retrier.run(lambda: ingest_line(holder["conn"], line), reconnect=reconnect)

    retrier.run(reconnect, reconnect=None)
    try:
        counts = consume(stdin or sys.stdin, store)
    finally:
        if holder["conn"] is not None:
            holder["conn"].close()
    log.info("ingestion finished: %s", summarize(counts))
    return counts


if __name__ == "__main__":
    try:
        main()
    except AuthFailed:
        sys.exit(1)  # the structured line was already written; nothing else is logged
    except RetryExhausted as exc:
        log.error("ingestion stopped: %s", exc)
        sys.exit(1)
