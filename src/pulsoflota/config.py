"""
Environment-driven configuration.

Secrets (DB DSN) come from environment variables injected at runtime by
docker-compose or the shell. No secrets are hard-coded here or in .env files
committed to the repository (no-cost security baseline, turn 1).
"""
from __future__ import annotations

import os


def get_db_dsn() -> str:
    """Return the PostgreSQL DSN from the environment.

    Raises RuntimeError if the env var is not set.
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Set it to a psycopg3-compatible DSN, e.g. "
            "'postgresql://user:pass@db:5432/pulsoflota'"
        )
    return dsn


def get_log_level() -> str:
    return os.environ.get("LOG_LEVEL", "INFO").upper()
