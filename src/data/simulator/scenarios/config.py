"""Scenario file model and validation (004 FR-001, FR-004; research R1; data-model E1).

A scenario file is a JSON array. Each element is validated strictly (`extra="forbid"`, ranges as in
the data model) before the simulator produces its first event. Nothing here reads a clock or a RNG.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

BUSES = ("B-101", "B-102", "B-103", "B-104", "B-105")
# P-884..P-899: not the first stop (C2's domain) and not the terminus.
C1_STOPS = tuple(f"P-{n}" for n in range(884, 900))

Bus = Literal[BUSES]  # type: ignore[valid-type]
C1Stop = Literal[C1_STOPS]  # type: ignore[valid-type]
Id = Annotated[str, Field(min_length=1)]
StartS = Annotated[StrictInt, Field(ge=0)]
WORLD_TYPES = ("C1", "C2", "C5")


class ScenarioConfigError(ValueError):
    """The scenario file is invalid. The message is safe to print and names the first problem."""


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Id
    start_s: StartS


class C1(_Base):
    """Extend the dwell of `bus` at `stop` so the follower closes up (bunching)."""

    type: Literal["C1"]
    bus: Bus
    stop: C1Stop
    extra_s: Annotated[float, Field(gt=300, le=600, allow_inf_nan=False)]


class C2(_Base):
    """Delay the next departure of `bus` from the first stop (gap)."""

    type: Literal["C2"]
    bus: Bus
    delay_s: Annotated[float, Field(gt=300, le=600, allow_inf_nan=False)]


class C5(_Base):
    """Break `bus` down on the road for `duration_s` and report the incident."""

    type: Literal["C5"]
    bus: Bus
    duration_s: Annotated[float, Field(gt=0, le=300, allow_inf_nan=False)]


class D1Silence(_Base):
    """The bus keeps moving but its reports do not arrive for `duration_s`."""

    type: Literal["D1_SILENCE"]
    bus: Bus
    duration_s: Annotated[float, Field(ge=1, allow_inf_nan=False)]


class D1Duplicates(_Base):
    """The next `count` events after `start_s` are delivered twice."""

    type: Literal["D1_DUPLICATES"]
    count: Annotated[StrictInt, Field(ge=1, le=1000)]


Scenario = Annotated[Union[C1, C2, C5, D1Silence, D1Duplicates], Field(discriminator="type")]


def _message(exc: ValidationError, index: int) -> str:
    err = exc.errors()[0]
    where = ".".join(str(p) for p in err["loc"][1:]) or "(item)"
    return f"scenario #{index + 1}: {where}: {err['msg']}"


def parse_scenarios(data: Any) -> list[Scenario]:
    """Validate a decoded JSON document. Raises `ScenarioConfigError` before anything is produced."""
    from pydantic import TypeAdapter

    if not isinstance(data, list):
        raise ScenarioConfigError("scenario file must be a JSON array")
    adapter = TypeAdapter(Scenario)
    out: list[Scenario] = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ScenarioConfigError(f"scenario #{i + 1}: must be a JSON object")
        if item.get("type") not in ("C1", "C2", "C5", "D1_SILENCE", "D1_DUPLICATES"):
            raise ScenarioConfigError(f"scenario #{i + 1}: type: unknown scenario type {item.get('type')!r}")
        try:
            out.append(adapter.validate_python(item))
        except ValidationError as exc:
            raise ScenarioConfigError(_message(exc, i)) from None
    ids = [s.id for s in out]
    dup = sorted({x for x in ids if ids.count(x) > 1})
    if dup:
        raise ScenarioConfigError(f"duplicate scenario id: {dup[0]}")
    world_by_bus: dict[str, list[str]] = defaultdict(list)
    for s in out:
        if s.type in WORLD_TYPES:
            world_by_bus[s.bus].append(s.id)
    for bus, names in sorted(world_by_bus.items()):
        if len(names) > 1:
            raise ScenarioConfigError(
                f"world scenarios {names[0]} and {names[1]} overlap on bus {bus}: one per bus")
    return out


def load_scenarios(path: str | Path | None) -> list[Scenario]:
    """Load and validate the scenario file. Unset, empty path or `[]` mean no scenario."""
    if path is None or str(path) == "":
        return []
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError:
        raise ScenarioConfigError(f"cannot read scenario file: {Path(path).name}") from None
    except json.JSONDecodeError as exc:
        raise ScenarioConfigError(f"scenario file is not valid JSON (line {exc.lineno})") from None
    return parse_scenarios(data)
