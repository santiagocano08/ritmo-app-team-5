# Contract: projection record and accuracy (phase 2b, FR-035, FR-036, SC-016)

Design note for review. The executable parts are `src/data/db/init/009_decision_mpc.sql` (Phase 2b section) and the tests named in `tasks.md` T049a to T049g. `docs/data-contract.md` is not edited by this story; the data owner writes its lines (marked `[006]`).

## `gold.mpc_projection` (append-only)

One row per (snapshot, bus, stop) of the "do nothing" projection, written by the recommend step in the cycle transaction.

| Column | Type | Note |
|---|---|---|
| `snapshot_id` | UUID | FK `gold.snapshots`; PK part 1 |
| `bus_id` | TEXT | PK part 2 |
| `stop_id` | TEXT | PK part 3 |
| `as_of_ts` | TIMESTAMPTZ | cycle reference time |
| `projected_departure_ts` | TIMESTAMPTZ | `as_of_ts` + `lead_s` |
| `lead_s` | NUMERIC, 0..1800 | projected departure − `as_of_ts` |
| `rules_version` | TEXT | |
| `max_bronze_id` | BIGINT | |

Rules: never updated or deleted by code; no row when the model is off (`MPC_ENABLED=off`), the snapshot is older than 15 s, or no bus has reported yet; rows are written also in cycles with no candidate; same bronze and rules give identical rows.

## `gold.v_projection_accuracy` (view)

Columns: `snapshot_id`, `bus_id`, `stop_id`, `as_of_ts`, `projected_departure_ts`, `lead_s`, `lead_bucket` (`0-5 min`, `5-10 min`, `10-30 min`), `actual_departure_ts`, `error_s` (real − projected, seconds), `abs_error_s`, `affected_by_decision`, `rules_version`, `max_bronze_id`.

- **Real departure**: first `silver.stop_visits.departure_ts` of the bus at the stop with `departure_ts ≥ as_of_ts`. If that visit is an estimated departure, or there is none yet, `actual_departure_ts` and both errors are NULL (never 0).
- **`affected_by_decision`**: an `applied` recommendation for the same bus whose decision time (`gold.recommendation.close_ts`) is after `as_of_ts` and, when the real departure exists, not after it. Effects of an action on other buses are not flagged (research R17).

## Aggregate query for SC-016

Per lead bucket, excluding `affected_by_decision` and rows without a real departure. The test of T049e runs this text unchanged. Add `AND a.as_of_ts >= ... AND a.as_of_ts < ...` inside the join condition to restrict it to a shift or a run.

```sql
SELECT b.lead_bucket,
       count(a.error_s)                                                          AS n_compared,
       round(avg(a.abs_error_s), 1)                                              AS mae_s,
       round((percentile_cont(0.5) WITHIN GROUP (ORDER BY a.abs_error_s))::numeric, 1) AS median_abs_error_s,
       max(a.abs_error_s)                                                        AS worst_abs_error_s,
       round(avg(a.error_s), 1)                                                  AS mean_error_s
FROM (VALUES ('0-5 min', 1), ('5-10 min', 2), ('10-30 min', 3)) AS b(lead_bucket, ord)
LEFT JOIN gold.v_projection_accuracy a
       ON a.lead_bucket = b.lead_bucket
      AND NOT a.affected_by_decision
      AND a.error_s IS NOT NULL
GROUP BY b.lead_bucket, b.ord
ORDER BY b.ord;
```

`n_compared` is 0 and the statistics are NULL for a bucket with nothing to compare. `mean_error_s` (the bias, positive when buses leave later than projected) is an extra column; SC-016 asks for the count, the mean absolute error, the median and the worst error.

## Worked example

A row projected at `as_of_ts = 17:00:00Z` for bus B-103 at P-890 with `lead_s = 420` (projected departure 17:07:00Z). The bus's first departure from P-890 at or after 17:00:00Z is 17:07:35Z, not estimated. Then `lead_bucket = '5-10 min'`, `error_s = 35`, `abs_error_s = 35`. If an `apply` of a hold on B-103 was decided at 17:03:00Z, `affected_by_decision` is true and the row is left out of the aggregate. If B-103 has not departed yet, `error_s` is NULL and the row is not counted.
