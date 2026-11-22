"""T030 — hold board and poller logic with a fake connection (004 FR-012, FR-017, FR-018, FR-028, SC-007).

No database: the connection is a fake that returns crafted decision rows and, for the second query, the rows of
`gold.recommendation` (006 R4: the recommendations come from the model's table, no longer from a seed file).
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
import psycopg
import pytest

from src.data.simulator.scenarios.holds import HoldBoard, HoldPoller, RecAction, rec_action
from src.data.tests.fixtures.rec_support import seed_like_rows

ROWS = seed_like_rows()
START = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
REC1 = "11111111-1111-4111-8111-111111111111"  # hold 90 s, B-103, P-887
REC3 = "33333333-3333-4333-8333-333333333333"  # reserve_dispatch (not a hold)
REC6 = "66666666-6666-4666-8666-666666666666"  # adjust_departure (recommended only, not executed in 006)
REC7 = "77777777-7777-4777-8777-777777777777"  # skip_stop (same)
REC4 = "44444444-4444-4444-8444-444444444444"  # hold 120 s (over the cap)
UNKNOWN = "99999999-9999-4999-8999-999999999999"


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


def _extra_rows() -> dict:
    from src.data.tests.fixtures.rec_support import make_row

    return {REC6: make_row(REC6, type="adjust_departure", bus="B-104", stop="P-883", duration_s=60,
                           expires="2026-11-24T22:35:00Z", case="C2"),
            REC7: make_row(REC7, type="skip_stop", bus="B-102", stop="P-890", duration_s=None,
                           expires="2026-11-24T22:35:00Z", case="C2")}


TABLE = {**ROWS, **_extra_rows()}


class FakeConn:
    """Answers the shared decision query and the lookup in `gold.recommendation`."""

    def __init__(self, rows, gate: threading.Event | None = None, table=None):
        self.rows, self.gate, self.closed = rows, gate, False
        self.calls = []
        self.table = TABLE if table is None else table
        self.lookups = []

    def execute(self, sql, params=None):
        if "gold.recommendation" in sql:
            ids = list(params["ids"] if isinstance(params, dict) else params[0])
            self.lookups.append(ids)
            return FakeResult([(r["rec_id"], r["doc"], r["params"]) for i in ids if (r := self.table.get(i))])
        self.calls.append(params)
        if self.gate is not None:
            self.gate.wait(5)
        last = (params or {}).get("last_id", 0)
        return FakeResult([r for r in self.rows if r[0] > last])

    def close(self):
        self.closed = True


def make(rows, connect=None, **kw):
    board = HoldBoard(seed=42, noncompliance=0.0)
    conn = FakeConn(rows)
    poller = HoldPoller("postgresql://u:p@h/db", board, START, 1.0, connect=connect or (lambda dsn: conn), **kw)
    return board, poller, conn


def lines(capsys) -> list[dict]:
    return [json.loads(x) for x in capsys.readouterr().err.splitlines() if x.startswith("{")]


def test_recommendation_row_becomes_an_action_with_its_expiry_in_run_seconds() -> None:
    act = rec_action(REC1, ROWS[REC1]["doc"], ROWS[REC1]["params"], START)
    assert act == RecAction(REC1, "hold", "B-103", "P-887", 90.0, None, 2100.0, None)
    over = rec_action(REC4, ROWS[REC4]["doc"], ROWS[REC4]["params"], START)
    assert over.duration_s == 120.0 and over.type == "hold"  # kept, refused later by the executor
    res = rec_action(REC3, ROWS[REC3]["doc"], ROWS[REC3]["params"], START)
    assert res.type == "reserve_dispatch" and res.duration_s is None and res.ready_s == 120


def test_apply_makes_one_order_with_the_seed_values() -> None:
    board, poller, _ = make([(1, REC1, "apply", None)])
    poller.poll_once()
    (o,) = board.pending_orders()
    assert (o.rec_id, o.bus_id, o.stop_id, o.hold_s, o.from_s, o.until_s) == (
        REC1, "B-103", "P-887", 90.0, float("-inf"), 2100.0)


def test_decided_at_sim_becomes_seconds_since_the_run_start() -> None:
    at = datetime(2026, 11, 24, 22, 10, 0, tzinfo=timezone.utc)
    board, poller, _ = make([(1, REC1, "apply", at)])
    poller.poll_once()
    assert board.pending_orders()[0].from_s == 600.0


def test_decision_for_a_row_not_found_yet_is_kept_and_retried(capsys) -> None:
    """006 R4: the row is written by a cycle that commits before the console can list it; a miss is a tolerance."""
    conn = FakeConn([(1, UNKNOWN, "apply", None)])
    board, poller, _ = make([], connect=lambda dsn: conn)
    poller.poll_once()
    assert board.pending_orders() == [] and poller.last_id == 1 and poller.unresolved_ids() == [UNKNOWN]
    conn.table = {**TABLE, UNKNOWN: ROWS[REC1] | {"rec_id": UNKNOWN}}  # the row shows up
    poller.poll_once()
    assert [o.rec_id for o in board.pending_orders()] == [UNKNOWN] and poller.unresolved_ids() == []
    out = [x for x in lines(capsys) if x.get("event") == "hold_order_waiting"]
    assert len(out) == 1 and out[0]["rec_id"] == UNKNOWN  # logged once, not on every poll


def test_discard_makes_no_order_and_needs_no_lookup() -> None:
    board, poller, conn = make([(1, REC1, "discard", None)])
    poller.poll_once()
    assert board.pending_orders() == [] and board.ignored_discard == 1 and conn.lookups == []


@pytest.mark.parametrize("rec_id,kind", [(REC6, "adjust_departure"), (REC7, "skip_stop")])
def test_adjust_and_skip_are_counted_not_executed_with_one_log_line(rec_id, kind, capsys) -> None:
    """FR-024, SC-008: accepted without executing; one `not_executed_in_this_story` line per rec_id."""
    board, poller, _ = make([(1, rec_id, "apply", None), (2, rec_id, "apply", None)])
    poller.poll_once()
    assert board.pending_orders() == [] and board.ignored_not_executed == {kind: 1}
    out = [x for x in lines(capsys) if x.get("event") == "not_executed_in_this_story"]
    assert len(out) == 1 and out[0]["rec_id"] == rec_id and out[0]["type"] == kind


def test_non_hold_recommendation_makes_no_order(capsys) -> None:
    board, poller, _ = make([(1, REC3, "apply", None)])
    poller.poll_once()
    assert board.pending_orders() == []
    assert any(x.get("reason") == "not_hold" for x in lines(capsys))


def test_same_rec_id_twice_makes_one_order() -> None:
    board, poller, _ = make([(1, REC1, "apply", None), (2, REC1, "apply", None)])
    poller.poll_once()
    assert len(board.pending_orders()) == 1


def test_hold_above_the_cap_is_refused_with_a_log_line(capsys) -> None:
    board, poller, _ = make([(1, REC4, "apply", None)])
    poller.poll_once()
    assert board.pending_orders() == []
    refused = [x for x in lines(capsys) if x.get("event") == "hold_order_refused"]
    assert refused and refused[0]["reason"] == "over_cap" and refused[0]["rec_id"] == REC4


def test_poll_advances_last_id_and_does_not_repeat_decisions() -> None:
    board, poller, conn = make([(1, REC1, "apply", None)])
    poller.poll_once()
    poller.poll_once()
    assert poller.last_id == 1 and conn.calls[-1]["last_id"] == 1 and len(board.pending_orders()) == 1


def test_database_error_keeps_the_board_and_logs_once_per_outage(capsys) -> None:
    state = {"up": True}
    conn = FakeConn([(1, REC1, "apply", None)])

    def connect(dsn):
        if not state["up"]:
            raise psycopg.OperationalError("connection to server at \"secret-host\" failed: password=hunter2")
        return conn

    board, poller, _ = make([], connect=connect)
    poller.poll_once()
    capsys.readouterr()
    state["up"] = False
    poller._drop()  # the next poll must reconnect
    for _ in range(5):
        poller.poll_once()  # must not raise
    err = capsys.readouterr().err
    assert len(board.pending_orders()) == 1  # the board is kept
    failed = [json.loads(x) for x in err.splitlines() if "hold_poll_failed" in x]
    assert len(failed) == 1 and failed[0]["error_class"] == "OperationalError"
    assert "secret-host" not in err and "hunter2" not in err and "Traceback" not in err
    state["up"] = True
    poller.poll_once()
    recovered = [x for x in lines(capsys) if x.get("event") == "hold_poll_recovered"]
    assert len(recovered) == 1


def test_query_error_in_the_middle_of_a_poll_is_caught(capsys) -> None:
    class Boom(FakeConn):
        def execute(self, sql, params=None):
            raise psycopg.errors.QueryCanceled("statement timeout")

    board, poller, _ = make([], connect=lambda dsn: Boom([]))
    poller.poll_once()
    assert poller.failed and board.pending_orders() == []


def test_the_board_lock_is_not_held_during_io() -> None:
    gate = threading.Event()
    board = HoldBoard(seed=42, noncompliance=0.0)
    poller = HoldPoller("postgresql://u:p@h/db", board, START, 1.0,
                        connect=lambda dsn: FakeConn([(1, REC1, "apply", None)], gate))
    t = threading.Thread(target=poller.poll_once, daemon=True)
    t.start()
    time.sleep(0.2)  # the fake connection is now stalled inside execute()
    started = time.monotonic()
    assert board.dwell_end("B-103", 10, "P-887", 20) == 20  # a board read during the stall
    board.cancel_bus("B-103")
    assert time.monotonic() - started < 0.5
    gate.set()
    t.join(5)
    assert len(board.pending_orders()) == 1
