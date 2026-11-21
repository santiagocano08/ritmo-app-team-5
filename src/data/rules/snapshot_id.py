"""Deterministic snapshot identity (research R5).

`sha256(as_of_ts ISO-8601 UTC | rules_version | max_bronze_id)` shaped as a UUID with
version-4 bits, so recomputing with the same inputs yields the same id.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone


def snapshot_id(as_of_ts: datetime, rules_version: str, max_bronze_id: int) -> uuid.UUID:
    as_of = as_of_ts.astimezone(timezone.utc).isoformat()
    digest = hashlib.sha256(f"{as_of}|{rules_version}|{max_bronze_id}".encode()).digest()
    return uuid.UUID(int=int.from_bytes(digest[:16], "big"), version=4)
