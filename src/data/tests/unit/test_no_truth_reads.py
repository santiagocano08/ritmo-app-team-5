"""T009 — static guard: the pipeline never reads the scenario truth (004 FR-010, SC-006).

Green by design: it can only fail when someone wires the truth into the pipeline, the ingestion,
the refresh loop, the rules or the API package.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
CODE_DIRS = [ROOT / "src" / "data" / n for n in ("rules", "pipeline", "refresh", "ingestion")]
CODE_DIRS += [ROOT / "src" / "pulsoflota", ROOT / "src" / "api"]
SQL_DIRS = [ROOT / "src" / "data" / "db", ROOT / "src" / "data" / "rules" / "sql"]

FORBIDDEN = re.compile(r"simulator\.scenarios|scenario_truth|SIM_TRUTH_PATH|TruthSink", re.IGNORECASE)
TRUTH_TABLE = re.compile(r"\btruth\b", re.IGNORECASE)


def _files(dirs, suffixes):
    return sorted(p for d in dirs for p in d.rglob("*") if p.suffix in suffixes and "__pycache__" not in p.parts)


def test_scanned_directories_exist() -> None:
    for d in CODE_DIRS + SQL_DIRS:
        assert d.is_dir(), d


def test_no_pipeline_module_touches_the_truth() -> None:
    config = ROOT / "src" / "pulsoflota" / "config.py"
    offenders = []
    for p in _files(CODE_DIRS, {".py"}):
        text = p.read_text(encoding="utf-8")
        if p == config:
            # the simulator's own settings live in the shared config module; only the getter may name it
            text = re.sub(r"(?s)def get_sim_truth_path\(.*?(?=\ndef |\Z)", "", text)
        if FORBIDDEN.search(text):
            offenders.append(str(p.relative_to(ROOT)))
    assert offenders == []


def test_no_sql_or_ddl_mentions_a_truth_table() -> None:
    offenders = [str(p.relative_to(ROOT)) for p in _files(SQL_DIRS, {".sql"})
                 if TRUTH_TABLE.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
