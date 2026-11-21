"""T040 - the 2026-11-18 drill evidence is kept in the repo, translated header and labels only."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs" / "ops" / "drill-baseline"
ORIGINAL = ROOT / ".drill-input" / "metricas.csv"
HEADER = "t_s,events,max_event_ts,ingestion_lag_s,duplicates,other_rejections,ingestion,api,db"
FILES = ("metrics.csv", "events.log", "rejections.txt", "restarts.txt", "README.md")
SPANISH = ("INICIO", "inyectada", "fin", "observacion", "LIMPIO", "simulacro", "tiempo", "rechazos", "metricas", "eventos")


def _text(name: str) -> str:
    path = BASE / name
    assert path.is_file(), f"baseline file not found: {path}"
    return path.read_text(encoding="utf-8")


def test_baseline_folder_has_the_five_files():
    for name in FILES:
        assert (BASE / name).is_file(), name


def test_metrics_header_and_rows():
    lines = _text("metrics.csv").splitlines()
    assert lines[0] == HEADER
    data = lines[1:]
    assert len(data) == 130
    assert data[0] == "7,0,,-1,0,0,running,running,running"
    assert data[-1] == "316,525,22:08:20,209,961,0,running,running,running"
    assert data[-1].split(",")[1] == "525"


@pytest.mark.skipif(not ORIGINAL.exists(), reason="local .drill-input/ not present")
def test_data_rows_are_byte_for_byte_the_original():
    original = ORIGINAL.read_bytes().split(b"\n", 1)[1]
    copy = (BASE / "metrics.csv").read_bytes().split(b"\n", 1)[1]
    assert copy == original


def test_rejections_and_events_and_restarts():
    assert _text("rejections.txt").strip() == "duplicate_event,971"
    events = _text("events.log").splitlines()
    expected = [
        ("0s 03:21:19Z", "START"),
        ("51s 03:22:10Z", "F1 injected: docker compose stop api"),
        ("82s 03:22:41Z", "F1 end: docker compose start api"),
        ("107s 03:23:06Z", "F2 injected: docker compose stop db"),
        ("138s 03:23:37Z", "F2 end: docker compose start db"),
        ("228s 03:25:07Z", "F3 injected: kill -9"),
        ("318s 03:26:37Z", "END observation"),
        ("329s 03:26:48Z", "CLEANED"),
    ]
    assert len(events) == 8
    for line, (stamp, label) in zip(events, expected):
        assert line.startswith(stamp) and label in line, line
    restarts = _text("restarts.txt").strip().splitlines()
    assert len(restarts) == 3
    assert [ln.rsplit("restarts=", 1)[1] for ln in restarts] == ["0", "0", "3"]


def test_no_spanish_label_remains():
    for name in ("metrics.csv", "events.log", "rejections.txt", "restarts.txt"):
        text = _text(name)
        for word in SPANISH:
            assert not re.search(rf"\b{word}\b", text, re.IGNORECASE), f"{word} in {name}"
