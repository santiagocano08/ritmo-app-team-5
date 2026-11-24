"""Check DB connectivity from the host for both stacks.

    uv run --frozen --extra dev python -m src.data.sim_console.check_db

Prints the resolved DSN with the password masked, whether the port is listening and a real
SELECT 1. Use it when the simulation console shows the database as disconnected.
"""
from __future__ import annotations

from src.data.sim_console.db_config import ENV_FILES, dsn_for, mask_dsn, port_open, probe


def check(target: str) -> bool:
    print(f"[{target}] env file: {ENV_FILES[target]}")
    try:
        dsn = dsn_for(target)
    except (SystemExit, ValueError) as exc:
        print(f"  config: FAIL ({exc})")
        return False
    print(f"  dsn:    {mask_dsn(dsn)}")
    listening = port_open(dsn)
    print(f"  port:   {'open' if listening else 'CLOSED (is that stack running?)'}")
    ok, error = probe(dsn)
    print(f"  select: {'OK' if ok else 'FAIL'}")
    if not ok:
        print(f"  detail: {error}")
        if not listening:
            print(
                "  hint: for pfsim, click a demo button in the console first (it starts the pfsim db "
                "on POSTGRES_PORT from .pfsim.env); for main, run `docker compose up -d db`."
            )
        else:
            print("  hint: check POSTGRES_PASSWORD in the env file against the running container.")
    return ok


def main() -> None:
    results = {target: check(target) for target in ("pfsim", "main")}
    print("\nsummary: " + ", ".join(f"{k}={'OK' if v else 'FAIL'}" for k, v in results.items()))


if __name__ == "__main__":
    main()
