---
description: "Task list for US-05 — Backend Read API for Live Corridor State"
---

# Tasks: US-05 — Backend Read API for Live Corridor State

**Input**: Design documents from `/specs/004-backend-read-api/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/read-api.openapi.yaml

**Tests**: INCLUDED. The plan adopts Gate 2 (pytest + coverage > 80 %) and Gate 1 (schema validation); spec SC-002/SC-003/SC-004 and research R5 require contract, integration and unit tests. Tests MUST be written and MUST FAIL before the matching implementation.

**Organization**: Tasks are grouped by user story (US-05.1 P1, US-05.2 P2) so each story is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 = US-05.1 (corridor state), US2 = US-05.2 (source status)
- Exact file paths are included in every task

## Path Conventions

Current Turn-1 backend tree (per plan.md "Project Structure"; no move to `src/backend/`):

- App: `src/api/` (FastAPI `main.py`, new `deps.py`, new `routers/`, new `reads/`)
- Shared: `src/pulsoflota/` (`db.py`, `config.py`, `models/read/` — all reused, unchanged)
- Tests: new `src/api/tests/` package (`contract/`, `integration/`, `unit/`), reusing gold fixtures under `src/data/tests/`
- Contracts (source of truth for response shapes): `contracts/read/corridor_now.schema.json`, `contracts/read/source_status.schema.json`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the API test package and router scaffolding the stories build on. No business logic here.

- [X] T001 [P] Create the API test package scaffolding: `src/api/tests/__init__.py`, `src/api/tests/contract/__init__.py`, `src/api/tests/integration/__init__.py`, `src/api/tests/unit/__init__.py` (empty files, so pytest discovers the new package per research R5)
- [X] T002 [P] Create `src/api/tests/conftest.py` that reuses the gold-seeding fixtures and DB-template machinery from `src/data/tests/conftest.py` and `src/data/tests/db_helpers.py` (import/re-export the existing `healthy`, `d1_source_outage`, and gold template fixtures; do NOT duplicate the harness)
- [X] T003 Create `src/api/routers/__init__.py` (empty package marker for the new routers package)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: DB dependency injection and the gold read queries that BOTH user stories call. Must complete before any story endpoint can work.

**⚠ CRITICAL**: No user story endpoint work can begin until this phase is complete.

- [X] T004 Implement the per-request DB connection dependency in `src/api/deps.py`: a FastAPI `Depends()` provider that opens a psycopg 3 connection from `config.get_db_dsn()` via the existing `src/pulsoflota/db.py` helper, using `row_factory=dict_row`, yields it, and closes it at end of request (SELECT-only, no explicit write transaction; per research R4)
- [X] T005 Implement the gold read module `src/api/reads/gold_reads.py` with parameterized psycopg 3 SQL only (NO f-strings/concatenation): Q0 latest-snapshot resolver `SELECT snapshot_id, as_of_ts FROM gold.snapshots ORDER BY as_of_ts DESC, max_bronze_id DESC LIMIT 1` (both ordering keys mandatory; zero rows ⇒ no-data), Q2 `SELECT doc FROM gold.corridor_now WHERE snapshot_id = %(snapshot_id)s`, and Q1 `SELECT doc FROM gold.source_status WHERE snapshot_id = %(snapshot_id)s`. Resolve the latest `snapshot_id` once per response and reuse it for the object read (data-contract §3 rule 3). Add `src/api/reads/__init__.py`.
- [X] T006 Create `src/api/routers/corridor_read.py` as an `APIRouter(prefix="/api/v1")` with no routes yet (shared router both stories hang endpoints off), and mount it in `src/api/main.py` via `app.include_router(...)`, replacing the commented `/api/v1` placeholder. Do NOT alter the existing `/healthz` endpoint or the global `Exception` handler (reused for FR-007 per research R3).

**Checkpoint**: DB dependency, gold reads, and the versioned router are in place — user story endpoints can now be added in parallel.

---

## Phase 3: User Story 1 — See current corridor state (US-05.1, Priority: P1) 🎯 MVP

**Goal**: Serve `GET /api/v1/corridor/{corridor_id}/now` → latest `corridor_now` v1.0.0 snapshot from gold, read-only, with a distinguishable 200 no-data body.

**Independent Test**: With a current snapshot seeded in gold, request `/api/v1/corridor/C6-008/now` and confirm the body validates against `contracts/read/corridor_now.schema.json` v1.0.0, reflects the latest snapshot, and carries only contract-defined fields (`extra="forbid"`). With empty gold, the same route returns HTTP 200 `{"status":"no_data","corridor_id":"C6-008"}`.

### Tests for User Story 1 (write FIRST, MUST FAIL before implementation) ⚠

- [X] T007 [P] [US1] Contract test in `src/api/tests/contract/test_read_api_contract.py`: request `/api/v1/corridor/C6-008/now` against a gold-seeded DB and assert the response body validates against `contracts/read/corridor_now.schema.json` (v1.0.0, `additionalProperties: false`) with no extra/missing field (SC-002), and that `corridor_id == "C6-008"` and `direction == 1`
- [X] T008 [P] [US1] Integration test in `src/api/tests/integration/test_read_api_endpoints.py`: (a) healthy gold ⇒ 200, body reflects the latest snapshot (`snapshot_id` matches Q0 result, `buses` present leader-first, `summary` with `buses_in_service`/`n_bunched`/`n_gaps`); (b) empty gold ⇒ HTTP 200 `{"status":"no_data","corridor_id":"C6-008"}` (FR-008) and never a 500; (c) unknown/unsupported corridor (e.g. `/api/v1/corridor/C6-999/now`) ⇒ HTTP 200 `{"status":"no_data","corridor_id":"C6-999"}` echoing the requested id, same envelope as empty gold, no distinct error status (FR-011) (use the reused gold fixtures from `src/api/tests/conftest.py`)
- [X] T009 [P] [US1] Unit test in `src/api/tests/unit/test_latest_snapshot_resolver.py`: Q0 resolver orders by `as_of_ts DESC, max_bronze_id DESC LIMIT 1` and returns the correct latest `snapshot_id`; zero-rows case returns the no-data signal (not an exception)

### Implementation for User Story 1

- [X] T010 [US1] Add `GET /api/v1/corridor/{corridor_id}/now` to `src/api/routers/corridor_read.py`: inject the DB connection via `Depends()` (T004), resolve latest snapshot via Q0 then fetch the gold doc via Q2 (T005), and return the doc. The gold `doc` is pre-validated against the contract by the pipeline — the endpoint serves it as-is and recomputes no business rule (research R1).
- [X] T011 [US1] Serialize the `/now` response through the existing `CorridorNowV100` model in `src/pulsoflota/models/read/corridor_now.py` (reused, unchanged) so `extra="forbid"` guarantees only contract fields are exposed (FR-003, SC-002)
- [X] T012 [US1] Implement the no-data branch for `/now` in `src/api/routers/corridor_read.py`: when Q0 returns zero rows, OR when the requested `{corridor_id}` is not the supported corridor (C6-008), respond HTTP 200 with the sibling envelope `{"status":"no_data","corridor_id":<requested corridor_id>}` echoing the requested id (no field invented inside the `corridor_now` contract; FR-008/FR-011; research R2 / data-model "No-data response"). Treat an unsupported corridor as the same no-data path — do NOT introduce a distinct error status or reveal that the corridor is unsupported. Let any unhandled DB error bubble to the global handler (FR-007) — add no per-endpoint try/except that could leak detail.

**Checkpoint**: US-05.1 is fully functional and independently testable (MVP). The corridor-now endpoint serves live and no-data states and passes its contract/integration/unit tests.

---

## Phase 4: User Story 2 — Know whether the data can be trusted (US-05.2, Priority: P2)

**Goal**: Serve `GET /api/v1/corridor/{corridor_id}/source-status` → latest `source_status` v1.0.0 from gold, including the `estimated` / `sources_down` freshness signal (served as-is, not recomputed) and a distinguishable 200 no-data body.

**Independent Test**: With gold where a bus has been silent > 2 min (`d1_source_outage` fixture), request `/api/v1/corridor/C6-008/source-status` and confirm `status == "estimated"`, the stale bus appears in `sources_down` with its `since` timestamp, and the response implies no alert. Healthy gold ⇒ `status == "live"`, `sources_down == []`. Empty gold ⇒ HTTP 200 `{"status":"no_data","corridor_id":"C6-008","sources_down":[]}`.

### Tests for User Story 2 (write FIRST, MUST FAIL before implementation) ⚠

- [X] T013 [P] [US2] Contract test in `src/api/tests/contract/test_read_api_contract.py`: request `/api/v1/corridor/C6-008/source-status` against gold-seeded DB and assert the body validates against `contracts/read/source_status.schema.json` (v1.0.0, `additionalProperties: false`) with no extra/missing field (SC-002)
- [X] T014 [P] [US2] Integration test in `src/api/tests/integration/test_read_api_endpoints.py`: (a) healthy gold ⇒ `status == "live"`, `sources_down == []`; (b) `d1_source_outage` fixture (bus silent > 2 min) ⇒ `status == "estimated"`, stale bus present in `sources_down` with `since`, no alert implied (FR-006, SC-003); (c) empty gold ⇒ HTTP 200 `{"status":"no_data","corridor_id":"C6-008","sources_down":[]}` (FR-008); (d) unknown/unsupported corridor (e.g. `/api/v1/corridor/C6-999/source-status`) ⇒ HTTP 200 `{"status":"no_data","corridor_id":"C6-999","sources_down":[]}` echoing the requested id, same envelope as empty gold (FR-011)

### Implementation for User Story 2

- [X] T015 [US2] Add `GET /api/v1/corridor/{corridor_id}/source-status` to `src/api/routers/corridor_read.py`: inject the DB connection via `Depends()` (T004), resolve latest snapshot via Q0 then fetch the gold doc via Q1 (T005), and serialize through the existing `SourceStatusV100` model in `src/pulsoflota/models/read/source_status.py` (reused, unchanged). The gold builder already classifies `status` and populates `sources_down`; the endpoint serves this as-is and does NOT recompute staleness (data-model FR-006 note, research R1).
- [X] T016 [US2] Implement the no-data branch for `/source-status`: when Q0 returns zero rows, OR when the requested `{corridor_id}` is not the supported corridor (C6-008), respond HTTP 200 with `{"status":"no_data","corridor_id":<requested corridor_id>,"sources_down":[]}` echoing the requested id, using the contract's first-class `no_data` state (FR-008/FR-011; research R2). Treat an unsupported corridor as the same no-data path — no distinct error status, no leak that the corridor is unsupported. No per-endpoint error handling that could leak detail; unhandled errors bubble to the global handler (FR-007).

**Checkpoint**: US-05.1 AND US-05.2 both work independently; both endpoints serve live, stale, and no-data states behind `/api/v1`.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, coverage, and gate validation across both stories.

- [X] T017 [P] Verify `GET /openapi.json` reflects both endpoints and that the generated OpenAPI matches `specs/004-backend-read-api/contracts/read-api.openapi.yaml` (including the distinct `no_data` response variants for both routes); add an OpenAPI-example/responses annotation to the endpoints in `src/api/routers/corridor_read.py` if the no-data variant is not documented (FR-009, SC-005)
- [X] T018 Confirm read-only safety: assert in an integration check (`src/api/tests/integration/test_read_api_endpoints.py`) or code review that the endpoints issue SELECT-only SQL and never INSERT/UPDATE/DELETE and never touch bronze (FR-005)
- [X] T019 Run `pytest src/api/tests -q` then `pytest --cov=src --cov-report=term-missing` and confirm coverage > 80 % (Gate 2); run the backend-ci static checks (ruff, mypy, Bandit — parameterized SQL only, no secrets) over the new files `src/api/deps.py`, `src/api/reads/gold_reads.py`, `src/api/routers/corridor_read.py` (Gate 1)
- [X] T020 [P] Execute the `quickstart.md` validation scenarios 1–5 (latest corridor state, source status + stale bus, no-data, error safety + correlation_id, typed client generation) and tick the Pass criteria in `specs/004-backend-read-api/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS both user stories (DB dep, gold reads, router mount).
- **User Story 1 (Phase 3)**: Depends on Foundational. Independently testable and deployable (MVP).
- **User Story 2 (Phase 4)**: Depends on Foundational. Independent of US1 (different endpoint in the same router file; no shared mutable state).
- **Polish (Phase 5)**: Depends on the user stories you intend to ship.

### User Story Dependencies

- **US-05.1 (P1)**: Needs only Phase 2. No dependency on US-05.2.
- **US-05.2 (P2)**: Needs only Phase 2. No dependency on US-05.1. Note: T010/T012 (US1) and T015/T016 (US2) edit the same file `src/api/routers/corridor_read.py`, so their implementation tasks are NOT marked [P] relative to each other; run one story's endpoint tasks, then the other's (tests for each story are in separate concerns and can be written in parallel).

### Within Each User Story

- Tests (T007–T009 for US1; T013–T014 for US2) MUST be written and MUST FAIL before the implementation tasks.
- Foundational gold reads (T005) and DB dep (T004) precede the endpoints.
- Endpoint handler before its no-data branch refinement within the same story.

### Parallel Opportunities

- Setup: T001 and T002 are [P] (different files); T003 is independent.
- US1 tests T007, T008, T009 are [P] (distinct test files).
- US2 tests T013, T014 are [P] (T013 in the contract file, T014 in the integration file).
- Polish: T017 and T020 are [P].
- If two developers are available: once Phase 2 is done, one takes US-05.1, the other US-05.2 — but coordinate the shared `corridor_read.py` edits (T010/T012 vs T015/T016).

---

## Parallel Example: User Story 1

```bash
# Launch all US-05.1 tests together (they MUST fail before implementation):
Task: "Contract test for /now in src/api/tests/contract/test_read_api_contract.py"
Task: "Integration test for /now live + no-data in src/api/tests/integration/test_read_api_endpoints.py"
Task: "Unit test for Q0 latest-snapshot resolver in src/api/tests/unit/test_latest_snapshot_resolver.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (test package + router scaffolding).
2. Phase 2: Foundational (DB dep, gold reads, mounted `/api/v1` router) — CRITICAL, blocks stories.
3. Phase 3: US-05.1 `/now` endpoint (tests first, then implementation + no-data branch).
4. **STOP and VALIDATE**: run US-05.1 tests; confirm schema-valid body and the 200 no-data envelope.
5. Demo the corridor-now read — this is the standalone MVP that unblocks the dispatcher console.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. Add US-05.1 → test independently → demo (MVP: live corridor state served).
3. Add US-05.2 → test independently → demo (trust/freshness signal on top).
4. Polish → OpenAPI/typed-client check, read-only assertion, coverage > 80 %, quickstart validation.

---

## Notes

- [P] = different files, no dependency on incomplete tasks.
- [US1]/[US2] map tasks to US-05.1 / US-05.2 for traceability.
- Tests must be written and must FAIL before implementation (plan Gate 2; research R5).
- No contract change, no version bump, no new field: the API serves the existing gold `doc` through the existing generated read models (plan "Data Contract Impact").
- psycopg 3 parameterized SQL only (`%(name)s`), no ORM, no string-built SQL (A05 baseline).
- Reuse the existing global `Exception` handler for errors + `correlation_id`; add no per-endpoint error formatting (FR-007, research R3).
- Scope guards (deferred, do NOT implement here): RBAC/JWT, WebSocket/SSE push, history/filtering/pagination/rate-limiting/caching, connection pooling, `age_s` staleness gating.
