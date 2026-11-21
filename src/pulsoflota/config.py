"""
Environment-driven configuration.

Secrets (DB DSN) come from environment variables injected at runtime by
docker-compose or the shell. No secrets are hard-coded here or in .env files
committed to the repository (no-cost security baseline, turn 1).

All variables are declared in .env.example (committed).  Copy that to .env
(git-ignored) before running the stack locally.
"""
from __future__ import annotations

import os


def get_db_dsn() -> str:
    """Return the PostgreSQL DSN from the environment.

    Raises RuntimeError if the env var is not set — no password defaults
    in code, per turn-1 security baseline.
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Copy .env.example to .env, set POSTGRES_PASSWORD, and re-run."
        )
    return dsn


def get_log_level() -> str:
    """Return the log level from LOG_LEVEL (default INFO)."""
    return os.environ.get("LOG_LEVEL", "INFO").upper()


def get_sim_seed() -> int:
    """Return the simulator RNG seed from SIM_SEED (default 42)."""
    raw = os.environ.get("SIM_SEED")
    if raw is None:
        return 42
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(
            f"SIM_SEED must be an integer, got: {raw!r}"
        )


def get_sim_duration_s() -> int:
    """Return the simulator duration in seconds from SIM_DURATION_S (default 3600)."""
    raw = os.environ.get("SIM_DURATION_S")
    if raw is None:
        return 3600
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(
            f"SIM_DURATION_S must be an integer, got: {raw!r}"
        )
