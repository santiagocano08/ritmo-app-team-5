"""Deterministic crafted bronze timelines for the 002 tests (R10, SC-002, SC-003).

No unseeded randomness: event ids are version-4-shaped UUIDs derived from a SHA-256 of
`<tag>:<counter>`, and all times are offsets in seconds from `T0` (the simulator's first
instant, 2026-11-24 22:00:00Z = 17:00 local). Buses move at a constant speed with staggered
starts, so a follower's time headway equals the difference of the start offsets and the
headway class (bunched < 300 s, regular 300..900 s, gap > 900 s at planned 600 s) is
unambiguous. Headway *values* are not compared by SC-002. The speed is low on purpose
(1.2 m/s) so that buses started up to ~3,300 s apart still share the 5,119.4 m corridor.
No PII; ids and names follow the 001 contract.

Backend `decision` / `confirmation` rows are not accepted by the 001 boundary (the contract
lists only the six turn-1 types), so they are inserted directly the way the backend writer
does (`insert_backend_commands`). Backend `incident_report` rows do pass the boundary.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.types.json import Jsonb

from src.data.ingestion.bronze import IngestResult, ingest

T0 = datetime(2026, 11, 24, 22, 0, 0, tzinfo=timezone.utc)
STEP_S = 5
SPEED_MPS = 1.2
STOPS = [f"P-{n}" for n in range(883, 901)]  # stop_seq k -> STOPS[k-1]
TERMINUS = STOPS[-1]
OPERATOR = "OP-01"


def iso(t: float) -> str:
    """Seconds after T0 -> RFC 3339 UTC string."""
    return (T0 + timedelta(seconds=t)).strftime("%Y-%m-%dT%H:%M:%SZ")


def seconds_between(a_iso: str, b_iso: str) -> float:
    f = "%Y-%m-%dT%H:%M:%SZ"
    return (datetime.strptime(b_iso, f) - datetime.strptime(a_iso, f)).total_seconds()


def trip_id(bus_id: str, n: int = 1) -> str:
    return f"C6-008-{bus_id}-{n:03d}"


@dataclass
class Builder:
    """Accumulates envelope dicts. `tag` keeps event ids unique across builders."""

    tag: str
    events: list[dict] = field(default_factory=list)
    _n: int = 0

    def _eid(self) -> str:
        self._n += 1
        digest = hashlib.sha256(f"{self.tag}:{self._n}".encode()).digest()
        return str(uuid.UUID(int=int.from_bytes(digest[:16], "big"), version=4))

    def _env(self, etype: str, at: float, payload: dict, source: str = "simulator") -> dict:
        env = {"schema_version": "1.0.0", "event_id": self._eid(), "event_type": etype,
               "source": source, "event_ts": iso(at), "payload": payload}
        self.events.append(env)
        return env

    # -- bus reports ------------------------------------------------------------
    def position(self, bus_id: str, trip: str, at: float, distance_m: float, speed_kmh: float = 4.3,
                 occupancy: int = 0, source: str = "simulator") -> dict:
        return self._env("bus_position", at, {
            "bus_id": bus_id, "operator": OPERATOR, "trip_id": trip, "direction": 1,
            "distance_along_m": round(distance_m, 1), "speed_kmh": speed_kmh,
            "schedule_deviation_s": 0, "doors_open": False, "occupancy": occupancy}, source)

    def drive(self, bus_id: str, start: float, until: float, speed_mps: float = SPEED_MPS,
              trip: str | None = None, source: str = "simulator") -> None:
        """Position every 5 s from `start` (distance 0) to `until`, inclusive, at constant speed."""
        trip = trip or trip_id(bus_id)
        t = start
        while t <= until:
            self.position(bus_id, trip, t, (t - start) * speed_mps, round(speed_mps * 3.6, 1), source=source)
            t += STEP_S

    def hold(self, bus_id: str, trip: str, start: float, until: float, distance_m: float) -> None:
        """A bus that stands still (for example broken down) but keeps reporting."""
        t = start
        while t <= until:
            self.position(bus_id, trip, t, distance_m, 0.0)
            t += STEP_S

    def stop_arrival(self, bus_id: str, trip: str, stop_id: str, at: float, boarded: int = 0,
                     alighted: int = 0, rejected: int = 0, occupancy: int = 0) -> dict:
        return self._env("stop_arrival", at, {
            "bus_id": bus_id, "trip_id": trip, "stop_id": stop_id, "boarded": boarded,
            "alighted": alighted, "rejected": rejected, "occupancy": occupancy})

    def stop_departure(self, bus_id: str, trip: str, stop_id: str, at: float, boarded: int = 0,
                       alighted: int = 0, rejected: int = 0, occupancy: int = 0) -> dict:
        return self._env("stop_departure", at, {
            "bus_id": bus_id, "trip_id": trip, "stop_id": stop_id, "boarded": boarded,
            "alighted": alighted, "rejected": rejected, "occupancy": occupancy})

    def stop_visit(self, bus_id: str, trip: str, stop_id: str, arrive: float, depart: float,
                   boarded: int = 0, alighted: int = 0, rejected: int = 0) -> None:
        """Arrival then departure at one stop; counts are carried by both payloads."""
        self.stop_arrival(bus_id, trip, stop_id, arrive, boarded, alighted, rejected)
        self.stop_departure(bus_id, trip, stop_id, depart, boarded, alighted, rejected)

    def traversal(self, bus_id: str, trip: str, segment: int, depart: float, arrive: float) -> None:
        """Departure from stop `segment` and arrival at stop `segment + 1` (segment k = seq k -> k+1)."""
        self.stop_departure(bus_id, trip, STOPS[segment - 1], depart)
        self.stop_arrival(bus_id, trip, STOPS[segment], arrive)

    # -- other events -------------------------------------------------------------
    def rider_arrival(self, stop_id: str, at: float, dest: str, origin: str = "street",
                      train_trip_id: str | None = None) -> dict:
        payload = {"stop_id": stop_id, "direction": 1, "origin": origin, "destination_stop_id": dest}
        if train_trip_id:
            payload["train_trip_id"] = train_trip_id
        return self._env("rider_arrival", at, payload)

    def incident(self, incident_type: str, target_id: str, at: float, duration_min: float,
                 reported_by: str = "script", source: str = "simulator") -> dict:
        return self._env("incident_report", at, {
            "incident_type": incident_type, "target_id": target_id,
            "duration_min": duration_min, "reported_by": reported_by}, source)

    # -- backend command events (command_event.schema.json) -------------------------
    def _command(self, etype: str, at: float, payload: dict) -> dict:
        return {"schema_version": "1.0.0", "event_id": self._eid(), "event_type": etype,
                "source": "backend", "event_ts": iso(at), "payload": payload}

    def _fixed_uuid(self, label: str) -> str:
        digest = hashlib.sha256(f"{self.tag}:{label}".encode()).digest()
        return str(uuid.UUID(int=int.from_bytes(digest[:16], "big"), version=4))

    def command_decision(self, at: float, action: str = "apply", user_id: str = "dispatcher-01") -> dict:
        return self._command("decision", at, {"rec_id": self._fixed_uuid("rec"), "action": action,
                                              "user_id": user_id, "ts": iso(at)})

    def command_confirmation(self, at: float, status: str = "received") -> dict:
        return self._command("confirmation", at, {"inst_id": self._fixed_uuid("inst"), "status": status,
                                                  "ts": iso(at)})

    def command_incident(self, at: float, target_id: str, duration_min: float | None = 15.0,
                         incident_type: str = "bus_breakdown") -> dict:
        return self._command("incident_report", at, {
            "incident_type": incident_type, "target_id": target_id,
            "duration_min": duration_min, "reported_by": "dispatcher"})


@dataclass(frozen=True)
class Timeline:
    name: str
    events: list[dict]
    as_of: str  # ISO UTC reference time the scenario is meant to be read at


def ingest_all(conn: psycopg.Connection, events: list[dict]) -> list[IngestResult]:
    """Ingest through the real boundary (validation, dedup, rejections)."""
    return [ingest(conn, e) for e in events]


def insert_backend_commands(conn: psycopg.Connection, commands: list[dict]) -> list[int]:
    """Insert backend command events into bronze.events as the backend writer does."""
    ids = []
    for c in commands:
        row = conn.execute(
            "INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload) "
            "VALUES (%s, %s, %s, %s, %s, now(), %s) RETURNING id",
            (c["source"], c["event_id"], c["schema_version"], c["event_type"], c["event_ts"],
             Jsonb(c["payload"]))).fetchone()
        ids.append(row[0])
    conn.commit()
    return ids


# -- timelines --------------------------------------------------------------------
def _staggered(name: str, starts: dict[str, float], as_of: float) -> Builder:
    b = Builder(name)
    for bus_id, start in starts.items():
        b.drive(bus_id, start, as_of)
    return b


def normal() -> Timeline:
    """Five buses 600 s apart: leader B-105, then B-104, B-103, B-102, B-101 (all regular)."""
    starts = {"B-105": 0, "B-104": 600, "B-103": 1200, "B-102": 1800, "B-101": 2400}
    as_of = 3000
    return Timeline("normal", _staggered("normal", starts, as_of).events, iso(as_of))


def c1_bunching() -> Timeline:
    """B-103 and B-101 bunched behind B-102, which has a gap to B-104 (fixture order)."""
    starts = {"B-105": 0, "B-104": 598, "B-102": 598 + 960, "B-103": 598 + 960 + 180,
              "B-101": 598 + 960 + 180 + 177}
    as_of = 2400
    return Timeline("c1_bunching", _staggered("c1_bunching", starts, as_of).events, iso(as_of))


def c2_gap() -> Timeline:
    """B-101 and B-105 trail with a gap (fixture order B-104, B-103, B-102, B-101, B-105)."""
    starts = {"B-104": 0, "B-103": 596, "B-102": 596 + 598, "B-101": 596 + 598 + 1082,
              "B-105": 596 + 598 + 1082 + 1308}
    as_of = 3600  # B-105 starts at 3,584 s: the reference time must fall after it, or it never reports
    return Timeline("c2_gap", _staggered("c2_gap", starts, as_of).events, iso(as_of))


def d1_source_outage(silent_for_s: int = 125, silent_bus: str = "B-103") -> Timeline:
    """As `normal`, but `silent_bus` stops reporting `silent_for_s` seconds before the reference time."""
    starts = {"B-105": 0, "B-104": 600, "B-103": 1200, "B-102": 1800, "B-101": 2400}
    as_of = 3000
    b = Builder("d1_source_outage")
    for bus_id, start in starts.items():
        b.drive(bus_id, start, as_of - silent_for_s if bus_id == silent_bus else as_of)
    return Timeline("d1_source_outage", b.events, iso(as_of))


def c5_breakdown() -> Timeline:
    """B-104 broken down (stationary, still reporting) between B-103 and B-102 (fixture order)."""
    starts = {"B-105": 0, "B-103": 1200, "B-102": 1200 + 597, "B-101": 1200 + 597 + 598}
    as_of = 3000
    b = Builder("c5_breakdown")
    for bus_id, start in starts.items():
        b.drive(bus_id, start, as_of)
    stuck_at = (as_of - 1500) * SPEED_MPS  # 1,800 m: between B-103 (2,160 m) and B-102 (1,443.6 m) at the reference time
    b.hold("B-104", trip_id("B-104"), 1500, as_of, stuck_at)
    b.incident("bus_breakdown", "B-104", at=1500, duration_min=60.0)
    return Timeline("c5_breakdown", b.events, iso(as_of))
