# Feature Specification: Turn-1 Run Environment and Base Simulator

**Feature Branch**: `001-base-simulator`

**Created**: 2026-11-17

**Status**: Draft

**Traces to**: PRD US-01 (partial — fleet state and headway inputs); turn-1 risk "data integrity" (Disciplined lane).

**Input**: User description: a reproducible turn-1 run environment (curated reference data, isolated containers) and a deterministic base simulator for corridor C6-008 (direction 1, 5+2 buses, 5 s step) whose events are validated against the accepted turn-1 contract and persisted to immutable bronze.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Curated, Reproducible Reference Data (Priority: P1)

A team member builds the reference data set from the raw sources. The simulator and the test fixtures then use the real C6-008 segments, stops, Prado train arrivals, hourly congestion factor and demand parameters, so the simulation is grounded in the real corridor and reproducible.

**Why this priority**: grounds realism and reproducibility. The simulator depends on this reference data (segments, stops, congestion factor, demand), so it MUST be built first.

**Independent Test**: rebuild the reference data twice; verify byte-identical output, total size under 1 MB, completeness of `SOURCES.md`, and that fixtures use the real stop ids.

**Acceptance Scenarios**:

1. **Given** the raw sources present, **When** the reference data is built twice, **Then** both builds are byte-identical and the total size is under 1 MB.
2. **Given** the reference data, **When** it is inspected, **Then** it contains the 17 direction-1 segments (length, free-flow speed, slope), the real C6-008 stops with their real stop ids, the Prado train arrivals with a weekday service calendar, the hourly congestion factor as the computed mean SIMM speed ÷ corridor free-flow speed (the 0.43–0.56 band is a sanity check: a warning is emitted if any value falls outside it, but the computed values are kept), and the demand parameters (Metro line A hourly shape and basin-6 feeder share).
3. **Given** the reference data, **When** `SOURCES.md` is inspected, **Then** every file has one line recording source URL, license, download date and the transformation applied.
4. **Given** the test fixtures, **When** they reference stops, **Then** they use the real stop ids from the reference data.

---

### User Story 2 - Isolated Run Environment (Priority: P2)

A team member runs a single command to start the database, the simulator/ingestion service and a minimal API service as separate containers. Stopping the API does not stop ingestion, so data capture survives a web/API failure (Principle III).

**Why this priority**: Principle III (isolated ingestion) is non-negotiable from the first turn, and this story provides the container backbone the other stories run on.

**Independent Test**: start all services with one command; stop the API container; verify ingestion keeps writing to bronze.

**Acceptance Scenarios**:

1. **Given** a clean environment, **When** the team runs the single start command, **Then** the database, the simulator/ingestion service and the API service start as separate services.
2. **Given** all services running, **When** the API service is stopped, **Then** the simulator/ingestion service keeps running and bronze keeps growing.
3. **Given** the API service, **When** its health endpoint is queried, **Then** it reports a healthy status (the only API feature in scope).

---

### User Story 3 - Validated Ingestion into Immutable Bronze (Priority: P3)

Every event the simulator emits is validated at the boundary against the accepted turn-1 event contract. Valid events land in immutable, insert-only bronze; invalid or duplicate events land in `bronze.rejections` with a reason. Malformed or duplicated data can never contaminate the indicators, which is the turn-1 data-integrity risk.

**Why this priority**: directly mitigates the turn-1 risk (data integrity) and enforces Contract-First (Principle II). It is the integrity mechanism the whole turn is built to prove.

**Independent Test**: feed crafted valid, invalid and duplicate events to the ingestion boundary (without the live simulator) and inspect bronze and `bronze.rejections`.

**Acceptance Scenarios**:

1. **Given** a valid event, **When** it reaches the boundary, **Then** it is stored in bronze exactly once, carrying both the event time and the arrival time stamped by ingestion.
2. **Given** an invalid event (wrong type, out-of-range value, undeclared field, bad UUID or timestamp), **When** it reaches the boundary, **Then** it is rejected and stored in `bronze.rejections` with the matching reason and the original message.
3. **Given** an event already in bronze, **When** the same `event_id` from the same source is submitted again, **Then** the duplicate is discarded and recorded in `bronze.rejections` with reason `duplicate_event`, and bronze is unchanged.
4. **Given** the bronze layer, **When** any operation is attempted, **Then** bronze is never updated or deleted (insert-only).

---

### User Story 4 - Deterministic Base Simulator (Priority: P4)

A team member runs the simulator with a seed and a duration. It produces a deterministic stream of contract-valid fleet and rider events for corridor C6-008 (direction 1), modelling realistic travel time, dwell and demand, so that the fleet-state and headway inputs feeding US-01 are reliable and reproducible.

**Why this priority**: this story is the data source that closes the turn-1 loop and directly produces the US-01 fleet-state and headway inputs. It is built last because the simulator depends on the reference data (US-1).

**Independent Test**: run the simulator twice with the same seed and compare the output stream; verify every emitted event validates against the contract and that a full peak-hour trip meets the duration target. No persistence layer is required to test the simulator's output.

**Acceptance Scenarios**:

1. **Given** a fixed seed S and duration D, **When** the simulator runs twice, **Then** both runs produce a byte-identical event stream (the same output hash).
2. **Given** a peak-hour run of direction 1, **When** an in-service bus completes an end-to-end trip, **Then** the trip takes ~25 min (≈19.5 min running + ≈5.7 min dwell) within ±20 %.
3. **Given** the fleet B-101..B-105 in service and B-106..B-107 in reserve, **When** the simulator runs, **Then** it emits a `bus_position` event every 5 s for each in-service bus, plus `stop_arrival`/`stop_departure` at each stop and one `rider_arrival` per boarding attempt.
4. **Given** a bus at capacity (40), **When** more riders arrive than free spaces, **Then** the excess riders are counted as rejected, do not board, and the onboard count never exceeds 40.

### Edge Cases

- A stop with no boardings and no alightings: dwell time falls to the 10 s minimum.
- A train arrives at Prado but no rider boards within the dwell window: an empty batch is produced, not an error.
- A rider arrives when the bus is at capacity: the rider is recorded as rejected and does not board.
- The same `event_id` from the same source is submitted twice: it is stored once and the duplicate is logged with reason `duplicate_event`.
- An event carries an undeclared field: it is rejected with reason `undeclared_field`.
- The simulator runs for a duration shorter than one trip: only partial-trip events are emitted.
- Reserve buses B-106/B-107: they are part of the fleet roster (available) but are not dispatched and do not run revenue trips in this story (no decision engine).
- A raw source needed to rebuild the reference data is missing: the build fails with a clear message naming the missing source.

## Requirements *(mandatory)*

### Functional Requirements

**Reference data**

- **FR-001**: The system MUST provide a curated reference data set under `data/reference/` (under 1 MB total) built reproducibly from the raw sources in `data/raw/`; rebuilding from the same raw sources MUST yield byte-identical output.
- **FR-002**: The reference data MUST include the 17 direction-1 segments of route C6-008 with real length, free-flow speed and slope.
- **FR-003**: The reference data MUST include the real C6-008 stops with their real stop ids.
- **FR-004**: The reference data MUST include the train arrivals at Prado station from the 2025 Metro GTFS with a weekday service calendar.
- **FR-005**: The reference data MUST include an hourly congestion factor (real speed / free-flow speed) aggregated from SIMM, the Sistema Inteligente de Movilidad de Medellín (real speed measurements on the corridor). The 0.43–0.56 value is a **sanity band**: the build emits a warning if the computed values fall outside it but keeps the computed values as-is; the band is never used as an acceptance range or a target to manufacture.
- **FR-006**: The reference data MUST include demand parameters: the hourly shape of Metro line A and the feeder share of basin 6.
- **FR-007**: The reference data MUST ship a `SOURCES.md` with one line per file, each recording source URL, license, download date and the transformation applied.
- **FR-008**: Test fixtures MUST use the real stop ids from the reference data.

**Run environment (containers)**

- **FR-009**: The system MUST start, with a single command, three separate services: a database, a simulator/ingestion service, and a minimal API service (Principle III).
- **FR-010**: Stopping the API service MUST NOT stop the simulator/ingestion service; ingestion MUST keep writing to the database while the API is down.
- **FR-011**: The API service MUST expose at least a health-check endpoint and no other API features in this story.

**Ingestion into bronze**

- **FR-012**: Every simulated event MUST be validated at the ingestion boundary against the accepted turn-1 event contract (`contracts/turn1-events`, v1.0.0, ADR-0001 and ADR-0002); the validation models MUST be derived from the contract schemas with no fields invented beyond the contract.
- **FR-013**: A valid event MUST be persisted to the bronze layer (immutable, insert-only) with both the event time and the arrival time stamped by ingestion.
- **FR-014**: An invalid event MUST be rejected and stored in `bronze.rejections` together with its reason and the original message.
- **FR-015**: The bronze layer MUST enforce idempotency on `source` + `event_id`; a duplicate submission MUST be discarded and recorded in `bronze.rejections` with reason `duplicate_event`, leaving bronze unchanged.
- **FR-016**: The bronze layer MUST never be updated or deleted (insert-only).

**Base simulator**

- **FR-017**: The simulator MUST model a fleet of buses B-101..B-105 in service and B-106..B-107 in reserve, each with capacity 40, on corridor C6-008, direction 1 only.
- **FR-018**: The simulator MUST advance in a 5-second step.
- **FR-019**: Travel time per segment MUST equal length / (free-flow speed × hourly congestion factor) × lognormal noise, where the hourly congestion factor is the ratio real speed / free-flow speed (0.43–0.56).
- **FR-020**: Dwell time at a stop MUST equal 10 s + 3 s per boarding + 2 s per alighting (TCQSM-based declared assumption).
- **FR-021**: Rider arrivals at Prado MUST occur in batches per train (from the GTFS) plus a 1–3 min walk, plus a street drip at the other stops.
- **FR-022**: Boarding MUST follow FIFO up to capacity; riders beyond capacity MUST be counted as rejected and MUST NOT board.
- **FR-023**: The simulator MUST emit, per the contract, a `bus_position` event every 5 s per in-service bus, plus `stop_arrival`, `stop_departure` and `rider_arrival` events. (`driver_confirmation` and `incident_report` exist in the contract but are NOT emitted by the base simulator; they arrive with the decision engine and scenario injectors, which are out of scope.)
- **FR-024**: The simulator MUST accept a seed and a duration as run parameters.
- **FR-025**: The same seed MUST produce byte-identical output (a deterministic event stream, including event ids).
- **FR-026**: A peak-hour end-to-end trip of direction 1 MUST take approximately 25 min (≈19.5 min running + ≈5.7 min dwell) within ±20 %.

### Key Entities *(include if feature involves data)*

- **Reference data set**: the curated, reproducible inputs (segments, stops, train arrivals, congestion factor, demand parameters) plus `SOURCES.md`; consumed by the simulator and the fixtures.
- **Simulated event**: the contract envelope (`schema_version`, `event_id`, `event_type`, `source`, `event_ts`, `arrival_ts`, `payload`) as defined by the accepted turn-1 contract; the four event types emitted here are `bus_position`, `stop_arrival`, `stop_departure`, `rider_arrival`.
- **Bronze event store**: the immutable, insert-only landing table for valid events; idempotent on `source` + `event_id`.
- **Bronze rejections**: the record of invalid or duplicate events, each with a reason and the original message.
- **Bus**: a vehicle B-101..B-107 with capacity 40, marked in-service or in-reserve.
- **Trip**: a direction-1 run over the ordered segments and stops of C6-008.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Two simulator runs with the same seed produce byte-identical output (identical output hash).
- **SC-002**: 100 % of emitted events validate against the turn-1 event contract.
- **SC-003**: An invalid event is captured in the rejections store with the correct reason.
- **SC-004**: A duplicate event (same source + event_id) is stored exactly once in bronze.
- **SC-005**: With the API service stopped, the bronze store keeps growing (ingestion survives the failure).
- **SC-006**: A peak-hour direction-1 trip at the **fixed 17:00 calibration hour** completes in ~22.8 min, within ±20% of the 25 min target (i.e. 20–30 min).
- **SC-007**: The reference data set rebuilds reproducibly (byte-identical) and stays under 1 MB.
- **SC-008**: A single command brings up the full run environment (database + simulator/ingestion + API).

## Assumptions

- The turn-1 event contract (`contracts/turn1-events`, v1.0.0) and ADR-0001/ADR-0002 are accepted and authoritative; this story consumes them and does not change them.
- Event ids are UUIDs per the contract, but determinism (same seed → same output) is achieved with a seeded generator so the same seed yields identical event ids.
- The single start command uses the project's mandated separate-service layout (database, simulator/ingestion, API); this story does not introduce a new stack.
- Reserve buses B-106/B-107 are part of the fleet roster as available but are not dispatched and do not run revenue trips in this story (the decision engine is out of scope).
- Alightings per stop follow a simple declared, tunable model (e.g., a per-stop alighting probability for each onboard rider), tuned so peak-hour dwell matches the ~5.7 min target.
- Lognormal travel-time noise uses a fixed, declared dispersion seeded by the run seed; it is tunable so the running-time target (~19.5 min) holds.
- "Peak hour" is fixed at **17:00** (line A PM peak, Afluencia 2025 — data-owner decision). The computed SIMM congestion factor is lowest at 23:00 only due to thin night samples; 17:00 is the operationally correct peak. SC-006 is checked at 17:00 (~22.8 min end-to-end trip, within 25 min ±20%).
- `bus_position` is emitted for in-service buses only; reserve buses are not in motion.
- The raw sources in `data/raw/` are present locally (git-ignored); the reference-data build is reproducible only when those sources are present.

## Out of Scope / Evolution

The following are deferred to later stories or turns (`docs/turns-ritmo.md`); they MUST NOT be built in this story:

- Silver and gold data layers and any derived metrics (headway, EWT, P(board ≤ t)); this story produces raw inputs only.
- Scenario injectors C1–C5 (bunching, gap, transfer surge, accident, broken-down bus).
- Data-fault handling D1 beyond basic idempotency: the duplicate/source-outage scenario injectors and the source-outage "Estimated, no alert" behaviour. These are deferred to **later stories within turn 1** (not later turns), consistent with `docs/turns-ritmo.md` §3.1 which lists source outage as turn-1 scope.
- The decision/recommendation engine (hold, adjust departure, reserve dispatch) and the dispatcher approval loop. These are deferred to **later stories within turn 1** (RF-2.1, RF-2.2, RF-2.3 are turn-1 adopted norms per `docs/turns-ritmo.md` §3.2; they are out of scope for this story, not for the full turn).
- ML models (travel-time and demand baselines/predictions, anomaly detection).
- API features beyond the health check.
- The dispatcher web console and the interactive map.
- Redis (Pub/Sub cache), PostGIS and lat/lon geometry; direction 2 and short-turning.
- Throughput targets (1,000 events/s, P99 ≤ 500 ms); the exercise fleet (5 + 2 buses, 5 s step) is in scope.
- Security norms adopted in turn 2 (RBAC, JWT, MFA, mTLS, HMAC, secret manager, security headers, SAST/SCA). Only the no-cost baseline applies here: parameterized queries, no secrets in the repository, and no stack traces in error responses.
- Route diversion (US-03).
