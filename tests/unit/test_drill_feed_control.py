"""T029 — scripts/drill/feed_control.py freezes and resumes only the simulator (exact-argv rule)."""
from __future__ import annotations

import importlib.util
import os
import signal
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "drill" / "feed_control.py"


def _load():
    assert SCRIPT.exists(), "scripts/drill/feed_control.py missing"
    spec = importlib.util.spec_from_file_location("feed_control", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _proc(root: Path, pid: int, *argv: str) -> None:
    d = root / str(pid)
    d.mkdir(parents=True)
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    _proc(tmp_path, 1, "sh", "-c",
          "python -m src.data.simulator.main --seed 42 | python -m src.data.ingestion.run")
    _proc(tmp_path, 7, "python", "-m", "src.data.simulator.main", "--seed", "42", "--duration", "3600")
    _proc(tmp_path, 8, "python", "-m", "src.data.ingestion.run")
    _proc(tmp_path, 9, "python", "-", "stop")
    return tmp_path


def test_selects_only_the_simulator(tree: Path) -> None:
    mod = _load()
    assert mod.find_pids(proc_root=tree, own_pid=9) == [7]


def test_exact_argv_not_substring(tmp_path: Path) -> None:
    mod = _load()
    _proc(tmp_path, 1, "sh", "-c", "python -m src.data.simulator.main | cat")
    _proc(tmp_path, 5, "python", "-m", "src.data.simulator.main.extra")
    _proc(tmp_path, 6, "grep", "src.data.simulator.main")
    assert mod.find_pids(proc_root=tmp_path, own_pid=99) == []


def test_never_selects_pid_1_or_itself(tmp_path: Path) -> None:
    mod = _load()
    _proc(tmp_path, 1, "python", "-m", "src.data.simulator.main")
    _proc(tmp_path, 9, "python", "-m", "src.data.simulator.main")
    assert mod.find_pids(proc_root=tmp_path, own_pid=9) == []


def test_stop_sends_sigstop_and_resume_sigcont(tree: Path) -> None:
    mod = _load()
    sent: list[tuple[int, int]] = []
    assert mod.run("stop", proc_root=tree, own_pid=9, kill=lambda p, s: sent.append((p, s))) == 0
    assert mod.run("resume", proc_root=tree, own_pid=9, kill=lambda p, s: sent.append((p, s))) == 0
    assert sent == [(7, signal.SIGSTOP), (7, signal.SIGCONT)]


def test_no_match_is_a_clear_non_zero_exit(tmp_path: Path, capsys) -> None:
    mod = _load()
    _proc(tmp_path, 1, "sh", "-c", "sleep 1")
    assert mod.run("stop", proc_root=tmp_path, own_pid=os.getpid(), kill=lambda p, s: None) != 0
    assert "simulator" in capsys.readouterr().err.lower()


def test_unknown_action_is_rejected(tree: Path) -> None:
    mod = _load()
    assert mod.run("explode", proc_root=tree, own_pid=9, kill=lambda p, s: None) != 0
