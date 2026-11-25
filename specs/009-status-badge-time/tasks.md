# Tasks: Status Badge Readable Time

**Input**: `/specs/009-status-badge-time/` (plan.md, spec.md, research.md, data-model.md, quickstart.md)

**Tests**: Included (default ON; spec and constitution do not opt out). Tests MUST be written and MUST FAIL before implementation.

**Organization**: One user story (US1, P1). Frontend only; no backend, contract or generated-type change (FR-007).

## Format: `[ID] [P?] [Story] Description`

All paths are relative to the repo root. Frontend commands run in the Node container (see quickstart.md); never `npm install`/`npm ci`, never pass `-e TZ`.

## Phase 1: Setup

No new dependencies or structure; nothing to set up.

## Phase 2: Foundational

**Purpose**: Make tests independent of host time zone (SC-002, research D2).

- [X] T001 Pin the test time zone by adding `env: { TZ: "America/Bogota" }` under `test` in `src/frontend/vite.config.ts`; if a Vitest run in the default container (UTC) still shows UTC output, fall back to setting `process.env.TZ = "America/Bogota"` at the top of the existing test setup file (or a new `src/frontend/tests/setup.ts` registered in `setupFiles`).

**Checkpoint**: A test calling `new Date("2026-11-24T22:42:08Z").getHours()` returns 17 without `-e TZ`.

## Phase 3: User Story 1 - Judge data freshness at a glance (P1) 🎯 MVP

**Goal**: Badge shows readable local time for `live`, "since" for `estimated`, and the fixed text for `no_data`.

**Independent Test**: Render/format each of the three states with fixed timestamps and compare the detail text.

### Tests for User Story 1 (write first, must FAIL)

- [X] T002 [P] [US1] Create unit tests for `formatStatusDetail` in `src/frontend/tests/shell/statusDetail.test.ts`: `live` + `2026-11-24T22:42:08Z` → `Último evento 17:42:08`; `estimated` with since 17:39 and 17:41 local (`2026-11-24T22:39:00Z`, `2026-11-24T22:41:00Z`) → `Una fuente no responde desde 17:39` (earliest); `no_data` → `Sin eventos del corredor`; zero-padding (`2026-11-24T12:05:09Z` → `07:05:09`); midnight (`2026-11-24T05:00:00Z` → `00:00:00`); `estimated` with empty or unparsable `since` → `Una fuente no responde`; `live` with unparsable `as_of_ts` → `Último evento`; no raw ISO string in any output.
- [X] T003 [P] [US1] Update `src/frontend/tests/shell/StatusBadge.test.tsx` (only if it asserts the raw ISO text) to expect the formatted detail strings from the acceptance scenarios; if it does not, add one case checking the three details render and `estimated` adds no alert.

### Implementation for User Story 1

- [X] T004 [US1] Create `src/frontend/src/components/shell/statusDetail.ts` exporting pure `formatStatusDetail(status, asOfTs, sourcesDown): string` using `Date` getters with manual zero-padding (no `toLocaleTimeString`, no new dependency), per data-model.md table and research D1/D3; types come from `src/frontend/src/api/generated/source-status.ts` (no `any`).
- [X] T005 [US1] In `src/frontend/src/App.tsx`, make `resolveSourceStatus` call `formatStatusDetail` instead of the inline template string; leave the header clock, alert banner text and `StatusBadge` untouched (FR-004, FR-005).
- [X] T006 [US1] Run the quickstart container command (vitest with coverage, eslint `--max-warnings 0`, `tsc --noEmit`) without `-e TZ`; confirm T002/T003 pass, coverage ≥ 80 %, and no generated or backend file changed.

**Checkpoint**: US1 works and is testable independently.

## Phase 4: Polish

- [X] T007 Run `vite build` in the same Node container from `src/frontend` and confirm it succeeds (SC-003).

## Dependencies & Execution Order

- T001 blocks all tests (Foundational).
- T002 and T003 run in parallel after T001; both MUST fail before T004.
- T004 → T005 → T006 → T007.

## Parallel Example

```text
Task: "Unit tests in src/frontend/tests/shell/statusDetail.test.ts"   (T002)
Task: "Badge test update in src/frontend/tests/shell/StatusBadge.test.tsx" (T003)
```

## Implementation Strategy

MVP is US1, the whole feature: T001 → tests (fail) → formatter → wire in App → verify → build.
