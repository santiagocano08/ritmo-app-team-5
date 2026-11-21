# Tasks: Turn-1 Run Environment and Base Simulator

**Input**: Design documents from `specs/001-base-simulator/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md, contracts/

**Tests**: Tests are **ON** by default for this project (constitution Principle V: coverage > 80 %). Test tasks are written first and MUST fail before the implementation they cover. Tasks note this; the test tasks themselves are checklist items with target file paths, not the test code.

**Organization**: Tasks are grouped by user story in the approved build order (US-1 → US-2 → US-3 → US-4) so each story is independently implementable and testable, followed by a short polish phase. Kept lean for a 4–5 hour data-owner review window (target 20–30 tasks).

**Feature branch**: `001-base-simulator` | **Turn**: 1 (active) | **Lane**: Disciplined

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Single Python project (one `pyproject.toml`, one `src/` layout) with three container entry points, per plan.md.
- `src/` (pulsoflota, reference, ingestion, simulator, api), `db/init/`, `data/{raw,reference}/`, `tests/{unit,contract,integration}/`.
- The authoritative event contract lives at the repo root `contracts/turn1-events/`; the **generated** Pydantic models live under `src/pulsoflota/models/` (do not confuse the two).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Scaffold the Python project per plan.md: `pyproject.toml` (python `>=3.12`, `uv`-managed, runtime deps `psycopg` 3 binary / `pydantic` V2 / `fastapi` / `uvicorn`, dev deps `datamodel-code-generator` / `pytest` / `pytest-cov`, with coverage `> 80 %` config), `Makefile` (`generate | reference | up | down | test | lint | clean`), `src/` package layout (`pulsoflota/`, `reference/`, `ingestion/`, `simulator/`, `api/`), `db/init/`, `data/raw/` (git-ignored) + `data/reference/`, `tests/{unit,contract,integration}/` + `tests/conftest.py`, and `.gitignore` entries for `data/raw/` and `.env`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T002 [P] Generate Pydantic V2 models from the accepted contract
- [X] T003 [P] Write the bronze schema init scripts (`CREATE SCHEMA IF NOT EXISTS bronze, silver, gold`), `db/init/002_bronze.sql` creating `bronze.events` (insert-only; columns per data-model.md E3: `id BIGSERIAL PK`, `source TEXT NOT NULL`, `event_id UUID NOT NULL`, `schema_version TEXT`, `event_type TEXT`, `event_ts TIMESTAMPTZ NOT NULL`, `arrival_ts TIMESTAMPTZ NOT NULL`, `payload JSONB NOT NULL`, `ingested_at TIMESTAMPTZ DEFAULT now()`, with `CONSTRAINT bronze_events_unique UNIQUE (source, event_id)`) and `bronze.rejections` (data-model.md E4: `original_message JSONB`, `reason TEXT NOT NULL`, `received_ts TIMESTAMPTZ NOT NULL`, `CHECK (reason IN ('missing_required_field','wrong_type','value_out_of_range','unknown_event_type','unsupported_schema_version','undeclared_field','invalid_uuid','invalid_timestamp','duplicate_event'))`); idempotent scripts.

**Checkpoint**: Foundation ready — contract models generated and bronze schema defined; user story implementation can now begin.

---

## Phase 3: User Story 1 — Curated, Reproducible Reference Data (Priority: P1) 🎯 MVP

**Goal**: A reproducible, curated reference-data set under `data/reference/` (<1 MB) built deterministically from `data/raw/`, with the 17 direction-1 segments, real C6-008 stops (`P-<objectid>`), Prado train arrivals, hourly congestion factor and demand parameters, plus `SOURCES.md`. The simulator and fixtures consume it.

**Independent Test**: rebuild the reference data twice; verify byte-identical output, total size under 1 MB, completeness of `SOURCES.md`, and that fixtures use the real stop ids.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T004 [P] [US1] Write `tests/unit/test_reference_build.py`: assert two rebuilds are byte-identical; total size < 1 MB; `segments.csv` has exactly 17 direction-1 rows; `congestion_factor.csv` has 24 rows with the 0.43–0.56 band as a sanity warning (values kept as computed, per R7); `SOURCES.md` has one line per file; `stops.csv` uses real `P-<objectid>` ids; a missing required raw source fails the build with a named message.

### Implementation for User Story 1

- [X] T005 [US1] Implement `src/reference/build.py`: deterministic `data/raw/` → `data/reference/` build — `segments.csv` (17 rows from `plata/tramos_c6008_s1_osm.csv`), `stops.csv` (real C6-008 stops with `stop_id = "P-<objectid>"` from `paradas_alimentadoras.geojson` filtered `ruta == "C6-008"` + direction 1, projected distance-along + `segment_id`, per R6), `train_arrivals.csv` (line-A Prado weekday arrivals from the 2025 GTFS, per R8), `congestion_factor.csv` (`mean(SIMM VELOCIDAD) ÷ length-weighted corridor free-flow speed` per hour, no tuning constant, per R7), `demand_params.csv` (Metro line A hourly shape + basin-6 feeder share, per R9). Fixed sort orders and rounding; no wall-clock dependence.
- [X] T006 [US1] Implement `src/reference/sources.py` and wire `data/reference/SOURCES.md` generation
- [X] T007 [US1] Update `contracts/turn1-events/examples/{valid,invalid}/*.json` stop_id values

**Checkpoint**: User Story 1 fully functional and testable independently — reference data is reproducible, complete, and grounded in the real corridor.

---

## Phase 4: User Story 2 — Isolated Run Environment (Priority: P2)

**Goal**: A single command starts three separate containers (database, simulator/ingestion, API). Stopping the API does not stop ingestion, so data capture survives a web/API failure (Principle III).

**Independent Test**: start all services with one command; stop the API container; verify ingestion keeps writing to bronze.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T008 [P] [US2] Write `tests/integration/test_health.py`: `GET /healthz` → `200 {"status": "healthy"}`.
- [X] T009 [P] [US2] Write `tests/integration/test_isolation.py`: start all services; `docker compose stop api`; assert the `ingestion` container keeps running and `bronze.events` keeps growing (Principle III). NOTE: this test finalizes once US-3 (ingestion write) and US-4 (simulator) land; the test scaffold is written now and run after those stories.

### Implementation for User Story 2

- [X] T010 [P] [US2] Implement `src/api/main.py`: FastAPI + uvicorn app exposing only `GET /healthz` → `200 {"status": "healthy"}` (DB-free so the API reports healthy even if the DB is briefly unreachable), generic errors with no stack traces, `DEBUG=False`; reserve `/api/v1` base unused.
- [X] T011 [US2] Write `docker-compose.yml` with three services — `db` (postgres:16, mount `db/init/` into `/docker-entrypoint-initdb.d/`), `ingestion` (entry point pipes the simulator's JSON-lines stdout into the ingestion reader: `python -m src.simulator.main --seed "$SEED" --duration "$DURATION" | python -m src.ingestion.run`), `api` (uvicorn) — plus `make up`/`make down`. DB DSN via an env var in the container (no secrets in the repo); stopping `api` is a separate service from `ingestion` so it cannot stop ingestion.

**Checkpoint**: User Story 2 fully functional — three isolated services start with one command; the API is health-only and isolated from ingestion.

---

## Phase 5: User Story 3 — Validated Ingestion into Immutable Bronze (Priority: P3)

**Goal**: Every event is validated at the boundary against the accepted turn-1 contract; valid events land in immutable, insert-only bronze; invalid/duplicate events land in `bronze.rejections` with a reason. Malformed or duplicated data can never contaminate the indicators (turn-1 data-integrity risk).

**Independent Test**: feed crafted valid, invalid and duplicate events to the ingestion boundary (without the live simulator) and inspect `bronze.events` and `bronze.rejections`.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T012 [P] [US3] Write `tests/contract/test_contract_examples.py`: every example in `contracts/turn1-events/examples/valid/` passes validation; every example in `examples/invalid/` is rejected with the expected reason (per the file name and the R12 mapping).
- [X] T013 [P] [US3] Write `tests/integration/test_bronze_ingest.py`: a valid envelope lands in `bronze.events` exactly once with `arrival_ts` stamped by ingestion; each invalid envelope lands in `bronze.rejections` with the matching reason; the same `source` + `event_id` twice → first accepted, second discarded to `bronze.rejections` with `duplicate_event`, and `bronze.events` is unchanged.
- [X] T014 [P] [US3] Write `tests/integration/test_bronze_immutable.py`: no `UPDATE`/`DELETE` on bronze; bronze row counts and checksums are invariant across a re-ingest.

### Implementation for User Story 3

- [X] T015 [P] [US3] Implement `src/ingestion/validate.py`: validate an envelope dict against the generated Pydantic V2 models and map `ValidationError` categories to the contract `rejection.schema.json` reason enum — missing required field → `missing_required_field`, wrong type → `wrong_type`, out-of-range/enum → `value_out_of_range`, `additionalProperties` violation → `undeclared_field`, bad UUID → `invalid_uuid`, bad date-time → `invalid_timestamp`, `schema_version` ≠ `"1.0.0"` → `unsupported_schema_version`, `event_type` not in enum → `unknown_event_type`. Deterministic code; no LLM (R12).
- [X] T016 [US3] Implement `src/ingestion/bronze.py`: `ingest(conn, envelope_dict) -> IngestResult` (`accepted` | `rejected` with reason) — validate; valid → `INSERT` into `bronze.events` with `arrival_ts = now()` (overwriting any value sent); a `UNIQUE (source, event_id)` violation is caught and routed to `bronze.rejections` with reason `duplicate_event`; invalid → `bronze.rejections` with the reason and `original_message` stored as-is. Insert-only (only `INSERT`, never `UPDATE`/`DELETE`); parameterized SQL.
- [X] T017 [US3] Implement `src/ingestion/run.py`: entry point that consumes JSON-lines from stdin, validates, and writes to bronze (the container's ingestion consumer); importable so crafted-event tests and the container pipe can call it.

**Checkpoint**: User Story 3 fully functional — ingestion validates, rejects and dedupes; bronze is immutable and idempotent on `source` + `event_id`.

---

## Phase 6: User Story 4 — Deterministic Base Simulator (Priority: P4)

**Goal**: A deterministic base simulator for corridor C6-008 (direction 1, 5+2 buses, 5 s step) that emits a contract-valid stream of fleet and rider events with realistic travel time, dwell and demand, feeding US-01's fleet-state and headway inputs.

**Independent Test**: run the simulator twice with the same seed and compare the output stream; verify every emitted event validates against the contract and that a peak-hour trip meets the duration target. No persistence layer is required to test the simulator's output.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T018 [P] [US4] Write `tests/unit/test_simulator_determinism.py`: `run(seed=42, duration)` twice produces a byte-identical JSON-lines stream (identical output hash, including identical `event_id`s).
- [X] T019 [P] [US4] Write `tests/unit/test_simulator_capacity.py`: `occupancy` never exceeds 40; riders beyond capacity are counted as `rejected` and do not board; boarding is FIFO.
- [X] T020 [US4] Write `tests/unit/test_simulator_travel_time.py`: a direction-1 end-to-end trip at the **FIXED 17:00 calibration peak hour** (data-owner decision; line A PM peak per Afluencia 2025) completes in ~22.8 min, within ±20 % of the 25 min target (i.e. 20–30 min); reserve buses B-106/B-107 emit no `bus_position`. (Encodes the data-owner override of the "lowest congestion-factor hour" assumption; SC-006 is checked at 17:00.)

### Implementation for User Story 4

- [X] T021 [US4] Implement `src/simulator/model.py`: fleet B-101..B-107 (capacity 40; B-101..B-105 in-service, B-106..B-107 reserve), trip over the ordered 17 segments + stops (loads `data/reference/`); travel time per segment = `length_m / (free_flow_kmh * 3.6 * hourly_congestion_factor) * lognormal_noise` with a single declared `SIGMA = 0.20` (seeded by the run seed); dwell = `10 + 3*boarded + 2*alighted` seconds, minimum 10 s (FR-020); demand = train batches at Prado (from `train_arrivals.csv`) + 1–3 min walk + street drip at other stops; FIFO boarding up to capacity with surplus counted as `rejected`. Payload constraints: `occupancy` (0–40), `speed_kmh` (0–120), `distance_along_m` (≥0), `direction` (1).
- [X] T022 [US4] Implement `src/simulator/engine.py`: `run(seed, duration) -> Iterator[dict]` yielding envelope dicts with no DB and no I/O — a single seeded `random.Random(seed)` for all randomness (event ids, travel-time noise, boardings/alightings, rider arrivals) in a fixed call order; event ids are deterministic seeded UUID v4; 5 s step; emits `bus_position` (in-service buses only), `stop_arrival`, `stop_departure`, `rider_arrival` (the four base-simulator types; `driver_confirmation`/`incident_report` are not emitted).
- [X] T023 [US4] Implement `src/simulator/main.py`: CLI `--seed S --duration D` → JSON-lines envelopes on stdout with `json.dumps(..., sort_keys=True)` so the byte stream is stable across runs; the container's producer.

**Checkpoint**: User Story 4 fully functional — the simulator is deterministic, realistic and capacity-safe; the full loop (simulate → validate → bronze) closes.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Spec/contract traceability and end-to-end validation across all stories

- [X] T024 Update `specs/001-base-simulator/spec.md` Assumptions line: replace *"Peak hour means the most congested hour per the congestion factor (lowest real/free ratio)"* with the data-owner decision — the calibration peak hour is FIXED at **17:00** (line A PM peak, Afluencia 2025), because the computed SIMM factor (mean VELOCIDAD ÷ length-weighted free-flow speed = 0.50–0.62) is lowest at 23:00 only due to thin night samples; SC-006 is checked at 17:00 (~22.8 min, within 25 min ±20 %). Align the matching peak-hour note in `specs/001-base-simulator/research.md` (R14) so the two stay consistent (one decision, both docs).
- [X] T025 [P] Run the `specs/001-base-simulator/quickstart.md` end-to-end validation (V1 reference reproducible, V2 isolation, V3 ingestion validates/rejects/dedupes, V4 simulator deterministic + 17:00 trip) and confirm `make test` coverage > 80 %; verify no deferred turn-2/turn-3 norms were implemented (turn-scope check per the data profile).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — can start immediately.
- **Foundational (Phase 2)**: depends on Setup — BLOCKS all user stories.
- **User Stories (Phase 3–6)**: all depend on Foundational; they proceed in priority order (US-1 → US-2 → US-3 → US-4), with the cross-story notes below.
- **Polish (Phase 7)**: depends on all user stories being complete.

### User Story Dependencies

- **US-1 (Reference data, P1)**: starts after Foundational; no dependencies on other stories. The simulator (US-4) depends on US-1's reference data.
- **US-2 (Run environment, P2)**: starts after Foundational. The bronze schema (T003) and API (T010) are ready in this story; the `ingestion` service's full function and the isolation test (T009) finalize once US-3 and US-4 land.
- **US-3 (Ingestion, P3)**: starts after Foundational; uses the generated models (T002) and bronze schema (T003). Independently testable with crafted events (no live simulator).
- **US-4 (Base simulator, P4)**: starts after Foundational and US-1 (consumes reference data). Determinism is testable with no persistence layer; the full pipe (simulate → bronze) needs US-3.

### Within Each User Story

- Tests MUST be written and FAIL before the implementation they cover.
- Leaf/independent modules before the modules that depend on them (validate before bronze; model before engine before main).
- A story is complete and independently testable before moving to the next priority.

### Cross-Story Notes (kept honest)

- US-2's isolation test (T009) and the `ingestion` container entry point (T011) only fully pass once US-3 (ingestion write) and US-4 (simulator) are in place — the test scaffold is written in US-2 and run after those stories.
- US-1's contract-examples update (T007) feeds US-3's contract test (T012), which iterates over the updated examples.

### Parallel Opportunities

- Foundational: T002 (model generation) and T003 (bronze DDL) run in parallel — different files, no interdependency.
- Within each story, all test files marked `[P]` run in parallel (T004; T008/T009; T012/T013/T014; T018/T019/T020).
- Leaf implementation modules marked `[P]` (T010 api, T015 validate) can start in parallel with their story's other work once their inputs exist.
- Different user stories can be worked in parallel by different reviewers if capacity allows (mind the cross-story notes above).

---

## Parallel Example: User Story 4

```bash
# Launch all tests for User Story 4 together (written first, must fail before impl):
Task: "tests/unit/test_simulator_determinism.py"   (T018)
Task: "tests/unit/test_simulator_capacity.py"       (T019)
Task: "tests/unit/test_simulator_travel_time.py"    (T020)

# Then implement sequentially (model -> engine -> main):
Task: "src/simulator/model.py"   (T021)
Task: "src/simulator/engine.py"  (T022, depends on T021)
Task: "src/simulator/main.py"    (T023, depends on T022)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories).
3. Complete Phase 3: User Story 1 (reference data).
4. **STOP and VALIDATE**: rebuild reference data twice — byte-identical, <1 MB, real stop ids.
5. Demo readiness: the curated, reproducible reference data is the MVP.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. Add US-1 (reference data) → test independently (MVP).
3. Add US-2 (run environment) → test isolation + health independently.
4. Add US-3 (ingestion into bronze) → test validate/reject/dedupe + immutability independently.
5. Add US-4 (base simulator) → test determinism/capacity/travel-time; the full loop closes.
6. Polish → spec/contract traceability + end-to-end quickstart validation.

### Single-Reviewer Strategy (4–5 hour window)

1. Review Setup + Foundational together (the contract models and bronze schema are the gate).
2. Review each story in priority order; each is independently testable, so the reviewer can stop and validate at each checkpoint.
3. Polish last: confirm the spec assumptions reflect the 17:00 decision and the quickstart passes end to end.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks.
- [Story] labels map tasks to specific user stories for traceability.
- Each user story is independently completable and testable.
- Tests are written first and must fail before the implementation they cover (Principle V).
- Commit after each task or logical group (Conventional Commits, inferred; agents do not commit).
- Deferred norms (Redis/PostGIS, 1,000 events/s, SAST/SCA, RBAC/JWT/MFA, mTLS, HMAC, secret manager, silver/gold metrics, scenario injectors, decision engine, route diversion) are NOT built in this story — recording one as evolution, not a blocking finding.
