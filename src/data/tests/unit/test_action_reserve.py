"""006 T057 — `reserve_dispatch` execution in the simulator (FR-008 row 1, FR-023, FR-024, FR-026; SC-008 reserve part).

No database: orders are put on the boards directly or through a fake poller connection. The reserve starts at
`start_s = from_s + ready_s` with `ready_s` read from the order row's `params`; the simulator never reads `config`.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest

from src.data.simulator.engine import run
from src.data.simulator.scenarios import scenario_events
from src.data.simulator.scenarios.actions import ActionBoard
from src.data.simulator.scenarios.holds import HoldBoard, RecAction
from src.data.simulator.scenarios.truth import TruthSink
from src.data.tests.fixtures.rec_support import make_row
from src.data.simulator.scenarios.holds import rec_action

START = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
REC_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
REC_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
DURATION = 3600
FROM_S, READY_S = 600.0, 120


def _digest(events) -> str:
    return hashlib.sha256("\n".join(json.dumps(e, sort_keys=True) for e in events).encode()).hexdigest()


def _of(events: list[dict], bus: str) -> list[dict]:
    return [e for e in events if e["payload"].get("bus_id") == bus]


def _seconds(event: dict) -> float:
    return (datetime.strptime(event["event_ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            - START).total_seconds()


def _stream(board: ActionBoard | None) -> list[dict]:
    return list(run(42, DURATION, actions=board))


def _reserve_board(rec_id: str = REC_A, bus: str = "B-108", from_s: float = FROM_S, ready_s: int = READY_S,
                   truth: TruthSink | None = None) -> ActionBoard:
    board = ActionBoard(truth=truth, when=lambda t: str(t))
    board.add_reserve(rec_id, bus, from_s, ready_s)
    return board


def test_order_start_is_the_decision_plus_the_readiness_delay() -> None:
    board = _reserve_board()
    (order,) = board.pending_reserves()
    assert (order.rec_id, order.bus_id, order.from_s, order.start_s) == (REC_A, "B-108", 600.0, 720.0)


def test_reserve_first_event_is_at_start_within_one_step() -> None:
    events = _stream(_reserve_board())
    mine = _of(events, "B-108")
    assert mine, "B-108 must appear in the stream"
    assert 0 <= _seconds(mine[0]) - 720 < 5
    assert {e["event_type"] for e in mine} >= {"bus_position", "stop_arrival", "stop_departure"}
    assert mine[0]["event_type"] == "stop_arrival" or mine[0]["event_type"] == "bus_position"


def test_reserve_emits_nothing_after_its_last_stop_and_is_not_redispatched() -> None:
    mine = _of(_stream(_reserve_board()), "B-108")
    assert {e["payload"]["trip_id"] for e in mine if "trip_id" in e["payload"]} == {"C6-008-B-108-001"}
    last = mine[-1]
    assert last["event_type"] == "stop_departure" and last["payload"]["stop_id"] == "P-900"
    assert _seconds(last) < DURATION - 300  # ended well before the run did: nothing re-dispatched


def test_same_decisions_give_the_same_stream() -> None:
    assert _digest(_stream(_reserve_board())) == _digest(_stream(_reserve_board()))


def test_no_order_means_the_baseline_stream_and_no_draw() -> None:
    baseline = list(run(42, DURATION))
    assert _stream(None) == baseline
    assert _stream(ActionBoard()) == baseline  # an empty board draws no random number


def test_second_order_for_a_reserve_already_ordered_is_ignored_with_a_log_line(capsys) -> None:
    board = _reserve_board()
    assert board.add_reserve(REC_B, "B-108", 650.0, READY_S) is None
    err = [json.loads(x) for x in capsys.readouterr().err.splitlines() if x.startswith("{")]
    assert any(x["event"] == "reserve_order_ignored" and x["rec_id"] == REC_B for x in err)
    assert len(board.pending_reserves()) == 1


def test_a_bus_that_is_not_a_reserve_is_refused(capsys) -> None:
    board = ActionBoard()
    assert board.add_reserve(REC_A, "B-103", 0.0, READY_S) is None
    assert board.pending_reserves() == []
    assert "reserve_order_ignored" in capsys.readouterr().err


def test_truth_gets_one_reserve_record_per_consumed_order_and_none_without_orders() -> None:
    truth = TruthSink([])
    _stream(_reserve_board(truth=truth))
    records = [r for r in truth.records() if r["type"] == "RESERVE"]
    assert len(records) == 1
    assert records[0]["rec_id"] == REC_A and records[0]["bus"] == "B-108" and records[0]["effective_ts"] == "720"
    empty = TruthSink([])
    _stream(ActionBoard(truth=empty, when=lambda t: str(t)))
    assert empty.records() == []


def test_hold_board_hands_a_reserve_approval_to_the_action_board() -> None:
    actions = ActionBoard()
    holds = HoldBoard(seed=42, noncompliance=0.0, actions=actions)
    row = make_row(REC_A, type="reserve_dispatch", bus="B-108", stop="P-883", duration_s=None, case="C5", ready_s=120)
    rec = rec_action(REC_A, row["doc"], row["params"], START)
    holds.apply_decision(REC_A, "apply", 600.0, rec)
    assert [(o.bus_id, o.start_s) for o in actions.pending_reserves()] == [("B-108", 720.0)]
    assert holds.pending_orders() == []


def test_reserve_without_ready_s_is_refused(capsys) -> None:
    actions = ActionBoard()
    holds = HoldBoard(seed=42, noncompliance=0.0, actions=actions)
    rec = RecAction(REC_A, "reserve_dispatch", "B-108", "P-883", None, None, 2100.0, None)
    holds.apply_decision(REC_A, "apply", 600.0, rec)
    assert actions.pending_reserves() == [] and "reserve_order_ignored" in capsys.readouterr().err


@pytest.mark.parametrize("kind", ["adjust_departure", "skip_stop"])
def test_adjust_and_skip_approvals_change_nothing_and_are_counted(kind, capsys) -> None:
    actions = ActionBoard()
    holds = HoldBoard(seed=42, noncompliance=0.0, actions=actions)
    row = make_row(REC_B, type=kind, bus="B-104", stop="P-883", duration_s=60 if kind == "adjust_departure" else None,
                   case="C2")
    holds.apply_decision(REC_B, "apply", 600.0, rec_action(REC_B, row["doc"], row["params"], START))
    assert holds.ignored_not_executed == {kind: 1} and actions.pending_reserves() == []
    assert list(scenario_events([], 42, DURATION, TruthSink([]), holds=holds, actions=actions)) \
        == list(run(42, DURATION))
    assert "not_executed_in_this_story" in capsys.readouterr().err
