"""T014 — bronze is insert-only.

1. Static guard: the ingestion code issues no UPDATE/DELETE/TRUNCATE on bronze.
2. Runtime: re-ingesting the same batch leaves bronze.events row count and
   checksum unchanged (duplicates only add rejections).
"""
from __future__ import annotations

import json
import pathlib
import re
import uuid

import pytest

from src.ingestion.bronze import ingest

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "contracts" / "turn1-events" / "examples" / "valid"


def test_ingestion_code_never_updates_or_deletes_bronze() -> None:
    forbidden = re.compile(r"\b(UPDATE|DELETE|TRUNCATE)\b", re.IGNORECASE)
    for path in (ROOT / "src" / "ingestion").glob("*.py"):
        code = "\n".join(l for l in path.read_text().splitlines() if not l.strip().startswith("#"))
        assert not forbidden.search(code), f"{path.name} contains UPDATE/DELETE/TRUNCATE"


@pytest.fixture()
def conn(db_dsn):
    import psycopg
    with psycopg.connect(db_dsn, autocommit=True) as c:
        yield c


def _snapshot(conn, ids: list[str]) -> tuple[int, str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*), coalesce(md5(string_agg(id::text || event_id::text || payload::text, ',' ORDER BY id)), '') "
            "FROM bronze.events WHERE event_id = ANY(%s::uuid[])",
            (ids,),
        )
        return cur.fetchone()


def test_reingest_does_not_change_bronze(conn) -> None:
    batch = []
    for path in sorted(EXAMPLES.glob("*.json")):
        msg = json.loads(path.read_text())
        msg["event_id"] = str(uuid.uuid4())
        batch.append(msg)
    ids = [m["event_id"] for m in batch]
    for m in batch:
        assert ingest(conn, m).accepted
    first = _snapshot(conn, ids)
    for m in batch:
        assert ingest(conn, dict(m)).reason == "duplicate_event"
    assert _snapshot(conn, ids) == first
    assert first[0] == len(batch)
