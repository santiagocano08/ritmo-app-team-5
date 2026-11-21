"""Operations documents (feature 003). Checks grow phase by phase."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "docs" / "ops"


def _read(name: str) -> str:
    path = OPS / name
    assert path.is_file(), f"doc not found: {path}"
    return path.read_text(encoding="utf-8")


def test_branch_protection_doc_names_checks_and_path():
    text = _read("ci-branch-protection.md")
    for check in ("`test`", "`contract`", "`build`"):
        assert check in text
    assert "Settings" in text and "Branches" in text and "Rulesets" in text
    assert "require status checks" in text.lower()
    assert "manual" in text.lower() and "administrator" in text.lower()
    lowered = text.lower()
    assert "renam" in lowered and "protection" in lowered
