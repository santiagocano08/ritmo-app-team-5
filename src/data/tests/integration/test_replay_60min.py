"""T056 — SC-001 on a 60-minute replay: every stored object validates against its schema (SC-001, SC-008).

Seeded simulator run (seed 42, 3,600 s) goes through the real ingestion boundary, then
`python -m src.data.pipeline.compute --from --to --step` writes one snapshot per step without
notifications. Slow: marked `slow`.
"""
from __future__ import annotations

import json

import pytest

from src.data.ingestion.bronze import ingest
from src.data.pipeline.compute import main
from src.data.simulator.engine import run
from src.data.tests.fixtures.gold_support import validator

REPLAY_STEP_S = 5          # CUT-2: change to 60 and record the reduced density in verification.md
SEED, DURATION_S = 42, 3600
FROM = "2026-11-24T22:00:05Z"
TO = "2026-11-24T23:00:00Z"

pytestmark = pytest.mark.slow


def test_replay_of_one_simulated_hour_validates_every_object(gold_conn, module_db_dsn, monkeypatch, capsys) -> None:
    for event in run(SEED, DURATION_S):
        assert ingest(gold_conn, event).accepted
    gold_conn.commit()

    monkeypatch.setenv("DATABASE_URL", module_db_dsn)
    capsys.readouterr()
    code = main(["--from", FROM, "--to", TO, "--step", str(REPLAY_STEP_S), "--no-notify"])
    lines = [json.loads(ln) for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert code == 0
    expected = DURATION_S // REPLAY_STEP_S
    assert len(lines) == expected, (len(lines), expected)

    total = 0
    for table in ("source_status", "corridor_now", "decision_inputs"):
        validate = validator(table)
        rows = gold_conn.execute(f"SELECT snapshot_id, doc, rules_version, max_bronze_id FROM gold.{table}").fetchall()  # noqa: S608
        assert len(rows) == expected, table
        for snapshot_id, doc, rules_version, max_id in rows:
            errors = list(validate.iter_errors(doc))
            assert not errors, (table, snapshot_id, errors[:2])
            assert doc["snapshot_id"] == str(snapshot_id)
            assert rules_version and max_id is not None
            total += 1
    assert total == 3 * expected

    # decision_inputs repeats buses and summary of corridor_now in every snapshot.
    mismatches = gold_conn.execute(
        "SELECT count(*) FROM gold.decision_inputs d JOIN gold.corridor_now c USING (snapshot_id) "
        "WHERE d.doc->'buses' IS DISTINCT FROM c.doc->'buses' OR d.doc->'summary' IS DISTINCT FROM c.doc->'summary'"
    ).fetchone()[0]
    assert mismatches == 0
