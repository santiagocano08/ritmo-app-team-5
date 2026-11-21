"""Freeze or resume the simulator inside the ingestion container (stdlib only).

Usage (from the host): docker compose exec -T ingestion python - stop < scripts/drill/feed_control.py
Only a process whose argv after the interpreter is exactly `-m src.data.simulator.main` (plus its own
options) is selected: never PID 1, never this helper, never a substring match on a shell line.
"""
from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

TARGET = ["-m", "src.data.simulator.main"]
ACTIONS = {"stop": signal.SIGSTOP, "resume": signal.SIGCONT}


def find_pids(proc_root: Path = Path("/proc"), own_pid: int | None = None) -> list[int]:
    own = os.getpid() if own_pid is None else own_pid
    found: list[int] = []
    for entry in Path(proc_root).iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid in (1, own):
            continue
        try:
            argv = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        args = [a.decode(errors="replace") for a in argv if a]
        if len(args) >= 3 and "python" in os.path.basename(args[0]) and args[1:3] == TARGET:
            found.append(pid)
    return sorted(found)


def run(action: str, proc_root: Path = Path("/proc"), own_pid: int | None = None, kill=os.kill) -> int:
    if action not in ACTIONS:
        print("usage: feed_control.py stop|resume", file=sys.stderr)
        return 2
    pids = find_pids(proc_root, own_pid)
    if not pids:
        print("no simulator process found (python -m src.data.simulator.main)", file=sys.stderr)
        return 1
    for pid in pids:
        kill(pid, ACTIONS[action])
    print(f"{action}: {len(pids)} simulator process(es)")
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else ""))
