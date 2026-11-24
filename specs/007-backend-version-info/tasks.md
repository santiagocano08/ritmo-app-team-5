---
description: "Task list for Backend Version/Build Info Endpoint (US-08)"
---

# Tasks: Backend Version/Build Info Endpoint

**Input**: Design documents from `/specs/007-backend-version-info/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/version-info.openapi.yaml, quickstart.md

**Tests**: INCLUDED. Constitution v1.4.0 Principle V (Test-First) is active in Turn 1, and the spec/quickstart explicitly prescribe unit + contract + integration tests. Per project policy, test tasks are ON and MUST be written and MUST FAIL before the implementation tasks in the same story run.

**Organization**: Tasks are grouped by user story. This feature has a single user story (US1, P1), which is also the MVP.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1)
- Exact file paths are included in every task

## Path Conventions

This feature extends the existing Turn-1 backend tree (`src/api/`, `src/pulsoflota/`), not the future `src/backend/` reorg (per plan.md Structure Decision and AGENTS.md). All paths below are repo-root-relative.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the existing backend workspace is ready; no new project or dependency is introduced (plan.md: "No new runtime dependency").

- [X] T001 Verify the backend environment runs the existing suite before changes: from repo root run `pytest src/api/tests -q` and confirm it passes, establishing the pre-change baseline (no files modified).
- [X] T002 [P] Confirm `src/pulsoflota/config.py` exists and is the single env-reader module (home for the new source-revision reader per research R1), and confirm `src/pulsoflota/models/read/` is the location for the new response model, without editing either yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure shared by the story. For this single-story slice the only truly shared, blocking artifact is the Pydantic V2 response model that both the contract test and the endpoint depend on.

**⚠ CRITICAL**: The response model (T003) blocks the endpoint implementation (T009) and the contract test (T006).

- [X] T003 [US1] Create the `VersionInfo` Pydantic V2 response model in `src/pulsoflota/models/read/version_info.py` with `model_config = ConfigDict(extra="forbid")` and exactly three required `str` fields, no extras (FR-005, SC-002, data-model.md): `app_version` (required, "Non-empty. SemVer-shaped string (e.g. `0.1.0`)"), `read_contract_version` (required, "Fixed literal `1.0.0` for this turn"), `source_revision` (required, "Non-empty; defaults to `unknown` when the build captured no revision"). All three fields always present on output (SC-002); emit the string `unknown` rather than `null` or an omitted key.

**Checkpoint**: Response model exists — contract test and endpoint can now be written.

---

## Phase 3: User Story 1 - Confirm the running backend build and contract version (Priority: P1) 🎯 MVP

**Goal**: Expose `GET /api/v1/version` on the existing FastAPI app, returning the backend application version, the read-contract version (`1.0.0`), and a source-revision identifier (`unknown` when the build captured none), in a fixed documented shape, reading no data store.

**Independent Test**: With the backend running, `curl -s http://localhost:8000/api/v1/version` returns HTTP 200 with exactly `app_version`, `read_contract_version` (= `1.0.0`), and `source_revision` and no other fields; with `APP_REVISION` unset, `source_revision` is `unknown`; and the request succeeds with the database stopped (quickstart Scenarios 1–3).

### Tests for User Story 1 (write FIRST, ensure they FAIL before implementation) ⚠

> **NOTE**: These tasks create test files. The test code is written now and MUST FAIL (red) before the implementation tasks T008–T010 are started. These are checklist items with target paths, not the final implementation.

- [X] T004 [P] [US1] Unit test for the build-metadata reader in `src/api/tests/unit/test_version_metadata.py`: assert the source-revision reader returns the `APP_REVISION` value when the env var is set, and returns the literal `unknown` when it is unset or empty (FR-004, SC-003, R1); assert the read-contract version constant equals `1.0.0` (FR-003, R3).
- [X] T005 [P] [US1] Contract test in `src/api/tests/contract/test_version_contract.py`: assert a 200 response from `GET /api/v1/version` matches the fixed shape in `specs/007-backend-version-info/contracts/version-info.openapi.yaml` — exactly the three fields `app_version`, `read_contract_version`, `source_revision`, no extras (`extra="forbid"`, FR-005, SC-002); `read_contract_version` equals `1.0.0`; `app_version` and `source_revision` are non-empty strings (`minLength: 1`).
- [X] T006 [P] [US1] Integration test in `src/api/tests/integration/test_version_endpoint.py`: using FastAPI `TestClient`, assert `GET /api/v1/version` returns 200 with the three fields (FR-001, FR-002); assert no database connection/dependency is invoked while serving the request (FR-006, SC-004); assert that with `APP_REVISION` unset the response reports `source_revision` = `unknown` (FR-004, SC-003).

### Implementation for User Story 1

- [X] T007 [US1] Add a source-revision reader and a read-contract-version constant to `src/pulsoflota/config.py` following the existing helper pattern (e.g. `get_log_level`, `get_sim_seed`): the reader returns the `APP_REVISION` env value and falls back to the literal `unknown` when unset/empty (FR-004, FR-007, R1); define the read-contract-version constant as the single named source of truth with value `1.0.0` (FR-003, R3). Values must come from this single build-time source, not inline in the handler (FR-007). (Makes T004 pass.)
- [X] T008 [US1] Expose the application version from a single declared source in `src/pulsoflota/config.py` (or reuse `app.version`), reading the already-declared `0.1.0` from `pyproject.toml` / the FastAPI app rather than introducing a third literal (FR-007, R2). (Depends on T007 file; keep one source of truth.)
- [X] T009 [US1] Implement the version router in `src/api/routers/version.py`: an `APIRouter` with `GET /version` under the `/api/v1` prefix, mirroring `src/api/routers/corridor_read.py`, declaring `response_model=VersionInfo` and a `summary` so it is auto-documented in OpenAPI (FR-009, R5). The handler builds the response from the `config.py` values (T007, T008) only — no database, cache, or stored-table read, no writes (FR-006); no local try/except (errors bubble to the global handler, R4). (Depends on T003, T007, T008; makes T005 and T006 pass.)
- [X] T010 [US1] Mount the new router on the existing app in `src/api/main.py` via `app.include_router(...)` under the `/api/v1` prefix, matching how `corridor_read.py` is included, so `GET /api/v1/version` appears in `/openapi.json` and `/docs` (FR-009). Do not add or alter the global exception handler — reuse it unchanged (FR-008, SC-005, R4). (Depends on T009.)

**Checkpoint**: `GET /api/v1/version` is live, documented, read-only, and all US1 tests pass.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Validate the slice end to end and confirm the Turn-1 gates.

- [X] T011 [US1] Run the quickstart validation in `specs/007-backend-version-info/quickstart.md` Scenarios 1–5: all-three-fields 200 (SC-001, SC-002), `unknown` fallback (SC-003), 200 with the database stopped (SC-004), `/api/v1/version` present in `/openapi.json` (FR-009), and the generic 500 shape `{"error": "internal_server_error", "correlation_id": "<uuid>"}` with no stack trace/path/internals (FR-008, SC-005).
- [X] T012 Run `pytest src/api/tests -q` and confirm all tests (unit, contract, integration) pass and that new-code coverage keeps total backend coverage > 80 % (Gate 2, Principle V). Confirm the response-shape/Pydantic validation passes (Gate 1, Turn-1 subset).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. The `VersionInfo` model (T003) blocks the contract test and the endpoint.
- **User Story 1 (Phase 3)**: Depends on Foundational. Tests (T004–T006) are written before implementation (T007–T010) and must fail first.
- **Polish (Phase 4)**: Depends on US1 implementation being complete.

### Task Dependencies (within US1)

- T003 → (T005 contract test, T009 endpoint)
- T004 → made to pass by T007
- T005, T006 → made to pass by T009/T010
- T007 → T008 (same file, keep one source of truth) → T009 → T010
- T009 → T010
- T010 → T011 → T012

### Within the User Story

- Tests (T004, T005, T006) MUST be written and MUST FAIL before implementation (T007–T010).
- Model (T003) before the endpoint (T009).
- Config readers (T007, T008) before the endpoint (T009).
- Router implementation (T009) before mounting (T010).

### Parallel Opportunities

- T001 and T002 (Setup) can run in parallel.
- The three test-authoring tasks T004, T005, T006 are different files and can be written in parallel (all before implementation).
- Implementation tasks are mostly sequential because they share `config.py` (T007→T008) and the router/app chain (T009→T010).

---

## Parallel Example: User Story 1 tests

```bash
# Author all three failing tests together (different files, no shared edits):
Task: "Unit test for build-metadata reader in src/api/tests/unit/test_version_metadata.py"
Task: "Contract test in src/api/tests/contract/test_version_contract.py"
Task: "Integration test in src/api/tests/integration/test_version_endpoint.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

This feature is a single P1 story and is itself the MVP:

1. Complete Phase 1: Setup (baseline suite green).
2. Complete Phase 2: Foundational (`VersionInfo` model).
3. Complete Phase 3: write failing tests, then implement reader → config → router → mount.
4. **STOP and VALIDATE**: run quickstart Scenarios 1–5 and the test suite.
5. Deploy/demo — `GET /api/v1/version` answers "which build is live?".

### Incremental Delivery

Setup + Foundational → US1 → validate → done. There are no further stories in this slice; deferred norms (RBAC/JWT, full SAST/SCA, frontend surfacing, readiness checks) are recorded as evolution in plan.md and are out of scope here.

---

## Notes

- [P] tasks = different files, no dependencies.
- [US1] label maps tasks to the single user story for traceability; Setup/Polish-wide tasks carry no story label.
- Verify the three tests fail before implementing (Principle V, Test-First).
- No database, ORM, or migration work: the endpoint reads no data store (FR-006).
- Values come from `config.py` / app metadata, never inline in the handler (FR-007).
- The global exception handler is reused unchanged (FR-008); do not add local error handling.
- Agents never commit/push; review and commit yourself (AGENTS.md).
