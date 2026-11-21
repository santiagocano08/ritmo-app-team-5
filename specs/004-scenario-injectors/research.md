# Research: Scenario Injectors, Hold Loop and Effect Table

**Feature**: 004-scenario-injectors | **Date**: 2026-11-21

Every number below is either in the repository (cited) or was measured during planning by running the
existing code at HEAD (`d7d674f`) with `PYTHONPATH=. uv run --frozen python`. Measurements are marked
**[measured]**. No threshold is invented; where the spec leaves a value open, the choice is derived from a
cited number and says so.

## Open items from Technical Context

| Item | Resolved in |
|---|---|
| Scenario configuration and plug-in into the engine | R1 |
| Hidden truth location and use | R2 |
| D1 channel layer | R3 |
| Hold executor: polling, mapping, compliance, dwell | R4 |
| Observation: `executed`, instruction status object | R5 |
| `incident` gold object | R6 |
| `recommendation_effect` gold object | R7 |
| Rules version, DDL, existing volumes | R8 |
| Demo script | R9 |
| Tests, golden hashes, coverage | R10 |
| Scope and evolution | R11 |
| Cycle cost | R12 |
| Dependencies | R13 |
| Time budget | R14 |

All `NEEDS CLARIFICATION` of Technical Context are resolved. Three questions that need an owner remain
in `plan.md` (Open questions); each has a default used by the plan.

## Findings from reading the code (they shape the decisions)

| Finding | Source | Consequence |
|---|---|---|
| The engine is pure: one `random.Random(seed)` drives event ids (`env()` draws 128 bits per event), travel-time noise, riders and destinations in a fixed call order. No DB, no wall clock. | `engine.py` | Injectors must not draw from it unless they run in scenario mode; the channel layer can sit after envelope creation. |
| Baseline output: seed 42, 3600 s = 3,851 lines, 1,439,431 bytes, SHA-256 `51a5e9b3063667320a6e66cab6293f84197822378783724dd664b6f6865d39e1`; seed 7 = `6bd20707…0132` (`6bd20707cf9aaccc852b6f8431e1129b759321b69f5cd06e5697c1638e0ab132`). **[measured]** | CLI stdout | These are the SC-001 pins. They match the 003 plan figures (3,851 events, 1,439,431 bytes). |
| Base timeline, seed 42, `run(42, 4200)`, seconds after 22:00:00Z: P-883 departures at 10, 635, 1235, 1835, 2435 (B-101..B-105), trip 1 of B-101 reaches P-900 at 1550; B-102 at 1970; B-103 at 2530; B-104 at 3145; B-105 at 3755; P-887 arrivals 510, 1045, 1650, 2265, 2895 with dwell 10 to 15 s. **[measured]** | probe | A trip lasts 1,295 to 1,540 s. With a start every 600 s, 2 or 3 buses are on the corridor, 3 only in windows such as [1235, 1550], [1835, 1970], [2435, 2530]. |
| `buses_in_service` counts buses on the corridor (departed P-883, trip not finished) that are not broken down. A waiting bus and a bus at the terminus layover are not counted. | `silver_bus_current_state.sql`, `classify.summarize` | The fixture value "4 of 5" cannot be reproduced; tests assert the rule (broken-down bus excluded), not the count. |
| Headway is measured to the nearest operational bus ahead, skipping a broken-down bus (ADR-0003 gate 2); order is distance descending, ties by bus id. | `headway.py` | A C5 gap behind the stopped bus needs a leader, the stopped bus and a follower: 3 buses on the corridor. |
| The ingestion boundary accepts the six turn-1 event types only; `decision` and `confirmation` are rejected there. The 002 builders already insert backend rows directly (`insert_backend_commands`). | `validate.py`, `bronze_builders.py` | The backend writes `decision` rows straight to `bronze.events`; tests do the same (FR-020). |
| Silver bus-state queries exclude `source = 'backend'`; `silver.incidents` includes every source and has `end_ts NOT NULL`. | silver SQL, `004_silver.sql` | Backend rows never move a bus; a null-duration backend incident would fail the silver insert (pre-existing, risk 7). |
| The refresh loop in `REFRESH_CLOCK=data` mode uses the newest non-backend bus report as reference time. | `refresh/run.py` | Gold time follows the simulated clock; a backend row's `event_ts` (a wall time) never matters for matching (R4). |
| Gold snapshots: `gold.snapshots` (unique on `as_of_ts, rules_version, max_bronze_id`), JSONB docs per snapshot with `rules_version` and `max_bronze_id`, `service_metric.ewt_s` per snapshot, one cycle transaction with an advisory lock. | `005_gold.sql`, `cycle.py`, `gold.py` | New gold objects follow the same pattern and join snapshots through `as_of_ts`. |
| `RULES_VERSION = "1.0.0"` is part of the snapshot id; one test pins it. | `rules/__init__.py`, `test_rules_version.py` | Bump needs one test edit (R8). |
| `src/data/rules/` is a CODEOWNERS path. | `.github/CODEOWNERS` | New rule files need the data owner's review. |
| The compose `ingestion` service runs `simulator | ingestion.run` with `DATABASE_URL` in its environment. | The simulator can open its own read-only connection with the same DSN; no new service. |

---

## R1 — Scenario configuration and how it plugs into the engine

**Decision**

- **Input**: one JSON file, path in `SIM_SCENARIO_FILE` or `--scenario-file PATH` (the flag wins).
  Unset or empty means no scenario. The content is a JSON array validated by Pydantic V2 models with
  `extra="forbid"` and a discriminated union on `type`. Nothing is enabled by default (FR-004).
  The file lives in the image under `src/` so compose needs no mount; tests use files under
  `src/data/tests/fixtures/scenarios/`.
- **Time**: `start_s` is an integer number of simulated seconds after the run start (the engine's `t`).
  An injector fires at the first 5 s step with `t >= start_s` whose preconditions hold, and its truth
  record states the effective step.
- **Seed**: the existing `--seed` / `SIM_SEED`. No second seed.
- **Plug-in**: `run()` gains two optional arguments, `hooks` and `holds`, both `None` by default. Every
  new call in the engine is guarded by `if hooks is not None` (or `holds`). With both `None` the engine
  executes the same statements in the same order, so the output is the baseline. Test: the golden-hash
  test is written and run **before** the first engine edit and stays in the suite.
- **Channel layer** (D1) wraps the generator in `main.py`; it is not part of the engine (R3).

**Injectors (parameters, ranges, and where each number comes from)**

| Type | Parameters | Effect in the engine | Range and reason |
|---|---|---|---|
| `C1` | `id`, `start_s`, `bus`, `stop`, `extra_s` | At the first arrival of `bus` at `stop` with `t >= start_s`, the dwell end (`phase_end`) is extended by `extra_s`. Events are the usual ones; the bus keeps reporting. | `300 < extra_s <= 600`. The rule bunches below 0.5 × 600 = 300 s (002 FR-022), so a leader delayed by more than 300 s puts the follower under 300 s when the nominal gap is 600 s. 600 is the planned headway: above it the follower would reach the stop before the leader leaves. `stop` is P-884..P-899 (not the first stop, which is C2's domain, and not the terminus). |
| `C2` | `id`, `start_s`, `bus`, `delay_s` | The next departure of `bus` from P-883 that is still in the future at the firing step is delayed: `start_at += delay_s` for a waiting bus, `phase_end += delay_s` for a layover. The R14 schedule of later trips is not changed (it uses `first_start + n × cycle`). | `300 < delay_s <= 600`. Gap rule is above 1.5 × 600 = 900 s, nominal start spacing is 600 s (measured departures 10, 635, 1235, 1835, 2435: gaps 625, 600, 600, 600), so more than 300 s of delay passes 900 s. |
| `C5` | `id`, `start_s`, `bus`, `duration_s` | At the first step with `t >= start_s` where `bus` is `driving`, the bus stops: `drive_t` does not advance, position reports continue with `speed_kmh = 0`, and one `incident_report` (`bus_breakdown`, `target_id = bus`, `duration_min = duration_s / 60`, `reported_by = script`) is emitted. After `duration_s` the bus resumes. | `0 < duration_s <= 300`. The R14 acceptance in 002 shows no base gap below 300 s, so a stop of at most 300 s cannot let the follower reach the stopped bus (the model has no overtaking rule). |
| `D1_SILENCE` | `id`, `start_s`, `bus`, `duration_s` | Channel layer (R3). | `duration_s >= 1`. A value of 120 or less is accepted (Estimated needs more than 120 s, spec edge case). Demo value 300 s (R9). |
| `D1_DUPLICATES` | `id`, `start_s`, `count` | Channel layer (R3). | `1 <= count <= 1000`. |

`bus` must be one of B-101..B-105 (reserve buses are not simulated, FR-029).

**Start-time validation** (fails before any event, AC10): unknown `type`, missing `start_s`, negative or
non-integer `start_s`, unknown bus or stop, a parameter outside its range, a duplicate `id`, an unknown
field. **Overlap rule**: two world scenarios (C1, C2, C5) on the same bus are rejected; combinations on
different buses are allowed; D1 scenarios may coexist with anything. A `start_s` at or after the run
duration is accepted and the truth record says `fired: false` (spec edge case).

**Why one mechanism for C1 and C2 is not enough, and why "speed up the follower" is dropped.** Delaying a
bus at the origin (C2) makes a gap ahead of it and bunches the bus behind it, so it cannot be the C1
case that leaves the pair isolated. A dwell extension en route (C1) bunches the follower and also opens a
gap ahead of the delayed bus, which the spec allows ("a gap opening elsewhere is allowed"). The spec offers
"delayed, or the bus behind sped up"; one mechanism is enough and a speed-up needs a second one (a
travel-time multiplier plus its bounds) for no demo value.

**Truth for the C1 edge case.** The spec asks the truth record to say when the target headway was not
reached. The injector cannot know it at firing time (the follower's dwells are not drawn yet). The engine
records the departure time of every bus at the C1 stop; when the next bus departs that stop, the C1 truth
record gets `follower_gap_s = departure(follower) − departure(delayed bus)` and
`target_reached = follower_gap_s < 300`. This is an engine-side measurement of the same quantity the
rule uses, not a forecast.

**Rationale**: minimal change to a pure engine; one validated file instead of two input paths; every
range comes from a number already in the spec or the 002 research.

**Alternatives considered**

- Inline `--scenario type:key=value` strings plus a file: two parsers for no test gain (rejected).
- Scenarios in the database (a table the simulator reads): the simulator would depend on the database
  to start, against FR-017 and Principle III (rejected).
- A second RNG for event ids in scenario mode, so the world does not shift after an injection: it would
  change ids only in scenario mode but not remove the shift caused by trip starts at different steps
  (`build_profile` draws from the main stream at trip start). Not worth a branch (rejected). Consequence:
  after the first world injection later events differ from the base case; the same configuration gives
  the same bytes (AC8).

## R2 — Where the hidden scenario truth lives and how tests use it

**Decision**

- A `TruthSink` writes **JSON lines**, one per injector, to `SIM_TRUTH_PATH` (or `--truth-path`) when
  set, otherwise to **stderr** as one line per record. It is created in `main.py` and passed to the
  injectors; it is not part of the engine's output stream.
- A record is appended when the injector fires; records of injectors that never fired are appended at the end of the run
  with `fired: false`. Order is therefore by effective time, then configuration order, and deterministic.
- Fields: `scenario_id`, `type`, `params` (the validated parameters), `bus`, `stop`, `fired`,
  `effective_ts` (UTC, ISO-8601, or null), plus type-specific fields: `follower_gap_s` and
  `target_reached` (C1), `event_ids` of duplicated events (D1 duplicates), `complied` and `rec_id` (hold
  records of Phase 2, R4). No event content beyond ids and times, no secrets, no PII (FR-011).
- **Never read by the pipeline.** Static guard `test_no_truth_reads.py`: no module under
  `src/data/{rules,pipeline,refresh,ingestion}` imports `src.data.simulator.scenarios` or mentions
  `scenario_truth` or `SIM_TRUTH_PATH`; no SQL or DDL file mentions a truth table; the schemas `bronze`,
  `silver`, `gold`, `config`, `ops` contain no truth object. A second test deletes and alters the truth
  file between simulation and pipeline computation and compares bronze, silver and gold hashes (AC9).
- **Tests**: the in-memory list of records is compared with gold: for each injected scenario, kind and
  bus match the gold state and the effective time matches the first snapshot in which the condition holds
  within one 5 s cycle (SC-006).

**Rationale**: FR-010 asks for a store outside every schema the pipeline reads; a file or the log stream
meets that with no new table, no new service and no grant. In compose, stderr ends in the container log,
which the demo script collects for the audit.

**Alternatives considered**

- A table in a separate schema `truth` in the same database: reachable by the same role, easy to misuse
  from SQL, needs DDL (rejected).
- A second database or a volume file only: more moving parts than stderr plus an optional path (rejected).
- Writing the truth at the end of the run only: a killed demo would leave nothing (rejected).

## R3 — D1 as a channel layer

**Decision**: `channel.py` wraps the event iterator after the engine has created each envelope. The
world and the RNG are untouched, so a run with only D1 scenarios is the base stream with some lines
removed (silence) or repeated (duplicates).

- **Silence** (`D1_SILENCE`): drop every `bus_position`, `stop_arrival` and `stop_departure` whose
  payload `bus_id` equals the target and whose `event_ts` lies in `[start, start + duration_s)`.
  `rider_arrival` events carry no bus and are untouched. The bus keeps moving in the world (FR-008). The
  silent interval has no effect on any other bus.
- **Duplicates** (`D1_DUPLICATES`): after `start_s`, each of the next `count` events is written twice in
  a row (same `source` and `event_id`, same bytes). Event ids are recorded in the truth. Ingestion records
  the second copy as `duplicate_event`, excluded from the rejection rate (003). Bronze, silver and gold
  equal the run without duplicates (AC7). The first `count` events after `start_s` are used, whatever their
  type, so the truth lists exactly which ids were repeated.
- Numbers for the demo: a silence of 300 s on B-101 from 250 s. The last report is at 245 s, so the bus is
  Estimated for as_of times greater than 365 s and listed in `sources_down` within one 5 s cycle (002
  SC-003 gives at most 125 s after the last report); it is Estimated for about 185 s of simulated time and
  live again after 550 s. At pace 0.9 that is about 33 s of wall time on screen.

**Rationale**: the same event ids and bytes as the world produced, no change to the engine, and exactly
the two D1 faults of the reduced mock.

**Alternatives considered**: stopping the bus emission inside the engine (it would alter the RNG order
and entangle D1 with the world; rejected); a re-delivery of an earlier event later in the run
(at-least-once behavior; more realistic but needs a buffer; rejected, YAGNI).

## R4 — The hold executor

### R4.1 Intake: how the simulator polls bronze read-only

**Decision**

- Enabled by `SIM_HOLDS=on` (default `off`, so the default stack never touches the database from the
  simulator). When off, the engine gets `holds=None`.
- A **daemon thread** runs `HoldPoller.poll_once()` every `SIM_HOLD_POLL_S` seconds of wall time
  (default 1.0). The engine never waits for it: at each step it reads an in-memory `HoldBoard` under a
  lock.
- **Connection**: its own connection from `DATABASE_URL`, opened with `connect_timeout=2`, `autocommit`,
  `default_transaction_read_only=on` and `statement_timeout=2000` ms. The poller never writes (a static
  test scans the module for INSERT/UPDATE/DELETE, like `test_no_bronze_writes`).
- **Query** (`rules/sql/hold_orders.sql`, shared with the pipeline, R5): new backend decisions
  `WHERE source = 'backend' AND event_type = 'decision' AND id > :last_id ORDER BY id`, with
  `decided_at_sim` = newest `event_ts` of a non-backend bus report with a smaller `id` (null when the
  decision precedes every report, for example crafted rows written before the run).
- **Database down**: any `psycopg.Error` is caught; the poller logs **one** JSON line on the transition
  to failed and one on recovery (no stack trace, no connection detail), keeps the board as it is, sleeps
  the interval and reconnects. New holds are not seen; the event stream is not delayed (the thread is
  separate and the board read is a dictionary lookup). This is FR-017 and SC-011.
- **Worst-case miss window**: an approval is seen within `SIM_HOLD_POLL_S` of wall time, which is 5
  simulated seconds at pace 1 (`SIM_PACE_S=1`) and 4.5 s at the demo pace 0.9. An approval that lands in
  that window before the bus arrives can miss the bus and ends `not_executed` (conservative: it never
  executes something the rule would not). With a pre-written decision (tests, pace 0) the order is known
  from step 0 and the run is deterministic (AC7).

### R4.2 Mapping `rec_id` to an order

- The simulator loads the seed file (`SEED_RECOMMENDATIONS_PATH`, default
  `src/data/seeds/recommendations.json`) at start, validates every entry with the generated
  `recommendation` model (so `hold` with `duration_s` outside 0 to 90 is rejected at load), and keeps
  entries with `action.type = "hold"`.
- A polled `decision` with `action = "apply"` and a known `rec_id` becomes an **order**: `bus_id`,
  `stop_id`, `hold_s = action.duration_s`, `from_s` (= `decided_at_sim` as seconds since the run start,
  or minus infinity), `until_s` (= `expires_ts`). `discard`, an unknown `rec_id` (counted and logged as
  `hold_order_ignored`, reason `unknown_rec`), an entry that is not a hold, and a second order with the
  same `rec_id` produce no order. A second order for the same bus and stop is kept and ends
  `not_executed` as a conflict (first by bronze id wins).
- The seed file is test and demo data, not a contract (spec Open integration items). Data loads the same
  file into `config.seed_recommendation` (R5) so both sides read one source of truth.
- Executor-level defense: `MAX_HOLD_S = 90` is also checked when an order is built, so a crafted entry
  above 90 s is refused (AC5) even if it bypassed the load check in a unit test.

### R4.3 Applying the order

- The engine looks up the board at the moment a bus arrives at a stop (`_arrive`). The order applies when
  `bus_id` and `stop_id` match, `from_s < t <= until_s` (strictly after the decision: a decision that comes
  after the arrival event cannot hold that visit, AC6) and the order is not cancelled. A breakdown firing
  on the bus cancels its pending orders (spec edge case).
- **Total dwell**: the departure time becomes `max(natural_end, t + hold_s)`. The natural dwell
  (`10 + 3 × boarded + 2 × alighted`, at least 10 s) is kept when it is already longer. The bus keeps
  emitting position reports with doors open. The observed dwell (`stop_departure` minus `stop_arrival`) is
  what data checks (R5).
- **Compliance**: draw `u = int(SHA-256("{seed}|hold|{rec_id}")[:8], 16) / 2**64`; the driver does **not**
  comply when `u < SIM_HOLD_NONCOMPLIANCE` (default 0.10, from the story brief, read from configuration).
  The draw uses no shared generator, so it cannot change the world's stream and does not depend on order
  of arrival. A test passes probability 1 and 0 (forced). For SC-008 the batch size is **N = 200**
  distinct `rec_id` values from a fixed seed: the count of non-compliant orders is reproducible run to run
  and equals the count in the truth records; the expected 20 is reported, not asserted as exact.
- Every order that is applied or refused for compliance appends one hold record to the truth (`rec_id`,
  `bus`, `stop`, `hold_s`, `complied`, effective step).

**Rationale**: a thread keeps the engine pure and the stream free of I/O; the board makes the engine
testable with a fake provider; strictly-after matching makes the result independent of poll timing in all
but the narrow live race documented above.

**Alternatives considered**

- Poll between steps in the main loop: a slow database (2 s timeout) would delay the stream (rejected;
  violates "never block").
- Listen with `LISTEN/NOTIFY` on decisions: the backend does not notify on bronze inserts, and the
  pipeline's channel is for gold snapshots (rejected).
- Sample compliance from the engine RNG: the draw order would depend on which orders arrive, breaking
  AC7 and the baseline identity (rejected).
- Hold added on top of the natural dwell: the spec Assumption chose total dwell; ADR-0003 says "dwell within
  ±15 s of the instructed duration". Kept as written; the plan states it.

## R5 — Observation of `executed` and the instruction status object

**Decision**

- One pure module `rules/holds.py` holds the constants and the observation rule used by data:
  `MAX_HOLD_S = 90` (ADR-0003 gate decision 8), `EXECUTED_TOLERANCE_S = 15` (ADR-0003, instruction
  schema), `match_visit(...)` and `observe(...)`. One definition each, as `ESTIMATED_AFTER_S` is.
- **Matching** (same rule as the engine in R4.3): a decision of `source = backend`, `action = apply`,
  known `rec_id`, matches the first `silver.stop_visits` row of the target bus at the target stop whose
  `arrival_ts` is strictly after `decided_at_sim` (any when null) and not after the recommendation's
  `expires_ts`. Orders are processed in bronze id order; the first order for a (bus, stop) takes the
  visit, a later one is `not_executed` (conflict).
- **Status** (one row per applied decision, in `gold.instruction_status`):
  - visit found with a departure: `observed_dwell_s = departure − arrival`; `executed` if
    `|observed_dwell_s − hold_s| <= 15` and `hold_s <= 90`, else `not_executed`. `ts_by_status.executed`
    or `.not_executed` = the departure event time.
  - no visit and the reference time is past `expires_ts`: `not_executed`, timestamp = `expires_ts`
    (covers AC6, a bus that never reaches the stop, and a breakdown that keeps it away).
  - a `bus_breakdown` incident of the bus that starts between `decided_at_sim` and the departure:
    `not_executed` (breakdown wins).
  - visit found but not yet departed, or the window still open: **no row yet** (pending).
  - `discard` and unknown `rec_id`: no row.
- Rows are rebuilt every cycle from bronze, silver and `config` (DELETE + INSERT in the cycle
  transaction), so reprocessing the same bronze gives the same rows (SC-012).
- **Which gold object carries it**: `gold.instruction_status` (columns in `data-model.md`): `rec_id`,
  `bus_id`, `stop_id`, `hold_s`, `observed_dwell_s`, `status` (`executed` | `not_executed`),
  `ts_by_status` JSONB with the one key, plus `rules_version` and `max_bronze_id`. Tests validate
  `status` and `ts_by_status` against `contracts/read/instruction.schema.json` (sub-schemas). `inst_id`
  and `text` belong to the backend; the backend joins by `rec_id` (open question 3). Data writes nothing
  to bronze; `confirmation` events stay the backend's.

**Known limitation (risk 4)**: a driver who did not comply but whose natural dwell is within ±15 s of D
reads as `executed`. At the demo stop the natural dwell is 10 to 15 s (measured at P-887 over the seven
visits of the 4,200 s run: 10 s in six, 15 s in one) against D = 90 s, so non-compliance reads `not_executed`.

**Alternatives considered**: a column on a new `gold.instruction` table that mimics the whole object
(rejected: would invent `inst_id`/`text`); writing a `confirmation` event with `executed` (rejected:
the backend is the only writer of command events, ADR-0003).

## R6 — The `incident` gold object (US-12, C5)

**Decision**

- Table `gold.incident`, one row per incident per snapshot, primary key `(snapshot_id, inc_id)`,
  `doc` JSONB validated by the generated `Incident` model, `rules_version`, `max_bronze_id`, and an
  `active` boolean for cheap filtering. Built in the cycle right after `build_snapshot`, from
  `silver.incidents` (already rebuilt for this cycle, so the two cannot differ).
- Mapping: `inc_id` = `silver.incidents.inc_id` (the bronze `event_id`, a UUID), `type` =
  `incident_type`, `target_id`, `duration_s = (end_ts − start_ts)` in seconds (= `duration_min × 60`),
  `since = start_ts`, `until = end_ts` when `end_ts <= as_of` (closed) else null (active),
  `reported_by` from the payload. Active means `start_ts <= as_of < end_ts` (002 FR-015).
- Console read: the rows of the latest snapshot, `WHERE active`. A convenience view
  `gold.incident_current` selects them for the newest snapshot of the current rules version.
- C5 shape (fixture `c5_breakdown`): active `bus_breakdown` incident for the bus, `reported_by =
  script`; the bus has `bus_state = broken_down` and `headway_ahead_s = null` (already built in 002);
  after `duration_s` the incident has `until` set and the bus returns to `in_service`.
- A scripted incident always has a numeric duration, so `duration_s` is never null for this story. The
  schema keeps it nullable for dispatcher reports (ADR-0003 gate 3). The pre-existing silver limit for a
  null-duration backend incident is recorded as risk 7, not changed here.

**Rationale**: same pattern as `corridor_now` (per-snapshot document, lineage columns), so replays and
audits work the same way.

**Alternatives considered**: a plain view over `silver.incidents` (it has no snapshot lineage and shows
only the latest cycle; rejected); gold rows for active incidents only (loses the closing time that the
schema models with `until`; rejected).

## R7 — The `recommendation_effect` gold object (US-11)

**Decision**: rebuilt each cycle in `pipeline/effects.py` from stored snapshots, then validated by the
generated model.

- **Orders considered**: every applied decision with a seeded `hold` recommendation (R5 matching).
- **Hold start `T0`**: the `arrival_ts` of the matched visit. If there is no matched visit (order
  never ran), `T0 = decided_at_sim` when known; otherwise no row (nothing to measure). The horizon is the
  recommendation's `horizon_s` (600 s in the `c1_bunching` fixture), so the window closes at `T1 = T0 +
  horizon_s`. **No row exists before `T1`** (AC2): the step needs a snapshot with `as_of_ts >= T1`.
- **`headway_before_s`**: `headway_ahead_s` of the held bus in the `corridor_now` doc of the last snapshot
  with `as_of_ts <= T0` (same rules version). At `T0` the bus has just arrived at the stop, so this is the
  headway at the target stop. Null if the bus is the leader, broken down, absent, or `Estimated` there.
- **`headway_after_s`**: the same field in the first snapshot with `as_of_ts >= T1`. After 600 s the held
  bus has left the stop, so "at the target stop" cannot be read literally; the plan uses the held bus at
  its position at `T1` (open question 2).
- **`headway_planned_s`**: `config.corridor_settings.headway_planned_s` (600).
- **`ewt_expected_s`**: the recommendation's `ewt_saving_s` when it is `>= 0`, else null (schema
  minimum 0).
- **`ewt_observed_s`**: `gold.service_metric.ewt_s` of the "after" snapshot, **clamped at 0**
  (schema minimum 0; the corridor EWT can be negative when headways are more regular than planned).
  Null when `computable` is false. The raw value stays in `gold.snapshots` lineage through
  `after_snapshot_id`.
- **Result** (pure `rules/effect.py`, threshold from `config.effect_settings.worked_threshold_s` = 30,
  ADR-0003 gate decision 6):
  1. `no_data` if `ewt_expected_s` or `ewt_observed_s` is null, or no "after" snapshot exists.
  2. `improvement = ewt_expected_s − ewt_observed_s` (applied as written; the semantic mismatch between a
     projected reduction and an observed EWT is reported to the data owner, spec Assumptions).
  3. `worked` if `improvement >= 30`; `partial` if `0 < improvement < 30`; if `improvement <= 0`: `partial`
     when the headway improved, `did_not_work` otherwise.
  4. "Headway improved" = `|after − planned| < |before − planned|`, both known (spec Assumptions). If
     either is null it counts as not improved.
  - Boundary cases: 29 s gives `partial`, 30 s gives `worked`; fixture values (55, 22) give `worked`.
- **Not executed holds** (AC5): the row is produced the same way; `T0` comes from the visit or
  `decided_at_sim`, so the dispatcher sees that the headway did not change.
- **Joins and lineage**: the doc validates against the schema; extra table columns carry
  `before_snapshot_id`, `after_snapshot_id`, `rules_version`, `max_bronze_id` (of the cycle that
  produced the row). A missing snapshot (refresh down in the window) gives `no_data`, and a later
  `compute --from --to` replay repairs the row on the next cycle because the table is rebuilt.
  Snapshot choice is `ORDER BY as_of_ts, max_bronze_id` so it is stable.
- Read-only: the step reads bronze, silver, gold and `config`, and writes only `gold.recommendation_effect`.
  The static guard on bronze writes covers the new files.

**Expectation for the demo (not a promise)**: a hold of at most 90 s moves a headway by at most 90 s. The
rule compares the seeded 55 s saving with the observed corridor EWT, so `worked` needs `ewt_observed_s <=
25`. The result is recorded as the rule yields it (SC-010); the numbers of the `c1_bunching` fixture
(before 180, after 530) cannot come from a single 90 s hold and are used only as rule input in tests.

**Alternatives considered**: recomputing headways at `T0` and `T1` from bronze with a second silver
build (duplicates the headway rule and needs a parametrized `bus_current_state`; rejected); a SQL view
(the result rule belongs in `rules/` as tested Python; rejected); freezing rows at first computation
(would hide a repair after a replay; rejected).

## R8 — Rules version, DDL and existing databases

**Decision**

- `RULES_VERSION` 1.0.0 → **1.1.0** (SemVer minor: new derivations, existing objects unchanged). It is
  bumped in Phase 1 with the first new gold table. `test_rules_version.py` is updated in the same commit.
  Snapshot ids change because they hash the version; a replay recomputes them.
- DDL in one new file, `src/data/db/init/007_scenarios.sql`, idempotent (`IF NOT EXISTS`, seeds with
  `ON CONFLICT DO NOTHING`), in three commented sections, one per phase. The throwaway test database
  applies `src/data/db/init/*.sql` in sorted order, so tests pick it up automatically.
- An existing volume does not get `007` (init scripts run on a fresh volume only, 003 R14). The demo uses a
  fresh project volume; for a developer stack the line to add to the runbook is
  `docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < src/data/db/init/007_scenarios.sql`.
- Generated read models: `make generate-read` gets `incident`, `recommendation` and
  `recommendation_effect` in `READ_SCHEMAS`; a second run leaves `git diff` empty.

## R9 — The demo script

**Decision**: `scripts/demo/run_demo.sh`, modelled on `scripts/drill/run_drill.sh` (003): own Compose
project `pulsoflota-demo`, own volume, non-default ports (`DEMO_POSTGRES_PORT` default 55433,
`DEMO_API_PORT` default 58001; aborts if a port is in use), refuses to run without `.env`, never prints
credentials, writes only under `demo-out/` (git-ignored).

Steps: `down -v` and `up -d` of its own project with `SIM_SEED=42`, `SIM_DURATION_S=2700`,
`SIM_PACE_S=0.9`, `REFRESH_CLOCK=data`, `SIM_SCENARIO_FILE` = the demo file, `SIM_HOLDS=on`, `SIM_TRUTH_PATH`
unset (truth goes to the container log); run `approve_hold.py` inside `ingestion` (piped, as
`feed_control.py`); sample the gold objects every 5 s into `demo-out/`; at the end print the table of
steps with the gold values read and the truth lines from the log.

**Pace**: wall seconds = simulated seconds × `SIM_PACE_S` / 5. 2,700 s × 0.9 / 5 = **486 s ≈ 8.1 min**
(the spec asks for about 8). At the default pace 1 it would be 540 s = 9 min.

**Timeline (candidate, seed 42, seconds after 22:00:00Z; to be fixed by dry run in Phase 4)**. The base
times that constrain it were measured (see Findings). After the first world injection later events differ
from the base case, so the final numbers are measured by a dry run at pace 0 and then pinned by an offline
test with a tolerance.

| Step | Simulated time | Wall time at 0.9 | What happens | Constraint from measurements |
|---|---|---|---|---|
| Start | 0 | 0 s | B-101 leaves P-883 at 10 s; B-102 to B-105 wait there | |
| D1 | `D1_SILENCE` B-101 from 250 s for 300 s | 45 s to 99 s | B-101 Estimated from about 370 s to 550 s; status `estimated`; no alert, no `bunched` | B-101 is alone on the corridor until B-102 leaves at 635 |
| C1 | `C1` on B-102 at a stop early in the corridor, `extra_s = 400`, `start_s = 700` | about 126 s | B-102 dwells 400 s longer; B-103 (departs 1235) closes to under 300 s | B-102 and B-103 are both on the corridor from 1235 to 1970; trip 1 of B-102 ends at 1970 |
| Decision | stand-in approves the seeded hold of B-103 for 90 s at a later stop, at a fixed simulated time after the `bunched` state shows | about 270 s | `decision` row written; B-103 dwells 90 s at the stop (natural dwell 10 to 15 s) | the stop must be after the bunching is visible and before B-103's horizon end; P-887 has dwell 10 to 15 s (measured) |
| Effect | hold start + 600 s | about 108 s of wall time after the hold | `recommendation_effect` row appears | window closes before the C5 step starts |
| C5 | `C5` on B-104 at about 2,400 s, `duration_s = 240` | about 432 s | B-104 halts, `bus_breakdown` incident active, bus `broken_down`; ends at about 2,640 s | B-104 is on the corridor from 1835 to 3145; the demo shows the breakdown and the incident only (FR-029) |
| Close | 2,700 s | 486 s | truth lines and the table printed | |

The C5 gap behind the stopped bus (the fixture shape) needs a leader, the stopped bus and a follower on the
corridor. For seed 42 that exists only in windows such as [1235, 1550] (B-101, B-102, B-103), so the
**integration test** for C5 uses a stop of B-102 at about 1,240 s for 240 s (ends 1,480 s, before B-101
finishes at 1,550 s) and asserts the gap behind it; the **demo** C5 step shows the breakdown and the
incident only, as FR-029 asks.

**Stand-in approval**: `approve_hold.py` is not part of `src/` (FR-020: no backend code is added to the
application). It waits until the newest non-backend `event_ts` reaches a given simulated time, then
inserts one `decision` row with a fresh UUID, `source = "backend"`, `action = "apply"` and a fixed
`user_id`, exactly as `command_event.schema.json` says. If the real backend is ready, the step is skipped.

**Alternatives considered**: running the demo at pace 1 (9 min) or pace 0.5 (4.5 min); pace 0.9 is the
nearest to the 8 minutes the spec states. A start offset in the simulator to skip the warm-up (rejected: it
would change the base case).

## R10 — Test strategy

- **Golden hashes first** (SC-001): `test_simulator_golden_hash.py` runs the CLI path for seed 42 and
  seed 7 at 3600 s and compares SHA-256 to the pinned values; it is also run with an empty scenario file and
  with `SIM_HOLDS` on against an empty bronze (Phase 2), both expected identical.
- **Determinism** (SC-001, AC8): two runs of the same scenario give the same event hash and the same truth.
- **Shape tests** (SC-003 to SC-005): after computing gold with `compute --from --to` on the crafted or
  simulated bronze, compare counts and states with the matching fixture's semantics, and with a
  `corridor_now` computed independently from the same bronze (existing `gold_support` helpers).
- **Contract**: every gold object validates against its schema (jsonschema, `format_checker`); the seed
  file validates against `recommendation.schema.json`; the scenario files are validated by the config
  model.
- **Human gate**: `discard`, no decision, unknown rec, a decision after departure, hold above 90 s:
  zero holds run and the bus stream equals the baseline.
- **Isolation** (SC-011): with the poller stopped, the database unreachable, `api` and `refresh` stopped,
  ingestion keeps inserting (host live check on project `pulsoflota-verify`, as in 003).
- **Static guards**: truth never read by the pipeline; no write to bronze from the poller, pipeline or
  rules; no `time`/`datetime.now`/unseeded `random` in `scenarios/injectors.py` and `channel.py`.
- **Coverage**: new code is mostly pure and covered by unit tests; the poller thread by an integration
  test with a real database. Quality rules (`rules/holds.py`, `rules/effect.py`) target about 100 %.
- **Live checks** use dedicated compose projects (`pulsoflota-verify`, `pulsoflota-demo`), never the
  default one (003 convention).

## R11 — Scope and evolution (not built)

C3 transfer surge and C4 segment accident; stochastic mode and calibrated rates; the "speed up the
follower" form of C1; reserve-bus dispatch (B-106, B-107 stay parked, Q3 = B); adjust-departure,
short-turn and reassign actions; the real recommendation door (backend integration, needs an ADR or
contract addendum); the decision engine; any REST/WebSocket endpoint or frontend; direction 2; Redis,
PostGIS, 1,000 events/s, HMAC, RBAC, SAST/SCA (turns 2 and 3); a second compose project file for the demo;
alerting on duplicates. A task that asks for one of these is flagged as outside the turn.

## R12 — Cycle cost

The new cycle steps read: incidents of this cycle (a few rows), backend decisions (a few rows), two
snapshots and one `service_metric` row per hold, and `config`. The 002 cycle already rebuilds five silver
tables from a few thousand bronze rows per simulated hour. Phase 3 measures the full cycle on the demo
run (2,700 s, about 2,900 events) before and after and records both in `verification.md`; the gate is that
the cycle stays well inside the 5 s refresh interval (a skipped tick is logged, 002 FR-039). No index is
added unless that measurement asks for one; the lookup of the "before" and "after" snapshots uses the
existing unique index on `gold.snapshots (as_of_ts, …)`.

## R13 — Dependencies

None added. Poller: `psycopg` 3 and `threading`. Scenario validation: Pydantic V2 (runtime dependency).
Compliance hash: `hashlib`. Schema checks in tests: `jsonschema` and `rfc3339-validator` (dev extra).
`pyproject.toml` and `uv.lock` are unchanged. `datamodel-code-generator` (dev extra) generates three read
models.

## R14 — Time budget (agent hours, 2026-11-22 and 23)

| Phase | Work | Estimate |
|---|---|---|
| 1 | golden hash, config model and validation, C1/C2/C5 hooks, channel layer, truth, incident table and step, shape tests | 1 h 45 min |
| 2 | hold rules, seed loader and model, poller thread, board, engine hold, instruction status, isolation test | 1 h 30 min |
| 3 | effect rule, pipeline step, tests, cycle timing | 45 min |
| 4 | dry runs, demo file, scripts, live run, verification | 1 h |
| Margin | Andon runs (about 2 min each), review fixes | 20 min |
| **Total** | | **5 h 20 min** |

This is over the 4–5 hour budget by about 20 minutes if nothing is cut. The cut order in `plan.md` Phases
(live test first, then the C2 live check) brings it to about 4 h 50 min. The 2026-11-24 demo needs Phases 1
to 4; Phase 3 can be cut only by dropping the effect step from the demo.
