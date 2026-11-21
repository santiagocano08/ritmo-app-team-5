"""
psycopg 3 connection helpers — parameterized SQL only.

No ORM, no Alembic.  Parameterized queries satisfy the no-cost security
baseline (A05 injection prevention).
"""
from __future__ import annotations

import psycopg
from psycopg import Connection


def get_connection(dsn: str) -> Connection:
    """Open a psycopg 3 connection and return it."""
    return psycopg.connect(dsn)
