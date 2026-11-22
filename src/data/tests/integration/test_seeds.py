"""T039 support — seed recommendations: loader validates, DELETE + INSERT is idempotent (004 FR-018, FR-019)."""
from __future__ import annotations

import json
from pathlib import Path

import psycopg
import pytest

from src.data import seeds
from src.data.pipeline.seeds import load_seeds

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios" / "seed_recommendations.json"
ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def conn(module_db_dsn):
    with psycopg.connect(module_db_dsn) as c:
        yield c


def dump(conn) -> list:
    return conn.execute("SELECT rec_id::text, doc FROM config.seed_recommendation ORDER BY rec_id").fetchall()


def test_loading_twice_leaves_the_table_unchanged(conn) -> None:
    load_seeds(conn, FIXTURE)
    conn.commit()
    first = dump(conn)
    load_seeds(conn, FIXTURE)
    conn.commit()
    assert dump(conn) == first and len(first) == 5
    assert all(doc["rec_id"] == rec for rec, doc in first)


def test_loading_a_smaller_file_replaces_the_rows(conn, tmp_path) -> None:
    one = tmp_path / "one.json"
    one.write_text(json.dumps(json.loads(FIXTURE.read_text())[:1]))
    load_seeds(conn, one)
    conn.commit()
    assert len(dump(conn)) == 1
    load_seeds(conn, FIXTURE)
    conn.commit()


def test_invalid_entry_is_rejected_and_nothing_is_replaced(conn, tmp_path) -> None:
    load_seeds(conn, FIXTURE)
    conn.commit()
    before = dump(conn)
    bad = json.loads(FIXTURE.read_text())
    bad[0]["unexpected"] = 1
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(seeds.SeedError):
        load_seeds(conn, path)
    conn.rollback()
    assert dump(conn) == before


def test_missing_file_is_a_clear_error(tmp_path) -> None:
    with pytest.raises(seeds.SeedError):
        seeds.load_recommendations(tmp_path / "nope.json")


def test_default_seed_file_is_valid_and_has_the_demo_hold() -> None:
    entries = seeds.load_recommendations(None)
    assert any(e.action.type == "hold" and e.action.bus_id == "B-103" and e.action.duration_s == 90 for e in entries)
    assert (ROOT / "src" / "data" / "seeds" / "recommendations.json").exists()


def test_seed_path_comes_from_the_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SEED_RECOMMENDATIONS_PATH", str(FIXTURE))
    assert len(seeds.load_recommendations(None)) == 5
