# Feature Specification: Silver and Gold Layers with M1/M2 Baselines

**Feature Branch**: `feature/002-silver-gold-baselines` (stacked on `feature/001-base-simulator`, not yet merged)

**Created**: 2026-11-18

**Status**: Draft

**Traces to**: console screens US-03 (data quality status) and US-04 (live fleet panel) as numbered in ADR-0003 and `contracts/read/`; the internal US-05 input `decision_inputs`; PRD US-01 (RF-1.2, headway, partial) and the data inputs of PRD US-02 (RF-2.1–RF-2.3). Turn-1 risk "data integrity" (Disciplined lane). Note: the PRD document itself numbers its stories differently (its US-03 is route diversion); this spec uses the ADR-0003 screen numbering.

**Input**: User description: "Turn the bronze events produced by story 001 into the silver and gold layers that feed the dispatcher console: silver current state (with the 2-minute Estimated rule and segment travel times), gold console views `source_status` and `corridor_now`, M1/M2 median baselines with a declared reference-data fallback, `decision_inputs`, and a 5 s refresh cycle that emits a PostgreSQL `NOTIFY`. Data only: no REST endpoints, no decision engine, no frontend."

**Ground truth (binding, not re-decided here)**: ADR-0001 (layers, `(source, event_id)` dedup, insert-only bronze, 2-minute Estimated rule, lineage = `rules_version` + `max_bronze_id`, PostgreSQL only); ADR-0002 and `contracts/turn1-events/` (bronze event types); ADR-0003 and `contracts/read/` (read schemas v1.0.0 and fixtures); `specs/001-base-simulator/` (bronze tables, reference data, services, simulator).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Silver Current State (Priority: P1)

The data owner needs a trustworthy per-bus picture derived only from bronze: where each bus last reliably was, whether its data is live or estimated, and the observed stop visits and segment travel times. A bus that stops reporting must be flagged as Estimated rather than given a fabricated position, and that flag alone must not create an alert.

**Why this priority**: every gold view and both baselines are computed from silver. It directly mitigates the turn-1 risk: missing data must not contaminate the metric or the recommendations.

**Independent Test**: load a fixed bronze batch (seeded simulator output plus crafted events) into an empty environment, build silver, and inspect the per-bus state, stop visits and segment traversals. Then drop silver, rebuild it from bronze, and compare.

**Acceptance Scenarios**:

1. **Given** bronze containing `bus_position` events for B-101..B-105, **When** silver is built, **Then** each bus has exactly one current-state record holding the values of its latest `bus_position` by event time, with its previous and next stop.
2. **Given** a bus whose latest report is more than 120 s older than the cycle reference time, **When** silver is built, **Then** that bus has `data_quality = estimated`, its position stays at the last valid reported value, and no bunching, gap or breakdown state is created because of the outage (D1 scenario).
3. **Given** the Estimated bus from scenario 2, **When** it reports again, **Then** it returns to `data_quality = live` in the next build.
4. **Given** a `stop_departure` of a bus at stop *i* and its `stop_arrival` at stop *i+1* on the same trip, **When** silver is built, **Then** one segment traversal exists with travel time = `t_arrival(i+1) − t_departure(i)`, its segment id and its time band.
5. **Given** a traversal during which the bus was Estimated, or during which the bus had an active `bus_breakdown` incident, **When** silver is built, **Then** the traversal is flagged so the M1 baseline excludes it.
6. **Given** a populated silver layer, **When** silver is dropped and rebuilt from bronze, **Then** the rebuilt silver is identical to the previous one.

---

### User Story 2 - Gold Console Views (Priority: P2)

The dispatcher console needs two ready-to-read objects per computation cycle: `source_status` (US-03, data quality status) and `corridor_now` (US-04, live fleet panel) for corridor C6-008, direction 1. `corridor_now` includes, per bus, the headway to the bus ahead compared with the 600 s planned headway and the bunched/gap classification. The data layer also computes the corridor mean wait and EWT for the same snapshot. Every output of a cycle shares one `snapshot_id` and carries its lineage.

**Why this priority**: these are the outputs the backend and the frontend consume. They depend on silver (P1) and can be demonstrated against the `contracts/read/fixtures/` scenarios without the baselines.

**Independent Test**: from a prepared silver state, compute one snapshot and validate `source_status` and `corridor_now` against their JSON Schemas. Compare states, ordering and summary counts with the matching fixture scenario. Re-ingest the same bronze batch and recompute at the same reference time.

**Acceptance Scenarios**:

1. **Given** five live buses with headways near 600 s (fixture `normal`), **When** a snapshot is computed, **Then** `source_status.status = live` with an empty `sources_down`, and `corridor_now` lists the buses ordered by `distance_along_m` descending, the first one `leader` with `headway_ahead_s = null` and the others `regular`.
2. **Given** B-103 without reports for more than 2 min (fixture `d1_source_outage`), **When** a snapshot is computed, **Then** `source_status.status = estimated`, `sources_down` contains B-103 with `since` = the event time of its last report, and B-103 appears in `corridor_now` with `data_quality = estimated`.
3. **Given** a follower whose headway to the bus ahead is below 300 s (< 50 % of 600 s), **When** a snapshot is computed, **Then** it is `bunched`. **Given** a headway above 900 s (> 150 %), **Then** it is `gap`. The summary counts `n_bunched` and `n_gaps` match the per-bus states.
3a. **Given** an Estimated bus (B-103) and the bus directly behind it (B-104) whose headways would classify them as `bunched` or `gap`, **When** a snapshot is computed, **Then** both are `regular`, B-103 keeps its `headway_ahead_s` value, and neither is counted in `n_bunched` or `n_gaps`.
4. **Given** B-104 with an active `bus_breakdown` incident (fixture `c5_breakdown`), **When** a snapshot is computed, **Then** B-104 is `broken_down` with `headway_ahead_s = null`, the bus behind it measures its headway to the next operational bus ahead, and `buses_in_service` excludes B-104.
5. **Given** any cycle, **When** its outputs are inspected, **Then** `source_status`, `corridor_now`, `decision_inputs` and the service-metric record share the same `snapshot_id`, and every gold row stores `rules_version` and `max_bronze_id`.
6. **Given** headways of 300 s and 900 s between operational buses, **When** the service metric is computed, **Then** mean wait = (300² + 900²) ÷ (2 · 1200) = 375 s and EWT = 375 − 300 = 75 s.
7. **Given** a bronze batch already ingested, **When** the same batch is ingested again and a snapshot is recomputed at the same reference time, **Then** silver and gold are unchanged (duplicates go to `bronze.rejections` and `max_bronze_id` does not move).

---

### User Story 3 - M1/M2 Baselines and Decision Inputs (Priority: P3)

The backend decision engine needs a forecast travel time per segment (M1), a forecast of rider arrivals at Prado (P-883) for the next 15 minutes (M2), and a single `decision_inputs` object that bundles these with the fleet state, the reserve resources, action costs, active incidents and the stops where regulation is allowed. Baselines are medians, with no trained model. When observed history is too short, a declared reference-data estimate is used instead, so the baseline is not built only from the simulator it is later used to evaluate. Every value records whether it came from observation or from reference data.

**Why this priority**: the decision engine (a later story) cannot start without these inputs, but the console views (P2) are useful without them.

**Independent Test**: with a seeded silver history, query M1 and M2 and check every value against an independently computed median or reference formula. Assemble `decision_inputs` for one snapshot and validate it against `decision_inputs.schema.json`.

**Acceptance Scenarios**:

1. **Given** a segment × time band with at least 5 eligible traversals (the minimum sample count), **When** M1 is computed, **Then** its value is the median of those traversal times and its source is `observed`, with the sample count recorded.
2. **Given** a segment × time band with fewer than 5 eligible traversals, **When** M1 is computed, **Then** its value is `length_m ÷ (free_flow_kmh ÷ 3.6) ÷ congestion_factor(hour)` from `data/reference/`, and its source is `reference`.
3. **Given** traversals flagged as travelled while Estimated or by a broken-down bus, **When** M1 is computed, **Then** they are not counted as samples.
4. **Given** a 15-minute band with at least 5 days of history of `rider_arrival` counts at P-883, **When** M2 is computed, **Then** the forecast is the median of those counts with source `observed`. **Given** fewer than 5 days of history, **Then** the forecast comes from the demand model (633.92 riders/day in direction 1 × the Metro line-A hourly shape ÷ 4) with source `reference`.
5. **Given** a snapshot, **When** `decision_inputs` is assembled, **Then** its `buses` and `summary` equal those of `corridor_now` for the same `snapshot_id`, `travel_time_forecast` has 17 entries (segments 1–17) for the current time band, and `resources`, `action_cost`, `active_incidents` and `enabled_stops` come from the static configuration (provisional values: `drivers_free` = 2, both penalties 0, `enabled_stops` = P-883..P-900) and the active incidents. The object validates against its schema.

---

### User Story 4 - Refresh Cycle (Priority: P4)

The backend needs to know when a new snapshot is ready so it can push updates without polling. A simple loop recomputes silver and gold every 5 s and, once a snapshot is fully readable, emits one PostgreSQL `NOTIFY` on a gold channel. No broker is used.

**Why this priority**: it is the first story to cut if time runs short. Without it, the backend can poll the query door, and snapshots can be computed on demand.

**Independent Test**: run the simulator, ingestion and the refresh loop for 10 minutes while a listener records notifications. Check the interval between snapshots and that each notification refers to a readable, complete snapshot. Stop the refresh loop and confirm ingestion keeps writing to bronze.

**Acceptance Scenarios**:

1. **Given** the environment running, **When** the refresh loop is active, **Then** a new snapshot is produced about every 5 s and exactly one notification carrying its `snapshot_id` is emitted after the snapshot is readable.
2. **Given** a cycle that takes longer than 5 s, **When** the next tick arrives, **Then** cycles do not overlap; the late tick is skipped.
3. **Given** a cycle that fails, **When** the failure happens, **Then** no partial snapshot becomes visible, no notification is emitted for it, the failure is logged, and the next cycle runs normally.
4. **Given** the refresh loop is stopped or crashing, **When** the simulator keeps emitting, **Then** ingestion keeps writing to bronze (Principle III).

### Edge Cases

- **No events ever received**: `source_status.status = no_data`, `sources_down` empty, `corridor_now.buses` empty with zero summary counts, M1/M2 fall back to reference values.
- **Exactly 120 s since the last report**: the bus stays `live`. It becomes `estimated` only when the gap is strictly more than 120 s.
- **All buses silent**: every in-service bus is `estimated` and listed in `sources_down`; the overall status is `estimated`, not `no_data`, because events were received before. All of them are `regular` (FR-011) and `n_bunched` = `n_gaps` = 0.
- **Two consecutive Estimated buses**: each Estimated bus and the bus directly behind it are `regular`, so the bus behind the second one is also forced to `regular` and every bus from the first Estimated bus down to that follower is excluded from `n_bunched` and `n_gaps`.
- **A bus never reported but expected in service**: it does not appear in `corridor_now` and is not listed in `sources_down` (the contract requires a `since` timestamp it cannot have).
- **Only one operational bus on the corridor**: it is `leader`; there is no headway, so mean wait and EWT for that snapshot are recorded as not computable instead of a fabricated number.
- **The leader is broken down**: it is `broken_down`; the furthest-ahead operational bus becomes `leader`.
- **Two buses at the same `distance_along_m`**: ordering is resolved by `bus_id`, so the output is deterministic. The follower has `headway_ahead_s = 0` and is `bunched`.
- **Headway exactly 300 s or exactly 900 s**: `regular` (thresholds are strict: < 50 % and > 150 %).
- **A bus that reached terminus P-900**: it leaves `corridor_now` until it starts a new trip.
- **Reserve buses B-106/B-107 not dispatched**: they never appear in `corridor_now` or `sources_down`; they are listed in `resources.reserve_free`. A dispatched reserve bus appears like any in-service bus and leaves `reserve_free`.
- **A `stop_departure` without a matching `stop_arrival` at the next stop yet**: no traversal is recorded until the arrival exists.
- **Duplicate bronze submissions**: rejected upstream (`duplicate_event`); silver and gold do not change.
- **Events received late** (arrival time much later than event time): all calculations use event time; out-of-order handling beyond this is turn 3.
- **Backend `command_event` rows in bronze** (`source = "backend"`): they never count as a bus report and never refresh a bus's `data_quality`.
- **An incident whose duration has elapsed**: it is no longer active; the bus leaves `broken_down` in the next snapshot.

## Clarifications

### Session 2026-11-18

- Q: How are an Estimated bus and the bus directly behind it classified in `corridor_now` (FR-011)? → A: Option B. The Estimated bus keeps its `headway_ahead_s` value, but it and the bus directly behind it are forced to `regular` and left out of `n_bunched` and `n_gaps`. Rationale: ADR-0001 says an Estimated bus never raises an alert on its own, and this matches the `d1_source_outage` fixture.
- Q: What is the minimum sample count for an observed M1/M2 median (FR-028, FR-030, FR-031)? → A: Option A. 5 for both M1 (eligible traversals per segment × hour band) and M2 (days of history per 15-minute band), kept in the static configuration so it can change without changing rules code.
- Q: What are the static configuration values for `decision_inputs` (FR-034)? → A: Option A. Provisional neutral values: `hold_penalty_s` = 0, `early_departure_penalty_s` = 0, `drivers_free` = 2 (one per reserve bus), `enabled_stops` = all 18 stops P-883..P-900. They are provisional and owned by the backend/decision-engine owner, who replaces them later.

## Requirements *(mandatory)*

### Functional Requirements

**General**

- **FR-001**: Silver and gold MUST be derived only from bronze, the reference data in `data/reference/`, and the static configuration tables of this feature. Recomputing them from scratch MUST give the same result as maintaining them cycle by cycle.
- **FR-002**: This feature MUST NOT update, delete or insert rows in bronze (bronze stays insert-only and is owned by ingestion, ADR-0001).
- **FR-003**: All time calculations MUST use event time (`event_ts`), never arrival time (ADR-0001).
- **FR-004**: Each computation cycle MUST use one reference time, which becomes `as_of_ts` of every output of that cycle. In live operation it is the current UTC time. In replays and tests it MUST be settable to a fixed value.
- **FR-005**: The same bronze contents, reference time and `rules_version` MUST produce identical silver and gold contents. Re-ingesting an already ingested batch MUST leave silver and gold unchanged.
- **FR-006**: All quality and derivation rules (Estimated rule, headway, classification, medians, fallbacks) MUST be deterministic, versioned under one `rules_version`, and MUST NOT call AI models or external services.

**Silver (P1)**

- **FR-007**: A *bus report* MUST be any bronze event of type `bus_position`, `stop_arrival` or `stop_departure` for that `bus_id` whose source is not `backend`.
- **FR-008**: For each bus, silver MUST keep the latest valid position: the `distance_along_m`, `trip_id` and event time of its latest `bus_position` by event time (ties resolved by the higher bronze row id).
- **FR-009**: For each bus, silver MUST keep a current-state record: bus id, current trip, latest valid position, previous and next stop (from `data/reference/stops.csv` by distance along the route), event time of the last report, `data_quality`, and operational status (in service, reserve, broken down).
- **FR-010**: A bus MUST be `estimated` when the reference time minus the event time of its last report is strictly greater than 120 s, and `live` otherwise. An Estimated bus MUST keep its last valid position; the data layer MUST NOT fabricate a new position for it.
- **FR-011**: An Estimated bus MUST NOT, on its own, produce a `bunched`, `gap` or `broken_down` state or an incident. In `corridor_now`, an Estimated bus keeps its computed `headway_ahead_s` value, but the Estimated bus and the bus directly behind it (the one whose bus ahead is the Estimated bus) MUST be classified `regular` instead of `bunched` or `gap`, and MUST NOT be counted in `n_bunched` or `n_gaps`. The `leader` label is not a bunched/gap classification and is unaffected (see Assumptions).
- **FR-012**: Silver MUST record stop visits by pairing each bus's `stop_arrival` and `stop_departure` at a stop on the same trip: arrival time, departure time, dwell, boarded, alighted, rejected.
- **FR-013**: Silver MUST record segment traversals. Segment *k* runs from the *k*-th stop to the next stop in `stops.csv` order (segments 1–17). Travel time = `t_arrival(next stop) − t_departure(stop)` for the same bus and trip. Each traversal records bus, trip, segment id, departure time, time band and travel time.
- **FR-014**: A traversal MUST be flagged as *travelled while Estimated* if the bus had a gap of more than 120 s between consecutive reports inside the traversal, and as *broken-down* if a `bus_breakdown` incident for that bus was active at any time during it.
- **FR-015**: Silver MUST derive incidents from `incident_report` events. An incident is active from its event time until event time + `duration_min`. Its identifier is the `event_id` of the `incident_report` event.

**Gold console views (P2)**

- **FR-016**: Each cycle MUST produce exactly one snapshot with one `snapshot_id` (UUID), shared by `source_status`, `corridor_now`, `decision_inputs` and the service-metric record of that cycle. Snapshots MUST be kept (no retention in turn 1, ADR-0001) so recommendations can reference them.
- **FR-017**: Every gold row MUST store `rules_version` and `max_bronze_id` (the highest bronze row id the cycle read).
- **FR-018**: `source_status` MUST validate against `contracts/read/source_status.schema.json` (v1.0.0). `status` is `no_data` if bronze has never held a bus report, `estimated` if at least one in-service bus is Estimated, and `live` otherwise. `sources_down` lists every in-service Estimated bus with `since` = event time of its last report.
- **FR-019**: `corridor_now` MUST validate against `contracts/read/corridor_now.schema.json` (v1.0.0) for corridor `C6-008`, direction 1. `buses` contains every bus on an active trip that has not reached P-900, ordered by `distance_along_m` descending, ties by `bus_id`. Each entry's `ts` is the event time of the last `bus_position` used.
- **FR-020**: `headway_ahead_s` MUST be the time headway to the nearest operational bus ahead: the time elapsed between the moment that bus passed the follower's current `distance_along_m` (from its silver position history) and the follower's position time. It MUST be `null` for the leader and for a `broken_down` bus, and a broken-down bus MUST be skipped when finding the bus ahead (ADR-0003 gate decisions 1 and 2).
- **FR-021**: `headway_planned_s` MUST be 600 s for every bus in turn 1, read from the static configuration rather than coded into the rules.
- **FR-022**: `bus_state` MUST follow this order: `broken_down` (active `bus_breakdown` incident), then `leader` (furthest-ahead operational bus), then `bunched` (`headway_ahead_s` < 0.5 × planned), then `gap` (> 1.5 × planned), otherwise `regular`, subject to FR-011 (an Estimated bus and the bus directly behind it are `regular` instead of `bunched` or `gap`).
- **FR-023**: `summary.buses_in_service` MUST count the buses in `corridor_now` that are not `broken_down`. `n_bunched` and `n_gaps` MUST equal the number of entries in those states.
- **FR-024**: For each snapshot, gold MUST record a corridor service metric from the non-null `headway_ahead_s` values of operational buses: mean wait = Σh² ÷ (2·Σh), scheduled wait = Σh_planned² ÷ (2·Σh_planned) (300 s with all planned headways at 600 s), and EWT = mean wait − scheduled wait. With no headway available it MUST be recorded as not computable. This record is a gold table, not a field of the read objects (their schemas are closed with `additionalProperties: false`).
- **FR-025**: No gold output MAY contain fields outside its schema. Changing a read schema is out of scope and requires a new ADR (ADR-0003 versioning rule).

**Baselines and decision inputs (P3)**

- **FR-026**: The M1 time band MUST be the local hour of day (America/Bogotá, UTC−5) of the traversal's departure, matching the hourly bands of `congestion_factor.csv`.
- **FR-027**: M1 MUST give, for each segment 1–17 × hour band 0–23, the median travel time of eligible traversals (not flagged by FR-014), with the sample count.
- **FR-028**: If a segment × band has fewer eligible traversals than the minimum sample count, M1 MUST use `length_m ÷ (free_flow_kmh ÷ 3.6) ÷ congestion_factor(hour)` from `data/reference/segments.csv` and `congestion_factor.csv`. The minimum sample count is 5 for M1 (eligible traversals per segment × hour band) and also 5 for M2 (days of history per 15-minute band). It MUST be held in the static configuration so it can be changed without changing rules code.
- **FR-029**: Every M1 and M2 value MUST record its source (`observed` or `reference`), its sample count, its band, `rules_version` and `max_bronze_id`.
- **FR-030**: M2 MUST give, for each local 15-minute band of the day (96 bands), the median over past days of the count of `rider_arrival` events at stop P-883 in that band, with the sample count (one sample per band per day with data).
- **FR-031**: If a 15-minute band has fewer samples than the minimum (5 days, FR-028), M2 MUST use 633.92 (`daily_riders_dir1` in `demand_volume.csv`) × `metro_line_a_shape` of the band's hour (`demand_params.csv`) ÷ 4, rounded to the nearest integer.
- **FR-032**: `decision_inputs` MUST validate against `contracts/read/decision_inputs.schema.json` (v1.0.0). Its `buses` and `summary` MUST equal those of `corridor_now` for the same snapshot. `travel_time_forecast` MUST hold the 17 M1 values for the band of `as_of_ts`. `demand_15min` MUST hold the M2 value for the next clock-aligned 15-minute window starting at or after `as_of_ts`.
- **FR-033**: `resources.reserve_free` MUST list the reserve buses (B-106, B-107) not currently on an active trip. `drivers_free`, `action_cost` and `enabled_stops` MUST come from small static configuration tables. `active_incidents` MUST list the identifiers of incidents active at the reference time.
- **FR-034**: The static configuration tables MUST hold the reserve roster (B-106, B-107), the planned headway (600 s), `drivers_free`, `hold_penalty_s`, `early_departure_penalty_s`, `enabled_stops` and the minimum sample count. Their provisional values are: `hold_penalty_s` = 0, `early_departure_penalty_s` = 0, `drivers_free` = 2 (one per reserve bus), `enabled_stops` = all 18 stops P-883..P-900, minimum sample count = 5. They MUST be changeable without changing rules code.
- **FR-035**: `decision_inputs`, M1 and M2 are internal to the backend decision engine and MUST NOT be exposed to the frontend (ADR-0003 gate decision 7). This feature exposes no endpoint.

**Refresh cycle (P4)**

- **FR-036**: A loop MUST recompute silver and gold every 5 s and produce one snapshot per cycle.
- **FR-037**: A snapshot MUST become visible to readers all at once. Readers MUST never see a partial snapshot.
- **FR-038**: After a snapshot is visible, the loop MUST emit exactly one PostgreSQL `NOTIFY` on a single gold channel whose payload carries the `snapshot_id`. No broker is used.
- **FR-039**: Cycles MUST NOT overlap. A tick that arrives while a cycle runs MUST be skipped.
- **FR-040**: A failed cycle MUST NOT publish a snapshot or a notification. It MUST log a structured error without stack traces in any outward message, and the next cycle MUST run normally.
- **FR-041**: The refresh loop MUST NOT be on the ingestion capture path. Stopping or crashing it MUST NOT stop ingestion into bronze (Principle III).

### Key Entities *(include if feature involves data)*

- **Bus current state (silver)**: one record per bus with current trip, latest valid position, previous/next stop, time of last report, `data_quality` (live/estimated) and operational status. Owner: data.
- **Position history (silver)**: deduplicated `bus_position` reports per bus and trip, ordered by event time. Used to compute time headways.
- **Stop visit (silver)**: one record per bus, trip and stop with arrival, departure, dwell and boarding counts.
- **Segment traversal (silver)**: one record per bus, trip and segment with departure time, hour band, travel time and the Estimated / broken-down exclusion flags.
- **Incident (silver)**: derived from `incident_report` events: identifier, type, target, start, end, reporter.
- **Snapshot (gold)**: one per cycle: `snapshot_id`, `as_of_ts`, `rules_version`, `max_bronze_id`. All gold outputs of a cycle reference it.
- **Source status, Corridor now, Decision inputs (gold)**: the three read objects, stored per snapshot in the exact shape of their schemas.
- **Service metric (gold)**: per snapshot: mean wait, scheduled wait, EWT, number of headways used.
- **M1 baseline**: per segment × hour band: value in seconds, source, sample count, lineage.
- **M2 baseline**: per 15-minute band at P-883: arrivals forecast, source, sample count, lineage.
- **Static configuration**: reserve roster, planned headway, drivers free, action costs, enabled stops. Versioned with the repository; no secrets.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a 60-minute seeded run, 100 % of the `source_status`, `corridor_now` and `decision_inputs` objects produced validate against their JSON Schemas (draft 2020-12, `additionalProperties: false`).
- **SC-002**: For bronze sequences built to reproduce the `normal`, `d1_source_outage`, `c2_gap` and `c5_breakdown` fixtures, the produced objects match the fixtures in bus order, `bus_state`, `data_quality`, `status`, `sources_down` and summary counts.
- **SC-003**: D1: after one bus's reports stop, it becomes `estimated` and appears in `sources_down` in the first snapshot whose reference time is more than 120 s after its last report (at most 125 s with the 5 s cycle). Zero `bunched`, `gap`, `broken_down` states or incidents are attributable to the outage: the Estimated bus and the bus directly behind it are `regular` and are not counted in `n_bunched` or `n_gaps`. It returns to `live` in the first snapshot after it reports again.
- **SC-004**: Re-ingesting an already ingested batch and recomputing at the same reference time leaves silver and gold identical, and `max_bronze_id` unchanged.
- **SC-005**: Dropping silver and gold and rebuilding them from bronze gives the same contents as the cycle-by-cycle state, for the same reference time.
- **SC-006**: 100 % of M1 (17 × 24) and M2 (96) values carry a source and a sample count. Every `reference` value equals the FR-028/FR-031 formula recomputed independently from `data/reference/` (M1 within 0.1 s, M2 exactly). Every `observed` value equals an independently computed median of its eligible samples.
- **SC-007**: For crafted headway sets, mean wait and EWT equal the FR-024 formulas exactly (e.g. four headways of 600 s → 300 s and 0 s; 300 s and 900 s → 375 s and 75 s).
- **SC-008**: 100 % of gold rows carry a non-null `rules_version` and `max_bronze_id`. All outputs of one cycle share one `snapshot_id`, and `decision_inputs.buses` equals `corridor_now.buses` in every snapshot.
- **SC-009**: In a 10-minute run with the refresh loop, at least 95 % of intervals between consecutive snapshots are 5 s ± 1 s. Every notification refers to a snapshot that is already fully readable, and no notification is emitted for a failed cycle.
- **SC-010**: With the refresh loop stopped for 2 minutes, the bronze row count keeps growing.
- **SC-011**: Test coverage of this feature's code is above 80 % (Gate 2), and the quality rules (Estimated rule, classification, medians, fallbacks) are covered close to 100 %.

## Assumptions

- **Stacking**: this feature builds on `feature/001-base-simulator`, which is not yet merged. It relies on `bronze.events`, `bronze.rejections`, the empty `silver`/`gold` schemas, `data/reference/` and the compose services from 001. If 001 changes before merging, this spec may need updating.
- **No fabricated positions**: ADR-0001 says a silent source must not fabricate a position, while the `corridor_now` schema describes an Estimated position as "extrapolated". This spec follows ADR-0001 and keeps the last valid position. The D1 fixture (B-103 with `ts` = last report) is consistent with that.
- **Time headway method**: headway is computed as a time gap from the position history of the bus ahead (FR-020), a common transit practice. The repository does not prescribe a method; the fixtures only fix the semantics (ADR-0003 gate decisions 1 and 2).
- **Local time bands**: the hourly bands in `congestion_factor.csv` and `demand_params.csv` are Medellín local time (UTC−5, no daylight saving). Event times are UTC and are converted for banding.
- **M2 fallback attributes all direction-1 riders to Prado**: the demand model gives 633.92 riders/day for direction 1 of the route and no Prado-only share. Because C6-008 direction 1 runs from the Prado station outward, this spec treats the whole figure as Prado arrivals. This is a declared simplification to review with the data owner.
- **Line-A hourly shape sums to 1** over 24 hours (checked in `demand_params.csv`), so ÷ 4 turns an hourly share into a 15-minute share.
- **Corridor-level service metric**: mean wait and EWT are computed per snapshot for the whole corridor from current headways. Per-stop, per-window and P85/P95 percentile variants are not requested here.
- **Scheduled wait**: EWT = mean wait − scheduled wait, with scheduled wait from the planned headways (300 s at 600 s), following the usual definition of excess wait time.
- **Incident identifier** = the `event_id` of the `incident_report` bronze event (both are UUID v4).
- **"No alert" at the data layer**: the data layer raises no alerts; alerts and recommendations belong to the backend. Here, "no alert on its own" means the outage produces no `bunched`/`gap`/`broken_down` state, no incident and no count increase that the backend would act on.
- **Fixture inconsistency to fix**: in `contracts/read/fixtures/c1_bunching/corridor_now.json`, B-102 has `headway_ahead_s = 752` with `bus_state = gap`, but 752 s is below the 900 s gap threshold stated in the schema. The schema rule governs. The fixture must be corrected by the data owner (CODEOWNERS on `contracts/`) before it is used as an acceptance example; until then, SC-002 excludes `c1_bunching`.
- **RF-1.2 tolerance**: the PRD's ±15 % deviation highlight is not the bunched/gap rule. This feature follows the contract thresholds (50 % / 150 %); highlighting is a frontend concern.
- **Provisional static configuration**: `hold_penalty_s` = 0, `early_departure_penalty_s` = 0, `drivers_free` = 2 (one per reserve bus), `enabled_stops` = all 18 stops P-883..P-900, and the minimum sample count of 5 are provisional neutral values. The backend/decision-engine owner owns these values and replaces them later. Changing them is a configuration change, not a rules change.
- **Leader and Estimated buses**: an Estimated bus that is the leader keeps the `leader` label (it has no headway to classify). Only `bunched` and `gap` are suppressed by FR-011. This follows from FR-022 and is not covered by the gate answer; confirm with the data owner if a different treatment is wanted.
- **Turn-1 security baseline only**: parameterized queries, no secrets in the repository, no stack traces in outward messages. The static configuration holds no secrets.

## Out of Scope / Evolution

The following MUST NOT be built in this story (`docs/turns-ritmo.md`):

- REST/WebSocket/SSE endpoints and the query door implementation (backend story).
- The decision engine, recommendations, `recommendation_effect`, `instruction` and the `incident` read object (backend and later stories).
- Scenario injectors C1, C2, C5 and D1 (story 003). Tests here use crafted bronze events instead.
- M3 and trained models (e.g. LightGBM); anomaly detection.
- Direction 2 and short-turning (turn 4).
- Out-of-order, impossible-position and burst data faults (turn 3).
- TimescaleDB, PostGIS and geometry, Redis or any broker (turn 3).
- Per-stop and percentile (P85/P95) service metrics and P(board ≤ t) (later story).
- Changes to any contract in `contracts/` (requires a new ADR).
- Turn-2 security norms (RBAC, JWT, MFA, mTLS, HMAC, secret manager, SAST/SCA).
