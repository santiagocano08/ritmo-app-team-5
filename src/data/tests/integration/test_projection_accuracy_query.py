"""006 T049e — the SC-016 aggregate query of `contracts/projection-accuracy.md`, run unchanged (FR-036).

Data: the crafted rows of `test_projection_accuracy_view.py` (see its table). Excluded from the aggregate: rows with
a NULL error (B-1/P-6, B-2/P-2, B-9/P-1) and rows flagged `affected_by_decision` (B-3/P-1, B-9/P-1).

Hand values (absolute errors in seconds, from the table of the view test):

- `0-5 min`: B-1/P-1 35, B-1/P-2 9, B-2/P-1 10, B-4 60, B-5 60, B-6 60, B-8 60 -> n 7, sum 294, MAE 42.0, sorted
  9 10 35 60 60 60 60 -> median 60.0, worst 60; signed 35 - 9 - 10 + 4 * 60 = 256 / 7 = 36.6.
- `5-10 min`: B-1/P-3 0 and B-1/P-4 51 -> n 2, MAE 25.5, median 25.5 (mean of the two middle values), worst 51, signed 25.5.
- `10-30 min`: B-1/P-5 100 -> n 1, MAE 100.0, median 100.0, worst 100, signed 100.0.
"""
from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from src.data.tests.fixtures.gold_support import clear_all
from src.data.tests.integration.test_projection_accuracy_view import SNAPSHOT, A, crafted, project, visit

DOC = Path(__file__).resolve().parents[4] / "specs" / "006-decision-mpc" / "contracts" / "projection-accuracy.md"


def aggregate_sql() -> str:
    if not DOC.exists():
        pytest.skip("specs/ is not mounted in this environment")
    blocks = re.findall(r"```sql\n(.*?)```", DOC.read_text(encoding="utf-8"), re.S)
    assert len(blocks) == 1, "the contract has exactly one aggregate query"
    return blocks[0]


@pytest.fixture()
def conn(module_db_dsn):
    with psycopg.connect(module_db_dsn) as c:
        clear_all(c)
        c.execute("INSERT INTO gold.snapshots (snapshot_id, as_of_ts, rules_version, max_bronze_id) "
                  "VALUES (%s, %s, 'test', 1)", (SNAPSHOT, A))
        yield c
        c.rollback()
        clear_all(c)


def D(x) -> Decimal:
    return Decimal(str(x))


def test_the_table_equals_the_hand_values(conn) -> None:
    crafted(conn)
    rows = conn.execute(aggregate_sql()).fetchall()
    assert rows == [("0-5 min", 7, D("42.0"), D("60.0"), D(60), D("36.6")),
                    ("5-10 min", 2, D("25.5"), D("25.5"), D(51), D("25.5")),
                    ("10-30 min", 1, D("100.0"), D("100.0"), D(100), D("100.0"))]


def test_a_bucket_with_nothing_to_compare_is_n_zero_and_null(conn) -> None:
    project(conn, "B-1", "P-1", 100)
    visit(conn, "B-1", "P-1", 130)
    project(conn, "B-1", "P-2", 1200)  # no real departure yet
    rows = conn.execute(aggregate_sql()).fetchall()
    assert rows[0] == ("0-5 min", 1, D("30.0"), D("30.0"), D(30), D("30.0"))
    assert rows[1] == ("5-10 min", 0, None, None, None, None)
    assert rows[2] == ("10-30 min", 0, None, None, None, None)


def test_an_empty_record_gives_three_empty_buckets(conn) -> None:
    rows = conn.execute(aggregate_sql()).fetchall()
    assert [r[:2] for r in rows] == [("0-5 min", 0), ("5-10 min", 0), ("10-30 min", 0)]
    assert all(r[2:] == (None,) * 4 for r in rows)
