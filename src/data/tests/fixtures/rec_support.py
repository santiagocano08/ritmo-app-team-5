"""Builder of `gold.recommendation` rows for tests (006 T028, research R4).

Replaces the retired seed file: the story-004 tests need a known `rec_id` that means "hold B-103 90 s at P-887".
Every row is validated with the generated `RecommendationV110` before it is inserted, so a test cannot write a
document the contract would refuse (a hold above 90 s is refused by the schema's conditional, not by the class, so
`over_cap` rows are allowed through `validate=False`, as the old seed loader allowed them).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.types.json import Jsonb

from src.data.rules.mpc import action_key
from src.pulsoflota.models.read.recommendation import RecommendationV110

T_SNAPSHOT = "cccc0006-0000-4000-8000-000000000001"


def _rfc3339(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_row(rec_id: str, *, type: str = "hold", bus: str = "B-103", stop: str = "P-887",
             duration_s: float | None = 90, expires: str = "2026-11-24T22:35:00Z", proposed: str | None = None,
             speed_pct: float | None = None, case: str = "C1", rank: int = 1, status: str = "proposed",
             ready_s: int | None = None, saving: float = 20.0, validate: bool = True) -> dict:
    """A row of `gold.recommendation` as plain data: doc, key, params and the two timestamps. `proposed` defaults to
    120 s before `expires`."""
    exp = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    prop = datetime.fromisoformat(proposed.replace("Z", "+00:00")) if proposed else exp - timedelta(seconds=120)
    action = {"type": type, "bus_id": bus, "stop_id": stop, "duration_s": duration_s}
    if speed_pct is not None:
        action["speed_reduction_pct"] = speed_pct
    doc = {"schema_version": "1.1.0", "rec_id": rec_id, "case": case, "action": action,
           "reason": f"retener {bus} 60 s en {stop} ahorra {saving:g} s por pasajero", "ewt_saving_s": saving, "horizon_s": 600,
           "data_quality": "live", "expires_ts": _rfc3339(exp), "conflicts_with": [], "rank": rank, "status": status,
           "lineage": {"model_version": "1.0.0", "rule_version": "1.6.0", "snapshot_id": T_SNAPSHOT}}
    if validate:
        RecommendationV110.model_validate(doc)
    params = {"ready_s": ready_s} if type == "reserve_dispatch" and ready_s is not None else {}
    return {"rec_id": rec_id, "doc": doc, "key": action_key(action), "case": case, "status": status,
            "proposed_ts": prop, "expires_ts": exp, "params": params}


def insert_recommendation(conn: psycopg.Connection, rec_id: str, commit: bool = True, **kw) -> str:
    """Insert one validated row (see `make_row`); returns its `rec_id`."""
    r = make_row(rec_id, **kw)
    conn.execute(
        "INSERT INTO gold.recommendation (rec_id, doc, key, \"case\", status, stale, proposed_ts, expires_ts, "
        "first_snapshot_id, params, lineage_detail, rules_version, max_bronze_id) "
        "VALUES (%s, %s, %s, %s, %s, false, %s, %s, %s, %s, %s, %s, 0) ON CONFLICT (rec_id) DO NOTHING",
        (rec_id, Jsonb(r["doc"]), r["key"], r["case"], r["status"], r["proposed_ts"], r["expires_ts"], T_SNAPSHOT,
         Jsonb(r["params"]), Jsonb({"source": "test"}), "1.6.0"))
    if commit:
        conn.commit()
    return rec_id


# The six recommendations the story-004 tests used (same ids, same numbers), as model rows.
SEED_LIKE = (
    dict(rec_id="11111111-1111-4111-8111-111111111111", bus="B-103", stop="P-887", duration_s=90,
         expires="2026-11-24T22:35:00Z", rank=1),
    dict(rec_id="22222222-2222-4222-8222-222222222222", bus="B-104", stop="P-887", duration_s=60,
         expires="2026-11-24T22:45:00Z", rank=2),
    dict(rec_id="33333333-3333-4333-8333-333333333333", type="reserve_dispatch", bus="B-106", stop="P-883",
         duration_s=None, expires="2026-11-24T22:45:00Z", rank=3, case="C5", ready_s=120),
    dict(rec_id="44444444-4444-4444-8444-444444444444", bus="B-102", stop="P-887", duration_s=120,
         expires="2026-11-24T22:25:00Z", rank=1, validate=False),  # over the 90 s cap: refused by the executor
    dict(rec_id="55555555-5555-4555-8555-555555555555", bus="B-103", stop="P-887", duration_s=45,
         expires="2026-11-24T22:35:00Z", rank=2),
)


def seed_like_rows() -> dict[str, dict]:
    return {kw["rec_id"]: make_row(**kw) for kw in SEED_LIKE}


def insert_seed_like(conn: psycopg.Connection) -> None:
    for kw in SEED_LIKE:
        insert_recommendation(conn, commit=False, **kw)
    conn.commit()
