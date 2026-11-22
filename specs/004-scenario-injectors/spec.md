# Feature Specification: Scenario Injectors, Hold Loop and Effect Table

**Feature Branch**: `feature/004-scenario-injectors` (stacked on `feature/003-ops-ci-reliability`, PR #9, which is stacked on `feature/002-silver-gold-baselines`; none merged yet)

**Created**: 2026-11-21

**Status**: Draft

**Traces to**: console screens US-10 (instruction status), US-11 (effect measurement) and US-12 (active incidents) as numbered in ADR-0003, plus the data inputs of US-03/US-04 already built in story 002; PRD US-02 (RF-2.1–RF-2.3, human gate on the hold). Turn-1 risk "data integrity" (Disciplined lane). Needed for the turn-1 workshop demo (2026-11-24).

**Input**: User description: "Data story for the turn-1 workshop demo. Make the dispatcher-console scenarios (C1 bunching, C2 gap, C5 breakdown, D1 source failure) happen on demand in the simulator in forced mode, close the loop for the cheapest dispatcher action (hold) so an approved hold is executed by the simulated bus and observed by the data layer, and measure its effect in a table. Data only: no decision engine, no REST/WebSocket endpoints, no frontend."

**Ground truth (binding, not re-decided here)**:

- `.specify/memory/constitution.md` v1.1.0 and `docs/turns-ritmo.md` (turn 1 adopted norms; Redis, PostGIS, HMAC, RBAC, 1,000 events/s deferred).
- ADR-0001 (bronze insert-only, `(source, event_id)` dedup, lineage = `rules_version` + `max_bronze_id`), ADR-0002 and `contracts/turn1-events/` (event envelope and payloads).
- ADR-0003 and `contracts/read/` (read contract v1.0.0 and the fixtures `c1_bunching`, `c2_gap`, `c5_breakdown`, `d1_source_outage`, `normal`). Responsibility boundary: the **backend** owns the decision engine, `rec_id`, and writes `command_event` (`decision`, `incident_report`, `confirmation`) to bronze with `source: "backend"`; **data** owns the `recommendation_effect` and `incident` gold views and decides that an instruction is `executed` by observing dwell within ±15 s of the instructed duration.
- `specs/001-base-simulator/` (simulator, R14 base case: 600 s planned headway, 5 s step, B-101..B-105 in service, B-106/B-107 in reserve), `specs/002-silver-gold-baselines/` (Estimated rule > 120 s, `bunched` < 50 % and `gap` > 150 % of planned, mean wait and EWT, `corridor_now`, `source_status`) and `specs/003-ops-ci-reliability/` (`ops.ingestion_health`, duplicates excluded from the rejection rate, CI-ready command).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scenario Injectors in Forced Mode (Priority: P1)

A team member starts the simulator with one or more scenarios configured (which scenario, when it starts, its parameters, a seed) and the scenario happens at that time, every run, exactly the same. The simulator emits only the events the real channel would emit, so the pipeline cannot tell an injected world from a real one. Each injector also leaves a hidden **scenario truth** record (which injector fired, when, with which parameters) that the pipeline never reads, so a test can compare what was injected with what the pipeline detected.

Scenarios:

- **C1 bunching**: one bus is delayed, or the bus behind it is sped up, until the headway between them is below 50 % of planned (< 300 s with the 600 s plan).
- **C2 gap**: the headway to a bus is above 150 % of planned (> 900 s), for example by a late departure at P-883.
- **C5 breakdown**: a bus stops and an `incident_report` is emitted for a configured duration; the bus appears as an active incident and as `broken_down`.
- **D1 source failure** (a channel layer, not a world injector; the world keeps moving): (a) one bus goes silent, so it becomes Estimated without raising any alert; (b) duplicate events are delivered. These are the 2 D1 failures of the reduced mock.

**Why this priority**: every demo step starts with a scenario that must be reproducible on demand. Without it the console has nothing to react to, and the hold loop (P2) and the effect table (P3) have nothing to act on.

**Independent Test**: for each scenario, run the simulator in forced mode with a fixed seed into an empty environment, let the pipeline compute gold, and compare the gold objects with the matching fixture in shape and meaning (counts of `bunched` and `gap`, Estimated, active incident). Compare the result with the scenario truth record.

**Acceptance Scenarios**:

1. **Given** no scenario configured, **When** the simulator runs with a seed and a duration, **Then** its output is byte-identical to the base simulator of story 001 for the same seed and duration.
2. **Given** C1 configured with a start time and parameters, **When** the run reaches the start time, **Then** the pipeline reports at least one bus as `bunched` (headway below 300 s), the `corridor_now` summary has `n_bunched` ≥ 1 and matches the per-bus states, and the shape matches `c1_bunching` (bunched followers; a gap opening elsewhere is allowed).
3. **Given** C2 configured (a late departure at P-883), **When** the run reaches the start time, **Then** at least one bus is `gap` (headway above 900 s), `n_gaps` matches the per-bus states, and the shape matches `c2_gap`.
4. **Given** C5 configured with a bus and a duration, **When** the run reaches the start time, **Then** the bus stops moving, an `incident_report` for it is in bronze, an active `bus_breakdown` `incident` is readable (reported by `script`), the bus is `broken_down`, and the shape matches `c5_breakdown` (`buses_in_service` excludes the broken-down bus; a gap opens behind it).
5. **Given** C5 and the configured duration elapsed, **When** the pipeline recomputes, **Then** the incident is no longer active and the bus is back in service.
6. **Given** D1(a) configured for one bus with a silence longer than 120 s, **When** the silence passes 120 s, **Then** that bus is `estimated` and listed in `source_status.sources_down`, the status is `estimated`, and no `bunched`, `gap`, `broken_down` state or incident and no alert is produced because of the outage (shape of `d1_source_outage`). **When** the bus reports again, **Then** it returns to `live`.
7. **Given** D1(b) configured, **When** duplicates are delivered, **Then** each duplicate is recorded in `bronze.rejections` with reason `duplicate_event`, is excluded from the real rejection rate, and silver and gold are identical to the same run without duplicates.
8. **Given** the same configuration and seed, **When** a scenario run is repeated, **Then** the event stream and the scenario truth record are byte-identical.
9. **Given** a scenario run, **When** the scenario truth record is deleted or altered before the pipeline computes, **Then** bronze, silver and gold are identical, and no pipeline code reads the record.
10. **Given** an invalid scenario configuration (unknown scenario, missing start time, a parameter outside its range, an unknown bus), **When** the simulator starts, **Then** it fails at start with a clear message and emits no event.

---

### User Story 2 - Closed Loop for "Hold" (Priority: P2)

When the dispatcher approves a hold recommendation, the backend writes a `decision` command event to bronze. The simulated bus then dwells at the target stop for the requested time (at most 90 s). With a configurable probability the driver does not comply. The data layer observes the real dwell and marks the instruction `executed` when it is within ±15 s of the requested hold, and `not_executed` otherwise.

**Why this priority**: it closes the demo loop (detect, recommend, approve, execute, measure) for the cheapest action, and it exercises Principle IV from the data side: nothing runs on the road without an approved `decision`. It depends on a scenario to act on (P1).

**Independent Test**: with the backend absent, write crafted `command_event` rows to bronze exactly as the contract says, run the simulator and the pipeline, and read the instruction status. Run once with compliance forced and once with non-compliance forced.

**Acceptance Scenarios**:

1. **Given** a bunching situation and a `decision` with `action: "apply"` for a hold of a bus at a stop for D seconds (D ≤ 90), **When** the bus reaches the stop, **Then** it departs no earlier than D seconds after it arrived, and the dwell is recorded by the usual `stop_arrival` / `stop_departure` events.
2. **Given** the hold above is complied with, **When** the bus has departed, **Then** the instruction is `executed` (observed dwell within ±15 s of D) and `ts_by_status.executed` is set.
3. **Given** the driver does not comply (forced by probability 1 in a test), **When** the bus has departed, **Then** the bus leaves with its natural dwell, the instruction is `not_executed`, and `ts_by_status.not_executed` is set.
4. **Given** a `decision` with `action: "discard"`, or no `decision` at all, **When** the bus reaches the stop, **Then** it behaves as in the base case, including with a hold recommendation present (Principle IV: no approval, no action).
5. **Given** a requested hold above 90 s, **When** the order is read, **Then** it is not executed beyond 90 s and the instruction is reported as not executed (the contract forbids holds above 90 s).
6. **Given** the approval arrives after the bus already departed the stop, **When** the bus is processed, **Then** the order cannot run, the bus is unchanged, and the instruction is `not_executed`.
7. **Given** the same seed, configuration and the same `command_event` rows, **When** the run is repeated, **Then** compliance outcomes and the event stream are identical.
8. **Given** the non-compliance probability is unset, **When** the simulator starts, **Then** the safe default applies (assumed 10 %); the value is read from configuration, never coded into the rule.
9. **Given** the same `command_event` is delivered twice (same `source` and `event_id`), **When** it is read, **Then** the hold is executed once.
10. **Given** the backend, the database read path, or the console is down, **When** ingestion runs, **Then** ingestion keeps capturing events (Principle III); only the execution of new holds is affected.

---

### User Story 3 - Recommendation Effect Table (Priority: P3)

After an approved hold and its horizon window, the dispatcher can see whether it worked: headway before and after, planned headway, the EWT the recommendation expected and the EWT observed, and a result. A table, not a chart (US-11).

**Why this priority**: it is the last step of the demo and closes the value hypothesis (did the action help P(board ≤ t)?). It needs the loop (P2) to have something to measure.

**Independent Test**: build bronze and silver for a hold with a known before/after headway and known EWT values, and read the effect row. Repeat with crafted inputs for each result value.

**Acceptance Scenarios**:

1. **Given** an applied hold whose horizon window has closed, **When** the effect is read, **Then** a row validating against `contracts/read/recommendation_effect.schema.json` (v1.0.0) exists with `headway_before_s`, `headway_after_s`, `headway_planned_s` (600), `ewt_expected_s`, `ewt_observed_s` and `result`.
2. **Given** a hold whose horizon window is still open, **When** the effect is read, **Then** no row exists for it yet.
3. **Given** `ewt_expected_s − ewt_observed_s ≥ 30`, **Then** `result` is `worked`. **Given** an improvement above 0 and below 30 s, or headway improved but EWT did not, **Then** `partial`. **Given** neither headway nor EWT improved, **Then** `did_not_work`. **Given** too few observations after the horizon, **Then** `no_data` with the unknown values null (gate decision 6 of ADR-0003).
4. **Given** the values of fixture `c1_bunching/recommendation_effect.json` (before 180, after 530, planned 600, expected 55, observed 22), **When** the rule is evaluated, **Then** the result is `worked`.
5. **Given** a hold that was `not_executed`, **When** the effect is read, **Then** the row is still produced from what was observed (the effect of the unexecuted order), so the dispatcher can see that nothing changed.
6. **Given** the same bronze contents, reference time and rules version, **When** the effect is recomputed, **Then** it is identical, and each row can be traced to its bronze events and rules version.
7. **Given** the effect view, **When** it is inspected, **Then** it is read-only and writes nothing to bronze.

---

### Edge Cases

- **Two scenarios overlap** (for example C1 and C5 on the same bus): the configuration is rejected at start unless the combination is declared valid; combinations on different buses are allowed and each leaves its own truth record.
- **Scenario start time after the end of the run**: nothing is injected, and the truth record states that it never fired.
- **C1 would need a headway the fleet cannot reach** (for example a delay too small): the run reports in the truth record that the target headway was not reached; it does not force it silently.
- **D1(a) silence of 120 s or less**: the bus does not become Estimated (the rule is strictly greater than 120 s). The injector accepts it and the truth record keeps the parameter.
- **D1(a) while the bus is held, broken down or at a stop**: the world behavior is unchanged; only the reports are missing.
- **D1(b) duplicates of a backend `command_event`**: counted once as a duplicate, the hold runs once.
- **A bus reports again after a long silence**: its position jumps ahead; this is not an impossible-position fault (deferred in `docs/turns-ritmo.md`).
- **Two approved holds for the same bus and stop**: the first applies and the second is reported as not executed (conflicting order).
- **A `decision` for a recommendation the pipeline cannot resolve to a bus, stop and duration**: it is ignored and counted; the bus is unchanged.
- **Breakdown of a bus that has a pending hold**: the breakdown wins, and the hold is `not_executed`.
- **Breakdown incident with unknown duration**: a scripted incident always has a numeric `duration_min` (the turn-1 `incident_report` contract requires it). A dispatcher report through the backend `command_event` may carry `duration_min = null` (ADR-0003 gate decision 3); it is an open-ended incident: active from its event time with no end, `duration_s` and `until` null in the `incident` view, and the bus stays `broken_down` until a later report closes it (research R6).
- **Effect window spans a data fault**: if a bus in the window is Estimated, the observation counts as missing, not as zero.

## Clarifications

### Session 2026-11-21

- Q: How does the simulator read approved decisions (FR-017)? → A: Option A. The simulator polls `bronze.events` read-only for `source = backend`, `event_type = decision` (the contract's command door). If the database is unreachable it keeps running without new holds and never blocks the event stream.
- Q: Where do the bus, stop, duration, expected EWT saving and horizon of a hold come from for a `rec_id` (FR-018)? → A: Option C. For this story the recommendations are seeded as test fixtures or a seed file keyed by `rec_id`, consistent with `contracts/read/recommendation.schema.json`; the `decision` event's `rec_id` points to them. The real door for recommendations is deferred to the backend integration (see the open integration item below). No contract or ADR change in this story.
- Q: Is the simulated reserve-bus dispatch of the C5 demo step part of this story (FR-029)? → A: Option B. Out of scope (Evolution). In the demo, the C5 step shows the breakdown and the active incident only.

### Open integration items

- **Recommendation door (contract gap)**: the `decision` command event carries only `rec_id`, `action`, `user_id` and `ts`. No door or table exists for the backend to hand data the recommendation (bus, stop, hold duration, `ewt_saving_s`, `horizon_s`). Until the backend integration defines it (with an ADR or contract addendum under the versioning rule), this story reads recommendations from a seed file or test fixtures keyed by `rec_id`.

## Requirements *(mandatory)*

### Functional Requirements

**Scenario injectors (P1)**

- **FR-001**: The simulator MUST support, in forced mode, the scenarios C1 bunching, C2 gap, C5 breakdown and the D1 source failures (a) silent bus and (b) duplicates. Each scenario MUST be enabled by configuration (command line or environment) with a start time and its parameters. With no scenario configured, the output MUST be byte-identical to the base simulator for the same seed and duration.
- **FR-002**: Forced mode MUST be deterministic: the same seed, duration and scenario configuration MUST produce a byte-identical event stream, including event ids. Injectors MUST NOT use unseeded randomness or the wall clock.
- **FR-003**: Every injected event MUST be exactly what the real channel would emit: same envelope, same event types and payload shapes as `contracts/turn1-events/` v1.0.0, validated at the ingestion boundary like any other event. No new event type, field or contract change is allowed. An injector MUST NOT write to bronze, silver or gold directly.
- **FR-004**: Every injector MUST be configurable by a start time (event time of the run) and its parameters, with safe defaults documented in `.env.example`. Defaults MUST NOT enable any scenario. Invalid configuration MUST fail at start with a clear message and emit no event (FR-001 byte-identity holds when nothing is enabled).
- **FR-005**: **C1** MUST delay one bus, or speed up the bus behind it, until the time headway between them is below 50 % of the planned headway (300 s with the 600 s plan), and keep the world consistent (buses do not overlap or pass each other without an event trail; capacity 40 and the base rules keep holding).
- **FR-006**: **C2** MUST produce a time headway above 150 % of the planned headway (900 s) behind a bus, for example by a late departure at P-883, using only world dynamics (no gap is written into the data).
- **FR-007**: **C5** MUST make the configured bus stop for the configured duration and MUST emit an `incident_report` (`bus_breakdown`, `reported_by: script`) for it. While stopped, the bus keeps reporting its position (it stays `live`, not Estimated). After the duration the bus resumes.
- **FR-008**: **D1(a)** MUST suppress every report (`bus_position`, `stop_arrival`, `stop_departure`) of the configured bus during the configured silence while the bus keeps moving in the simulated world. It MUST NOT change any other bus.
- **FR-009**: **D1(b)** MUST deliver already-emitted events again with the same `source` and `event_id`, in a configured quantity.
- **FR-010**: Each fired injector MUST write one record to a **scenario truth** store: scenario id, injector name, configured start time, parameters, the bus or stop affected, whether it fired, and the event time it took effect. The pipeline (ingestion, silver, gold, refresh, ops views) MUST NOT read it, and it MUST NOT be reachable from the read contract. It is for tests and demo audit only.
- **FR-011**: The scenario truth store MUST NOT contain secrets, PII or the content of events beyond ids and times.

**Closed loop for hold (P2)**

- **FR-012**: A hold order MUST be created only from a `decision` `command_event` with `action: "apply"` (Principle IV). A `discard`, a missing decision, or an expired or unknown one MUST leave the world unchanged.
- **FR-013**: An approved hold MUST make the target bus dwell at the target stop so that its total dwell (departure time minus arrival time) equals the requested hold of at most 90 s, when the driver complies. A hold above 90 s MUST NOT be executed as such.
- **FR-014**: Driver compliance MUST be decided by a seeded draw per order with a configurable non-compliance probability. The default is 10 % (assumption, from the story brief) and it MUST be read from configuration. A non-complying driver MUST leave with the natural dwell.
- **FR-015**: Data MUST mark an instruction `executed` when the observed dwell of the target bus at the target stop is within ±15 s of the requested hold, and `not_executed` otherwise (ADR-0003; the backend never declares execution). The observation MUST use bronze events only and event time, and MUST record the status transition times in `ts_by_status` of `instruction.schema.json`.
- **FR-016**: An order that can no longer run (the bus already departed the stop at the time the order is read, a conflicting second order, a breakdown) MUST end as `not_executed` and MUST NOT change the bus.
- **FR-017**: The simulator MUST obtain approved decisions from the **command door** defined by the contract: backend `command_event` rows in bronze (`source: "backend"`, `event_type: "decision"`). The simulator MUST poll `bronze.events` read-only for those rows. If the database is unreachable, it MUST keep running without new holds and MUST NOT block the event stream or make ingestion depend on the backend (Principle III).
- **FR-018**: The hold order MUST identify bus, stop and duration. The `decision` payload carries only `rec_id`, `action`, `user_id` and `ts`; bus, stop, duration, `ewt_saving_s` and `horizon_s` live in the `recommendation` object. In this story the recommendations MUST be seeded as test fixtures or a seed file keyed by `rec_id`, shaped as `contracts/read/recommendation.schema.json`, and the `decision` event's `rec_id` MUST resolve to them. The real door for recommendations is deferred to the backend integration (see Open integration items). This story MUST NOT add a table, event type or field to a published contract, nor change any ADR.
- **FR-019**: The `executed` / `not_executed` observation MUST be exposed as a read-only gold object whose shape is the `instruction` read contract status and `ts_by_status`; it MUST NOT write to bronze, and `confirmation` events remain the backend's.
- **FR-020**: Acceptance in this story MUST use crafted `command_event` rows written to bronze exactly as `command_event.schema.json` says (valid envelope, `source: "backend"`, UUID ids). No backend code is required or added.

**Incident view (P1 acceptance, US-12)**

- **FR-021**: Data MUST expose the `incident` gold view (shape `contracts/read/incident.schema.json` v1.0.0) built from the incident reports in bronze: `inc_id`, `type`, `target_id`, `duration_s` (minutes × 60; null when the duration is unknown), `since`, `until` (null while active), `reported_by`. An incident is active from its event time until event time plus its duration, consistent with story 002 (FR-015); an incident with unknown duration is active with no end (open-ended).

**Effect table (P3)**

- **FR-022**: A read-only gold view MUST produce `recommendation_effect` rows validating against `contracts/read/recommendation_effect.schema.json` (v1.0.0), one per approved hold, only after its horizon window has closed.
- **FR-023**: `headway_before_s` MUST be the headway at the target stop immediately before the action was applied. `headway_after_s` MUST be the headway ahead of the held bus (the target bus of the action) in the first snapshot at or after the start of the action plus `horizon_s`, since the bus has left the target stop by then (plan-gate decision 2, 2026-11-21). `headway_planned_s` MUST come from configuration (600 s), not from rules code. Unknown values are null.
- **FR-024**: `ewt_observed_s` MUST be the EWT of the corridor service metric (story 002 FR-024) after the horizon window, clamped at 0 because the read schema's minimum is 0 (plan-gate decision 2). `ewt_expected_s` is the projection carried by the recommendation (see FR-018).
- **FR-025**: `result` MUST follow ADR-0003 gate decision 6 exactly: `worked` if `ewt_expected_s − ewt_observed_s ≥ 30`; `partial` if the improvement is above 0 and below 30 s, or the headway improved but EWT did not; `did_not_work` if neither improved; `no_data` if observations are insufficient or the expected EWT is null. The 30 s threshold MUST be configuration, not coded into the rules.
- **FR-026**: Effect rows MUST be deterministic and recomputable from bronze, reference data and static configuration, and MUST store `rules_version` and `max_bronze_id` (ADR-0001 lineage). The view MUST NOT write to bronze, silver or gold state tables.
- **FR-027**: No output of this story MAY contain fields outside its read schema (`additionalProperties: false`).

**Cross-cutting**

- **FR-028**: Principle III: ingestion MUST keep running and capturing if the hold loop, the effect view, the backend or the console is down or failing. Failures in the loop MUST emit one structured JSON log line without stack traces or secrets and MUST NOT stop the simulator's regular events.
- **FR-029**: The simulated reserve-bus dispatch (B-106 or B-107 departing after the breakdown) is out of scope (Evolution). Reserve buses stay parked as in story 001. In the demo, the C5 step MUST show only the breakdown and the active incident.
- **FR-030**: Test-first: for each behavior-changing requirement a failing test or check MUST exist before the implementation. New code MUST keep total coverage above 80 % (Gate 2), and quality rules (headway and effect classification, compliance draw, execution observation) SHOULD be close to 100 %. The CI-ready command (`docker compose --profile tools build tests && docker compose --profile tools run --rm tests`) MUST stay green.
- **FR-031**: Config MUST come from the environment with safe defaults and no secrets in the repository. New variables MUST be documented in `.env.example`.
- **FR-032**: Out of scope (Evolution), and MUST NOT be built: C3 transfer surge and C4 segment accident (design only), stochastic mode and calibrated rates (ML training), reserve-bus dispatch, adjust-departure, short-turn and reassign actions, the real door for recommendations (backend integration), the decision engine, any REST/WebSocket endpoint, any frontend, and direction 2.

### Key Entities *(include if feature involves data)*

- **Scenario configuration**: which scenario, its start time, its parameters, the seed. Input to the simulator; never read by the pipeline.
- **Scenario truth record**: what each injector did (id, name, start, parameters, affected bus or stop, fired or not, effective event time). Hidden from the pipeline; read only by tests and demo audit.
- **Injected event**: an ordinary contract event (`bus_position`, `stop_arrival`, `stop_departure`, `incident_report`, duplicates) indistinguishable from real-channel events.
- **Hold order**: the executable form of an approved hold: bus, stop, duration (≤ 90 s), its originating `rec_id`, and the driver compliance outcome. Derived from an approved `decision` command event.
- **Command event (decision)**: backend-written bronze row; the only trigger for a hold (Principle IV). Owned by the backend; data only reads it.
- **Instruction execution observation**: data's `executed` / `not_executed` status for an instruction, with `ts_by_status`, from observed dwell within ±15 s.
- **Incident (gold view)**: active or closed incident for US-12, built from bronze incident reports.
- **Recommendation effect (gold view)**: per approved hold, headway before and after, planned headway, expected and observed EWT, result. Owned by data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

All are checked by execution with a fixed seed and are part of the CI-ready test suite or a documented run.

- **SC-001**: With no scenario configured, the output hash equals that of the story-001 simulator for the same seed and duration. With a scenario configured, two runs give the same event-stream hash and the same scenario truth record.
- **SC-002**: 100 % of injected events validate against the turn-1 event contract; 0 are rejected for contract reasons (D1(b) duplicates are the only rejections, with reason `duplicate_event`).
- **SC-003**: **C1**: in the computed gold, `n_bunched` ≥ 1 with the bunched follower's headway below 300 s, and the counts and states equal those of a `corridor_now` computed independently from the same bronze (shape of `c1_bunching`). **C2**: `n_gaps` ≥ 1 with headway above 900 s (shape of `c2_gap`). Bus order, `bus_state`, `data_quality` and summary counts match the fixture's semantics in each case.
- **SC-004**: **C5**: an active `bus_breakdown` incident for the configured bus validates against `incident.schema.json`, the bus is `broken_down` with `headway_ahead_s = null`, `buses_in_service` is 4 of 5, and after the configured duration the incident is no longer active (shape of `c5_breakdown`).
- **SC-005**: **D1(a)**: the silent bus is `estimated` and in `sources_down` in the first snapshot whose reference time is more than 120 s after its last report (at most 125 s with the 5 s cycle, story 002 SC-003); zero `bunched`, `gap`, `broken_down` states or incidents are attributable to it; it returns to `live` after reporting. **D1(b)**: M duplicates delivered give M `duplicate_event` rows, a real rejection rate unchanged, and silver and gold identical to the run without duplicates.
- **SC-006**: For every scenario, the scenario truth record and the pipeline's detection agree on the injected bus and kind: the gold object that shows the effect names the same bus and the same kind. The truth records the **injection** time (for C1 and C2, the step where the injector acted, not the moment the effect becomes visible). The time from injection to the first gold snapshot that shows the effect is reported separately as the "detection time"; it is a measure, not a pass condition on the truth time. Deleting the truth record does not change bronze, silver or gold.
- **SC-007**: With a crafted approved hold (D ≤ 90 s) and forced compliance, the bus's observed dwell is within ±15 s of D and the instruction is `executed`. With forced non-compliance it is `not_executed`. With `discard`, no decision, or a hold above 90 s executed as such, 0 holds run.
- **SC-008**: Over a seeded batch of N approved holds, the share of non-compliant orders is reproducible run to run and equals the share counted in the truth of the draw; with the default probability the expected share is 10 % (reported for the batch size N chosen in the plan, not asserted as exact).
- **SC-009**: The effect rule gives the expected `result` for each crafted case: the `c1_bunching` fixture values give `worked`; an improvement of 29 s gives `partial`; an improvement of 30 s gives `worked`; no headway or EWT improvement gives `did_not_work`; insufficient observations give `no_data`. 100 % of effect rows validate against `recommendation_effect.schema.json`.
- **SC-010**: In the seeded demo run (D1 Estimated → C1 with an approved hold and its effect → C5 showing the breakdown and the active incident only → close), every step produces its gold objects (the C1 step also the effect row), and the run takes about 8 minutes of wall-clock time at the demo pace. The effect `result` of the C1 hold is recorded as the rule yields it; if it is not `worked`, it is reported as such and not tuned.
- **SC-011**: With the hold loop, the effect view and the backend stopped, bronze row count keeps growing (Principle III). Stopping the database for the retry window of story 003 does not make the simulator or ingestion exit.
- **SC-012**: Re-ingesting the same bronze batch (including `command_event` rows) and recomputing at the same reference time leaves silver, gold, instruction status and effect rows unchanged.
- **SC-013**: Total coverage stays above 80 % with the CI-ready command green; no read or write contract file under `contracts/` and no ADR line changes unless an approved ADR says so.

## Assumptions

- The default non-compliance probability is 10 % (from the story brief); it is an assumption, to be recalibrated later with real driver data (ML training, out of scope).
- The hold is a total dwell: the bus leaves no earlier than D seconds after arriving (D is the requested hold). This is the reading of "dwell within ±15 s of the instructed duration" in ADR-0003. If the team wants the hold to be added on top of the natural dwell, the observation rule changes with it; the plan states it.
- "Headway improved" for the `partial` / `did_not_work` rule means closer to the planned headway (smaller absolute distance to 600 s) after the horizon than before. The repository does not define it; this is the working definition.
- ADR-0003 gate decision 6 compares a projected EWT *reduction* (`ewt_expected_s`) with an observed EWT (`ewt_observed_s`), as the fixture does (55 and 22 give `worked`). The rule is applied as written; the semantic mismatch is reported to the data owner, not changed here.
- The headway used before and after is the time headway of story 002 (FR-020), measured at the target stop.
- The horizon window length is `horizon_s` of the recommendation (600 s in the C1 fixture); the story invents no other value.
- Scenario start times, durations and silence lengths have no default that enables a scenario. Their demo values (for example a silence above 120 s) are chosen in the plan and recorded in the demo script.
- Reserve buses B-106 and B-107 are not dispatched by the base simulator, and this story does not dispatch them (FR-029).
- Recommendations are seeded as test fixtures or a seed file keyed by `rec_id` (FR-018); the seed is test and demo data, not a new contract.
- The hidden scenario truth is stored outside the `bronze`, `silver`, `gold`, `config` and `ops` schemas the pipeline reads; the exact place (file or separate store) is decided in the plan, with the guarantee of FR-010.
- The demo uses the 600 s planned headway and the existing refresh cycle of 5 s. Pace follows `SIM_PACE_S`.
- Only numbers in the repository or in the story brief are used: 600 s, 50 % and 150 %, 120 s, 90 s, ±15 s, 30 s, 10 %, 5 s step, 5 + 2 buses, 80 % coverage, about 8 minutes of demo. No other threshold is invented.
- Rules versioning (`rules_version`) and lineage follow story 002; a new version label for the new rules is chosen in the plan.
