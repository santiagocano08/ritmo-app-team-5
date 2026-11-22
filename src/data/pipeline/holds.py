"""`gold.instruction_status` builder (004 FR-015, FR-016, FR-019, FR-026; research R5; data-model E7).

Rebuilt every cycle (DELETE + INSERT) from bronze (backend `decision` rows, read-only), silver
(`stop_visits`, `incidents`) and `gold.recommendation` (006: the model's table, which replaced the seed file), so the
same inputs give the same rows.
One row per approved hold that has a status; an order that is still pending has no row. The rule itself
(matching, cap, tolerance, conflict, breakdown) lives in `src.data.rules.holds`. Data writes nothing to
bronze and never writes a `confirmation`. The caller owns the transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone

import psycopg
from psycopg.types.json import Jsonb

from src.data.rules import RULES_VERSION
from src.data.rules.holds import HOLD_ORDERS_SQL, Order, Visit, observe

_HOLDS = ("SELECT rec_id::text, doc, expires_ts FROM gold.recommendation "
          "WHERE doc->'action'->>'type' = 'hold'")
_COMPLETED = ("SELECT bus_id, stop_id, arrival_ts, departure_ts FROM silver.stop_visits "
              "WHERE bus_id = ANY(%(buses)s) AND stop_id = ANY(%(stops)s)")
# Arrivals that have no completed visit yet: the bus is at the stop (same arrival choice as silver).
_OPEN = """
SELECT a.bus_id, a.stop_id, a.event_ts
FROM (SELECT DISTINCT ON (e.payload->>'bus_id', e.payload->>'trip_id', e.payload->>'stop_id')
             e.payload->>'bus_id' AS bus_id, e.payload->>'trip_id' AS trip_id,
             e.payload->>'stop_id' AS stop_id, e.event_ts
      FROM bronze.events e
      WHERE e.event_type = 'stop_arrival' AND e.source <> 'backend'
        AND e.id <= %(max_id)s AND e.event_ts <= %(as_of)s
        AND e.payload->>'bus_id' = ANY(%(buses)s) AND e.payload->>'stop_id' = ANY(%(stops)s)
      ORDER BY e.payload->>'bus_id', e.payload->>'trip_id', e.payload->>'stop_id', e.event_ts, e.id) a
WHERE NOT EXISTS (SELECT 1 FROM silver.stop_visits v
                  WHERE v.bus_id = a.bus_id AND v.trip_id = a.trip_id AND v.stop_id = a.stop_id)
"""
_BREAKDOWNS = ("SELECT target_id, start_ts FROM silver.incidents "
               "WHERE incident_type = 'bus_breakdown' AND target_id = ANY(%(buses)s) ORDER BY start_ts")
_INSERT = ("INSERT INTO gold.instruction_status (rec_id, bus_id, stop_id, hold_s, observed_dwell_s, status, "
           "ts_by_status, rules_version, max_bronze_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)")


def _rfc3339(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_orders(conn: psycopg.Connection, max_bronze_id: int) -> list[Order]:
    """Approved holds in bronze id order: known hold recommendations only, the first decision per `rec_id`."""
    holds: dict[str, tuple[dict, datetime]] = {}
    for rec_id, doc, expires_ts in conn.execute(_HOLDS).fetchall():
        holds[rec_id.lower()] = (doc, expires_ts.astimezone(timezone.utc))
    orders: list[Order] = []
    seen: set[str] = set()
    sql = HOLD_ORDERS_SQL.read_text(encoding="utf-8")
    for _id, rec_id, action, decided_at in conn.execute(sql, {"last_id": 0, "max_id": max_bronze_id}).fetchall():
        rec_id = str(rec_id).lower()
        if action != "apply" or rec_id not in holds or rec_id in seen:
            continue
        seen.add(rec_id)
        doc, expires_ts = holds[rec_id]
        act = doc["action"]
        orders.append(Order(rec_id, act["bus_id"], act["stop_id"],
                            float(act["duration_s"] if act.get("duration_s") is not None else 0),
                            decided_at, expires_ts))
    return orders


def build_instruction_status(conn: psycopg.Connection, as_of_ts: datetime, max_bronze_id: int) -> int:
    """Rebuild `gold.instruction_status` for the cycle. Returns the number of rows."""
    as_of = as_of_ts.astimezone(timezone.utc)
    orders = build_orders(conn, max_bronze_id)
    conn.execute("DELETE FROM gold.instruction_status")
    if not orders:
        return 0
    buses = sorted({o.bus_id for o in orders})
    stops = sorted({o.stop_id for o in orders})
    visits: dict[tuple[str, str], list[Visit]] = {}
    for bus, stop, arr, dep in conn.execute(_COMPLETED, {"buses": buses, "stops": stops}).fetchall():
        visits.setdefault((bus, stop), []).append(Visit(arr, dep))
    for bus, stop, arr in conn.execute(_OPEN, {"buses": buses, "stops": stops, "max_id": max_bronze_id,
                                               "as_of": as_of}).fetchall():
        visits.setdefault((bus, stop), []).append(Visit(arr, None))
    breakdowns: dict[str, list[datetime]] = {}
    for bus, start in conn.execute(_BREAKDOWNS, {"buses": buses}).fetchall():
        breakdowns.setdefault(bus, []).append(start)
    by_rec = {o.rec_id: o for o in orders}
    outcomes = observe(orders, visits, breakdowns, as_of)
    with conn.cursor() as cur:
        for out in sorted(outcomes, key=lambda x: x.rec_id):
            o = by_rec[out.rec_id]
            cur.execute(_INSERT, (out.rec_id, o.bus_id, o.stop_id, o.hold_s, out.observed_dwell_s, out.status,
                                  Jsonb({out.status: _rfc3339(out.ts)}), RULES_VERSION, max_bronze_id))
    return len(outcomes)
