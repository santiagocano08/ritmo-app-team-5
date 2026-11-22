"""T010 — rules version, package skeletons and pytest markers (FR-006, FR-017)."""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]


def test_rules_version() -> None:
    from src.data.rules import RULES_VERSION

    assert RULES_VERSION == "1.4.0"


@pytest.mark.parametrize("name", ["src.data.rules", "src.data.pipeline", "src.data.refresh"])
def test_packages_importable(name: str) -> None:
    importlib.import_module(name)


def test_slow_and_live_markers_registered(tmp_path: Path) -> None:
    # The probe lives in tmp_path: in the compose `tests` service the tests/ mount is read-only.
    probe = tmp_path / "test_marker_probe.py"
    probe.write_text(
        "import pytest\n\n@pytest.mark.slow\ndef test_a(): pass\n\n@pytest.mark.live\ndef test_b(): pass\n"
    )
    out = subprocess.run(
        [sys.executable, "-m", "pytest", str(probe), "-c", str(ROOT / "pyproject.toml"),
         "--rootdir", str(ROOT), "--strict-markers", "--no-cov", "-q", "-p", "no:cacheprovider"],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert out.returncode == 0, out.stdout + out.stderr
