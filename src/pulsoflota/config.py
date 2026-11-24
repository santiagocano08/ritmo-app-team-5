"""
Environment-driven configuration.

Secrets (DB DSN) come from environment variables injected at runtime by
docker-compose or the shell. No secrets are hard-coded here or in .env files
committed to the repository (no-cost security baseline, turn 1).

All variables are declared in .env.example (committed).  Copy that to .env
(git-ignored) before running the stack locally.
"""
from __future__ import annotations

import math
import os
from importlib.metadata import PackageNotFoundError, version
from typing import Final

# Read-contract version the backend targets this turn. Single named source of truth
# mirroring the existing corridor_now / source_status read contracts (both pinned to
# 1.0.0). Reporting it implies no contract change (FR-003, R3).
READ_CONTRACT_VERSION: Final = "1.0.0"


def get_source_revision() -> str:
    """Return the build-time source revision from APP_REVISION, or `unknown`.

    The variable is injected at build/packaging time. When unset or empty the reader
    returns the literal `unknown` so metadata-less builds still succeed (FR-004, R1).
    """
    return os.environ.get("APP_REVISION") or "unknown"


def get_app_version() -> str:
    """Return the backend application version from the installed package metadata.

    Sourced from the single declaration in pyproject.toml (`version = "0.1.0"`) via the
    installed distribution, avoiding a second inline literal (FR-007, R2).
    """
    try:
        return version("pulsoflota")
    except PackageNotFoundError:
        return "0.0.0"


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

def get_sim_planned_headway_s() -> int:
    """Return the planned headway in seconds from SIM_PLANNED_HEADWAY_S (default 420; 600 before issue #42).

    Used by the simulator to space bus starts (R14). The gold rules read the same
    value from config.corridor_settings.headway_planned_s; a test keeps them equal.
    """
    raw = os.environ.get("SIM_PLANNED_HEADWAY_S")
    if raw is None:
        return 420
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(
            f"SIM_PLANNED_HEADWAY_S must be an integer, got: {raw!r}"
        )
    if value <= 0:
        raise RuntimeError(
            f"SIM_PLANNED_HEADWAY_S must be > 0, got: {value}"
        )
    return value


def _positive_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be a number, got: {raw!r}")
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError(f"{name} must be a finite number > 0, got: {raw!r}")
    return value


def get_ingestion_retry_initial_s() -> float:
    """Seconds to wait after the first database failure (INGESTION_RETRY_INITIAL_S, default 1)."""
    return _positive_float("INGESTION_RETRY_INITIAL_S", 1.0)


def get_ingestion_retry_max_wait_s() -> float:
    """Cap of the wait between attempts (INGESTION_RETRY_MAX_WAIT_S, default 5)."""
    return _positive_float("INGESTION_RETRY_MAX_WAIT_S", 5.0)


def get_ingestion_retry_total_s() -> float:
    """Total retry window of one outage (INGESTION_RETRY_TOTAL_S, default 120)."""
    return _positive_float("INGESTION_RETRY_TOTAL_S", 120.0)


def get_sim_scenario_file() -> str | None:
    """Path of the scenario file from SIM_SCENARIO_FILE; unset or empty means no scenario (004)."""
    return os.environ.get("SIM_SCENARIO_FILE") or None


def get_sim_truth_path() -> str | None:
    """Path of the scenario truth file from SIM_TRUTH_PATH; unset or empty means stderr (004)."""
    return os.environ.get("SIM_TRUTH_PATH") or None


def get_sim_holds() -> bool:
    """True when the hold loop is on (SIM_HOLDS=on). Default `off`; anything else is an error (004)."""
    raw = (os.environ.get("SIM_HOLDS") or "off").strip().lower()
    if raw not in ("on", "off"):
        raise RuntimeError(f"SIM_HOLDS must be 'on' or 'off', got: {raw!r}")
    return raw == "on"


def get_sim_hold_poll_s() -> float:
    """Seconds between polls of the hold decisions (SIM_HOLD_POLL_S, default 1)."""
    return _positive_float("SIM_HOLD_POLL_S", 1.0)


def get_sim_hold_noncompliance() -> float:
    """Probability that a driver does not comply with an approved hold (SIM_HOLD_NONCOMPLIANCE, default 0.10)."""
    raw = os.environ.get("SIM_HOLD_NONCOMPLIANCE")
    if raw is None or raw == "":
        return 0.10
    try:
        value = float(raw)
    except ValueError:
        raise RuntimeError(f"SIM_HOLD_NONCOMPLIANCE must be a number, got: {raw!r}")
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise RuntimeError(f"SIM_HOLD_NONCOMPLIANCE must be between 0 and 1, got: {raw!r}")
    return value


def get_mpc_enabled() -> bool:
    """True when the decision model runs (MPC_ENABLED=on, the default). `off` skips candidates and publishing but
    still derives the status of existing recommendations. Anything else is an error (006)."""
    raw = (os.environ.get("MPC_ENABLED") or "on").strip().lower()
    if raw not in ("on", "off"):
        raise RuntimeError(f"MPC_ENABLED must be 'on' or 'off', got: {raw!r}")
    return raw == "on"
