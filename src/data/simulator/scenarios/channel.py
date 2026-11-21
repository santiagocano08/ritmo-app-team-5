"""D1 channel layer (004 FR-008, FR-009; research R3).

Wraps the finished event stream, after the engine created every envelope: the world and the RNG are
untouched, so a run with only D1 scenarios is the base stream with some lines removed (silence) or
repeated (duplicates). No RNG draw, no wall clock.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from datetime import datetime

from src.data.simulator.scenarios.truth import TruthSink

BUS_REPORTS = frozenset({"bus_position", "stop_arrival", "stop_departure"})
_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _seconds(event_ts: str, t0: datetime) -> float:
    return (datetime.strptime(event_ts, _FORMAT).replace(tzinfo=t0.tzinfo) - t0).total_seconds()


def apply_channel(events: Iterable[dict], scenarios: Sequence, t0: datetime, truth: TruthSink) -> Iterator[dict]:
    silences = [s for s in scenarios if s.type == "D1_SILENCE"]
    dups = [{"scn": s, "left": s.count} for s in scenarios if s.type == "D1_DUPLICATES"]
    for event in events:
        sec = _seconds(event["event_ts"], t0)
        if event["event_type"] in BUS_REPORTS:
            bus = event["payload"]["bus_id"]
            hit = [s for s in silences if s.bus == bus and s.start_s <= sec < s.start_s + s.duration_s]
            if hit:
                for s in hit:
                    if not truth.record(s.id)["fired"]:
                        truth.fire(s.id, event["event_ts"])
                continue
        copies = 1
        for d in dups:
            if d["left"] > 0 and sec >= d["scn"].start_s:
                d["left"] -= 1
                copies += 1
                rec = truth.record(d["scn"].id)
                if not rec["fired"]:
                    truth.fire(d["scn"].id, event["event_ts"])
                rec["event_ids"].append(event["event_id"])
        for _ in range(copies):
            yield event
