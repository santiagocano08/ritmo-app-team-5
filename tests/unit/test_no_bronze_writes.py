"""T025 — static guard: nothing in the rules, pipeline or refresh code writes to bronze (FR-002).

Scans SQL files and Python source (including SQL held in strings) for INSERT / UPDATE / DELETE /
TRUNCATE statements that target the `bronze.` schema.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCANNED = [ROOT / "src" / "rules", ROOT / "src" / "pipeline", ROOT / "src" / "refresh"]

WRITE = re.compile(
    r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|TRUNCATE(?:\s+TABLE)?(?:\s+ONLY)?)\s+(?:\"?bronze\"?\s*\.)",
    re.IGNORECASE,
)


def _files() -> list[Path]:
    return sorted(p for d in SCANNED for p in d.rglob("*") if p.suffix in {".py", ".sql"})


@pytest.mark.parametrize("statement", [
    "INSERT INTO bronze.events (id) VALUES (1)",
    "insert  into  bronze.rejections SELECT 1",
    "UPDATE bronze.events SET payload = '{}'",
    "DELETE FROM bronze.events",
    "TRUNCATE bronze.events",
    "TRUNCATE TABLE bronze.rejections",
    'DELETE FROM "bronze".events',
])
def test_detector_flags_every_write_form(statement: str) -> None:
    assert WRITE.search(statement)


@pytest.mark.parametrize("statement", [
    "SELECT * FROM bronze.events",
    "INSERT INTO silver.position_history SELECT id FROM bronze.events",
    "DELETE FROM silver.stop_visits",
    "-- reads bronze.events only",
])
def test_detector_ignores_reads_and_other_schemas(statement: str) -> None:
    assert not WRITE.search(statement)


def test_silver_sql_files_are_part_of_the_scan() -> None:
    names = {p.name for p in _files() if p.suffix == ".sql"}
    assert {"silver_position_history.sql", "silver_incidents.sql", "silver_bus_current_state.sql",
            "silver_stop_visits.sql", "silver_segment_traversals.sql"} <= names
    assert any(p.name == "silver.py" for p in _files())


def test_no_write_statement_targets_bronze() -> None:
    offenders = [f"{p.relative_to(ROOT)}: {m.group(0)}"
                 for p in _files() for m in WRITE.finditer(p.read_text(encoding="utf-8"))]
    assert offenders == []
