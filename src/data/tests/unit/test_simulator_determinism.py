"""T018 — Simulator determinism and contract validity (FR-017..FR-026, SC-001)."""
from __future__ import annotations

import hashlib
import io
import json

from src.pulsoflota.models.turn1_events import EventEnvelopeRoot
from src.data.simulator import main as sim_main
from src.data.simulator.engine import run
from src.data.simulator.model import IN_SERVICE


def _stream(seed: int, duration: int) -> bytes:
    buf = io.StringIO()
    sim_main.main(["--seed", str(seed), "--duration", str(duration)], out=buf)
    return buf.getvalue().encode()


def test_same_seed_is_byte_identical() -> None:
    a, b = _stream(42, 900), _stream(42, 900)
    assert a and hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()


def test_different_seed_differs() -> None:
    assert _stream(42, 900) != _stream(43, 900)


def test_event_ids_are_seeded_and_unique() -> None:
    ids = [e["event_id"] for e in run(42, 900)]
    assert len(ids) == len(set(ids))
    assert ids == [e["event_id"] for e in run(42, 900)]


def test_every_event_validates_against_contract() -> None:
    types = set()
    for line in _stream(42, 1800).decode().splitlines():
        EventEnvelopeRoot.model_validate(json.loads(line))
        types.add(json.loads(line)["event_type"])
    assert types == {"bus_position", "stop_arrival", "stop_departure", "rider_arrival"}


def test_lines_use_sorted_keys() -> None:
    line = _stream(42, 60).decode().splitlines()[0]
    assert line == json.dumps(json.loads(line), sort_keys=True)


def test_one_position_per_in_service_bus_every_5s() -> None:
    pos = [e for e in run(42, 60) if e["event_type"] == "bus_position"]
    assert len(pos) == len(IN_SERVICE) * (60 // 5)
