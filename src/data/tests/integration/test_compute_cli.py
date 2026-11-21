"""T042 — `python -m src.data.pipeline.compute` (contracts/compute-and-refresh.md; FR-004, FR-037, FR-038, FR-040, R5, R6)."""
from __future__ import annotations

import json
from pathlib import Path

import psycopg
import pytest
from jsonschema import Draft202012Validator, FormatChecker

import src.data.pipeline.gold as gold_module
from src.data.pipeline.compute import main
from src.data.pipeline.cycle import ADVISORY_LOCK_KEY
from src.data.tests.fixtures import bronze_builders as bb
from src.data.tests.fixtures.gold_support import count

NOTIFY_SCHEMA = Path(__file__).resolve().parents[4] / "specs" / "002-silver-gold-baselines" / "contracts" / \
    "gold_snapshot_notify.schema.json"
AS_OF = "2026-11-24T22:50:00Z"   # T0 + 3000 s


@pytest.fixture
def cli(gold_conn, module_db_dsn, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", module_db_dsn)
    bb.ingest_all(gold_conn, bb.normal().events)

    def run(*argv: str) -> tuple[int, list[dict]]:
        capsys.readouterr()
        code = main(list(argv))
        lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.strip()]
        return code, lines

    return run


@pytest.fixture
def listener(module_db_dsn):
    with psycopg.connect(module_db_dsn, autocommit=True) as conn:
        conn.execute("LISTEN gold_snapshot")
        yield conn


def _notifications(listener) -> list:
    return list(listener.notifies(timeout=0.5))


def test_as_of_prints_one_json_line_and_exits_zero(cli, gold_conn) -> None:
    code, lines = cli("--as-of", AS_OF, "--no-notify")
    assert code == 0 and len(lines) == 1
    assert set(lines[0]) == {"snapshot_id", "as_of_ts", "max_bronze_id", "status"}
    assert lines[0]["as_of_ts"] == AS_OF and lines[0]["status"] == "live"
    assert lines[0]["max_bronze_id"] == gold_conn.execute("SELECT max(id) FROM bronze.events").fetchone()[0]
    assert count(gold_conn, "gold.snapshots") == 1


def test_replay_produces_one_snapshot_per_step(cli, gold_conn) -> None:
    code, lines = cli("--from", "2026-11-24T22:49:50Z", "--to", AS_OF, "--step", "5", "--no-notify")
    assert code == 0
    assert [ln["as_of_ts"] for ln in lines] == ["2026-11-24T22:49:50Z", "2026-11-24T22:49:55Z", AS_OF]
    assert count(gold_conn, "gold.snapshots") == 3


def test_replay_step_defaults_to_five_seconds(cli) -> None:
    _, lines = cli("--from", "2026-11-24T22:49:55Z", "--to", AS_OF, "--no-notify")
    assert len(lines) == 2


def test_no_notify_sends_nothing(cli, listener) -> None:
    cli("--as-of", AS_OF, "--no-notify")
    assert _notifications(listener) == []


def test_one_valid_notification_per_new_snapshot_and_none_for_a_noop(cli, listener, module_db_dsn) -> None:
    validator = Draft202012Validator(json.loads(NOTIFY_SCHEMA.read_text(encoding="utf-8")),
                                     format_checker=FormatChecker())
    _, lines = cli("--as-of", AS_OF)
    got = _notifications(listener)
    assert len(got) == 1 and got[0].channel == "gold_snapshot"
    payload = json.loads(got[0].payload)
    assert list(validator.iter_errors(payload)) == [] and payload["snapshot_id"] == lines[0]["snapshot_id"]
    with psycopg.connect(module_db_dsn) as reader:    # readable by the time it is delivered
        assert reader.execute("SELECT count(*) FROM gold.corridor_now WHERE snapshot_id = %s",
                              (payload["snapshot_id"],)).fetchone()[0] == 1

    code, again = cli("--as-of", AS_OF)               # same inputs: no new snapshot, no notification
    assert code == 0 and again[0]["snapshot_id"] == payload["snapshot_id"]
    assert _notifications(listener) == []


def test_a_rolled_back_cycle_exits_nonzero_and_notifies_nothing(cli, listener, gold_conn, monkeypatch, capsys) -> None:
    def failing(*args, **kwargs):
        raise RuntimeError("boom /secret/path")

    monkeypatch.setattr(gold_module, "build_snapshot", failing)
    capsys.readouterr()
    code = main(["--as-of", AS_OF])
    err = capsys.readouterr().err
    assert code != 0
    assert "Traceback" not in err and "boom" not in err and "/secret/path" not in err
    assert json.loads(err.strip().splitlines()[-1])["correlation_id"]
    assert count(gold_conn, "gold.snapshots") == 0
    assert _notifications(listener) == []


def test_replay_stops_at_the_first_failed_cycle(cli, gold_conn, monkeypatch) -> None:
    calls = {"n": 0}
    original = gold_module.build_snapshot

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("second cycle fails")
        return original(*args, **kwargs)

    monkeypatch.setattr(gold_module, "build_snapshot", flaky)
    code, lines = cli("--from", "2026-11-24T22:49:50Z", "--to", AS_OF, "--no-notify")
    assert code != 0 and len(lines) == 1
    assert count(gold_conn, "gold.snapshots") == 1


def test_a_cycle_is_skipped_while_the_advisory_lock_is_held(cli, gold_conn, module_db_dsn, listener) -> None:
    with psycopg.connect(module_db_dsn) as holder:
        holder.execute("SELECT pg_advisory_xact_lock(%s)", (ADVISORY_LOCK_KEY,))
        code, lines = cli("--as-of", AS_OF)
        holder.rollback()
    assert code == 0 and lines == []
    assert count(gold_conn, "gold.snapshots") == 0
    assert _notifications(listener) == []


def test_the_cli_ignores_refresh_clock(cli, monkeypatch) -> None:
    monkeypatch.setenv("REFRESH_CLOCK", "wall")
    _, lines = cli("--as-of", AS_OF, "--no-notify")
    assert lines[0]["as_of_ts"] == AS_OF


def test_arguments_are_validated(cli, capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code != 0
    with pytest.raises(SystemExit):
        main(["--as-of", "not-a-time"])
    with pytest.raises(SystemExit):
        main(["--from", AS_OF, "--to", "2026-11-24T22:00:00Z"])
    with pytest.raises(SystemExit):
        main(["--from", AS_OF, "--to", AS_OF, "--step", "0"])
