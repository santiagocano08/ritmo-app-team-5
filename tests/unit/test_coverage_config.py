"""The coverage omit list is closed (feature 003, CI coverage finding).

Two offline ETL modules are omitted because their tests need the git-ignored `data/raw/` and
skip in CI. The data simulation console (`src/data/sim_console/`, story 006) is a local test harness
that drives docker compose and a browser UI, so it is omitted too. This test pins the whole list so
nobody widens it silently, and the gate stays 80 %.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_omit_list_is_exactly_the_agreed_entries() -> None:
    omit = PYPROJECT["tool"]["coverage"]["run"]["omit"]
    assert sorted(omit) == sorted(
        [
            "src/pulsoflota/models/*",
            "src/data/tests/*",
            "src/api/tests/*",
            "src/data/reference/build.py",
            "src/data/reference/sources.py",
            "src/data/sim_console/*",
        ]
    )


def test_offline_etl_modules_exist_and_stay_tested() -> None:
    assert (ROOT / "src/data/reference/build.py").is_file()
    assert (ROOT / "src/data/reference/sources.py").is_file()


def test_coverage_floor_is_not_lowered() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "--cov-fail-under=80" in compose
