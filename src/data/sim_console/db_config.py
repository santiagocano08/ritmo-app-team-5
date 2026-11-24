"""Host-side database connection config for the data-team harness.

Docker services get ``DATABASE_URL`` from compose (host ``db``, port 5432 **inside** the
compose network). A Python process running on the host cannot resolve ``db``, so the DSN is
rebuilt from the same ``POSTGRES_*`` values with host ``127.0.0.1`` and the *published*
``POSTGRES_PORT`` (5432 for the main stack, 55432 for pfsim). Secrets stay in the
git-ignored env files; nothing is hard-coded here.
"""
from __future__ import annotations

import os
import socket
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

# Which git-ignored file holds the credentials for each stack.
ENV_FILES = {"pfsim": HERE / ".pfsim.env", "main": ROOT / ".env"}
DEFAULT_PORTS = {"pfsim": "55432", "main": "5432"}


def load_env(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE reader for the env files (no dependency, same rules as compose)."""
    if not path.exists():
        raise SystemExit(
            f"missing {path}: copy {path.name}.example next to it and set POSTGRES_PASSWORD"
        )
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def _credentials(env: dict[str, str]) -> tuple[str, str, str]:
    """Return (user, password, dbname) from POSTGRES_* or, failing that, from DATABASE_URL."""
    user = env.get("POSTGRES_USER") or ""
    password = env.get("POSTGRES_PASSWORD") or ""
    dbname = env.get("POSTGRES_DB") or ""
    if all((user, password, dbname)):
        return user, password, dbname

    raw = env.get("DATABASE_URL") or ""
    parsed = urlsplit(raw)
    if parsed.scheme not in ("postgresql", "postgres"):
        raise SystemExit(
            "no POSTGRES_USER/PASSWORD/DB and DATABASE_URL is not a postgresql:// DSN"
        )
    return (
        user or parsed.username or "",
        password or parsed.password or "",
        dbname or parsed.path.lstrip("/"),
    )


def make_dsn(env: dict[str, str], port: str, host: str = "127.0.0.1") -> str:
    """Build a DSN a host-side Python process can actually connect with."""
    user, password, dbname = _credentials(env)
    if not all((user, password, dbname)):
        raise SystemExit("incomplete credentials: check POSTGRES_USER/PASSWORD/DB in the env file")
    return (
        f"postgresql://{quote(user, safe='')}:{quote(password, safe='')}"
        f"@{host}:{port}/{quote(dbname, safe='')}"
    )


def dsn_for(target: str = "pfsim", env_file: Path | None = None) -> str:
    """Resolve the DSN for ``pfsim`` or ``main``.

    Precedence: explicit ``SIM_CONSOLE_DSN_<TARGET>`` shell/env-file value, then
    ``SIM_CONSOLE_DSN`` (pfsim only), then the POSTGRES_* values of the target env file.
    """
    if target not in ENV_FILES:
        raise ValueError(f"unknown target {target!r}; use 'pfsim' or 'main'")
    env = load_env(env_file or ENV_FILES[target])

    specific = f"SIM_CONSOLE_DSN_{target.upper()}"
    override = os.environ.get(specific) or env.get(specific)
    if not override and target == "pfsim":
        override = os.environ.get("SIM_CONSOLE_DSN") or env.get("SIM_CONSOLE_DSN")
    if override:
        return override

    port = env.get("POSTGRES_PORT") or DEFAULT_PORTS[target]
    return make_dsn(env, port)


def mask_dsn(dsn: str) -> str:
    """Same DSN with the password replaced by **** (safe to print/log)."""
    try:
        parts = urlsplit(dsn)
    except ValueError:
        return "****"
    if not parts.password:
        return dsn
    host = parts.hostname or ""
    netloc = f"{parts.username or ''}:****@{host}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def port_open(dsn: str, timeout: float = 0.5) -> bool:
    """Cheap TCP check: distinguishes 'stack not running' from 'bad credentials'."""
    parts = urlsplit(dsn)
    with socket.socket() as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((parts.hostname or "127.0.0.1", parts.port or 5432)) == 0


def probe(dsn: str) -> tuple[bool, str]:
    """Return (ok, error). Never raises: this is a diagnostic helper."""
    try:
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return True, ""
    except Exception as exc:  # noqa: BLE001 - diagnostics must surface any failure
        return False, str(exc).strip()
