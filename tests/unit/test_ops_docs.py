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


# ---------------------------------------------------------------------------
# Phase 4 (T039): post-mortem, runbook, SLI/SLO proposal and drill rerun table.
# ---------------------------------------------------------------------------

import csv
import re

import pytest

BASELINE = OPS / "drill-baseline"
F3_MARK_S = 228  # F3 injected at 228 s in docs/ops/drill-baseline/events.log


def read_samples(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def lag_after_f2(rows: list[dict[str, str]], f3_mark_s: int) -> int:
    """`ingestion_lag_s` of the last sample strictly before the F3 mark (same rule for both columns)."""
    before = [r for r in rows if r["t_s"].isdigit() and int(r["t_s"]) < f3_mark_s]
    return int(before[-1]["ingestion_lag_s"])


def f3_lag(rows: list[dict[str, str]]) -> int:
    """`ingestion_lag_s` of the last sample of the observation window."""
    return int(rows[-1]["ingestion_lag_s"])


def f3_mark_from_events(path: Path) -> int:
    for line in path.read_text(encoding="utf-8").splitlines():
        if "F3 injected" in line:
            return int(line.split("s ", 1)[0])
    raise AssertionError("F3 mark not found")


def test_baseline_lag_numbers_follow_the_fixed_rule():
    rows = read_samples(BASELINE / "metrics.csv")
    mark = f3_mark_from_events(BASELINE / "events.log")
    assert mark == F3_MARK_S
    assert lag_after_f2(rows, mark) == 120
    assert f3_lag(rows) == 209


def test_post_mortem_sections_and_numbers():
    text = _read("post-mortem-2026-11-18-drill.md")
    lowered = text.lower()
    for section in ("summary", "timeline", "impact", "root cause", "what went well", "actions", "lessons"):
        assert re.search(rf"^#+ .*{section}", lowered, re.MULTILINE), f"section missing: {section}"
    for number in ("31 s", "120 s", "209 s", "971", "65 %", "525 of 525"):
        assert number in text, f"number missing: {number}"
    assert "125 s" in text and "204 s" in text and "off" in lowered
    for story in ("US1", "US2", "US3"):
        assert story in text
    assert "@" not in text  # blameless: no individual is named or mentioned


def test_runbook_covers_the_recovery_cases():
    text = _read("runbook-ingestion-refresh-unhealthy.md")
    lowered = text.lower()
    for needle in (
        "docker compose ps",
        "ops.ingestion_health",
        "database outage",
        "stopped feed",
        "crashing ingestion",
        "stalled `refresh`",
        "006_ops.sql",
        "escalat",
    ):
        assert needle in lowered, f"runbook missing: {needle}"


def test_sli_slo_doc_is_marked_as_proposal():
    text = _read("sli-slo-proposal.md")
    assert "PROPOSAL" in text.splitlines()[0] or "PROPOSAL" in "\n".join(text.splitlines()[:3])
    lowered = text.lower()
    assert "sli" in lowered and "slo" in lowered and "error budget" in lowered
    assert "403" in text and "minutes" in lowered
    assert "constitutional-amendment" in text


DRILL_ROWS = (
    "Ingestion survives F2",
    "Lag after F2",
    "F3 lag",
    "Duplicates counted as rejections",
    "Real rejection rate",
    "`unhealthy` transitions",
    "Bronze integrity",
)


def test_drill_rerun_table_is_complete_and_matches_baseline():
    text = _read("drill-rerun.md")
    for row in DRILL_ROWS:
        assert row in text, f"row missing: {row}"
    assert "TBD" not in text
    assert "2 s" in text and "45" in text and "90" in text
    assert "t_s,events,max_event_ts,ingestion_lag_s,duplicates,other_rejections,ingestion,api,db" in text
    assert "strictly before the F3 mark" in text and "last sample of the observation window" in text
    assert "reported 125 s and 204 s" in text or "quoted 125 s and 204 s" in text
    rows = read_samples(BASELINE / "metrics.csv")
    after_f2, f3 = lag_after_f2(rows, F3_MARK_S), f3_lag(rows)
    table = [ln for ln in text.splitlines() if ln.startswith("|")]
    lag_f2_row = next(ln for ln in table if "Lag after F2" in ln)
    lag_f3_row = next(ln for ln in table if "F3 lag" in ln)
    assert f"{after_f2} s" in lag_f2_row.split("|")[2]
    assert f"{f3} s" in lag_f3_row.split("|")[2]
