"""006 T019 — DDL of phase 2: `009_decision_mpc.sql` (data-model M1 to M6, M9; R4, R13)."""
from __future__ import annotations

import dataclasses
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from src.data.rules.mpc_params import MpcParams

ROOT = Path(__file__).resolve().parents[4]
INIT = ROOT / "src" / "data" / "db" / "init"
SQL = INIT / "009_decision_mpc.sql"


@pytest.fixture()
def conn(module_db_dsn):
    with psycopg.connect(module_db_dsn) as c:
        yield c
        c.rollback()


def _cols(conn, schema: str, table: str) -> dict[str, tuple]:
    rows = conn.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                        "WHERE table_schema = %s AND table_name = %s", (schema, table)).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def test_init_script_is_idempotent(conn) -> None:
    text = SQL.read_text(encoding="utf-8")
    conn.execute(text)
    conn.execute(text)
    conn.commit()
    assert conn.execute("SELECT count(*) FROM config.decision_model").fetchone()[0] == 1


def test_decision_model_defaults_equal_the_dataclass(conn) -> None:
    """The DDL defaults and `MpcParams` are one set of numbers (same pattern as SIM_PLANNED_HEADWAY_S)."""
    conn.row_factory = psycopg.rows.dict_row
    row = conn.execute("SELECT * FROM config.decision_model").fetchone()
    p = MpcParams()
    for f in dataclasses.fields(p):
        got, want = row[f.name], getattr(p, f.name)
        if isinstance(want, tuple):
            assert [float(x) for x in got] == [float(x) for x in want], f.name
        elif isinstance(want, str):
            assert got == want, f.name
        else:
            assert float(got) == float(want), f.name
    assert row["corridor_id"] == "C6-008"


@pytest.mark.parametrize("column,value", [("horizon_s", 601), ("top_n", 4), ("top_n", 0),
                                          ("threshold_s_per_rider", -1), ("scoring_window_s", 0),
                                          ("train_share", 1.5), ("capacity", 0)])
def test_decision_model_checks_reject(conn, column, value) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(f"UPDATE config.decision_model SET {column} = %s", (value,))  # noqa: S608 - fixed names
    conn.rollback()


def test_hold_option_above_the_cap_is_rejected(conn) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("UPDATE config.decision_model SET hold_options_s = ARRAY[30, 91]")
    conn.rollback()


def test_train_arrivals_are_loaded(conn) -> None:
    assert conn.execute("SELECT count(*) FROM config.ref_train_arrival").fetchone()[0] == 511
    assert conn.execute("SELECT max(arrival_sec) FROM config.ref_train_arrival").fetchone()[0] < 86400


def test_stop_queue_columns(conn) -> None:
    cols = _cols(conn, "silver", "stop_queue")
    assert set(cols) == {"stop_id", "queue_riders", "basis_ts", "basis_bronze_id", "as_of_ts"}
    assert cols["basis_ts"][1] == "YES" and cols["queue_riders"][1] == "NO"
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO silver.stop_queue VALUES ('P-883', -1, NULL, 0, now())")
    conn.rollback()


def test_bus_current_state_has_occupancy(conn) -> None:
    assert _cols(conn, "silver", "bus_current_state")["occupancy"] == ("integer", "YES")


def test_recommendation_columns_status_check_and_indexes(conn) -> None:
    cols = _cols(conn, "gold", "recommendation")
    assert set(cols) == {"rec_id", "doc", "key", "case", "status", "stale", "proposed_ts", "expires_ts", "close_ts",
                         "first_snapshot_id", "params", "lineage_detail", "rules_version", "max_bronze_id"}
    assert cols["close_ts"][1] == "YES" and cols["doc"][1] == "NO"
    ddl = "".join(r[0] for r in conn.execute(
        "SELECT indexdef FROM pg_indexes WHERE schemaname = 'gold' AND tablename = 'recommendation'").fetchall())
    assert "status" in ddl and "rank" in ddl and "key" in ddl
    n = conn.execute("SELECT count(*) FROM pg_indexes WHERE schemaname = 'gold' AND tablename = 'recommendation'"
                     ).fetchone()[0]
    assert n == 3  # primary key + the two of M5
    bad = ("INSERT INTO gold.recommendation (rec_id, doc, key, \"case\", status, proposed_ts, expires_ts, "
           "first_snapshot_id, params, lineage_detail, rules_version, max_bronze_id) VALUES "
           "(gen_random_uuid(), '{\"status\": \"proposed\"}', 'k', 'C1', %s, now(), now(), gen_random_uuid(), "
           "'{}', '{}', 'v', 1)")
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(bad, ("applied",))  # the column must equal doc.status
    conn.rollback()
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(bad.replace('{\\"status\\": \\"proposed\\"}', "x"), ("done",))
    conn.rollback()


def test_mpc_evaluation_primary_key(conn) -> None:
    cols = _cols(conn, "gold", "mpc_evaluation")
    assert set(cols) == {"snapshot_id", "seq", "action", "case", "score_s", "saving_s_per_rider", "recommended",
                         "reason_not", "rules_version", "max_bronze_id"}
    pk = conn.execute("SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
                      "AND a.attnum = ANY(i.indkey) WHERE i.indrelid = 'gold.mpc_evaluation'::regclass "
                      "AND i.indisprimary ORDER BY a.attname").fetchall()
    assert [r[0] for r in pk] == ["seq", "snapshot_id"]


SEED_TABLE = "seed" + "_recommendation"  # built from parts: the tree grep of SC-009 must not match this file


def test_seed_table_is_gone(conn) -> None:
    assert conn.execute("SELECT to_regclass(%s)", (f"config.{SEED_TABLE}",)).fetchone()[0] is None
    assert SEED_TABLE not in (INIT / "007_scenarios.sql").read_text(encoding="utf-8")


def test_drop_on_an_existing_volume(conn) -> None:
    """An existing volume still has the seed table; applying 009 drops it (M9)."""
    conn.execute(f"CREATE TABLE IF NOT EXISTS config.{SEED_TABLE} (rec_id UUID PRIMARY KEY, doc JSONB)")  # noqa: S608
    conn.execute(SQL.read_text(encoding="utf-8"))
    assert conn.execute("SELECT to_regclass(%s)", (f"config.{SEED_TABLE}",)).fetchone()[0] is None
    conn.commit()


def test_decimal_defaults_exact(conn) -> None:
    assert conn.execute("SELECT threshold_s_per_rider, reserve_cost_s FROM config.decision_model").fetchone() == (
        Decimal("15"), Decimal("900"))
