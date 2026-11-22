"""Hold executor of the simulator: board, read-only poller, seeded compliance (004 FR-012 to FR-018; research R4).

An approved hold is a backend `decision` row in `bronze.events`. A daemon thread reads those rows with a
read-only session and puts orders on an in-memory `HoldBoard`; the engine looks the board up when a bus
arrives at a stop. The engine never waits for the thread: a board read is a dictionary lookup under a
lock that is never held during input or output. If the database is down the poller logs one line, keeps
the orders it has and retries; the event stream is not delayed (SC-011).

This module only reads bronze (SELECT through `rules/sql/hold_orders.sql`); a static test keeps it so.
Log lines are JSON on stderr and carry the exception class only, never its text.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import threading
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import psycopg

from src.data.rules.holds import HOLD_ORDERS_SQL, MAX_HOLD_S, hold_in_range
from src.data.seeds import load_recommendations
from src.data.simulator.scenarios.truth import TruthSink

MAX_BIGINT = 2**63 - 1
_SQL: list[str] = []  # the query text, read once


def log_event(event: str, **fields: object) -> None:
    sys.stderr.write(json.dumps({"event": event, **fields}, sort_keys=True, default=str) + "\n")
    sys.stderr.flush()


@dataclass(frozen=True)
class SeedHold:
    """What a seeded `rec_id` means for the executor. `is_hold` is false for other action types."""
    rec_id: str
    bus_id: str
    stop_id: str
    hold_s: float
    expires_s: float  # simulated seconds since the run start
    is_hold: bool


def load_seeds(path: str | Path | None, start: datetime) -> dict[str, SeedHold]:
    """Seed entries by `rec_id`. A hold above `MAX_HOLD_S` is kept (and logged); the executor refuses it."""
    seeds: dict[str, SeedHold] = {}
    for e in load_recommendations(path):
        is_hold = e.action.type == "hold"
        hold_s = float(e.action.duration_s) if e.action.duration_s is not None else 0.0
        rec_id = str(e.rec_id)
        if is_hold and not hold_in_range(hold_s):
            log_event("hold_seed_over_cap", rec_id=rec_id, duration_s=hold_s, max_hold_s=MAX_HOLD_S)
        seeds[rec_id] = SeedHold(rec_id, str(e.action.bus_id), e.action.stop_id, hold_s,
                                 (e.expires_ts - start).total_seconds(), is_hold)
    return seeds


def compliance_draw(seed: int, rec_id: str) -> float:
    """`SHA-256("{seed}|hold|{rec_id}")` as a fraction of 1 (first 8 bytes / 2**64). No shared generator."""
    digest = hashlib.sha256(f"{seed}|hold|{rec_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def complies(seed: int, rec_id: str, noncompliance: float) -> bool:
    """The driver does not comply when the draw is below the probability (1 = never, 0 = always complies)."""
    return not compliance_draw(seed, rec_id) < noncompliance


@dataclass
class Order:
    rec_id: str
    bus_id: str
    stop_id: str
    hold_s: float
    from_s: float  # the order applies strictly after this simulated second (-inf: before every report)
    until_s: float  # and up to this one (expires_ts)
    complies: bool = True
    cancelled: bool = False
    consumed: bool = False


class HoldBoard:
    """Thread-safe orders by (bus, stop). The poller writes, the engine reads."""

    def __init__(self, seeds: Mapping[str, SeedHold], seed: int, noncompliance: float,
                 truth: TruthSink | None = None, when: Callable[[int], str] | None = None) -> None:
        self._seeds = dict(seeds)
        self._seed, self._p = seed, noncompliance
        self._truth, self._when = truth, when or (lambda t: str(t))
        self._lock = threading.Lock()
        self._orders: dict[tuple[str, str], list[Order]] = defaultdict(list)
        self._seen: set[str] = set()
        self.ignored_unknown = 0
        self.ignored_discard = 0

    # -- intake (poller side) -----------------------------------------------------
    def apply_decision(self, rec_id: str, action: str, from_s: float) -> Order | None:
        """Turn a polled decision into an order. `discard`, unknown ids and non-holds make none."""
        rec_id = rec_id.lower()
        if action != "apply":
            self.ignored_discard += 1
            return None
        seed = self._seeds.get(rec_id)
        if seed is None:
            self.ignored_unknown += 1
            log_event("hold_order_ignored", rec_id=rec_id, reason="unknown_rec")
            return None
        if not seed.is_hold:
            log_event("hold_order_ignored", rec_id=rec_id, reason="not_hold")
            return None
        return self.add_order(rec_id, seed.bus_id, seed.stop_id, seed.hold_s, from_s, seed.expires_s)

    def add_order(self, rec_id: str, bus_id: str, stop_id: str, hold_s: float, from_s: float,
                  until_s: float) -> Order | None:
        with self._lock:
            if rec_id in self._seen:
                return None  # the same rec_id twice is one order
            self._seen.add(rec_id)
        if not hold_in_range(hold_s):
            log_event("hold_order_refused", rec_id=rec_id, reason="over_cap", hold_s=hold_s, max_hold_s=MAX_HOLD_S)
            self._record(rec_id, bus_id, stop_id, hold_s, None, None, "over_cap")
            return None
        order = Order(rec_id, bus_id, stop_id, float(hold_s), from_s, until_s,
                      complies=complies(self._seed, rec_id, self._p))
        with self._lock:
            self._orders[(bus_id, stop_id)].append(order)
        return order

    # -- engine side -----------------------------------------------------------------
    def dwell_end(self, bus_id: str, t: int, stop_id: str, natural_end: int) -> int:
        """Departure second of the visit that starts at `t`: `max(natural_end, t + hold_s)` for a complying order.

        The first order by arrival on the board that matches applies; any other order that also matches
        this visit is cancelled (a conflict). A non-complying driver keeps the natural dwell.
        """
        with self._lock:
            hits = [o for o in self._orders.get((bus_id, stop_id), ())
                    if not o.cancelled and not o.consumed and o.from_s < t <= o.until_s]
            if not hits:
                return natural_end
            winner = hits[0]
            winner.consumed = True
            for loser in hits[1:]:
                loser.cancelled = True
        self._record(winner.rec_id, bus_id, stop_id, winner.hold_s, winner.complies, t, None)
        return max(natural_end, math.ceil(t + winner.hold_s)) if winner.complies else natural_end

    def cancel_bus(self, bus_id: str) -> None:
        """A breakdown cancels every pending order of the bus."""
        with self._lock:
            for (bus, _), orders in self._orders.items():
                if bus == bus_id:
                    for o in orders:
                        if not o.consumed:
                            o.cancelled = True

    def pending_orders(self) -> list[Order]:
        with self._lock:
            return [o for orders in self._orders.values() for o in orders if not o.cancelled and not o.consumed]

    def _record(self, rec_id, bus_id, stop_id, hold_s, complied, t, refused) -> None:
        if self._truth is None:
            return
        self._truth.add_record({
            "scenario_id": f"hold-{rec_id}", "type": "HOLD", "rec_id": rec_id, "bus": bus_id, "stop": stop_id,
            "hold_s": hold_s, "complied": complied, "refused": refused,
            "fired": refused is None, "effective_ts": self._when(t) if t is not None else None})


class Decision(NamedTuple):
    id: int
    rec_id: str
    action: str
    decided_at: datetime | None


def connect_read_only(dsn: str) -> psycopg.Connection:
    """Own connection, read-only by session default, with 2 s connect and statement timeouts."""
    return psycopg.connect(dsn, connect_timeout=2, autocommit=True,
                           options="-c default_transaction_read_only=on -c statement_timeout=2000")


def fetch_decisions(conn, last_id: int, max_id: int = MAX_BIGINT) -> list[Decision]:
    """Backend decisions after `last_id`, in id order, with `decided_at_sim` (shared query)."""
    if not _SQL:
        _SQL.append(HOLD_ORDERS_SQL.read_text(encoding="utf-8"))
    rows = conn.execute(_SQL[0], {"last_id": last_id, "max_id": max_id}).fetchall()
    return [Decision(r[0], str(r[1]), str(r[2]), r[3]) for r in rows]


class HoldPoller:
    """Polls decisions and feeds the board. `poll_once` never raises on a database problem."""

    def __init__(self, dsn: str, board: HoldBoard, start: datetime, interval_s: float,
                 connect: Callable[[str], object] = connect_read_only) -> None:
        self._dsn, self._board, self._start, self._interval = dsn, board, start, interval_s
        self._connect = connect
        self._conn = None
        self._stop = threading.Event()
        self.thread: threading.Thread | None = None
        self.last_id = 0
        self.failed = False

    def poll_once(self) -> None:
        try:
            if self._conn is None:
                self._conn = self._connect(self._dsn)
            decisions = fetch_decisions(self._conn, self.last_id)
        except (psycopg.Error, OSError) as exc:
            self._drop()
            if not self.failed:
                self.failed = True
                log_event("hold_poll_failed", error_class=type(exc).__name__)
            return
        if self.failed:
            self.failed = False
            log_event("hold_poll_recovered")
        for d in decisions:  # board writes take the lock briefly; no input or output happens under it
            from_s = -math.inf if d.decided_at is None else (d.decided_at - self._start).total_seconds()
            self._board.apply_decision(d.rec_id, d.action, from_s)
            self.last_id = max(self.last_id, d.id)

    def _drop(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001 - closing a broken connection must not raise
                pass

    def start(self) -> None:
        self.thread = threading.Thread(target=self._loop, name="hold-poller", daemon=True)
        self.thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            self.poll_once()

    def stop(self) -> None:
        self._stop.set()
        if self.thread is not None:
            self.thread.join(timeout=6)
        self._drop()
