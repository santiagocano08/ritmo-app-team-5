"""FastAPI dependencies for the read API (US-05).

Per-request psycopg 3 connection, opened from the environment DSN and closed at the
end of the request (research R4). Reads are SELECT-only, so no explicit write
transaction is opened. Injected via `Depends()` so handlers never build a global
client and tests can override the DB with a throwaway database.
"""
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import psycopg
from psycopg.rows import dict_row

from src.pulsoflota.config import get_db_dsn


def get_db_connection() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    """Yield a per-request psycopg 3 connection with `dict_row`, closed on completion."""
    with psycopg.connect(get_db_dsn(), row_factory=dict_row) as conn:
        yield conn
