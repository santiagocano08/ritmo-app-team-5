# Data Model: Data Fixes and Boarding-Probability Metrics

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Research**: [research.md](research.md)

Everything here lives in PostgreSQL schemas `config`, `silver` and `gold`, created or altered by
`src/data/db/init/008_data_fixes_metrics.sql` (idempotent). Bronze is not touched (insert-only, ADR-0001). Owner of every
object: the data layer (CODEOWNERS data owner). Times are `timestamptz` in UTC; "local" is the fixed UTC−5 offset of
`src/data/rules/timebands.py`; `band` is `timebands.m2_band` (0–95), `local_date` is `timebands.local_date`.

## Entity overview

| ID | Object | Kind | Change | Phase |
|---|---|---|---|---|
| E1 | `data/reference/congestion_factor.csv` → `config.ref_congestion_factor` | reference | values regenerated (rotated by 5 rows) | 1 |
| E2 | `config.corridor_settings.min_stop_headways` | config | new column | 2 |
| E3 | `silver.stop_visits.estimated_at_departure` | silver | new column, new index | 2 |
| E4 | `gold.service_metric` | gold | same columns, new definition | 2 |
| E5 | `gold.service_metric_stop` | gold | new table | 2 |
| E6 | `gold.stop_ewt_band` | gold | new table | 2 |
| E7 | `gold.stop_boarding_band` | gold | new table | 3 |
| E8 | `gold.stop_boarding_band_v` | gold view | new | 3 |
| E9 | `silver.position_history`, `silver.bus_current_state` | silver | filter and flags | 4 |
| E10 | pure types in `src/data/rules/` | code | new | 1–4 |

## E1 — Congestion factor by local hour (US1)

| Column | Type | Rule |
|---|---|---|
| `hour` | smallint 0–23 | **local** hour (UTC−5) |
| `congestion_factor` | numeric > 0 | `round(mean(VELOCIDAD of the rows whose local hour = h) / free_flow_kmh, 4)` |

Derivation: `FECHAHORA` (UTC, all 109,085 rows end in `Z`) → local hour with `timebands.local_hour_band`; free flow is the
length-weighted mean of `v_libre_kmh` (unchanged). Invariant (checked once in Phase 1 against the file in git and by the
data owner's verifier; no frozen copy is kept): factor(h) = old factor((h + 5) mod 24). Values:
17 h = 0.4816, 18 h = 0.4575 (slowest), 03 h = 0.5656 (highest). No schema change; the simulator and M1 read it by local hour as before (FR-013).

## E2 — `config.corridor_settings.min_stop_headways`

| Column | Type | Default | Rule |
|---|---|---|---|
| `min_stop_headways` | int NOT NULL, `CHECK (min_stop_headways >= 1)` | 5 | minimum number of stop headways for the corridor EWT to be `computable` (R6) |

## E3 — `silver.stop_visits` (S4) with the departure-quality flag

Existing columns unchanged (`bus_id`, `trip_id`, `stop_id`, `arrival_ts`, `departure_ts`, `dwell_s`, `boarded`,
`alighted`, `rejected`; PK `(bus_id, trip_id, stop_id)`).

| New column | Type | Rule |
|---|---|---|
| `estimated_at_departure` | boolean NOT NULL DEFAULT false | true when the bus's previous report (any of `bus_position`, `stop_arrival`, `stop_departure`; non-backend; `id <= M`; strictly earlier distinct `event_ts`) is more than `ESTIMATED_AFTER_S` (120 s, parameter `estimated_after_s`) before `departure_ts`. No earlier report: false |

New index `silver_stop_visits_stop_dep_idx ON silver.stop_visits (stop_id, departure_ts)`.
Rebuilt every cycle with the rest of silver; no lineage columns (silver has none).

## E4 — `gold.service_metric` (G4, unchanged shape, new meaning)

Columns as today: `snapshot_id` (PK, FK to `gold.snapshots`), `n_headways`, `mean_wait_s`, `scheduled_wait_s`, `ewt_s`,
`computable`, `rules_version`, `max_bronze_id`. One row per snapshot.

| Column | New definition |
|---|---|
| `n_headways` | Σ over stops of the stop headways whose closing departure is in `(as_of_ts − 15 min, as_of_ts]` and not excluded |
| `mean_wait_s` | `Σh² / (2Σh)` over those headways; NULL when not computable |
| `scheduled_wait_s` | `Σhp² / (2Σhp)`, `hp` = `config.corridor_settings.headway_planned_s` (600), one per headway; NULL when not computable |
| `ewt_s` | `mean_wait_s − scheduled_wait_s`; NULL when not computable. Can be negative (better than planned) |
| `computable` | `n_headways >= min_stop_headways AND Σh > 0` |

Rounded to 3 decimals as before. Per-snapshot sums come from E5, so E4 and E5 cannot disagree.

## E5 — `gold.service_metric_stop` (new, per snapshot and stop)

| Column | Type | Rule |
|---|---|---|
| `snapshot_id` | uuid, FK `gold.snapshots` | part of PK |
| `stop_id` | text | every stop of `config.ref_stops` (18), part of PK |
| `n_headways` | int ≥ 0 | headways in the trailing window, not excluded |
| `sum_headway_s` | numeric ≥ 0 | Σh |
| `sum_headway_sq_s` | numeric ≥ 0 | Σh² |
| `sum_planned_s` | numeric ≥ 0 | Σhp = n · planned |
| `sum_planned_sq_s` | numeric ≥ 0 | Σhp² = n · planned² |
| `n_excluded` | int ≥ 0 | headways in the window dropped because either departure had `estimated_at_departure` |
| `computable` | boolean | `n_headways >= 1` (a stop with fewer than two usable departures is not computable, never 0) |
| `rules_version`, `max_bronze_id` | text, bigint NOT NULL | lineage |

Append-only with the snapshot (same pattern as `service_metric`). About 9,700 rows for a demo run (540 snapshots × 18).

## E6 — `gold.stop_ewt_band` (new, closed 15-minute local bands)

| Column | Type | Rule |
|---|---|---|
| `local_date` | date | local date of the band |
| `band` | smallint 0–95 | PK part |
| `stop_id` | text | PK part |
| `n_headways`, `sum_headway_s`, `sum_headway_sq_s`, `sum_planned_s`, `sum_planned_sq_s`, `n_excluded` | as E5 | headways whose **closing departure** falls in the band |
| `rules_version`, `max_bronze_id` | text, bigint NOT NULL | lineage of the cycle that wrote the row |

PK `(local_date, band, stop_id)`. A band is **closed** when its end (UTC) is at or before the cycle's `as_of_ts`. Only
closed bands have rows. A row exists for a stop that has at least one candidate headway (counted or excluded) in the band;
no row means zeros. The whole table is deleted and rebuilt each cycle from `silver.stop_visits`, like `m1_baseline`, so the
same bronze gives the same rows (SC-005, SC-011 analogue).

## E7 — `gold.stop_boarding_band` (new, additive counts)

| Column | Type | Rule |
|---|---|---|
| `local_date`, `band`, `stop_id` | date, smallint, text | PK; the band of the rider's **arrival** (local time) |
| `n_riders` | int ≥ 0 | `rider_arrival` events at the stop in the band with `event_ts <= as_of`, open ones included |
| `n_board_le_5` | int ≥ 0 | riders whose next departure from the stop is at most 300 s after arrival |
| `n_board_le_10` | int ≥ 0 | … at most 600 s |
| `n_board_le_15` | int ≥ 0 | … at most 900 s |
| `rules_version`, `max_bronze_id` | text, bigint NOT NULL | lineage |

`CHECK (n_board_le_5 <= n_board_le_10 AND n_board_le_10 <= n_board_le_15 AND n_board_le_15 <= n_riders)`.
Rows exist for (stop, band) pairs with at least one rider, including the band that contains `as_of_ts` (it is open;
its counts can still rise as departures happen). Deleted and rebuilt each cycle.

**Rider rule.** For a rider at stop `s` arriving at `a`: `d` = the smallest `departure_ts` in `silver.stop_visits` at `s` with
`a <= d <= as_of_ts`. If `d` exists and `d − a <= t` the rider counts in `n_board_le_t`. If no `d` exists the rider counts
only in `n_riders` (open, or never served). A rider at a stop outside `config.ref_stops` counts nowhere.

## E8 — `gold.stop_boarding_band_v` (new view)

All columns of E7 plus:

| Column | Rule |
|---|---|
| `band_start_ts`, `band_end_ts` | UTC instants of the band |
| `closed` | `band_end_ts <=` the `as_of_ts` of the newest snapshot |
| `final` | `band_end_ts + 15 min <=` the `as_of_ts` of the newest snapshot: every rider of the band has had the 15 minutes the largest `t` needs |

No snapshot yet: `closed` and `final` are false. Read queries are in [contracts/gold-stop-metrics.md](contracts/gold-stop-metrics.md).

## E9 — silver rules for impossible positions and untrusted buses (US5, US6)

- `silver.position_history`: only `bus_position` rows with `0 <= distance_along_m <= route_end` (`route_end` =
  `max(config.ref_stops.distance_along_m)`, 5,119.4 m).
- `silver.bus_current_state`: the position columns (`distance_along_m`, `position_ts`, `position_trip_id`, `prev_stop_id`,
  `next_stop_id`) and the waiting test come from the newest **in-range** position. `data_quality` is `estimated` when any of
  these holds: (a) the newest report is older than `estimated_after_s` (as today); (b) the bus's newest `bus_position` report
  by `(event_ts, id)` is out of range; (c) `bus_id` is in the new parameter `untrusted_buses` (text array, empty by default).
  `last_report_ts` is unchanged, so `sources_down.since` is the last report time.
- `rebuild_silver(conn, as_of_ts, max_bronze_id, untrusted_buses=())` and `run_cycle(..., untrusted_buses=frozenset())`
  gain the optional argument; the compute CLI passes none.

## E10 — pure types (no I/O), `src/data/rules/`

| Module | Types and functions (signatures only) |
|---|---|
| `headway.py` | `BusObs.departure_ts: datetime \| None`; `pass_time(history, distance_m, origin_m=0.0, departure_ts=None)`; `headway_s(..., ahead_departure_ts=None, origin_m=0.0)` |
| `stop_metrics.py` | `Departure(stop_id, bus_id, trip_id, ts, estimated)`; `StopSums(n, sum_h, sum_h2, n_excluded)`; `stop_intervals(departures) -> list[Interval]`; `window_sums(departures, lo, hi) -> StopSums` (closing departure in `(lo, hi]`); `band_sums(departures, as_of) -> dict[(local_date, band), StopSums]` (closed bands only); `add(a, b)` |
| `service_metric.py` | `ServiceMetric` (as today); `service_metric(n, sum_h, sum_h2, planned_s, min_headways) -> ServiceMetric`; `ewt_from_sums(...)` |
| `boarding.py` | `wait_s(arrival, departures_sorted, as_of) -> float \| None`; `count_riders(arrivals, departures_by_stop, as_of, local band function) -> dict[(local_date, band, stop), BoardCounts]` with `BOARDING_THRESHOLDS_S = (300, 600, 900)` |
| `clock.py` | `ClockDecision(as_of: datetime \| None, untrusted: frozenset[str])`; `trusted_clock(latest_by_bus: Mapping[str, datetime], limit_s) -> ClockDecision` with `MIN_BUSES_FOR_CLOCK_GUARD = 2` |

All are deterministic; the planned headway, the minimum count and the thresholds are arguments or named constants, never
inline literals in SQL or pipeline code (`ESTIMATED_AFTER_S` stays the single 120 s value).

## State and derivation rules (summary)

| Question | Rule |
|---|---|
| Which band owns a stop headway? | The band of the **closing** (later) departure, local time |
| When is a headway excluded? | Either departure has `estimated_at_departure`; counted in `n_excluded` |
| When is a band closed? | `band_end <= as_of_ts` |
| When is a boarding band final? | `band_end + 15 min <= newest snapshot as_of_ts` |
| Corridor EWT from stops? | Sum the stop sums, then apply the formulas (never average stop EWTs) |
| Not computable? | Stop: `n_headways < 1`. Corridor row: `n_headways < min_stop_headways` or `Σh = 0`. Values NULL, never 0 |
| Which bus is untrusted by the clock? | Newest report (by arrival) more than 120 s ahead of `median_low` of the other buses' newest; fewer than 2 buses reporting: nobody |
| What does an unplaceable bus look like? | `estimated`, last valid position kept (or none), in `sources_down`, state `regular` |

## Lineage

Every new gold row stores `rules_version` and `max_bronze_id` of the cycle that wrote it (ADR-0001). A band or boarding row
therefore traces to the bronze events with `id <= max_bronze_id` and to the rules version. Per-snapshot rows also carry the
`snapshot_id`. Rows are not versioned per range of bronze events (a range per band would need a second column; deferred with the history layer).

## Contract and fixtures impact

`contracts/` is untouched. `gold.service_metric` is not a read-contract object (plain columns, data-contract Q4), so no JSON
Schema changes. The read fixtures in `contracts/read/fixtures/` have no `service_metric` file and stay as they are.
