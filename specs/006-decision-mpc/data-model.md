# Data Model: Decision Model (Simulation-Based MPC)

**Feature**: `specs/006-decision-mpc` | **Date**: 2026-11-22

Owner of every object below: the data layer (`src/data/pipeline/`, `src/data/rules/`). All DDL is in `src/data/db/init/009_decision_mpc.sql`, idempotent (`IF NOT EXISTS`, `OR REPLACE`), with one section per phase (2, 2b, 4, 6). An existing volume does not re-run init scripts: apply the file by hand (quickstart.md). Every derived row carries `rules_version` and `max_bronze_id` (ADR-0001). Bronze is not touched.

Naming follows the repository: tables in lower snake case; `doc` columns hold exactly the JSON Schema object.

## Summary of objects

| Id | Object | Kind | Phase | Rebuilt |
|---|---|---|---|---|
| M1 | `config.decision_model` | config, 1 row | 1 (values), 6 (trend columns, optional) | static |
| M2 | `config.ref_train_arrival` | reference | 2 | at reference load |
| M3 | `silver.stop_queue` | silver | 2 | every cycle (DELETE + INSERT) |
| M4 | `silver.bus_current_state.occupancy` | silver column | 2 | every cycle |
| M5 | `gold.recommendation` | gold, state | 2 | upsert every cycle |
| M6 | `gold.mpc_evaluation` | gold, diagnostic | 2 | replaced every cycle |
| M7 | `gold.decision_log` | gold | 4 | replaced every cycle |
| M8 | In-memory projection types | not stored | 1 | per cycle |
| M9 | Removed: `config.seed_recommendation` | | 2 | dropped |
| M10 | `gold.mpc_projection` | gold, append-only | 2b | appended every cycle (never rewritten) |
| M11 | `gold.v_projection_accuracy` | gold, view | 2b | computed on read |

## M1. `config.decision_model` (one row)

Every model parameter. Source and owner are recorded per column in the DDL comments. Values are the data owner's declarations (spec Clarifications, Sessions 2026-11-21 and 2026-11-22) unless marked.

| Column | Type | Default | Source |
|---|---|---|---|
| `corridor_id` | TEXT PK | `C6-008` | |
| `scoring_window_s` | INT CHECK > 0 | 1800 | FR-005, Clarification 2026-11-21 |
| `horizon_s` | INT CHECK = 600 | 600 | FR-018, ADR-0007 (the CHECK pins it) |
| `step_s` | INT CHECK > 0 | 5 | simulator `STEP_S` (rounding grid) |
| `capacity` | INT CHECK > 0 | 40 | simulator `CAPACITY`, FR-005 |
| `threshold_s_per_rider` | NUMERIC CHECK ≥ 0 | 15 | FR-012 |
| `top_n` | INT CHECK BETWEEN 1 AND 3 | 3 | FR-012 |
| `reserve_ready_s` | INT CHECK ≥ 0 | 120 | declared assumption (data owner) |
| `reserve_cost_s` | NUMERIC CHECK ≥ 0 | 900 | declared (data owner) |
| `slow_duration_s` | INT CHECK > 0 | 300 | declared (data owner) |
| `slow_shares` | NUMERIC[] | `{0.10,0.20}` | FR-008; published as `action.speed_reduction_pct = share × 100` (10, 20) |
| `hold_options_s` | INT[] | `{30,60,90}` | FR-008, each ≤ 90 (CHECK) |
| `adjust_options_s` | INT[] | `{-120,-60,60,120}` | FR-008 |
| `skip_reach_stops` | INT CHECK > 0 | 4 | prototype reach, declared here |
| `queue_trigger_riders` | INT CHECK > 0 | 20 | FR-008 (half a bus) |
| `proposal_ttl_s` | INT CHECK > 0 | 120 | FR-030 |
| `rest_s` | INT CHECK ≥ 0 | 300 | FR-030 |
| `freshness_max_s` | INT CHECK > 0 | 15 | FR-017, ADR-0006 |
| `rate_window_s` | INT CHECK > 0 | 1800 | FR-003 (30 minutes) |
| `train_share` | NUMERIC CHECK BETWEEN 0 AND 1 | 0.80 | `data/reference/SOURCES.md` assumption |
| `walk_mean_s` | INT CHECK ≥ 0 | 120 | mean of the simulator's walk (60 to 180 s) |
| `model_version` | TEXT | `1.0.0` | `lineage.model_version` |
| Phase 6 (optional): `trend_window_s` | INT | 900 | FR-031 |
| Phase 6 (optional): `trend_min_samples` | INT | 3 | FR-031 |
| Phase 6 (optional): `trend_ratio_min` / `trend_ratio_max` | NUMERIC | 0.7 / 1.5 | FR-031 |

`rules/mpc_params.py` has a frozen dataclass `MpcParams` with the same fields and these defaults, so pure tests need no database. `pipeline/recommend.py` reads the row and builds `MpcParams` from it. A test keeps the dataclass defaults equal to the DDL defaults (same pattern as `SIM_PLANNED_HEADWAY_S` and `headway_planned_s`).

## M2. `config.ref_train_arrival`

| Column | Type | Note |
|---|---|---|
| `arrival_sec` | INT PK-part | second of day, `< 86400` (the simulator ignores later rows) |
| `train_trip_id` | TEXT PK-part | |

511 rows from `data/reference/train_arrivals.csv`. Loaded by `pipeline/reference.py` (DELETE + INSERT in the same transaction as the other reference tables).

## M3. `silver.stop_queue`

One row per stop (18).

| Column | Type | Note |
|---|---|---|
| `stop_id` | TEXT PK | |
| `queue_riders` | INT CHECK ≥ 0 | rejected at the newest arrival + riders arrived since |
| `basis_ts` | TIMESTAMPTZ NULL | `event_ts` of that arrival (NULL: no arrival in the window) |
| `basis_bronze_id` | BIGINT | largest bronze id used (FR-004 traceability) |
| `as_of_ts` | TIMESTAMPTZ | cycle reference time |

Rule: R3 in research.md. SQL file `rules/sql/silver_stop_queue.sql` (CODEOWNERS), run last in the silver build order.

## M4. `silver.bus_current_state.occupancy`

`ALTER TABLE silver.bus_current_state ADD COLUMN IF NOT EXISTS occupancy INT` (NULL when no in-range position). Taken from the `bus_position.payload.occupancy` of the same row that gives `distance_along_m`.

## M5. `gold.recommendation`

One row per `rec_id`. Written only by `pipeline/recommend.py`. Never by the backend or the simulator.

| Column | Type | Mutable | Note |
|---|---|---|---|
| `rec_id` | UUID PK | no | R7 |
| `doc` | JSONB NOT NULL | yes | exactly `recommendation.schema.json` 1.1.0, validated with `RecommendationV110` before insert; `status` inside is the derived one |
| `key` | TEXT NOT NULL | no | `type|bus|stop|duration|speed_reduction_pct` (read from `doc.action`) |
| `case` | TEXT | no | copy of `doc.case`, for the log and filters |
| `status` | TEXT CHECK in (`proposed`,`applied`,`discarded`,`expired`) | yes | same value as `doc.status` (a CHECK keeps them equal) |
| `stale` | BOOLEAN | yes | still `proposed` but no longer in the top 3; DECIDED: it keeps its last rank and frozen numbers until it expires |
| `proposed_ts` | TIMESTAMPTZ | no | `as_of` of the first publication |
| `expires_ts` | TIMESTAMPTZ | no | `proposed_ts + proposal_ttl_s` |
| `close_ts` | TIMESTAMPTZ NULL | yes | `min(expires_ts, passed_ts)` once expired; decision time once decided; drives the rest rule |
| `first_snapshot_id` | UUID | no | snapshot of the first publication |
| `params` | JSONB NOT NULL | no | what the simulator needs and `doc` does not carry: `{"ready_s": 120}` for `reserve_dispatch`; `{}` for every other type. The slow-down intensity is **not** here: it is `doc.action.speed_reduction_pct` (decision 2) |
| `lineage_detail` | JSONB NOT NULL | yes | R10: parameters used, projector input, base score, riders, candidates, trend ratios |
| `rules_version` | TEXT | yes | |
| `max_bronze_id` | BIGINT | yes | |

Indexes: `(status, ((doc->>'rank')::int))` for Q13; `(key)` for matching and rest.

Status transitions (derived, never written from outside):

```text
proposed --first decision 'apply'------------> applied
proposed --first decision 'discard'----------> discarded
proposed --as_of > expires_ts or bus passed--> expired   (no decision)
applied / discarded / expired: terminal
```

A decision that arrives after expiry still gives `applied` or `discarded` (decision wins; 004's executor then reports `not_executed` with reason `expired`).

Reads: the console reads Q13 (`SELECT doc FROM gold.recommendation WHERE doc->>'status' = 'proposed' ORDER BY (doc->>'rank')::int`). The simulator reads `SELECT rec_id, doc, params FROM gold.recommendation WHERE rec_id = ANY(%s)` (read-only session).

## M6. `gold.mpc_evaluation`

Replaced every cycle. One row per evaluated candidate, plus the baseline. Empty when no action is a candidate.

| Column | Type | Note |
|---|---|---|
| `snapshot_id` | UUID | |
| `seq` | INT | order evaluated (catalog order, then bus, then stop) |
| `action` | JSONB | the doc's `action` object (type, bus, stop, duration, `speed_reduction_pct` for `slow_down`) |
| `case` | TEXT | trigger |
| `score_s` | NUMERIC | total passenger-seconds; the baseline row has `action = {"type": "none"}` |
| `saving_s_per_rider` | NUMERIC | |
| `recommended` | BOOLEAN | in this cycle's top 3 |
| `reason_not` | TEXT NULL | `below_threshold`, `resting`, `not_top_3`, `unsafe_target` |
| `rules_version`, `max_bronze_id` | | |

PK `(snapshot_id, seq)`. Used by tests (SC-003, SC-004, SC-005) and for explanation.

## M7. `gold.decision_log` (phase 4)

Exactly the columns of data contract v0.3 H2.

| Column | Type | Source |
|---|---|---|
| `rec_id` | UUID PK | `gold.recommendation` |
| `case` | TEXT | |
| `action` | JSONB | `doc.action` |
| `proposed_ts` | TIMESTAMPTZ | |
| `expires_ts` | TIMESTAMPTZ | |
| `outcome` | TEXT | `gold.recommendation.status` |
| `decided_ts` | TIMESTAMPTZ NULL | first decision's `payload.ts` |
| `user_id` | TEXT NULL | first decision's `payload.user_id` |
| `reason` | TEXT NULL | first decision's `payload.reason`, `NULLIF(btrim(...), '')`; copied, never used in a computation |
| `instruction_status` | TEXT NULL | `gold.instruction_status.status` |
| `effect_result` | TEXT NULL | NULL until the story-004 effect table exists |
| `rules_version`, `max_bronze_id` | | |

Index on `proposed_ts` (Q11 filter and order). Rebuilt by DELETE + INSERT after the recommendation step in the same transaction. Sorting for the insert is by `proposed_ts, rec_id`, so equal inputs give equal rows.

## M8. In-memory types (`rules/projector.py`, not stored)

- `BusState`: `bus_id`, `kind` (`service`, `waiting`, `reserve`), `distance_m`, `next_stop_idx`, `occupancy`, `at_stop` (arrival second and planned dwell, or none), `quality` (`live`/`estimated`), `broken_until` (or none), `slow` (share, until, or none), `holds` (stop → seconds), `skip_until`.
- `StopState`: `queue`, `rate_by_hour`, `train_batches` (list of second, size) for Prado.
- `Inputs`: buses, stops, `m1[hour][segment]`, `trend[segment]`, `alight_share[stop]`, `next_departures` (slots), `params`, `as_of`.
- `Action`: `type`, `bus_id`, `stop_idx`, `hold_s`, `share` (fraction; published as `speed_reduction_pct = share × 100`), `duration_s`, `shift_s`.
- `Projection`: `departures[(bus, stop)]` (seconds from `as_of`), `wait_s`, `onboard_delay_s`, `reserve_cost_s`, `score_s`, `riders`.

`Inputs` serializes to canonical JSON (sorted keys) for `lineage_detail.inputs` and for the determinism test.

## M9. Removed

`config.seed_recommendation` (`DROP TABLE IF EXISTS`), its section in `007_scenarios.sql`, `src/data/seeds/`, `pipeline/seeds.py`. See research.md R4.

## M10. `gold.mpc_projection` (phase 2b, FR-035)

The model's "do nothing" departures, kept so the data owner can measure the model over time. One row per (snapshot, bus, stop) with a projected departure inside the 1,800 s window. Written only by `pipeline/recommend.py` in the cycle transaction, after the evaluation write; append-only like `gold.snapshots` (code never updates or deletes it). Written when the model is on and the snapshot is fresh, including cycles with no candidate; not written when `MPC_ENABLED=off`, when the snapshot is older than `freshness_max_s`, or before any bus has reported (`silver.bus_current_state` empty: the roster buses are placeholders and the cycle's time is not the feed's).

| Column | Type | Note |
|---|---|---|
| `snapshot_id` | UUID, FK `gold.snapshots` | PK part 1 |
| `bus_id` | TEXT | PK part 2 |
| `stop_id` | TEXT | PK part 3 |
| `as_of_ts` | TIMESTAMPTZ | the cycle reference time (copied from the snapshot, so the view needs no join) |
| `projected_departure_ts` | TIMESTAMPTZ | `as_of_ts` + projected seconds (5 s grid, rounded to 3 decimals) |
| `lead_s` | NUMERIC CHECK BETWEEN 0 AND 1800 | projected departure − `as_of_ts`; the 1,800 s is the scoring window |
| `rules_version`, `max_bronze_id` | | lineage (ADR-0001) |

Index `(bus_id, stop_id, as_of_ts)` serves the view's lookup. Insert is `ON CONFLICT DO NOTHING`: the snapshot id is a deterministic function of `(as_of, rules_version, max_bronze_id)`, so running the same cycle twice leaves the same rows and a replay of the same bronze produces identical rows (SC-001, SC-016). Buses included: every bus the projector gives a departure to in the baseline (service, estimated, `sources_down` obstacles, and waiting buses with a terminal slot); a reserve is not dispatched in "do nothing", so it has no row.

## M11. `gold.v_projection_accuracy` (phase 2b, FR-036)

A view over M10, `silver.stop_visits` and `gold.recommendation`; nothing is stored, so it reflects visits that arrive after the row was written.

| Column | Meaning |
|---|---|
| `snapshot_id`, `bus_id`, `stop_id`, `as_of_ts`, `projected_departure_ts`, `lead_s` | from M10 |
| `lead_bucket` | `0-5 min` (lead < 300 s), `5-10 min` (300 ≤ lead < 600), `10-30 min` (lead ≥ 600) |
| `actual_departure_ts` | the `departure_ts` of the bus's first `silver.stop_visits` row at that stop with `departure_ts ≥ as_of_ts`; NULL if there is none yet or if that visit is an estimated departure (`estimated_at_departure`) |
| `error_s` | `actual_departure_ts − projected_departure_ts` in seconds (positive: the bus left later than projected); NULL when `actual_departure_ts` is NULL, never 0 |
| `abs_error_s` | `|error_s|` |
| `affected_by_decision` | true when a `gold.recommendation` row with `status = 'applied'` for the same bus has `close_ts` (the decision's event time) after `as_of_ts` and, if the real departure exists, at or before it |
| `rules_version`, `max_bronze_id` | from M10 |

Matching rules and their reasons are in research R17. The aggregate query for SC-016 is in [contracts/projection-accuracy.md](contracts/projection-accuracy.md).

## Relationships

```text
bronze.events (decision, source=backend) --first per rec_id--> gold.recommendation.status
gold.snapshots --first_snapshot_id--> gold.recommendation --1:1--> gold.decision_log
gold.recommendation (type=hold) --rec_id--> gold.instruction_status (004, now reads M5)
gold.decision_inputs.doc + gold.m1_baseline + gold.m2_baseline + silver.* --> Inputs --> projector --> gold.mpc_projection (2b)
gold.mpc_projection + silver.stop_visits + gold.recommendation(applied) --> gold.v_projection_accuracy (2b)
```

## Validation rules (by object)

- `gold.recommendation.doc` validates against `recommendation.schema.json` 1.1.0 (generated model, plus the jsonschema contract test on a sample of rows in integration tests). `rank` is 1 to 3; `horizon_s = 600`; `hold.duration_s` in 0..90; `slow_down.duration_s` in 1..1800; `reserve_dispatch` and `skip_stop` `duration_s` null; `conflicts_with` contains only `rec_id`s present in the table.
- At most 3 rows with `stale = false` and `status = 'proposed'` per cycle.
- No row targets a bus that is `estimated` or in `sources_down` in the snapshot that created or refreshed it.
- `proposed_ts`, `expires_ts`, `first_snapshot_id`, `key`, `rec_id`, `params` never change after insert (a test updates the table twice and compares).
