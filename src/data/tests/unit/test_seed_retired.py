"""006 T030 — the seed is gone (FR-025, SC-009; research R4).

The strings are built from parts so that this file does not match its own search.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
TOKENS = ("seed" + "_recommendation", "recommendations" + ".json", "SEED_RECOMMENDATIONS" + "_PATH")
SKIP_DIRS = {".git", ".venv", "specs", "docs", "node_modules", ".kiro", ".specify", "__pycache__", ".pytest_cache"}


def _files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                             capture_output=True, text=True)
        names = out.stdout.splitlines() if out.returncode == 0 else []
    except FileNotFoundError:  # no git binary (the CI image)
        names = []
    if not names:  # walk the tree that is mounted
        names = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file()]
    return [ROOT / n for n in names if not (set(Path(n).parts) & SKIP_DIRS) and (ROOT / n).is_file()]


def test_no_file_outside_specs_and_docs_mentions_the_seed() -> None:
    hits = []
    for path in _files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits += [f"{path.relative_to(ROOT)}: {t}" for t in TOKENS if t in text]
    assert hits == []


def test_seed_modules_and_files_do_not_exist() -> None:
    assert not (ROOT / "src" / "data" / "seeds").exists()
    assert not (ROOT / "src" / "data" / "pipeline" / "seeds.py").exists()
    assert not (ROOT / "src" / "data" / "tests" / "fixtures" / "scenarios" / ("seed_" + "recommendations" + ".json")).exists()


def test_config_has_no_seed_path_getter() -> None:
    from src.pulsoflota import config

    assert not hasattr(config, "get_seed_" + "recommendations_path")
