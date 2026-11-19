# Data Model — Silver and Gold Layers with M1/M2 Baselines

**Feature**: 002-silver-gold-baselines | **Turn**: 1 (active) | **Date**: 2026-11-18

This document describes the tables this feature adds and how they derive from bronze. The read
objects keep the exact shape of `contracts/read/*.schema.json` v1.0.0; this document does not
redefine them. Bronze (`bronze.events`, `bronze.rejections`) is unchanged and is only read
(FR-002). The DDL below is a sketch for review; the init scripts in the implementation are the
source of truth.

New init scripts, all idempotent (`IF NOT EXISTS`) and applied after the 001 scripts:

| Script | Content |
|---|---|
| `db/init/003_config.sql` | `config` schema (DECIDED, R11; ADR-0001 addendum), static settings and their seed values, empty reference tables |
| `db/init/004_silver.sql` | silver tables |
| `db/init/005_gold.sql` | gold tables |

Ownership (Principle II): every table below is owned by the **data** module (CODEOWNERS on
`src/rules/`, `db/`). The backend only reads gold (ADR-0003).

---

## Layer flow

```
bronze.events (insert-only, 001)
   │   one REPEATABLE READ transaction per cycle; reads id <= M, event_ts <= as_of_ts
   ▼
silver.*  (deleted and rebuilt each cycle — R2)
   │
   ├─► gold.m1_baseline, gold.m2_baseline  (replaced each cycle)
   ▼
gold.snapshots ──┬─ gold.source_status
                 ├─ gold.corridor_now
                 ├─ gold.decision_inputs
                 └─ gold.service_metric      (append-only, one set per snapshot)
   │
   └─► pg_notify('gold_snapshot', {"snapshot_id": …})  delivered at COMMIT
```

`config.*` is read by every step and is never derived.

---

## C — Static configuration and reference tables (`config` schema, R11 DECIDED)

### C1 `config.corridor_settings` (one row; seeded by `003_config.sql`)

| Column | Type | Seed value | Source |
|---|---|---|---|
| `corridor_id` | TEXT PK | `'C6-008'` | FR-019 |
| `direction` | SMALLINT CHECK (=1) | `1` | FR-019 |
| `headway_planned_s` | NUMERIC > 0 | `600` | FR-021 |
| `drivers_free` | INT ≥ 0 | `2` | FR-034, Clarifications |
| `hold_penalty_s` | NUMERIC ≥ 0 | `0` | FR-034 |
| `early_departure_penalty_s` | NUMERIC ≥ 0 | `0` | FR-034 |
| `min_sample_count` | INT ≥ 1 | `5` | FR-028 (M1 and M2) |
| `m2_stop_id` | TEXT | `'P-883'` | FR-030 |

All values are provisional and owned by the backend/decision-engine owner (spec Assumptions).
`headway_planned_s` (600) is read by the gold rules. The simulator reads its own
`SIM_PLANNED_HEADWAY_S` (default 600, R14); a Phase 0 test asserts that the two are equal.

### C2 `config.fleet_roster`

| Column | Type | Seed |
|---|---|---|
| `bus_id` | TEXT PK | B-101..B-107 |
| `role` | TEXT CHECK IN (`in_service`,`reserve`) | B-101..B-105 `in_service`; B-106, B-107 `reserve` |

### C3 `config.enabled_stops`

| Column | Type | Seed |
|---|---|---|
| `stop_id` | TEXT PK | P-883..P-900 (all 18 stops, FR-034) |

### C4 Reference tables (loaded from `data/reference/` by `src/pipeline/reference.py`)

Loaded at refresh-loop or compute start, and by the test template database, with `DELETE` +
`INSERT` in one transaction. The rows are exactly the CSV contents.

| Table | Columns | CSV |
|---|---|---|
| `config.ref_stops` | `stop_seq` (1..18, file order), `stop_id` PK, `distance_along_m`, `segment_id` | `stops.csv` |
| `config.ref_segments` | `segment_id` PK (1..17), `length_m`, `free_flow_kmh` | `segments.csv` |
| `config.ref_congestion_factor` | `hour` PK (0..23), `congestion_factor` | `congestion_factor.csv` |
| `config.ref_demand_shape` | `hour` PK (0..23), `metro_line_a_shape` | `demand_params.csv` |
| `config.ref_demand_volume` | `daily_riders_dir1` (one row) | `demand_volume.csv` |

Segment *k* runs from `ref_stops.stop_seq = k` to `stop_seq = k+1` (FR-013). The terminus stop is
the row with the highest `stop_seq` (P-900).

---

## S — Silver (rebuilt each cycle; derived only from bronze + `config`)

Common input: a *bus report* is a bronze row with `event_type IN ('bus_position','stop_arrival',
'stop_departure')` and `source <> 'backend'` (FR-007). Every silver query also applies
`id <= M AND event_ts <= as_of_ts` (R4).

### S1 `silver.position_history`

One row per `bus_position` bronze row, the input to headway (FR-020).

| Column | Type | From |
|---|---|---|
| `bronze_id` | BIGINT PK | `bronze.events.id` |
| `bus_id`, `trip_id` | TEXT | payload |
| `event_ts` | TIMESTAMPTZ | envelope |
| `distance_along_m` | NUMERIC | payload |

Index `(bus_id, trip_id, event_ts, bronze_id)`.

### S2 `silver.incidents` (FR-015)

| Column | Type | Rule |
|---|---|---|
| `inc_id` | UUID PK | `event_id` of the `incident_report` |
| `incident_type` | TEXT | payload `incident_type` |
| `target_id` | TEXT | payload |
| `start_ts` | TIMESTAMPTZ | `event_ts` |
| `end_ts` | TIMESTAMPTZ | `event_ts + duration_min * interval '1 minute'` |
| `reported_by` | TEXT | payload |
| `source` | TEXT | envelope (`simulator`/`script`/`backend`) |
| `bronze_id` | BIGINT | lineage |

Active at T ⇔ `start_ts <= T < end_ts` (R7).

### S3 `silver.bus_current_state` (FR-008 – FR-011)

One row per bus that has at least one bus report.

| Column | Type | Rule |
|---|---|---|
| `bus_id` | TEXT PK | |
| `trip_id` | TEXT | trip of the latest bus report by `(event_ts, id)` |
| `distance_along_m` | NUMERIC NULL | latest `bus_position` by `(event_ts, id)` (FR-008); never extrapolated (FR-010) |
| `position_ts` | TIMESTAMPTZ NULL | its `event_ts` → `corridor_now.ts` |
| `position_trip_id` | TEXT NULL | its `trip_id` |
| `prev_stop_id`, `next_stop_id` | TEXT NULL | R7 rule over `config.ref_stops` |
| `last_report_ts` | TIMESTAMPTZ | max `event_ts` of bus reports → `sources_down.since` |
| `data_quality` | TEXT CHECK IN (`live`,`estimated`) | `estimated` ⇔ `as_of_ts − last_report_ts > 120 s` (strict) |
| `on_corridor` | BOOLEAN | current trip has no `stop_arrival` at the terminus stop |
| `operational_status` | TEXT CHECK IN (`in_service`,`reserve`,`broken_down`,`off_corridor`) | R7 precedence |
| `as_of_ts` | TIMESTAMPTZ | cycle reference time |

State transition per bus, evaluated fresh each cycle:

```
             last report age > 120 s
   live ─────────────────────────────► estimated
     ▲                                    │
     └──────── new bus report ────────────┘   (next cycle)
```

`estimated` never creates an incident, a `broken_down` state or a count (FR-011). The suppression
itself is applied in gold (G3).

### S4 `silver.stop_visits` (FR-012)

| Column | Type | Rule |
|---|---|---|
| `bus_id`, `trip_id`, `stop_id` | TEXT, PK together | pairing key |
| `arrival_ts`, `departure_ts` | TIMESTAMPTZ | from `stop_arrival` / `stop_departure` |
| `dwell_s` | NUMERIC | `departure_ts − arrival_ts` |
| `boarded`, `alighted`, `rejected` | INT | from the `stop_departure` payload (R7) |

A row exists only when both events exist.

### S5 `silver.segment_traversals` (FR-013, FR-014)

| Column | Type | Rule |
|---|---|---|
| `bus_id`, `trip_id`, `segment_id` | PK together | segment *k* = stop_seq *k* → *k+1* |
| `departure_ts` | TIMESTAMPTZ | `stop_departure` at stop *k* |
| `arrival_ts` | TIMESTAMPTZ | `stop_arrival` at stop *k+1*, same trip |
| `travel_s` | NUMERIC | `arrival_ts − departure_ts` |
| `hour_band` | SMALLINT 0..23 | local hour (America/Bogotá) of `departure_ts` (FR-026) |
| `travelled_while_estimated` | BOOLEAN | any consecutive bus-report gap > 120 s within `[departure_ts, arrival_ts]` |
| `broken_down` | BOOLEAN | a `bus_breakdown` incident for the bus overlaps the interval |

No row until the arrival at *k+1* exists (edge case). Eligible for M1 ⇔ both flags false.

---

## G — Gold

All gold rows carry `rules_version TEXT NOT NULL` and `max_bronze_id BIGINT NOT NULL` (FR-017,
SC-008). An empty bronze gives `max_bronze_id = 0`.

### G1 `gold.snapshots` (append-only, FR-016)

| Column | Type | Rule |
|---|---|---|
| `snapshot_id` | UUID PK | deterministic, version-4 bits (R5) |
| `as_of_ts` | TIMESTAMPTZ | cycle reference time (FR-004) |
| `rules_version`, `max_bronze_id` | | lineage |

Unique `(as_of_ts, rules_version, max_bronze_id)`. The latest snapshot is the one with the highest
`as_of_ts`. No retention in turn 1.

### G2 `gold.source_status`, `gold.corridor_now`, `gold.decision_inputs` (append-only)

One row per snapshot each, with `snapshot_id` PK/FK → `gold.snapshots`, `doc JSONB NOT NULL`
holding the object exactly as its schema defines it (FR-018, FR-019, FR-032, FR-025), plus
`rules_version` and `max_bronze_id`. `doc->>'snapshot_id'` and `doc->>'as_of_ts'` equal the
snapshot row. `gold.source_status` also stores `status` as a column for cheap reads.

### G3 Rules that build the read objects (Python, `src/rules/`)

Input: the silver rows of buses with `on_corridor = true`, ordered by `distance_along_m` DESC, ties
by `bus_id` ASC (FR-019).

1. **Headway** (FR-020, R8): for each bus that is not broken down, the nearest *operational* bus
   ahead (skipping broken-down buses) gives `pass_time` by interpolation over its S1 history on its
   current trip. `headway_ahead_s = position_ts − pass_time`, clamped at 0 (R8, DECIDED). It is 0 for
   an equal distance, `null` for the leader and for broken-down buses.
2. **State** (FR-022), first match wins: `broken_down` → `leader` (furthest-ahead operational bus)
   → `bunched` (`h < 0.5 × planned`) → `gap` (`h > 1.5 × planned`) → `regular`.
3. **FR-011 suppression**: if a bus is Estimated, that bus and the bus whose bus-ahead is it get
   `regular` instead of `bunched`/`gap`. `leader` and `broken_down` are unchanged. This applies to
   consecutive Estimated buses too (edge case).
4. **Summary** (FR-023): `buses_in_service` = entries not `broken_down`. `n_bunched`/`n_gaps` =
   counts of entries in those states.
5. **source_status** (FR-018): `no_data` if bronze (≤ M) has no bus report at all. `estimated` if
   any on-corridor bus is Estimated. `live` otherwise. `sources_down` = on-corridor Estimated buses
   ordered by `bus_id`, `since = last_report_ts`.
6. **decision_inputs** (FR-032, FR-033): `buses`/`summary` are the same Python objects as
   `corridor_now`. `travel_time_forecast` = 17 rows of `gold.m1_baseline` for the local hour of
   `as_of_ts`, ordered by `segment_id`. `demand_15min` = `gold.m2_baseline` for the next window
   (R13, DECIDED). `resources.reserve_free` = roster `reserve` buses not on the corridor, ordered.
   `drivers_free`, `action_cost`, `enabled_stops` come from `config`. `active_incidents` = S2 rows
   active at `as_of_ts`, ordered by `inc_id`.

Every list has a fixed order, so the stored JSON is byte-stable (FR-005).

### G4 `gold.service_metric` (FR-024; one row per snapshot)

| Column | Type | Rule |
|---|---|---|
| `snapshot_id` | UUID PK/FK | |
| `n_headways` | INT | number of non-null headways of operational buses |
| `mean_wait_s` | NUMERIC NULL | Σh² ÷ (2·Σh) |
| `scheduled_wait_s` | NUMERIC NULL | Σhp² ÷ (2·Σhp) over the same buses |
| `ewt_s` | NUMERIC NULL | `mean_wait_s − scheduled_wait_s` |
| `computable` | BOOLEAN | false when `n_headways = 0` or Σh = 0; the three values are then NULL |
| `rules_version`, `max_bronze_id` | | lineage |

Worked examples (SC-007): headways {300, 900} → 375 s and EWT 75 s; four × 600 → 300 s and EWT 0.

### G5 `gold.m1_baseline` (FR-026 – FR-029; 17 × 24 = 408 rows, replaced each cycle)

| Column | Type | Rule |
|---|---|---|
| `segment_id` | SMALLINT 1..17 | PK with `hour_band` |
| `hour_band` | SMALLINT 0..23 | |
| `forecast_travel_s` | NUMERIC ≥ 0 | `percentile_cont(0.5)` of eligible S5 `travel_s` when `n_samples >= min_sample_count`; otherwise `length_m / (free_flow_kmh / 3.6) / congestion_factor(hour_band)` |
| `source` | TEXT CHECK IN (`observed`,`reference`) | |
| `n_samples` | INT ≥ 0 | eligible traversals, also recorded when the source is `reference` |
| `rules_version`, `max_bronze_id` | | |

### G6 `gold.m2_baseline` (FR-030, FR-031; 96 rows, replaced each cycle)

| Column | Type | Rule |
|---|---|---|
| `band` | SMALLINT 0..95 PK | local `hour × 4 + minute div 15` |
| `stop_id` | TEXT | `config.corridor_settings.m2_stop_id` (P-883) |
| `arrivals_forecast` | INT ≥ 0 | median of per-day counts when `n_samples >= min_sample_count`, rounded half away from zero (R13, DECIDED; `round(...::numeric)`); otherwise `round(daily_riders_dir1 × metro_line_a_shape(hour) / 4)` with the same rounding |
| `source` | TEXT | `observed` / `reference` |
| `n_samples` | INT | qualifying (local date, band) samples (R12, DECIDED): the band has ended (`band_end <= as_of_ts`) and holds at least one non-backend `bus_position`; the sample value is the count of `rider_arrival` at the M2 stop in that band, possibly 0 |
| `rules_version`, `max_bronze_id` | | |

---

## Invariants checked by tests

| Invariant | Spec |
|---|---|
| No `INSERT`/`UPDATE`/`DELETE`/`TRUNCATE` targets `bronze.` in `src/rules/`, `src/pipeline/`, `src/refresh/` (static guard) | FR-002 |
| Same bronze + `as_of_ts` + `rules_version` → byte-identical silver and gold rows | FR-005, SC-004 |
| Drop and recreate silver and gold, recompute at the same `as_of_ts` → identical | SC-005 |
| Every gold row has non-null lineage; the five gold rows of a cycle share `snapshot_id` | SC-008 |
| `decision_inputs.doc.buses == corridor_now.doc.buses` and the same for `summary` | FR-032, SC-008 |
| Every stored `doc` validates against its JSON Schema | SC-001 |
| Each M1/M2 value equals an independent oracle | SC-006 |
