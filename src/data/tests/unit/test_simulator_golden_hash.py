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

# Re-pinned 2026-11-23 for the 7 + 4 fleet and the 420 s planned headway (issue #42, contract v0.5). The values of
# the 5 + 2 fleet at 600 s were 8bae0e52… (seed 42) and 27a8206e… (seed 7).
GOLDEN = {
    42: "a65846b0aa5c0dbf4699ae55661dd09479550f2fcf14d148fdd6d7d8760327f4",
    7: "925ca659b5217a9cb3d898fe4b4fc8fd24562a9d4efa09677349e59fbc7223df",
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
    assert data.count(b"\n") == 5358
    assert len(data) == 2_004_758


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


def test_holds_on_with_an_empty_bronze_is_the_baseline(module_db_dsn, monkeypatch: pytest.MonkeyPatch) -> None:
    """T027: `--holds on` against an empty bronze leaves the stream byte-identical (004 FR-001, FR-017, SC-001)."""
    import psycopg

    with psycopg.connect(module_db_dsn) as conn:
        conn.execute("TRUNCATE bronze.events, bronze.rejections RESTART IDENTITY")
        conn.commit()
    monkeypatch.setenv("DATABASE_URL", module_db_dsn)
    for seed in (42, 7):
        assert hashlib.sha256(_stream(seed, ["--holds", "on"])).hexdigest() == GOLDEN[seed]
    monkeypatch.setenv("SIM_HOLDS", "on")
    assert hashlib.sha256(_stream(42)).hexdigest() == GOLDEN[42]


def test_holds_on_with_the_database_down_is_the_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://nobody:x@127.0.0.1:1/none")
    assert hashlib.sha256(_stream(42, ["--holds", "on"])).hexdigest() == GOLDEN[42]


def test_holds_off_does_not_need_a_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert hashlib.sha256(_stream(42, ["--holds", "off"])).hexdigest() == GOLDEN[42]
