---
description: "Task list for 002-silver-gold-baselines"
---

# Tasks: Silver and Gold Layers with M1/M2 Baselines

**Input**: `specs/002-silver-gold-baselines/` (spec `61b5268`, plan `4f00b08`): `plan.md`, `spec.md`, `research.md` (R1–R16, all decided), `data-model.md`, `quickstart.md`, `contracts/`.

**Branch**: `feature/002-silver-gold-baselines` (stacked on `feature/001-base-simulator`). **Lane**: Disciplined. **Turn**: 1.

**Tests**: ON (default; the spec and the constitution do not opt out). Principle V applies.

**Budget**: about 4–5 hours of agent work. Estimates per phase are in each phase header and sum to about 4 h 25 min.

**Phase numbering**: Phases 0–4 are the plan's phases. Phase 0 holds both Setup and Foundational work. A final Polish phase follows.

## Format: `- [ ] T### [P?] [US?] Description. Covers: ids`

- **[P]**: can run in parallel with the other [P] tasks of the same block (different files, no dependency on an incomplete task).
- **[US1..US4]**: the user story. Phase 0 and Polish carry no story label.
- **(CUT-n)**: member of cut list *n* (see "Cut List"). Unmarked tasks are not cuttable.
- **Covers**: FR / SC / research ids. `R14` and the other `R` ids refer to `research.md`.
- Test files use the names in `plan.md`. Where a plan file is split across tasks, the later task adds test functions to the same file (so it is not [P] with the earlier one).

## Test-first rule

Inside each phase, the test tasks come first and **MUST be written and MUST FAIL before the implementation task that names them** ("makes T### pass"). Each implementation task lists the test task(s) it satisfies. Each phase ends with a verification task that runs the check named in `plan.md` and `quickstart.md`.

Test commands (from `quickstart.md`):

- Whole suite with coverage: `docker compose --profile tools run --rm tests`
- One file: `docker compose --profile tools run --rm tests python -m pytest <file> --no-cov -q`
- Any change to the init scripts needs a fresh volume for the live stack: `docker compose down -v && docker compose up -d --build`. Tests use throwaway databases (R10) and do not need it.

## Cut List

If time runs short, cut in this order (plan.md "What is cut"):

| Cut | What | Tasks |
|---|---|---|
| **CUT-1** | Only the expensive Phase 4 checks: the failure test, the notify integration test, the 10-minute live cadence run (SC-009 full), and the 10-minute part of T071. The loop, the `REFRESH_CLOCK` selector and the `refresh` service stay, because without the loop nobody recomputes gold during the live demo. T071 keeps its short check (fresh-volume stack, one `gold_snapshot` notification within 15 s, SC-010). | T066, T067, T068, T071 (10-minute part only) |
| **CUT-2** | SC-001 at full density: run the 60-minute replay with `--step 60` (60 snapshots) instead of `--step 5` (720), keep the `slow` marker, record the reduced density in `verification.md`. | T056 (the density parameter), T074 (the record) |
| **CUT-3** | M2 observed-path tests beyond one crafted 5-day case: the R12 sample-rule edge cases. The x.5 rounding cases (one per M2 path, R13) are in T053 and stay. | T054 |

**Not cuttable** (this is the minimum delivery, see "Implementation Strategy"): Phases 0–3 except the CUT-2 and CUT-3 items above, including the R14 simulator fix, the `c1_bunching` fixture fix (T075), the M1 and M2 reference fallbacks, `decision_inputs` schema validity, and the idempotency and lineage tests. In Phase 4: T064, T065, T069, T070 and the short check of T071 (the refresh loop itself).

---

## Phase 0: Foundations (~50 min)

**Purpose**: a clean simulator base case, then everything the later phases build on: read models, dev dependencies, DDL and seed, reference loader, test database fixture and bronze builders.

**Ends with**: T024 (R14 acceptance green, updated 001 simulator tests green, fixtures valid, DDL/seed test green, ADR addendum present).

### 0A. R14 simulator base-case fix (FIRST)

- [x] T001 [P] Write the R14 acceptance test in `tests/unit/test_simulator_base_headway.py`. For seeds 42 and 7, run `run(seed, 7200)` with no injections, take the `stop_arrival` events at P-883 ordered by `event_ts`, and assert (1) the median gap between consecutive ones is 600 s ± 60 s and (2) no gap is below 300 s. Add a test that the simulator default planned headway is 600 (the equality with the seeded `config.corridor_settings.headway_planned_s` is asserted in T016, once the table exists). Add a test that setting `SIM_PLANNED_HEADWAY_S` to another value changes the start spacing. MUST fail against the current simulator. Covers: R14, FR-021, FR-022 (base case must not look bunched), SC-002, SC-003.
- [x] T002 [P] Write `tests/unit/test_env_example.py`: `.env.example` contains `SIM_PLANNED_HEADWAY_S=600`, `REFRESH_INTERVAL_S=5`, `REFRESH_CLOCK=data`, no secret values, and `src.pulsoflota.config.get_sim_planned_headway_s()` returns 600 when the variable is unset and the variable's value when set. Also parse `docker-compose.yml` (PyYAML, from T011) and assert that the `ingestion` service environment passes `SIM_PLANNED_HEADWAY_S` with the default 600 (for example `${SIM_PLANNED_HEADWAY_S:-600}`), so the planned headway changes without editing compose. MUST fail. Covers: R14, R3, R16, FR-021.
- [x] T003 Add `get_sim_planned_headway_s()` to `src/pulsoflota/config.py` (reads `SIM_PLANNED_HEADWAY_S`, default 600, same style as `SIM_SEED`). Add `SIM_PLANNED_HEADWAY_S=600`, `REFRESH_INTERVAL_S=5` and `REFRESH_CLOCK=data` (comment: `data` for the simulator demo, `wall` for real telemetry; the code default is `wall`) to `.env.example`. No secrets. In `docker-compose.yml`, pass `SIM_PLANNED_HEADWAY_S: ${SIM_PLANNED_HEADWAY_S:-600}` to the `ingestion` service environment. Makes T002 pass. Covers: R14, R3, R16.
- [x] T004 Fix the simulator schedule in `src/simulator/model.py` and `src/simulator/engine.py`: remove `START_HEADWAY_S` and `LAYOVER_S`; buses start 600 s apart (`SIM_PLANNED_HEADWAY_S`); trip *n+1* of each bus is dispatched from P-883 at `start_at + n × cycle` with `cycle = (number of in-service buses) × planned headway` (3,000 s), or immediately if the bus reaches the terminal after that time. Change schedule generation only: no event type, field, payload or contract changes, no change to the ingestion boundary. Keep the run seeded and deterministic. Makes T001 pass. Covers: R14, FR-025 (no contract change).
- [x] T005 Run the whole 001 suite (`docker compose --profile tools run --rm tests`) and list the tests that fail because they depend on the old spacing (candidates: `tests/unit/test_simulator_travel_time.py`, `tests/unit/test_simulator_capacity.py`, `tests/unit/test_simulator_determinism.py`). Write the list as a short "Phase 0 findings" section in `specs/002-silver-gold-baselines/verification.md` (create the file). Covers: R14.
- [x] T006 Update only the 001 simulator tests found in T005 (files under `tests/unit/test_simulator_*.py`) so they match the new spacing (for example the number of completed trips in one hour, rider-arrival bounds, seeded expectations). Do not weaken a check to make it pass and do not change a contract test; each changed assertion gets a one-line comment `# R14: new spacing`. Covers: R14, FR-025.
- [x] T007 R14 checkpoint: run the 001 unit and contract suites, then `tests/unit/test_simulator_base_headway.py`, all green. Recount the events of the 1-hour seed-42 run (old number 3,986) and record the new count and the median/minimum P-883 gap for seeds 42 and 7 in `specs/002-silver-gold-baselines/verification.md`. Covers: R14, plan "Scale/Scope".

### 0B. Remaining foundations

- [x] T008 [P] Write `tests/contract/test_read_fixtures.py`: validate all 18 fixtures under `contracts/read/fixtures/` against `contracts/read/*.schema.json` with `Draft202012Validator` and a `FormatChecker` (uuid, date-time); validate `specs/002-silver-gold-baselines/contracts/gold_snapshot_notify.schema.json` against the metaschema and check one valid and one invalid payload. MUST fail until the dev dependencies exist. Covers: SC-001, Gate 1, R9.
- [x] T009 [P] Write `tests/unit/test_generated_read_models.py`: `src.pulsoflota.models.read.source_status`, `corridor_now` and `decision_inputs` import, and the `normal` fixture of each validates through its model (`model_validate`) and dumps back with `model_dump(mode="json")` to the same JSON. MUST fail until T012. Covers: Principle II, R9, FR-025.
- [x] T010 [P] Write `tests/unit/test_rules_version.py`: `src.rules.RULES_VERSION == "1.0.0"`; `src.rules`, `src.pipeline` and `src.refresh` are importable; the pytest markers `slow` and `live` are registered (run under `--strict-markers`). MUST fail. Covers: FR-006, FR-017.
- [x] T011 Update `pyproject.toml` and relock `uv.lock`: dev extra += `jsonschema`, `rfc3339-validator` (and `PyYAML` if not already locked, for the compose test in T065); package list += `src/rules`, `src/pipeline`, `src/refresh`; register pytest markers `slow` and `live`. No new runtime dependency. Makes T008 pass. Covers: R9, SC-001.
- [x] T012 Add the `generate-read` target to `Makefile` (datamodel-code-generator over `contracts/read/{source_status,corridor_now,decision_inputs}.schema.json` into `src/pulsoflota/models/read/`, same options as the existing event-model target) and generate the three modules. Generated files are never hand-edited. Makes T009 pass. Covers: Principle II, R9.
- [x] T013 Create `src/rules/__init__.py` with `RULES_VERSION = "1.0.0"` and empty `src/pipeline/__init__.py` and `src/refresh/__init__.py`. Makes T010 pass. Covers: FR-006, FR-017, R1.
- [x] T014 [P] Write `tests/integration/test_db_fixture.py`: the throwaway-database fixture creates a database from a template built by applying `db/init/*.sql` in order, gives each test module its own database, drops it at teardown, and leaves the compose database untouched (row counts in the live `bronze.events` do not change). MUST fail. Covers: R10, SC-004, SC-005 (isolation prerequisite).
- [x] T015 Add the module-scoped throwaway-database fixture to `tests/conftest.py` (`CREATE DATABASE … TEMPLATE <session template>`, template built once per session from `db/init/*.sql` in order, then reference tables loaded when T020 exists) and add `./db:/app/db:ro` to the `tests` service in `docker-compose.yml`. Makes T014 pass. Covers: R10.
- [x] T016 [P] Write `tests/integration/test_schema_init.py`: the `config`, `silver` and `gold` tables of `data-model.md` exist; `config.corridor_settings.headway_planned_s` equals the simulator default `get_sim_planned_headway_s()` (R14); seed values equal FR-034 (`headway_planned_s` 600, `drivers_free` 2, `hold_penalty_s` 0, `early_departure_penalty_s` 0, `min_sample_count` 5, `m2_stop_id` `P-883`, roster B-101..B-107 with B-106/B-107 `reserve`, 18 enabled stops P-883..P-900); the reference tables loaded by `src/pipeline/reference.py` equal the CSVs in `data/reference/`; loading twice leaves them unchanged; `gold.snapshots` has a unique key on `(as_of_ts, rules_version, max_bronze_id)`; every gold table has non-null `rules_version` and `max_bronze_id`; init scripts re-run without error (`IF NOT EXISTS`). Add a test that `docs/adr/0001-data-layers-and-ingestion-semantics.md` contains the `config` addendum line. MUST fail. Covers: FR-034, FR-028, FR-017, R11, SC-008.
- [x] T017 [P] Create `db/init/003_config.sql`: `config` schema, `corridor_settings`, `fleet_roster`, `enabled_stops` with the seed values and constraints of data-model C1–C3, and the empty reference tables of C4 (`ref_stops`, `ref_segments`, `ref_congestion_factor`, `ref_demand_shape`, `ref_demand_volume`). Idempotent. Part of making T016 pass. Covers: FR-034, FR-021, FR-028, R11.
- [x] T018 [P] Create `db/init/004_silver.sql`: tables `silver.position_history`, `silver.incidents`, `silver.bus_current_state`, `silver.stop_visits`, `silver.segment_traversals` with the columns, keys, CHECK constraints and the `(bus_id, trip_id, event_ts, bronze_id)` index of data-model S1–S5 (for example `data_quality IN ('live','estimated')`, `hour_band 0..23`). Idempotent. Part of making T016 pass. Covers: FR-008–FR-015, FR-026.
- [x] T019 [P] Create `db/init/005_gold.sql`: `gold.snapshots` (PK `snapshot_id`, unique `(as_of_ts, rules_version, max_bronze_id)`), `gold.source_status`, `gold.corridor_now`, `gold.decision_inputs` (`snapshot_id` PK/FK, `doc JSONB NOT NULL`), `gold.service_metric`, `gold.m1_baseline` (`source IN ('observed','reference')`, `forecast_travel_s >= 0`), `gold.m2_baseline` (`band 0..95`, `arrivals_forecast >= 0`); every table has `rules_version TEXT NOT NULL` and `max_bronze_id BIGINT NOT NULL`. Idempotent. Part of making T016 pass. Covers: FR-016, FR-017, FR-024, FR-029, SC-008.
- [x] T020 Create `src/pipeline/reference.py`: load `data/reference/{stops,segments,congestion_factor,demand_params,demand_volume}.csv` into `config.ref_*` with `DELETE` + `INSERT` in one transaction (parameterized, `stop_seq` = file order). Wire it into the fixture of T015 when building the template. Part of making T016 pass. Covers: FR-001, FR-013, FR-028, FR-031, R11.
- [x] T021 Add the one-line addendum to `docs/adr/0001-data-layers-and-ingestion-semantics.md`: *"Addendum 2026-11-18: a fourth schema, `config`, holds static configuration and reference tables. It holds no derived data and no secrets."* Change nothing else in the file. Makes the addendum check of T016 pass. Covers: R11.
- [x] T022 [P] Write `tests/integration/test_bronze_builders.py`: the builders of `tests/fixtures/bronze_builders.py` are deterministic (fixed ids and times, no unseeded randomness), every event passes the real boundary `src.ingestion.bronze.ingest`, and builders exist for the `normal`, `c1_bunching`, `d1_source_outage`, `c2_gap` and `c5_breakdown` timelines, for stop visits and traversals, for incident reports with `duration_min`, and for backend `command_event` rows. MUST fail. Covers: R10, SC-002, data-profile testing (small deterministic fixtures).
- [x] T023 Create `tests/fixtures/bronze_builders.py`: deterministic crafted bronze timelines with constant speeds and staggered starts so headway classes are unambiguous (the fixture comparison in SC-002 does not compare headway values). Include helper functions for position streams, stop arrival/departure pairs, incident reports and backend command events. No PII. Makes T022 pass. Covers: SC-002, SC-003, R10.
- [x] T075 [P] Fix the `c1_bunching` fixture (data owner approved 2026-11-18). In `contracts/read/fixtures/c1_bunching/corridor_now.json`, change only B-102's `headway_ahead_s` from `752` to `960`; B-102 stays `gap` and `n_gaps` stays 1. This is a fixture correction, not a schema change: no ADR, no change to any schema or other fixture. Add to `tests/contract/test_read_fixtures.py` a check that every bus in every `corridor_now` fixture has a `bus_state` consistent with its `headway_ahead_s` against the thresholds 300 s and 900 s (planned 600), except `leader`, `broken_down` and the buses FR-011 forces to `regular`; the check fails on the old value and passes on `960`. Covers: SC-002, FR-022, spec Assumptions.
- [x] T024 **Phase 0 verification** (quickstart §Phase 0): run `make generate-read` twice and confirm `git diff --exit-code src/pulsoflota/models/read/`; run `tests/unit/test_simulator_base_headway.py`, the updated 001 simulator tests, `tests/contract/test_read_fixtures.py` (all 18 fixtures valid, including the corrected `c1_bunching`; notify schema valid), `tests/unit/test_env_example.py` (including the compose wiring of `SIM_PLANNED_HEADWAY_S`), `git diff --stat contracts/` showing only `contracts/read/fixtures/c1_bunching/corridor_now.json` with a one-value change, `tests/integration/test_schema_init.py`, `tests/integration/test_db_fixture.py`, `tests/integration/test_bronze_builders.py`; run `grep -n "config" docs/adr/0001-data-layers-and-ingestion-semantics.md` and confirm `git diff` of the ADR shows one added line. All green. Record results in `specs/002-silver-gold-baselines/verification.md`. Covers: R14, R11, SC-001, FR-034.

**Checkpoint**: clean base case, base for every later test in place.

---

## Phase 1: User Story 1 – Silver Current State (Priority: P1) (~60 min)

**Goal**: a trustworthy per-bus silver picture derived only from bronze, with the strict 120 s Estimated rule, stop visits, segment traversals with exclusion flags, and incidents.

**Independent Test**: load a fixed bronze batch into a throwaway database, build silver, inspect per-bus state, visits and traversals; drop silver, rebuild, compare.

**Ends with**: T033 (US1 scenarios 1–6, Estimated boundary, rebuild equality, bronze untouched).

### Tests for User Story 1 (write first; MUST fail)

- [x] T025 [P] [US1] Write `tests/unit/test_no_bronze_writes.py`: a static guard that no `INSERT`, `UPDATE`, `DELETE` or `TRUNCATE` statement targets `bronze.` in `src/rules/`, `src/pipeline/`, `src/refresh/` (SQL files and Python strings). Covers: FR-002, data-model invariants.
- [x] T026 [P] [US1] Write `tests/integration/test_silver.py` (current state), crafted through the builders of T023: one row per bus holding its latest `bus_position` by `(event_ts, id)` with ties by higher bronze id, with `prev_stop_id` and `next_stop_id` (a bus dwelling at P-891, 3240.5 m, gives prev P-891 and next P-892); report age 120 s → `live`, 121 s → `estimated` with the position unchanged and not extrapolated; a new report returns it to `live` in the next build; a `source = backend` event never refreshes `last_report_ts`; a bus that never reported has no row; a bus with a `stop_arrival` at P-900 on its current trip is `on_corridor = false`; reserve buses B-106/B-107 undispatched have no corridor row; `operational_status` precedence (`broken_down`, `in_service`, `reserve`, `off_corridor`); events later than `as_of_ts` or with `id > M` are ignored; arrival time is never used. Covers: FR-003, FR-007–FR-011, US1 scenarios 1–3, edge cases, R4, R7.
- [x] T027 [P] [US1] Write `tests/integration/test_silver_visits_traversals.py`: stop visits pair arrival and departure on the same trip (dwell, boarded, alighted, rejected from the `stop_departure` payload) and no row exists until both exist; a traversal has `travel_s = t_arrival(i+1) − t_departure(i)`, its segment id (1–17) and `hour_band` = local hour (fixed UTC−5 offset) of the departure, checked at the T051 boundaries (departures at 04:59:59Z, 05:00:00Z and 19:00:00Z give bands 23, 0 and 14); no traversal until the arrival at the next stop exists; `travelled_while_estimated` is set when two consecutive bus reports inside `[t_departure, t_arrival]` (ends included) are more than 120 s apart, and not at exactly 120 s; `broken_down` is set when a `bus_breakdown` incident for that bus overlaps the interval; incidents are active on `[event_ts, event_ts + duration_min)`, `duration_min = 0` is never active, incidents from `source = backend` count, the incident id is the `incident_report` `event_id`, and only a `bus_breakdown` with a bus target makes that bus `broken_down`. Covers: FR-012–FR-015, FR-026, US1 scenarios 4–5, R7.
- [x] T028 [P] [US1] Write `tests/integration/test_rebuild.py` (silver part): build silver at a fixed `as_of_ts`, drop and recreate the `silver` schema tables, rebuild at the same `as_of_ts`, compare ordered dumps of every silver table (identical); the rebuild uses `DELETE` and not `TRUNCATE` (a concurrent reader transaction is not blocked); bronze row count and checksum are unchanged by a build. Covers: FR-001, FR-002, FR-005, US1 scenario 6, R2.

### Implementation for User Story 1

- [x] T029 [US1] Create `src/rules/sql/silver_position_history.sql` and `src/rules/sql/silver_incidents.sql` (parameterized with `$as_of_ts` and `$M`; read bronze with `payload->>'…'`, filter `id <= M AND event_ts <= as_of_ts`) and `src/pipeline/silver.py`, the runner that deletes and rebuilds all silver tables in dependency order from the SQL files, using only parameterized queries. Makes the history and incident parts of T026/T027, T025 and T028 pass. Covers: FR-001, FR-007, FR-015, R1, R2, R4.
- [x] T030 [P] [US1] Create `src/rules/sql/silver_bus_current_state.sql`: latest position, current trip, `prev`/`next` stop from `config.ref_stops`, `last_report_ts`, strict `> 120 s` Estimated rule from the constant in one place (a parameter, not a literal in several queries), `on_corridor`, `operational_status` with the R7 precedence. Makes T026 pass. Covers: FR-008–FR-011, R7.
- [x] T031 [P] [US1] Create `src/rules/sql/silver_stop_visits.sql`: pair arrival and departure per bus, trip and stop; counts from the `stop_departure` payload. Makes the visit tests of T027 pass. Covers: FR-012, R7.
- [x] T032 [P] [US1] Create `src/rules/sql/silver_segment_traversals.sql`: segments from `config.ref_stops` order, `travel_s`, `hour_band` as `extract(hour from (t AT TIME ZONE 'UTC' - interval '5 hours'))`, the same fixed UTC−5 offset as Python (T051/T058), not `AT TIME ZONE 'America/Bogota'`, the two exclusion flags. Makes the traversal tests of T027 pass. Covers: FR-013, FR-014, FR-026, R7.
- [x] T033 [US1] **Phase 1 verification** (quickstart §Phase 1): run `tests/integration/test_silver.py`, `tests/integration/test_silver_visits_traversals.py`, `tests/integration/test_rebuild.py`, `tests/unit/test_no_bronze_writes.py`; all green. Record in `verification.md`. Covers: US1 scenarios 1–6, FR-001, FR-002, FR-010.

**Checkpoint**: silver is correct and rebuildable; US1 is independently testable.

---

## Phase 2: User Story 2 – Gold Console Views (Priority: P2) (~60 min)

**Goal**: one snapshot per cycle with `source_status`, `corridor_now` and the service metric, computed on demand with the `compute` CLI.

**Independent Test**: from prepared silver, compute one snapshot and validate both objects against their JSON Schemas; compare with the fixture scenarios; re-ingest and recompute.

**Ends with**: T050 (SC-002 on 5 fixtures, SC-003, SC-004, SC-007, SC-008, schema validation, clamp to 0).

### Tests for User Story 2 (write first; MUST fail)

- [x] T034 [P] [US2] Write `tests/unit/test_headway.py`: known position histories give the expected interpolated pass time and `headway_ahead_s`; the first sample already `>=` the follower's distance uses its time; equal distance gives exactly 0; a negative difference (stale follower) is clamped to 0 (R8, DECIDED); the nearest operational bus ahead is used and a `broken_down` bus is skipped; leader and broken-down buses give `null`; interpolation uses the bus ahead's current trip only. Covers: FR-020, R8, ADR-0003 gate decisions 1–2.
- [x] T035 [P] [US2] Write `tests/unit/test_classify.py`: state order `broken_down` → `leader` → `bunched` (< 0.5 × 600) → `gap` (> 1.5 × 600) → `regular`; exactly 300 s and 900 s are `regular`; FR-011 (an Estimated bus and the bus directly behind it are `regular`, the Estimated bus keeps its headway value, neither counts in `n_bunched`/`n_gaps`); two consecutive Estimated buses; all buses silent → status `estimated`, all `regular`; an Estimated leader keeps `leader`; equal distance → 0 and `bunched` (tie by `bus_id`); a broken-down leader hands `leader` to the furthest operational bus; single operational bus; summary counts (`buses_in_service` excludes `broken_down`); `source_status` rules (`no_data`, `estimated`, `live`, `sources_down` ordered by `bus_id` with `since` = last report time, never-reported bus not listed); the planned headway comes from a parameter, not a literal. Covers: FR-011, FR-018, FR-019, FR-021–FR-023, US2 scenarios 1–4 and 3a, edge cases.
- [x] T036 [P] [US2] Write `tests/unit/test_service_metric.py`: {300, 900} → mean wait 375 s and EWT 75 s; four × 600 → 300 s and 0 s; scheduled wait 300 s at planned 600; uses non-null headways of all operational buses including those forced to `regular` by FR-011 (R8); no headway or Σh = 0 → not computable with NULL values and `n_headways = 0`. Covers: FR-024, SC-007, US2 scenario 6.
- [x] T037 [P] [US2] Write `tests/unit/test_snapshot_id.py`: the id is deterministic for `(as_of_ts ISO-8601 UTC, rules_version, max_bronze_id)`, differs when any input differs, has UUID version-4 and variant bits, and validates as `format: uuid`. Covers: R5, FR-016, FR-005.
- [x] T038 [P] [US2] Write `tests/integration/test_gold_fixtures.py`: crafted bronze (T023) for `normal`, `c1_bunching`, `d1_source_outage`, `c2_gap` and `c5_breakdown`; the produced `source_status` and `corridor_now` equal the fixtures in bus order, `bus_state`, `data_quality`, `status`, `sources_down` and summary counts (not headway values). `c1_bunching` is included, using the corrected fixture of T075 (B-102 `gap`, `n_gaps` 1), so the file covers 5 scenarios. Covers: SC-002, US2 scenarios 1–4.
- [x] T039 [P] [US2] Write `tests/integration/test_gold_d1.py`: after one bus's reports stop, it is `estimated` and in `sources_down` in the first snapshot whose reference time is more than 120 s after its last report (at most 125 s with a 5 s step); it and the bus behind it are `regular` and not counted; it is `live` again in the first snapshot after it reports; zero `bunched`, `gap` or `broken_down` states or incidents attributable. Covers: SC-003, FR-010, FR-011.
- [x] T040 [P] [US2] Write `tests/integration/test_idempotency.py`: ingest a batch twice (second time all `duplicate_event`, `max_bronze_id` unchanged), recompute at the same `as_of_ts` → no new snapshot row, byte-identical silver and gold; recompute twice in a row → still one snapshot. Covers: SC-004, FR-005, US2 scenario 7, R5.
- [x] T041 [P] [US2] Write `tests/integration/test_gold_contract.py`: every stored `doc` validates against its JSON Schema (draft 2020-12, format checks); `doc->>'snapshot_id'` and `doc->>'as_of_ts'` equal the snapshot row; `source_status`, `corridor_now` and `service_metric` of one cycle share one `snapshot_id`; every gold row has non-null `rules_version` and `max_bronze_id`; empty bronze gives `no_data`, empty `buses`, zero counts, `max_bronze_id = 0`; a failure while building rolls back with no snapshot row. Covers: SC-001, SC-008, FR-016–FR-019, FR-025, FR-037, FR-040 (cycle level).
- [x] T042 [P] [US2] Write `tests/integration/test_compute_cli.py` (contract `contracts/compute-and-refresh.md`): `--as-of` prints one JSON line (`snapshot_id`, `as_of_ts`, `max_bronze_id`, `status`) and exits 0; `--from/--to --step` produces one snapshot per step; `--no-notify` sends no notification; without it a listener on `gold_snapshot` receives exactly one payload per new snapshot, that validates against `gold_snapshot_notify.schema.json`, after the snapshot is readable; no notification for a no-op recompute or a rolled-back cycle; a skipped cycle when the advisory lock is held; the CLI ignores `REFRESH_CLOCK`; non-zero exit after a failed cycle. Covers: FR-004, FR-037, FR-038, FR-040, R5, R6.

### Implementation for User Story 2

- [x] T043 [P] [US2] Create `src/rules/headway.py`: pass-time interpolation, equal-distance rule, clamp to 0, nearest operational bus ahead (pure functions, no database). Makes T034 pass. Covers: FR-020, R8.
- [x] T044 [P] [US2] Create `src/rules/classify.py`: `bus_state` with the FR-022 order and the FR-011 suppression, summary counts, `source_status` status and `sources_down` (pure functions; the planned headway is an argument). Makes T035 pass. Covers: FR-011, FR-018, FR-021–FR-023.
- [x] T045 [P] [US2] Create `src/rules/service_metric.py`: mean wait, scheduled wait, EWT, not-computable case. Makes T036 pass. Covers: FR-024, SC-007.
- [x] T046 [P] [US2] Create `src/rules/snapshot_id.py`: `uuid.UUID(int=…, version=4)` from `sha256(as_of_ts | rules_version | max_bronze_id)`. Makes T037 pass. Covers: R5.
- [x] T047 [US2] Create `src/pipeline/gold.py`: build `source_status` and `corridor_now` through the generated models (T012) and store `model_dump(mode="json")` in `doc`; fixed list orders; insert `gold.snapshots` with `ON CONFLICT DO NOTHING`, then the `source_status`, `corridor_now` and `service_metric` rows with `rules_version` and `max_bronze_id`. Orchestration only, no thresholds. Makes T038, T039 and T041 pass together with T048. Covers: FR-016–FR-019, FR-025, FR-017, SC-008.
- [x] T048 [US2] Create `src/pipeline/cycle.py`: one `REPEATABLE READ` transaction; `pg_try_advisory_xact_lock` (skip and log if held); `M = max(id)` (0 if empty); rebuild silver (T029–T032); build and store gold (T047); `pg_notify('gold_snapshot', '{"snapshot_id": …}')` only when the snapshot insert was new; rollback on any error with a structured JSON log line (error class and correlation id, no traceback in outward text); takes `as_of_ts` as an argument. Makes T040 and T042 pass. Covers: FR-004, FR-005, FR-037, FR-038, FR-040, R4, R5, R6.
- [x] T049 [US2] Create `src/pipeline/compute.py`: the `--as-of`, `--from/--to/--step` and `--no-notify` CLI of `contracts/compute-and-refresh.md`; reads `DATABASE_URL` and `LOG_LEVEL`; loads the reference tables at start; one JSON line per snapshot. Makes T042 pass. Covers: FR-004, R16.
- [x] T050 [US2] **Phase 2 verification** (quickstart §Phase 2): run T034–T042 test files; all green. Manual check on the live stack: `docker compose run --rm ingestion python -m src.pipeline.compute --as-of "<UTC time inside the simulated hour>"` prints a `snapshot_id`, and `SELECT doc FROM gold.corridor_now WHERE snapshot_id = '<id>'` returns a schema-shaped object (simulated events start at 2026-11-24 22:00:00Z). Record in `verification.md`. Covers: SC-002, SC-003, SC-004, SC-007, SC-008, R8.
- [x] T050a [US2] Waiting-bus rework (data owner decision 2026-11-20, R7): `tests/integration/test_waiting_buses.py` (crafted buses waiting at P-883 at 0 m before the first trip and during a layover; written first, failed) and `tests/integration/test_real_run_acceptance.py` (real simulator run, seed 42, 3,600 s, `ingest`, `run_cycle` every 5 min: no bunched, no gaps, headways 300–900 s); fix in `src/rules/sql/silver_bus_current_state.sql`, `db/init/004_silver.sql` (`waiting` column) and `src/pipeline/gold.py` (`sources_down`). Covers: SC-002, SC-003, R7, R14.

**Checkpoint**: US2 works with silver only. The `compute` CLI delivers on-demand snapshots, which is the fallback if Phase 4 is cut.

---

## Phase 3: User Story 3 – M1/M2 Baselines and Decision Inputs (Priority: P3) (~50 min)

**Goal**: M1 per segment × hour band, M2 per 15-minute band at P-883, and `decision_inputs` with the reference fallbacks.

**Independent Test**: seed silver history, compare each M1/M2 value with an independent oracle, validate `decision_inputs` and its equality with `corridor_now`.

**Ends with**: T063 (SC-006 oracles, `decision_inputs` valid and equal to `corridor_now`, SC-001 replay, SC-005).

### Tests for User Story 3 (write first; MUST fail)

- [x] T051 [P] [US3] Write `tests/unit/test_timebands.py`: local hour band (UTC−5 fixed offset, no `zoneinfo`), M2 band index `local_hour × 4 + local_minute div 15` (96 bands, boundaries 00:00, 00:14, 00:15, 23:59), first clock-aligned 15-minute window with `window_start_ts >= as_of_ts` (an `as_of_ts` exactly on a boundary returns that boundary), and the UTC/local date change at 05:00Z → 00:00 local (UTC−5), tested at 04:59:59Z (previous local day, hour band 23, M2 band 95) and 05:00:00Z (new local day, hour band 0, M2 band 0); 19:00Z is 14:00 local. Covers: FR-026, FR-030, FR-032, R7, R13.
- [x] T076 [P] [US3] Write `tests/integration/test_timebands_sql.py`: for the boundary instants listed in T051 (04:59:59Z, 05:00:00Z, 05:14:59Z, 05:15:00Z, 19:00:00Z, 04:59:00Z next day), the SQL expression of T032 and `src/rules/timebands.py` give the same hour band and the same 15-minute band index. MUST fail until T058 exists. Covers: FR-026, FR-030, R7.
- [x] T052 [P] [US3] Write `tests/integration/test_baselines.py` (M1): all 408 rows (17 × 24) exist with `source`, `n_samples`, `rules_version`, `max_bronze_id`; `reference` values equal an independent oracle `length_m ÷ (free_flow_kmh ÷ 3.6) ÷ congestion_factor(hour)` computed from the CSVs within 0.1 s; with ≥ 5 crafted eligible traversals the value is `observed` and equals `statistics.median` (even count: mean of the two middle values); 4 samples → `reference` with `n_samples = 4`; flagged traversals (Estimated, broken-down) are not counted. Covers: FR-027–FR-029, SC-006, US3 scenarios 1–3, R13.
- [x] T053 [P] [US3] Write `tests/integration/test_baselines.py` (M2, same file as T052, add after it): all 96 rows exist with `source` and `n_samples`; `reference` rows equal `Decimal(633.92 × shape(hour) / 4).quantize(ROUND_HALF_UP)` exactly (R13, oracle uses `Decimal`, not Python `round`); one crafted 5-day observed case → `observed` and the median of the daily counts at P-883 for that band, with one R12 basic check (a completed band with the simulator running and no riders counts as sample 0). Add one x.5 rounding case per M2 path (R13, round half away from zero): on the observed path, daily counts {2, 3} give median 2.5 → 3; on the reference path, a crafted `config` shape and volume for which `daily_riders_dir1 × shape(hour) / 4` is exactly x.5 gives the value rounded up through the formula (oracle in `Decimal`). These two cases stay even if CUT-3 is taken. Covers: FR-030, FR-031, FR-029, SC-006, US3 scenario 4, R12, R13.
- [x] T054 [US3] (CUT-3) Add to `tests/integration/test_baselines.py` (after T053): R12 sample-rule edge cases only (a band that has not ended is not a sample; a band with no non-backend `bus_position` in it is not a sample; backend events do not count as the simulator running; today's completed bands count). The x.5 rounding cases are in T053. Covers: R12, SC-006.
- [x] T055 [P] [US3] Write `tests/integration/test_decision_inputs.py`: validates against `decision_inputs.schema.json`; `buses` and `summary` equal `corridor_now` for the same `snapshot_id`; `travel_time_forecast` has 17 entries ordered by segment for the local hour of `as_of_ts`; `demand_15min` is the next window at or after `as_of_ts`; `reserve_free` = [B-106, B-107] while undispatched and a dispatched reserve leaves it; `drivers_free` 2; both penalties 0; 18 enabled stops; `active_incidents` lists the ids active at `as_of_ts` ordered by id and drops an incident when its duration has elapsed; a change to a `config` value changes the output without a code change. Covers: FR-032–FR-035, SC-001, SC-008, US3 scenario 5.
- [x] T056 [P] [US3] Write `tests/integration/test_replay_60min.py` (marked `slow`): seeded run (seed 42, 3,600 s simulated) piped through `ingest` into a throwaway database; `python -m src.pipeline.compute --from … --to … --step 5 --no-notify` (720 snapshots); 100 % of `source_status`, `corridor_now` and `decision_inputs` objects validate against their schemas. Take the step from a module constant `REPLAY_STEP_S = 5`. (CUT-2: change the constant to 60 and record the reduced density in `verification.md`.) Covers: SC-001, SC-008.
- [x] T057 [US3] Extend `tests/integration/test_rebuild.py` (after T028; not [P] with it): after a replay, drop and recreate `silver` and `gold`, recompute at the last `as_of_ts`; silver, M1/M2 and that snapshot equal the cycle-by-cycle state, including the `snapshot_id`. Covers: SC-005, FR-001, FR-005, R5.

### Implementation for User Story 3

- [x] T058 [P] [US3] Create `src/rules/timebands.py` (local hour band, 15-minute band index, next window; fixed UTC−5 offset). Makes T051 and T076 pass. Covers: FR-026, FR-030, FR-032.
- [x] T059 [P] [US3] Create `src/rules/sql/gold_m1_baseline.sql`: 17 × 24 rows; `percentile_cont(0.5)` over eligible traversals when `n_samples >= min_sample_count` from `config.corridor_settings`, otherwise the reference formula (unrounded); `n_samples` always recorded. Replaces the table each cycle with `DELETE` + `INSERT`. Makes T052 pass. Covers: FR-027–FR-029, R13.
- [x] T060 [P] [US3] Create `src/rules/sql/gold_m2_baseline.sql`: per-day counts of `rider_arrival` at the M2 stop for qualifying (local date, band) pairs (band ended and at least one non-backend `bus_position` in it, R12); median over days with `percentile_cont(0.5)` **cast to `numeric` before `round`** (half away from zero); otherwise `round(daily_riders_dir1 × shape(hour) / 4)` on `numeric`. Makes T053 and T054 pass. Covers: FR-030, FR-031, FR-029, R12, R13.
- [x] T061 [US3] Extend `src/pipeline/gold.py`: execute the M1/M2 SQL, build `decision_inputs` through the generated model (same Python objects for `buses` and `summary` as `corridor_now`; forecasts from `gold.m1_baseline` for the local hour of `as_of_ts`; `demand_15min` from `gold.m2_baseline`; `reserve_free`, `drivers_free`, `action_cost`, `enabled_stops` from `config`; `active_incidents` from `silver.incidents`), and insert the `gold.decision_inputs` row with lineage. Makes T055 pass. Covers: FR-032–FR-035, SC-008.
- [x] T062 [US3] Extend `src/pipeline/cycle.py` so the cycle runs the baselines before the gold build and stores the five gold rows of a snapshot under one `snapshot_id` in the same transaction. Makes T056 and T057 pass. Covers: FR-016, FR-029, FR-032, SC-001, SC-005.
- [x] T063 [US3] **Phase 3 verification** (quickstart §Phase 3): run `tests/unit/test_timebands.py`, `tests/integration/test_timebands_sql.py`, `tests/integration/test_baselines.py`, `tests/integration/test_decision_inputs.py`, `tests/integration/test_rebuild.py` and the `slow` replay `tests/integration/test_replay_60min.py` (`-m slow`); all green. Record in `verification.md`. Covers: SC-001, SC-005, SC-006, SC-008.

**Checkpoint**: US1–US3 complete and verified. Phase 4 is still required for the live demo (the loop recomputes gold); only its expensive checks are cuttable.

---

## Phase 4: User Story 4 – Refresh Cycle (Priority: P4) (loop not cuttable; expensive checks CUT-1, ~30 min)

**Goal**: a 5 s loop that recomputes the snapshot and sends one `NOTIFY` after it is readable, as a separate compose service off the capture path.

**Independent Test**: run simulator, ingestion and the refresh loop with a listener (10 minutes for the full SC-009 check, at least one notification within 15 s for the short check); stop the refresh loop and check that bronze keeps growing.

**Ends with**: T071 (no-overlap, clock selector, short live check and SC-010 always; failure, notify and the 10-minute SC-009 run unless CUT-1).

### Tests for User Story 4 (write first; MUST fail)

- [x] T064 [P] [US4] Write `tests/unit/test_refresh_loop.py` (injected clock and a slow fake cycle): no concurrent cycles; the tick that falls inside a slow cycle is skipped, not queued (sleep to the next future 5 s boundary); clock selector: `data` → `as_of_ts` = max `event_ts` of non-backend bus reports (backend events ignored; wall clock used while there are none, which yields `no_data`), `wall` → current UTC from the injected clock, unset → `wall`; `REFRESH_INTERVAL_S` is read from the environment; connect with retry; with an injected fake cycle that raises once, the loop logs the failure and the next tick runs the cycle normally (FR-040, so this case survives CUT-1). Covers: FR-036, FR-039, FR-040, R3, R6, R16.
- [x] T065 [P] [US4] Write `tests/unit/test_compose_refresh.py` (needs PyYAML from T011): the `refresh` service exists, uses the existing image with command `python -m src.refresh.run`, `depends_on` only `db` with `service_healthy`, `restart: unless-stopped`, takes `DATABASE_URL`, `LOG_LEVEL`, `REFRESH_CLOCK`, `REFRESH_INTERVAL_S` from the environment, and no other service depends on `refresh`; `ingestion` still depends only on `db`. Covers: FR-041, R16, Principle III.
- [x] T066 [P] [US4] (CUT-1) Write `tests/integration/test_refresh_failure.py`: a forced error in a cycle leaves no snapshot row and sends no notification, logs one JSON error line with the error class and a correlation id and no traceback, and the next cycle succeeds. Covers: FR-040, SC-009.
- [x] T067 [P] [US4] (CUT-1) Write `tests/integration/test_notify.py`: with the loop running against a throwaway database, a listener receives exactly one payload per new snapshot; each payload validates against `specs/002-silver-gold-baselines/contracts/gold_snapshot_notify.schema.json`; the snapshot is readable on receipt. Covers: FR-038, SC-009, R6.
- [x] T068 [P] [US4] (CUT-1) Write `tests/integration/test_refresh_live.py` (marked `live`, run with the stack up and `REFRESH_CLOCK=data`): over 10 minutes, at least 95 % of the intervals between consecutive notifications are 5 s ± 1 s and every notification refers to a readable snapshot. Covers: SC-009, FR-036.

### Implementation for User Story 4

- [x] T069 [US4] Create `src/refresh/run.py`: the 5 s loop calling `src.pipeline.cycle`, clock selector (`REFRESH_CLOCK=wall|data`, code default `wall`), skip-late-tick scheduling, JSON log lines via `json.dumps` in a `logging.Formatter` (`event`, `snapshot_id`, `as_of_ts`, `max_bronze_id`, `duration_ms`, `status`), connect with retry like `src/ingestion/run.py`, reference tables loaded at start, no new dependency. Makes T064, T066 and T067 pass. Covers: FR-036, FR-039, FR-040, R3, R6, R16.
- [x] T070 [US4] Add the `refresh` service to `docker-compose.yml` (existing image, `prod` target, command `python -m src.refresh.run`, `REFRESH_CLOCK` and `REFRESH_INTERVAL_S` from `.env` with `data` and `5` defaults, `depends_on: db (service_healthy)`, `restart: unless-stopped`). `ingestion` and `api` are unchanged. Makes T065 pass. Covers: FR-041, R16, SC-010.
- [x] T071 [US4] **Phase 4 verification** (quickstart §Phase 4). Short check, always kept: run T064 and T065 (and T066/T067 unless CUT-1 is taken); bring the stack up from a fresh volume (`docker compose down -v && docker compose up -d --build`); with a listener on `gold_snapshot`, confirm at least one notification arrives within 15 s and its payload validates against the notify schema, and that over the first minute the intervals between notifications are roughly 5 s (informal SC-009 smoke, no pass threshold; record the observed intervals); run the SC-010 commands (`docker compose stop refresh`, count `bronze.events`, `sleep 120`, count again, higher, `docker compose start refresh`). Long check (CUT-1): run `tests/integration/test_refresh_live.py -m live` for 10 minutes (SC-009) and record the interval statistics. Record the results and both counts in `verification.md`. Covers: SC-009, SC-010, FR-041.

**Checkpoint**: all four stories work independently.

---

## Phase 5: Polish and Cross-Cutting (~15 min)

- [x] T072 Run the whole suite with coverage (`docker compose --profile tools run --rm tests`): coverage above 80 % overall and `src/rules/` close to 100 % (check the `--cov-report` term-missing output for `src/rules/*.py`). Add missing unit tests under `tests/unit/` only for uncovered rule branches. Covers: SC-011, Gate 2, Principle V.
- [x] T073 [P] Final guard checks: `git diff --stat contracts/` shows exactly one change, the one-value edit of T075 in `contracts/read/fixtures/c1_bunching/corridor_now.json` (schemas and all other fixtures unchanged); `git diff --stat` shows no change to `db/init/001_*.sql` and `db/init/002_*.sql`, ingestion code, or any bronze writer; no deferred item implemented (Redis, PostGIS, direction 2, endpoints, injectors; research R15). If one appears, remove it or record it as `evolution`. Covers: FR-002, FR-025, FR-035, R15, Principle III.
- [x] T074 Finish `specs/002-silver-gold-baselines/verification.md`: the commands run, results per phase, event recount (T007), coverage numbers, any cut list item taken (for CUT-2 the reduced replay density and for CUT-1/CUT-3 what was not done), and the T075 fixture correction (`c1_bunching` now part of SC-002). Covers: SC-001–SC-011, plan "Done".

---

## Dependencies and Execution Order

### Phase dependencies

- **Phase 0**: starts immediately. Inside it, 0A (R14) comes first and blocks everything that reads simulator output. 0B follows (T008–T010 can start alongside T001–T007 because they touch other files, but T008 onward must not be merged before T007 is green).
- **Phase 1** needs T015–T023 (DB fixture, DDL, reference loader, builders).
- **Phase 2** needs Phase 1 and T012 (generated models).
- **Phase 3** needs Phase 2 (`cycle.py`, `gold.py`, `compute.py`).
- **Phase 4** needs Phase 2 (cycle) and Phase 3 (full snapshot). Its loop and compose service are required; only the CUT-1 checks are cut first.
- **Phase 5** needs every phase that was kept.

### Story dependencies

```text
Phase 0 (R14 → base) ──► US1 (silver) ──► US2 (gold views, compute CLI) ──► US3 (M1/M2, decision_inputs) ──► US4 (refresh loop; expensive checks CUT-1) ──► Polish
```

US2 reads silver; US3 extends the same cycle and gold builder; US4 wraps the cycle. They are independently testable at each checkpoint but built in this order because they share `cycle.py` and `gold.py`.

### Within a phase

- Tests first and failing, then rules (pure functions, SQL), then orchestration (`gold.py`, `cycle.py`), then CLI/service, then the verification task.
- `gold.py` and `cycle.py` are edited in Phases 2 and 3 and are never [P] with each other.

---

## Parallel Opportunities

- **Phase 0**: T001 ∥ T002; T008 ∥ T009 ∥ T010; T014 ∥ T016 ∥ T022; T017 ∥ T018 ∥ T019.
- **Phase 1**: T025 ∥ T026 ∥ T027 ∥ T028; then T030 ∥ T031 ∥ T032 (after T029).
- **Phase 2**: T034–T042 (nine test files) all in parallel; then T043 ∥ T044 ∥ T045 ∥ T046.
- **Phase 3**: T051 ∥ T052/T053 ∥ T055 ∥ T056; then T058 ∥ T059 ∥ T060.
- **Phase 4**: T064 ∥ T065 ∥ T066 ∥ T067 ∥ T068.
- **Phase 0**: T075 is parallel with the rest of 0B (it touches only the fixture and `test_read_fixtures.py`, which T008 creates, so run it after T008).
- **Phase 3**: T076 ∥ T051 (different files).

```bash
# Phase 2 test block (different files, no dependencies):
Task: "tests/unit/test_headway.py"        Task: "tests/unit/test_classify.py"
Task: "tests/unit/test_service_metric.py" Task: "tests/unit/test_snapshot_id.py"
Task: "tests/integration/test_gold_fixtures.py"  Task: "tests/integration/test_gold_d1.py"
Task: "tests/integration/test_idempotency.py"    Task: "tests/integration/test_gold_contract.py"
Task: "tests/integration/test_compute_cli.py"
```

---

## Implementation Strategy

### MVP first (User Story 1)

1. Phase 0 (R14 first), then Phase 1. Stop and validate silver (T033).
2. Phase 2 gives the console views. This is the first demonstrable increment (on demand through `compute`).

### Incremental delivery

1. Phases 0–2: a usable, verified gold with `source_status`, `corridor_now` and the service metric.
2. Phase 3: baselines and `decision_inputs` for the backend decision engine.
3. Phase 4: the refresh loop and push by `NOTIFY`. The loop is not cuttable, because nobody else recomputes gold during the live demo. Only the failure test, the notify integration test and the 10-minute live cadence run (CUT-1) can be dropped; the short check of T071 stays.

**Minimum delivery** (stated once): Phases 0–3 plus T064, T065, T069, T070 and the short check of T071.
4. Polish: coverage, guard checks, `verification.md`.

### Time check

Phase 0 (~50) + Phase 1 (~60) + Phase 2 (~60) + Phase 3 (~50) + Phase 4 (~30) + Polish (~15) ≈ 265 min (about 4 h 25 min). If Phase 0–2 take more than 3 h in total, apply CUT-2 and CUT-3 before starting Phase 3, and decide on CUT-1 (the expensive Phase 4 checks) at the end of Phase 3. T075 and T076 are small additions inside the existing phase estimates.

## Notes

- Do not modify contracts, with one exception: the one-value fixture correction of T075 in `contracts/read/fixtures/c1_bunching/corridor_now.json` (schemas and all other fixtures unchanged). Do not modify bronze tables, the ingestion boundary or any 001 test beyond the R14 updates in T006.
- Rules never use an LLM or an external call. Parameterized queries only. No secrets in `.env.example`.
- Tasks do not commit; review and commit yourself (Conventional Commits, for example `feat(data): derive silver current state from bronze`).
