"""Stop-based EWT rows (005 US3; research R4, R5; data-model E4-E6).

Orchestration only: reads `silver.stop_visits` (restricted to the stops of `config.ref_stops`) and `config`,
calls the pure rules in `src/data/rules/stop_metrics.py` and `service_metric.py`, and writes gold in the
caller's transaction. The planned headway and the minimum sample come from `config.corridor_settings`.
Parameterized SQL only; bronze is never touched.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import psycopg

from src.data.rules import RULES_VERSION
from src.data.rules.service_metric import ServiceMetric, service_metric
from src.data.rules.stop_metrics import ZERO, Departure, add, band_sums, window_sums_by_stop
from src.data.rules.timebands import WINDOW


def _utc(value: datetime) -> datetime:
    return value.astimezone(timezone.utc)


def read_departures(cur: psycopg.Cursor) -> list[Departure]:
    """Departures of this cycle's silver at the reference stops."""
    rows = cur.execute(
        "SELECT v.stop_id, v.bus_id, v.trip_id, v.departure_ts, v.estimated_at_departure "
        "FROM silver.stop_visits v JOIN config.ref_stops r ON r.stop_id = v.stop_id "
        "ORDER BY v.stop_id, v.departure_ts, v.bus_id, v.trip_id").fetchall()
    return [Departure(r[0], r[1], r[2], _utc(r[3]), bool(r[4])) for r in rows]


def _planned_sums(n: int, planned: Decimal) -> tuple[Decimal, Decimal]:
    return n * planned, n * planned * planned


def insert_snapshot_rows(snapshot_cur: psycopg.Cursor, snapshot_id: UUID, as_of: datetime, planned_s: Decimal,
                         min_headways: int, max_bronze_id: int) -> ServiceMetric:
    """Write one `gold.service_metric_stop` row per reference stop for the trailing window `(as_of - 15 min, as_of]`
    and return the corridor metric computed from the **sum of the stop sums** (never an average of stop EWTs).

    Uses its own plain cursor on the caller's connection (same transaction), so it does not depend on the row
    factory of the cursor it is called from."""
    with snapshot_cur.connection.cursor() as cur:
        return _insert_snapshot_rows(cur, snapshot_id, as_of, planned_s, min_headways, max_bronze_id)


def _insert_snapshot_rows(cur: psycopg.Cursor, snapshot_id: UUID, as_of: datetime, planned_s: Decimal,
                          min_headways: int, max_bronze_id: int) -> ServiceMetric:
    stops = [r[0] for r in cur.execute("SELECT stop_id FROM config.ref_stops ORDER BY stop_seq").fetchall()]
    per_stop = window_sums_by_stop(read_departures(cur), as_of - WINDOW, as_of)
    total = ZERO
    for stop in stops:
        s = per_stop.get(stop, ZERO)
        total = add(total, s)
        sum_p, sum_p2 = _planned_sums(s.n, planned_s)
        cur.execute(
            "INSERT INTO gold.service_metric_stop (snapshot_id, stop_id, n_headways, sum_headway_s, sum_headway_sq_s, "
            "sum_planned_s, sum_planned_sq_s, n_excluded, computable, rules_version, max_bronze_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (snapshot_id, stop, s.n, s.sum_h, s.sum_h2, sum_p, sum_p2, s.n_excluded, s.n >= 1,
             RULES_VERSION, max_bronze_id))
    return service_metric(total.n, total.sum_h, total.sum_h2, planned_s, min_headways)


def rebuild_ewt_bands(conn: psycopg.Connection, as_of_ts: datetime, max_bronze_id: int) -> None:
    """Replace `gold.stop_ewt_band` for this cycle: closed bands only, same lineage as the cycle (R5).

    Runs after the silver rebuild, in the caller's transaction, so the same bronze gives the same rows."""
    as_of = _utc(as_of_ts)
    with conn.cursor() as cur:
        planned = cur.execute("SELECT headway_planned_s FROM config.corridor_settings").fetchone()[0]
        bands = band_sums(read_departures(cur), as_of)
        cur.execute("DELETE FROM gold.stop_ewt_band")
        for (day, band, stop), s in sorted(bands.items()):
            sum_p, sum_p2 = _planned_sums(s.n, planned)
            cur.execute(
                "INSERT INTO gold.stop_ewt_band (local_date, band, stop_id, n_headways, sum_headway_s, "
                "sum_headway_sq_s, sum_planned_s, sum_planned_sq_s, n_excluded, rules_version, max_bronze_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (day, band, stop, s.n, s.sum_h, s.sum_h2, sum_p, sum_p2, s.n_excluded, RULES_VERSION,
                 max_bronze_id))
