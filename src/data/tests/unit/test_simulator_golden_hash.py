"""T002 — golden hashes of the base simulator stream (004 FR-001, SC-001).

With no scenario configured the CLI output must stay byte-identical to the 003 baseline.
Written and run green on the untouched engine, before any engine edit.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest

from src.data.simulator.main import main

GOLDEN = {
    42: "51a5e9b3063667320a6e66cab6293f84197822378783724dd664b6f6865d39e1",
    7: "6bd20707cf9aaccc852b6f8431e1129b759321b69f5cd06e5697c1638e0ab132",
}


def _stream(seed: int, extra: list[str] | None = None) -> bytes:
    buf = io.StringIO()
    main(["--seed", str(seed), "--duration", "3600", *(extra or [])], out=buf)
    return buf.getvalue().encode()


@pytest.fixture(autouse=True)
def _no_scenario_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("SIM_SCENARIO_FILE", "SIM_TRUTH_PATH", "SIM_HOLDS"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("seed", [42, 7])
def test_base_stream_matches_golden_hash(seed: int) -> None:
    assert hashlib.sha256(_stream(seed)).hexdigest() == GOLDEN[seed]


def test_seed_42_shape() -> None:
    data = _stream(42)
    assert data.count(b"\n") == 3851
    assert len(data) == 1_439_431


EMPTY = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios" / "empty.json"


@pytest.mark.parametrize("seed", [42, 7])
def test_empty_scenario_file_is_the_baseline(seed: int) -> None:
    """T019: `[]` means no scenario (004 FR-004, AC1)."""
    assert hashlib.sha256(_stream(seed, ["--scenario-file", str(EMPTY)])).hexdigest() == GOLDEN[seed]


def test_empty_variable_is_the_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIM_SCENARIO_FILE", "")
    assert hashlib.sha256(_stream(42)).hexdigest() == GOLDEN[42]
    monkeypatch.setenv("SIM_SCENARIO_FILE", str(EMPTY))
    assert hashlib.sha256(_stream(42)).hexdigest() == GOLDEN[42]


def test_scenario_run_is_reproducible_and_differs_from_the_baseline(tmp_path: Path) -> None:
    fixture = EMPTY.with_name("c5_demo.json")
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    first = _stream(42, ["--scenario-file", str(fixture), "--truth-path", str(a)])
    second = _stream(42, ["--scenario-file", str(fixture), "--truth-path", str(b)])
    assert first == second and a.read_bytes() == b.read_bytes()
    assert hashlib.sha256(first).hexdigest() != GOLDEN[42]
