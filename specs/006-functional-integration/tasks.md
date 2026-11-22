---
description: "Task list for Functional Integration (Turn-1 Whole) — US-07"
---

# Tasks: Functional Integration (Turn-1 Whole)

**Input**: Design documents from `/specs/006-functional-integration/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md

**Tests**: INCLUDED. The constitution (§V Test-First and Automated Gates) mandates testing and
coverage > 80 %; no "no tests" opt-out exists in spec.md or the constitution, so test/verification
tasks are generated. Because this is an integration/packaging story that adds **no product
behavior, contract or business logic** (FR-013), the verification tasks are the documented
end-to-end validation (FR-015), build-time config validation (`nginx -t`), and image/header
inspection checks (FR-009/FR-010/FR-012) — not new unit-test logic. Existing pytest/Vitest suites
stay unchanged and must still pass (plan Testing; quickstart "Existing automated gates"). Each
story's verification tasks are written to FAIL before its implementation exists and to pass once it
does.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing
of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Web application, current Turn-1 tree kept as-is (plan "Structure Decision"): backend at `src/api/`,
`src/data/`, `src/pulsoflota/`; frontend SPA at `src/frontend/`. This story is additive at the
infrastructure layer only — no application source module is modified (FR-013). New artifacts:
`src/frontend/Dockerfile`, a `deploy/` reverse-proxy config directory, and edits to
`docker-compose.yml`, `.env.example`, `README.md`, `AGENTS.md`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the integration workspace and pin the external proxy choice before any
service wiring.

- [X] T001 Verify the local checkout is on branch `006-functional-integration` and that the five pre-built parts exist (`src/api/`, `src/data/`, `src/pulsoflota/`, `src/frontend/package.json` with a `build` script, root `Dockerfile`, `docker-compose.yml`); record any gap as a blocker before proceeding (plan Summary; research R1).
- [X] T002 [P] Create the reverse-proxy config directory `deploy/frontend/` as the home for the Nginx static-serve + `/api/v1` forward config (research R1/R3; plan Source Code layout — final directory name fixed here).
- [X] T003 [P] Pin the exact Nginx base image patch tag to use in the frontend image and record it as a note at the top of `src/frontend/Dockerfile` (create the file placeholder); loose tags like `nginx:latest` are rejected for reproducibility (research R3 "exact pin").

**Checkpoint**: Branch and inputs confirmed; proxy config directory and base-image pin decided.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Confirm the integration contract boundary is stable before wiring any service, so no
later task silently edits the committed contract or the SPA's request path.

**⚠ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Confirm the committed read contract is consumed unchanged: verify `contracts/read/corridor_now.schema.json` and `contracts/read/source_status.schema.json` declare version `1.0.0` and that `src/frontend/src/api/client.ts` pins `EXPECTED_SCHEMA_VERSION === "1.0.0"`; no new `contracts/` directory is created for this feature (FR-013, FR-014; research R2).
- [X] T005 Confirm the SPA default API base is the relative path `/api/v1`: verify `resolveBaseUrl()` in `src/frontend/src/api/client.ts` returns `/api/v1` when `VITE_API_BASE_URL` is unset, so same-origin serving needs no code change and no CORS config (FR-011; research R1).
- [X] T006 Confirm the simulator/gold path can produce corridor C6-008 snapshots under the committed default `REFRESH_CLOCK=data` in `.env.example`, so the end-to-end validation has live data and needs no mocks in the request path (FR-003; research R5).

**Checkpoint**: Contract boundary and data source confirmed stable — user-story wiring, packaging and docs can begin.

---

## Phase 3: User Story 1 - Run the whole Turn-1 system together and see live corridor state (Priority: P1) 🎯 MVP

**Goal**: One `docker compose up` brings up all five Turn-1 services healthy, and the dispatcher
console loads against the real backend showing live corridor C6-008 state (leader-first,
~5 s refresh) with the estimated-source, no-data and backend-interruption cases behaving as
specified.

**Independent Test**: Bring up the full stack with one command against gold data for C6-008, open
the console in a browser, and confirm it loads from the real backend (no mock fixtures in the path),
shows the fleet leader-first with state/headway/quality, auto-refreshes about every 5 s, and passes
the five validation cases and the ingestion-isolation check in `quickstart.md`.

> **NOTE: Write/author the verification steps first; running them before the implementation of
> Phase 3/4 exists MUST fail (no `frontend` service, no proxy), then pass once T011–T014 land.**

### Verification for User Story 1

- [X] T007 [P] [US1] Author the five validation cases in `specs/006-functional-integration/quickstart.md` as the executable E2E walkthrough and confirm it matches the delivered service/port names: live snapshot render (FR-004), ~5 s auto-refresh (FR-005), estimated source with no alert (FR-006), no-data state distinct from error (FR-007), and backend interruption + self-recovery (FR-008) (FR-015, SC-004).
- [X] T008 [P] [US1] Author the contract-drift check in `specs/006-functional-integration/quickstart.md`: live `GET /api/v1/corridor/C6-008/now` returns `schema_version == "1.0.0"` and validates against `contracts/read/corridor_now.schema.json`; on any mismatch, STOP and request a contract decision rather than edit the contract or generated types (FR-014, SC-007).
- [X] T009 [P] [US1] Author the ingestion-isolation check in `specs/006-functional-integration/quickstart.md`: after `docker compose stop api frontend`, `ingestion` and `db` must stay `(healthy)` (Principle III; data-model "Invariant").

### Implementation for User Story 1

- [X] T010 [US1] Author the Nginx reverse-proxy config in `deploy/frontend/` that serves the built SPA from the static root and forwards the relative path `/api/v1` by `proxy_pass` to the `api` service by its compose service name, keeping one browser origin (FR-011; research R1).
- [X] T011 [US1] Write the multi-stage `src/frontend/Dockerfile`: Node build stage runs `npm ci` + `npm run build`; final runtime stage (pinned Nginx base from T003) contains only the built `dist/` assets plus the `deploy/frontend/` proxy config, with `nginx -t` passing at build (FR-009; research R3; plan Testing).
- [X] T012 [US1] Add the `frontend` service to `docker-compose.yml`: build from `src/frontend/Dockerfile`, publish the console port (e.g. `8080`), mount/copy the `deploy/frontend/` config, and set startup ordering `depends_on: { api: { condition: service_healthy } }` so the console starts only after `api` is healthy (FR-001, FR-002; research R4).
- [X] T013 [US1] Add a `healthcheck` to the `frontend` service in `docker-compose.yml` that probes the proxy's locally served index (HTTP 200), NOT the upstream backend, so a mid-session backend blip does not flap the container (FR-002; research R4; data-model "Health rule").
- [X] T014 [US1] Verify no existing compose dependency edge is added onto `ingestion` (it keeps `depends_on` on `db` only) and that stopping `api`/`frontend` cannot stop `ingestion` (Principle III; data-model "Invariant").
- [X] T015 [US1] Run the five validation cases, the contract-drift check and the ingestion-isolation check from `quickstart.md` against the running stack; confirm all five services report `(healthy)` (SC-001), the console renders live leader-first with ~5 s refresh (SC-002/SC-003), and the estimated/no-data/interruption cases behave as specified (SC-004).

**Checkpoint**: User Story 1 is fully functional — the whole Turn-1 stack runs with one command and the console shows live C6-008 state against the real backend.

---

## Phase 4: User Story 2 - Package the dispatcher console as a hardened, same-origin service (Priority: P2)

**Goal**: The shipped console image runs as non-root UID 10001, contains only built static assets,
is served under one origin that forwards `/api/v1`, and returns the mandatory security headers while
omitting stack-revealing ones.

**Independent Test**: Build and inspect the shipped console image and run it behind its reverse
proxy: confirm it runs as non-root UID 10001, contains only built static assets (no build runtime,
source or dependency tree), serves under one origin that forwards backend calls, and returns the
required security headers while omitting stack-revealing ones.

> **NOTE: Author the image-inspection checks first; they MUST fail before the hardening in
> T019–T021 is applied, then pass once it is.**

### Verification for User Story 2

- [X] T016 [P] [US2] Author the shipped-image inspection checks in `specs/006-functional-integration/quickstart.md`: `docker compose exec frontend id` shows `uid=10001` (FR-010), the image contains only built static assets with no `node` runtime / source / `node_modules` (FR-009), and the required headers are present while stack-revealing ones are absent (FR-012) — pass criterion SC-005 (zero exceptions).
- [X] T017 [P] [US2] Author the header-assertion list in `specs/006-functional-integration/quickstart.md` to verify via `curl -sI` on the console origin: PRESENT — `Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none';`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`; ABSENT — `Server` version banner, `X-Powered-By`, any Nginx/FastAPI version string (FR-012, SC-005; research R3).

### Implementation for User Story 2

- [X] T018 [US2] In `src/frontend/Dockerfile`, set the runtime stage to run as non-root UID 10001 (mirror the backend `Dockerfile` UID/GID 10001 + `USER` pattern) and ensure the final image carries only `dist/` assets and the proxy config — no Node runtime, source or `node_modules` (FR-009, FR-010; research R3; data-model "Shipped console artifact").
- [X] T019 [US2] In the `deploy/frontend/` Nginx config, add the four mandatory response headers verbatim: `Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none';`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` (FR-012, SC-005; research R3).
- [X] T020 [US2] In the `deploy/frontend/` Nginx config, remove/hide stack-revealing headers (`server_tokens off;` and strip/unset `Server` and `X-Powered-By`) so no technology or version string is emitted (FR-012, SC-005; research R3).
- [X] T021 [US2] Confirm the Vite production build emits no inline script/style incompatible with `script-src 'self'`; if any is emitted, add the minimal hashed/nonce allowance in the CSP rather than loosening it, and note this as a validation step (research R3 CSP note; quickstart).
- [X] T022 [US2] Build the console image and run the T016/T017 inspection checks against it: confirm non-root UID 10001, assets-only contents, all four headers present and zero stack-revealing headers (SC-005).

**Checkpoint**: The console ships as a hardened, same-origin service; User Story 1 and User Story 2 both hold independently.

---

## Phase 5: User Story 3 - Trustworthy run instructions and reconciled documentation (Priority: P3)

**Goal**: Project documentation — README first — accurately describes the full integrated setup
(configure settings, one-command start, reach the console against the real backend), and no document
still claims the frontend does not exist.

**Independent Test**: Hand the updated README to someone unfamiliar with the project and have them
follow it end to end — configure the required environment settings, start the whole stack with one
command, and open the console against the real backend — and they find no documentation claiming the
console does not exist.

> **NOTE: Author the documentation-walkthrough verification first; it MUST fail while docs are stale
> (missing `frontend` service / API-base setting, surviving "no frontend yet" lines), then pass once
> T024–T027 land.**

### Verification for User Story 3

- [X] T023 [P] [US3] Author the documentation walkthrough in `specs/006-functional-integration/quickstart.md`: a new contributor configures `.env` (including the console API base / same-origin proxy default), runs the one-command start, opens the console against the real backend, and finds no "frontend does not exist" statement anywhere (FR-016, FR-017, SC-006).

### Implementation for User Story 3

- [X] T024 [US3] Add the console runtime configuration to `.env.example`: document the console API base / same-origin proxy default (`/api/v1` relative) and the optional `VITE_API_BASE_URL` override (unset → relative `/api/v1`, for non-default topologies only); add no secret (FR-016; data-model "Console runtime configuration").
- [X] T025 [US3] Update `README.md` to describe the full integrated setup: `.env` configuration (including the console API base / same-origin proxy default), the one-command start (`docker compose up --build`), the five services with ports and health checks, and how to open the console against the real backend (FR-016, SC-006).
- [X] T026 [US3] Reconcile `README.md` and `AGENTS.md` to match the delivered setup — service list (five services incl. `frontend`), the real `src/frontend` layout — and remove the stale "no frontend yet" statements in `AGENTS.md` (line ~61 body text and the `src/` row of the repository-layout table, ~line 68) (FR-017, SC-006; research R6).
- [X] T027 [US3] Review all project documentation (`README.md`, `docs/`, `AGENTS.md`) for any remaining statement that the frontend does not exist and correct it; confirm the described run instructions match what actually ships (FR-017, SC-006).

**Checkpoint**: Documentation is trustworthy and reconciled; all three user stories hold independently.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final cross-cutting validation that the integration changed no existing behavior and
that all gates still pass.

- [X] T028 [P] Run the existing backend gate unchanged — `docker compose --profile tools run --rm tests` — and confirm pytest passes with coverage > 80 % (plan Testing; quickstart "Existing automated gates").
- [X] T029 [P] Run the existing frontend gate unchanged — `cd src/frontend && npm ci && npm run lint && npm test && npm run build` — and confirm lint, `tsc --noEmit`, Vitest (coverage > 80 %) and the Vite build all pass (plan Testing; quickstart "Existing automated gates").
- [X] T030 Confirm FR-013 holds: diff the touched application source to verify no new user-facing feature, data contract or business-logic module was introduced — only infrastructure (`src/frontend/Dockerfile`, `deploy/frontend/`), compose, env and docs changed (FR-013).
- [X] T031 Execute the full `quickstart.md` walkthrough once more end to end against a clean `docker compose up --build` as the final acceptance of SC-001 through SC-007.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (confirms the contract boundary and data source are stable).
- **User Stories (Phase 3–5)**: All depend on Foundational completion.
  - US1 (P1) is the MVP and delivers the running stack; US2 and US3 build on the artifacts US1 wires.
  - US2 depends on US1's `src/frontend/Dockerfile` and `deploy/frontend/` existing (it hardens them).
  - US3 depends on US1's delivered service/port names and US2's shipped artifact to document them accurately.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: Starts after Foundational. No dependency on other stories — independently testable as the running functional whole.
- **User Story 2 (P2)**: Shares the `src/frontend/Dockerfile` and `deploy/frontend/` config created in US1; sequence US2 after US1. Independently testable by image inspection + header checks.
- **User Story 3 (P3)**: Documents what US1/US2 ship; sequence after them so docs match reality. Independently testable via the README walkthrough.

### Within Each User Story

- Verification steps are authored before implementation and MUST fail before it, pass after.
- US1: proxy config (T010) and Dockerfile (T011) before compose wiring (T012–T014) before validation run (T015).
- US2: hardening the Dockerfile (T018) and headers (T019–T021) before the image inspection run (T022).
- US3: `.env.example` (T024) before README (T025) before doc reconciliation (T026–T027).

### Parallel Opportunities

- Setup: T002 and T003 can run in parallel ([P]).
- US1 verification authoring: T007, T008, T009 in parallel ([P], all editing distinct sections of quickstart.md — coordinate the single file or stage sequentially if editing concurrently).
- US2 verification authoring: T016, T017 in parallel ([P]).
- Polish: T028 (backend gate) and T029 (frontend gate) in parallel ([P]).
- Across stories: US1 must land first (it creates the Dockerfile + proxy config US2 hardens and the setup US3 documents), so US2/US3 do not run fully parallel with US1 in this story.

---

## Parallel Example: User Story 1

```bash
# Author the US1 verification sections together (distinct quickstart.md sections):
Task: "T007 Author the five validation cases in quickstart.md"
Task: "T008 Author the contract-drift check in quickstart.md"
Task: "T009 Author the ingestion-isolation check in quickstart.md"

# Polish gates run in parallel:
Task: "T028 Run backend pytest gate (coverage > 80%)"
Task: "T029 Run frontend lint/tsc/vitest/build gate (coverage > 80%)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational (confirms contract boundary + data source — blocks all stories).
3. Complete Phase 3: User Story 1 (proxy config + frontend image + compose wiring + validation run).
4. **STOP and VALIDATE**: run the five validation cases and the ingestion-isolation check from `quickstart.md`; confirm all five services healthy and the console shows live C6-008 state.
5. This is the deployable functional whole — demo it.

### Incremental Delivery

1. Setup + Foundational → integration boundary confirmed stable.
2. US1 → one-command stack with live console → validate independently → demo (MVP!).
3. US2 → harden and inspect the shipped console image → validate independently.
4. US3 → reconcile README and docs → validate with a fresh-contributor walkthrough.
5. Polish → re-run existing gates, confirm FR-013 (no behavior change), final end-to-end acceptance.

### Parallel Team Strategy

This story is largely sequential by artifact dependency (US1 creates what US2 hardens and US3
documents). With multiple people:

1. Everyone completes Setup + Foundational together.
2. One person drives US1 to a running stack.
3. Once the `src/frontend/Dockerfile` and `deploy/frontend/` config exist, a second person takes US2 hardening while a third drafts US3 docs against the known service/port names.
4. Converge on Polish gates together.

---

## Notes

- [P] tasks = different files, no dependencies. Several US1/US2 verification tasks edit distinct sections of the single `quickstart.md`; treat them as parallel in planning but serialize the actual file edits to avoid conflicts.
- [Story] label maps each task to its user story for traceability.
- This story adds no product behavior, contract or business logic (FR-013); verification is the documented E2E walkthrough plus image/header/contract-drift checks, not new unit-test logic.
- On any live schema mismatch against contract v1.0.0: STOP and request a contract decision — never edit the contract or the generated types (FR-014).
- Agents never commit/push; review and commit the changes yourself (AGENTS.md).
- Stop at any checkpoint to validate the story independently.
