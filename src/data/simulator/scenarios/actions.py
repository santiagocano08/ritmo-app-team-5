"""Approved-action board of the simulator, reserve part (006 FR-008 row 1, FR-023; contracts/execution.md).

An approved `reserve_dispatch` is an order `(reserve bus, from_s, start_s = from_s + ready_s)`. `ready_s` comes from
the recommendation row's `params`; the simulator never reads `config`. The engine asks the board at every step which
reserves are due. With no order the board answers an empty list and draws nothing, so the stream is the baseline.

The poller thread writes orders and the engine reads them under a lock that is never held during input or output.
"""
from __future__ import annotations

import json
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass

from src.data.simulator.model import RESERVE
from src.data.simulator.scenarios.truth import TruthSink


def log_event(event: str, **fields: object) -> None:
    sys.stderr.write(json.dumps({"event": event, **fields}, sort_keys=True, default=str) + "\n")
    sys.stderr.flush()


@dataclass
class ReserveOrder:
    rec_id: str
    bus_id: str
    from_s: float
    start_s: float
    consumed: bool = False


class ActionBoard:
    def __init__(self, truth: TruthSink | None = None, when: Callable[[int], str] | None = None) -> None:
        self._truth, self._when = truth, when or (lambda t: str(t))
        self._lock = threading.Lock()
        self._reserves: dict[str, ReserveOrder] = {}  # by bus id: one order per reserve
        self._seen: set[str] = set()

    def add_reserve(self, rec_id: str, bus_id: str, from_s: float, ready_s: int | None) -> ReserveOrder | None:
        rec_id = rec_id.lower()
        with self._lock:
            if rec_id in self._seen:
                return None
            self._seen.add(rec_id)
            reason = None
            if bus_id not in RESERVE:
                reason = "not_a_reserve"
            elif bus_id in self._reserves:
                reason = "already_ordered"
            if ready_s is None:
                reason = "missing_ready_s"
            if reason is None and ready_s is not None:
                order = ReserveOrder(rec_id, bus_id, from_s, from_s + ready_s)
                self._reserves[bus_id] = order
                return order
        log_event("reserve_order_ignored", rec_id=rec_id, bus_id=bus_id, reason=reason)
        return None

    def start_reserves(self, t: int, running: set[str]) -> list[str]:
        """Reserve bus ids to put in service at step `t`: orders due and not consumed, in order of start then id."""
        with self._lock:
            due = sorted((o for o in self._reserves.values() if not o.consumed and o.start_s <= t),
                         key=lambda o: (o.start_s, o.bus_id))
            for o in due:
                o.consumed = True
        started = []
        for o in due:
            if o.bus_id in running:
                log_event("reserve_order_ignored", rec_id=o.rec_id, bus_id=o.bus_id, reason="already_running")
                continue
            started.append(o.bus_id)
            if self._truth is not None:
                self._truth.add_record({
                    "scenario_id": f"reserve-{o.rec_id}", "type": "RESERVE", "rec_id": o.rec_id, "bus": o.bus_id,
                    "fired": True, "effective_ts": self._when(t)})
        return started

    def pending_reserves(self) -> list[ReserveOrder]:
        with self._lock:
            return [o for o in self._reserves.values() if not o.consumed]
