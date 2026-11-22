"""Load the seed recommendations into `config.seed_recommendation` (004 FR-018, FR-019; data-model E3).

DELETE + INSERT in the caller's transaction, like `load_reference`. A hold above `MAX_HOLD_S` loads (the
generated model does not bound it) with a log line; the hold executor refuses it and data reports it
`not_executed`. Parameterized statements only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from src.data.rules.holds import hold_in_range
from src.data.seeds import load_recommendations


def load_seeds(conn: psycopg.Connection, path: str | Path | None = None) -> int:
    """Replace `config.seed_recommendation` with the file contents. Returns the number of rows.

    An invalid file raises `SeedError` before anything is deleted.
    """
    entries = load_recommendations(path)
    for e in entries:
        if e.action.type == "hold" and not hold_in_range(e.action.duration_s if e.action.duration_s is not None else 0):
            sys.stderr.write(json.dumps({"event": "hold_seed_over_cap", "rec_id": str(e.rec_id),
                                         "duration_s": e.action.duration_s}, sort_keys=True) + "\n")
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("DELETE FROM config.seed_recommendation")
            cur.executemany(
                "INSERT INTO config.seed_recommendation (rec_id, doc) VALUES (%s, %s)",
                [(e.rec_id, Jsonb(e.model_dump(mode="json"))) for e in entries])
    return len(entries)
