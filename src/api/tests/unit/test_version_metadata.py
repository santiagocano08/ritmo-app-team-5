"""Unit tests for the build-metadata reader and read-contract constant (US-08).

Covers the source-revision reader (APP_REVISION env var with an `unknown` fallback,
FR-004/SC-003/R1) and the fixed read-contract-version constant (FR-003/R3).
"""
from __future__ import annotations

import pytest

from src.pulsoflota.config import READ_CONTRACT_VERSION, get_source_revision


def test_source_revision_returns_env_value_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_REVISION", "a1b2c3d")
    assert get_source_revision() == "a1b2c3d"


def test_source_revision_falls_back_to_unknown_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_REVISION", raising=False)
    assert get_source_revision() == "unknown"


def test_source_revision_falls_back_to_unknown_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_REVISION", "")
    assert get_source_revision() == "unknown"


def test_read_contract_version_constant_is_1_0_0() -> None:
    assert READ_CONTRACT_VERSION == "1.0.0"
