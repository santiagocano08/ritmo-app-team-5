"""T037 — deterministic snapshot id (R5, FR-016, FR-005)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.rules.snapshot_id import snapshot_id

AS_OF = datetime(2026, 11, 24, 22, 50, 0, tzinfo=timezone.utc)


def test_same_inputs_give_the_same_id() -> None:
    assert snapshot_id(AS_OF, "1.0.0", 42) == snapshot_id(AS_OF, "1.0.0", 42)


def test_any_input_change_changes_the_id() -> None:
    base = snapshot_id(AS_OF, "1.0.0", 42)
    assert snapshot_id(AS_OF + timedelta(seconds=5), "1.0.0", 42) != base
    assert snapshot_id(AS_OF, "1.0.1", 42) != base
    assert snapshot_id(AS_OF, "1.0.0", 43) != base


def test_id_has_version_4_and_rfc4122_variant_bits() -> None:
    sid = snapshot_id(AS_OF, "1.0.0", 42)
    assert isinstance(sid, UUID) and sid.version == 4 and sid.variant == "specified in RFC 4122"
    assert UUID(str(sid)) == sid


def test_same_instant_in_another_time_zone_gives_the_same_id() -> None:
    local = AS_OF.astimezone(timezone(timedelta(hours=-5)))
    assert snapshot_id(local, "1.0.0", 42) == snapshot_id(AS_OF, "1.0.0", 42)
