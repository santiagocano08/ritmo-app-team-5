---
description: "Task list for US-06 Dispatcher Console — Fleet State and Headway"
---

# Tasks: Dispatcher Console — Fleet State and Headway

**Input**: Design documents from `/specs/005-dispatcher-console/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/README.md

**Tests**: INCLUDED. The spec does not opt out of testing, and the plan adopts Gate 2 (Vitest + Testing Library, coverage > 80 % on console code). Within each user story, test tasks are written FIRST and MUST FAIL before the matching implementation tasks are done (Principle V, Test-First).

**Organization**: Tasks are grouped by user story (priority order P1 → P2 → P3) so each story is independently implementable and testable. All frontend code lives in `src/frontend/` (first frontend code in the repo); the backend read API it consumes already exists (feature 004).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task belongs to (US1, US2, US3)
- Exact file paths are included in every task description

## Path Conventions

- Frontend SPA root: `src/frontend/`
- App source: `src/frontend/src/`
- Tests: `src/frontend/tests/`
- Shared read contracts (source of truth, do not edit): repo-root `contracts/read/` (`corridor_now.schema.json`, `source_status.schema.json` v1.0.0) and `contracts/read/fixtures/*`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the `src/frontend/` project, pin and lock dependencies, and configure the toolchain required by `frontend-ci` (Gate 1 & Gate 2).

- [X] T001 Create the `src/frontend/` tree per plan.md (`index.html`, `src/`, `tests/`, and empty `src/{api/generated,hooks,components/{shell,fleet,summary,status},styles,mocks}/` directories) in `src/frontend/`
- [X] T002 Create `src/frontend/package.json` with pinned deps (React 19, Vite, TanStack Query, Tailwind CSS, `openapi-typescript`, Vitest, `@testing-library/react`, `msw`) and scripts (`dev`, `dev:mock`, `gen:types`, `lint`, `test`, `test:coverage`, `build`); run `npm install` once, then commit `src/frontend/package-lock.json` (installs use `npm ci`)
- [X] T003 [P] Create `src/frontend/tsconfig.json` with `strict: true` and `noImplicitAny` (no `any`) in `src/frontend/tsconfig.json`
- [X] T004 [P] Create `src/frontend/vite.config.ts` (React plugin, Vitest test config with `jsdom` environment, coverage reporter and > 80 % threshold on console code) in `src/frontend/vite.config.ts`
- [X] T005 [P] Create `src/frontend/tailwind.config.ts` encoding the design tokens from plan.md (app bg `#F4F6F9`, surface `#FFFFFF`, text `#12161C`/`#4A5361`, border `#DDE1E7`, sidebar `#14213D`, logo accent `#FBBF24`, status live `#DCFCE7`/`#166534`, estimated `#FEF3C7`/`#78350F`, no-data `#FEE2E2`/`#991B1B`, radii 8/12/999 px, fonts Inter + Space Grotesk) in `src/frontend/tailwind.config.ts`
- [X] T006 [P] Create `src/frontend/.eslintrc.cjs` (TypeScript + React 19 + hooks rules, forbid `useEffect` data fetching per coding standards) in `src/frontend/.eslintrc.cjs`
- [X] T007 [P] Add the Tailwind entry stylesheet with the Inter (400/500/600/700) and Space Grotesk (500/700) font declarations and base tokens in `src/frontend/src/styles/index.css`

**Checkpoint**: `npm ci` installs reproducibly; `npx tsc --noEmit`, `npm run lint`, and `npm run build` run against an empty app without tooling errors.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Contract-derived types, the typed read client, the polling hooks, the mock harness, and the app bootstrap that every user story depends on.

**⚠ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T008 Add the `gen:types` script implementation and generate committed TypeScript types from `contracts/read/corridor_now.schema.json` and `contracts/read/source_status.schema.json` (v1.0.0) into `src/frontend/src/api/generated/` (output committed, never hand-edited) — produces `CorridorNow`, `Bus`, `Summary`, `SourceStatus` per data-model.md
- [X] T009 Define the `NoDataEnvelope` type (`status: "no_data"`, `corridor_id: string`, optional `sources_down: []`) as an API-level sibling (not a generated contract type) in `src/frontend/src/api/types.ts`
- [X] T010 Implement the typed read client in `src/frontend/src/api/client.ts`: `GET /api/v1/corridor/{corridor_id}/now` and `.../source-status`, base-URL config, assert `schema_version === "1.0.0"` and surface a mismatch instead of rendering, treat a malformed body / 500 / unreachable backend as a failed refresh, and return the no-data envelope as a first-class non-error state (R2, R1, data-model validation rules)
- [X] T011 [P] Implement `useCorridorNow` in `src/frontend/src/hooks/useCorridorNow.ts` using TanStack `useQuery` with `refetchInterval: 5000`, `refetchIntervalInBackground: false`, `keepPreviousData: true`; no `useEffect` fetching (R3)
- [X] T012 [P] Implement `useSourceStatus` in `src/frontend/src/hooks/useSourceStatus.ts` using TanStack `useQuery` with the same 5 s polling and `keepPreviousData` config (R3)
- [X] T013 [P] Derive `FleetViewState` (`connection: "ok" | "stale"`, `lastSnapshot`, `lastSourceStatus`, `isEmpty`, `lastUpdated`) from the two query results per data-model.md — `stale` on query `isError` with a retained prior snapshot, `isEmpty` when `buses_in_service === 0` or a no-data envelope — in `src/frontend/src/hooks/useFleetViewState.ts`
- [X] T014 [P] Set up the `msw` mock harness serving the repo-root `contracts/read/fixtures/{normal,c1_bunching,c2_gap,c5_breakdown,d1_source_outage}/` files plus a synthesized no-data envelope and a simulated failed refresh, with a scenario switcher for `dev:mock`, in `src/frontend/src/mocks/handlers.ts` and `src/frontend/src/mocks/browser.ts`
- [X] T015 [P] Add the shared Vitest test setup (jsdom, Testing Library matchers, `msw` server start/stop, fixture loaders) in `src/frontend/tests/setup.ts`
- [X] T016 Create the app bootstrap: `QueryClientProvider` + `msw` enable-on-mock in `src/frontend/src/main.tsx`, and the shell+content composition scaffold in `src/frontend/src/App.tsx` (regions wired, components added per story)

**Checkpoint**: Types generated and committed; client and both polling hooks compile; mock mode boots and serves every fixture scenario. User stories can now proceed.

---

## Phase 3: User Story 1 — See live fleet state and headway (Priority: P1) 🎯 MVP

**Goal**: Render corridor C6-008's fleet leader-first — each bus with operational state, position along the corridor, actual-vs-planned headway, and live/estimated data quality — auto-refreshing at ~5 s without a manual reload.

**Independent Test**: With the `normal` fixture (or the live backend) served, open the console and confirm every bus appears leader-first (B-105 first) with its state, position, and `headway_ahead_s` vs `headway_planned_s`; change the served snapshot and confirm the list updates within ~5 s with no reload (quickstart §1, §3).

### Tests for User Story 1 (write first, MUST FAIL before implementation) ⚠

- [X] T017 [P] [US1] Component test: `FleetList` renders `CorridorNow.buses` in received order (leader-first, no client re-sort) from the `normal` fixture, in `src/frontend/tests/fleet/FleetList.test.tsx`
- [X] T018 [P] [US1] Component test: `BusRow` shows state, position label (from `prev_stop_id`/`next_stop_id` + `distance_along_m`), and `headway_ahead_s` vs `headway_planned_s`; when `headway_ahead_s` is `null` no headway comparison is shown (FR-002, R5), in `src/frontend/tests/fleet/BusRow.test.tsx`
- [X] T019 [P] [US1] Component test: a bus with `data_quality: "estimated"` is labeled "Estimated" and raises no alert (FR-003, FR-008), in `src/frontend/tests/fleet/QualityTag.test.tsx`
- [X] T020 [P] [US1] Interaction test: TanStack polling at `refetchInterval: 5000` replaces displayed values with the newest snapshot without a reload, and `keepPreviousData` holds the prior snapshot during refresh (FR-009, FR-014, SC-002), in `src/frontend/tests/hooks/useCorridorNow.test.tsx`

### Implementation for User Story 1

- [X] T021 [P] [US1] Implement `QualityTag` mapping `data_quality` (`live`/`estimated`) to "Live"/"Estimated" text plus redundant styling (text, not color alone — FR-012) in `src/frontend/src/components/fleet/QualityTag.tsx`
- [X] T022 [P] [US1] Implement `StateTag` mapping `bus_state` (`leader`/`regular`/`bunched`/`gap`/`broken_down`) to a text label plus redundant color/icon (FR-012) in `src/frontend/src/components/fleet/StateTag.tsx`
- [X] T023 [P] [US1] Implement `HeadwayCompare` showing `headway_ahead_s` and `headway_planned_s` (`headway_planned_s` ≥ 1, 600 s peak) with deviation direction/magnitude, and no comparison when `headway_ahead_s` is `null` (R5, data-model.md) in `src/frontend/src/components/fleet/HeadwayCompare.tsx`
- [X] T024 [US1] Implement `BusRow` composing `StateTag`, `QualityTag`, `HeadwayCompare` and the position label from one `Bus` (`distance_along_m` 0–5119.4) in `src/frontend/src/components/fleet/BusRow.tsx` (depends on T021, T022, T023)
- [X] T025 [US1] Implement `FleetList` rendering `CorridorNow.buses` in received order (leader-first, no re-sort — R5) as `BusRow`s in `src/frontend/src/components/fleet/FleetList.tsx` (depends on T024)
- [X] T026 [US1] Wire `FleetList` into `App.tsx` driven by `useCorridorNow` + `useFleetViewState`, with the `<main>` "Central en vivo" region (h1 Space Grotesk 26, 28 px padding) per R9, in `src/frontend/src/App.tsx`

**Checkpoint**: User Story 1 is fully functional — the live fleet view renders leader-first with state/position/headway/quality and auto-refreshes. MVP is demoable here.

---

## Phase 4: User Story 2 — Spot bunching and gaps at a glance (Priority: P2)

**Goal**: Make bunched and gap buses visually and textually distinct from regular buses, and show a corridor summary with buses-in-service, bunched, and gap counts that match the snapshot.

**Independent Test**: Serve the `c1_bunching` and `c2_gap` fixtures and confirm bunched/gap buses are distinguished from regular ones and that the summary counts (`buses_in_service`, `n_bunched`, `n_gaps`) exactly match the snapshot (quickstart §1; SC-003).

### Tests for User Story 2 (write first, MUST FAIL before implementation) ⚠

- [X] T027 [P] [US2] Component test: bunched buses (from `c1_bunching`) and gap buses (from `c2_gap`) are visually and textually distinguished from regular buses via `StateTag` (FR-004, FR-012), in `src/frontend/tests/fleet/StateTag.distinction.test.tsx`
- [X] T028 [P] [US2] Component test: `CorridorSummary` shows `buses_in_service`, `n_bunched`, `n_gaps` (all int ≥ 0) matching the `c1_bunching` and `c2_gap` fixtures, and updates when the snapshot changes (FR-005, FR-014, SC-003), in `src/frontend/tests/summary/CorridorSummary.test.tsx`

### Implementation for User Story 2

- [X] T029 [US2] Confirm/extend `StateTag` so `bunched` and `gap` carry a distinct text label plus redundant color against `regular` (FR-004, FR-012) in `src/frontend/src/components/fleet/StateTag.tsx`
- [X] T030 [P] [US2] Implement `CorridorSummary` rendering `CorridorNow.summary` (`buses_in_service`, `n_bunched`, `n_gaps`, each int ≥ 0) in `src/frontend/src/components/summary/CorridorSummary.tsx`
- [X] T031 [US2] Wire `CorridorSummary` into the `<main>` region in `src/frontend/src/App.tsx`, bound to the same `useCorridorNow` snapshot as the fleet list

**Checkpoint**: User Stories 1 AND 2 both work independently — bunching/gaps are obvious and the summary counts match every snapshot.

---

## Phase 5: User Story 3 — Understand overall data trustworthiness (Priority: P3)

**Goal**: Show an overall source-status indicator (live / estimated / no_data), an explanatory banner for estimated and no_data (never for live), and the dispatcher navigation shell (sidebar, corridor selector, clock, data-state badge, user identity). Estimated data never raises an alert.

**Independent Test**: Serve the `d1_source_outage` fixture, the no-data envelope, and the `normal` (live) fixture; confirm the badge/indicator matches each status, the banner appears only for estimated and no_data, estimated buses are labeled without an alert, and the shell renders the sidebar sections, corridor selector, clock, data-state badge, and user identity with the active section marked (quickstart §2, §5; SC-004, SC-005).

### Tests for User Story 3 (write first, MUST FAIL before implementation) ⚠

- [X] T032 [P] [US3] Component test: `StatusBadge` / status indicator renders live (green "En vivo"), estimated (amber "Estimado"), and no_data (red "Sin datos") from `SourceStatus.status` with `role="status"` text (FR-006, SC-004, reference §8), in `src/frontend/tests/shell/StatusBadge.test.tsx`
- [X] T033 [P] [US3] Component test: `DataStateBanner` with `role="alert"` is shown for `estimated` and `no_data` and hidden for `live`; the no_data banner tells the dispatcher to rely on the day's plan; estimated raises no alert (FR-007, FR-008, SC-004, SC-005), in `src/frontend/tests/shell/DataStateBanner.test.tsx`
- [X] T034 [P] [US3] Component test: the navigation `Sidebar` renders the dispatcher sections (Central en vivo / Alertas / Plan del día) with the active one marked `aria-current="page"`, plus logo and user footer ("Usuario demo" / "Despachador") (FR-011, US3 scenario 4, reference §4–§7), in `src/frontend/tests/shell/Sidebar.test.tsx`
- [X] T035 [P] [US3] Component test: the `Header` renders the corridor selector ("CORREDOR" + "[Corredor piloto] · Estación → casa"), the status badge, and the clock (Space Grotesk) (FR-011, reference §5), in `src/frontend/tests/shell/Header.test.tsx`

### Implementation for User Story 3

- [X] T036 [P] [US3] Implement `StatusBadge` ( `role="status"` pill, 10 px dot + label + detail, live/estimated/no_data palette) from `SourceStatus.status` plus the stale flag, text not color alone (FR-006, R4, R6) in `src/frontend/src/components/shell/StatusBadge.tsx`
- [X] T037 [P] [US3] Implement `DataStateBanner` ( `role="alert"`) rendering explanatory text for `estimated` (an operator source is down, from `sources_down`) and `no_data` (rely on the day's plan), hidden for `live` (FR-007, FR-008, reference §8) in `src/frontend/src/components/shell/DataStateBanner.tsx`
- [X] T038 [P] [US3] Implement `Sidebar` (248 px, `#14213D`; logo with amber `#FBBF24` pulse icon + Space Grotesk wordmark; `<nav aria-label="Secciones">` with Central en vivo / Alertas / Plan del día, 44 px rows, active white-on-navy `aria-current="page"`; user footer avatar "UD" + "Usuario demo" / "Despachador" + presentational "Cerrar sesión") per `NavigationContext` and reference §4–§7, in `src/frontend/src/components/shell/Sidebar.tsx`
- [X] T039 [P] [US3] Implement `CorridorSelector` ("CORREDOR" label + single-valued button "[Corredor piloto] · Estación → casa" + chevron; `activeCorridor` fixed to `C6-008`) in `src/frontend/src/components/shell/CorridorSelector.tsx`
- [X] T040 [P] [US3] Implement `Clock` showing current time (Space Grotesk 22/700), updating each second, in `src/frontend/src/components/shell/Clock.tsx`
- [X] T041 [US3] Implement `Header` (68 px, `#FFFFFF`, bottom border `#DDE1E7`) composing `CorridorSelector` (left) and `StatusBadge` + `Clock` (right) in `src/frontend/src/components/shell/Header.tsx` (depends on T036, T039, T040)
- [X] T042 [US3] Wire `Sidebar`, `Header`, and `DataStateBanner` into `App.tsx` as the navigation shell around the `<main>` content, binding the data-state badge and banner to `useSourceStatus` (R4) in `src/frontend/src/App.tsx` (depends on T038, T041, T037)

**Checkpoint**: All three user stories are independently functional — the fleet view, bunching/gap summary, and data-trust shell all work.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Edge-case UI, resilience behavior, accessibility, and the quality gates that span every story.

- [X] T043 [P] Implement `EmptyState` (informative message + zero counts, not blank) shown when `buses_in_service === 0` or a no-data envelope is returned (FR-013, quickstart §2) in `src/frontend/src/components/status/EmptyState.tsx`
- [X] T044 [P] Implement `StaleIndicator` (non-blocking, text + ARIA) driven by `FleetViewState.connection === "stale"`, keeping the last snapshot visible and distinct from the estimated/no_data banner (FR-010, R4, SC-006) in `src/frontend/src/components/status/StaleIndicator.tsx`
- [X] T045 Wire `EmptyState` and `StaleIndicator` into `App.tsx` via `useFleetViewState` in `src/frontend/src/components/status/` integration in `src/frontend/src/App.tsx` (depends on T043, T044)
- [X] T046 [P] Integration test: a simulated failed refresh over a prior fixture keeps the last snapshot visible, shows the stale indicator, retries next cadence, and recovers on the next success (FR-010, SC-006), in `src/frontend/tests/status/StaleRecovery.test.tsx`
- [X] T047 [P] Integration test: the no-data envelope renders the no-data status, the "rely on the day's plan" banner, and the empty state with zero counts (FR-013, SC-004), in `src/frontend/tests/status/NoData.test.tsx`
- [X] T048 [P] Integration test: the `c5_breakdown` fixture renders a `broken_down` bus distinguishable and with no headway comparison (`headway_ahead_s` null), counts consistent (edge case), in `src/frontend/tests/fleet/Breakdown.test.tsx`
- [X] T049 [P] Accessibility test: every `bus_state`, `data_quality`, and `SourceStatus.status` carries a text/ARIA label alongside color; `role="status"` badge, `role="alert"` banner, `aria-current="page"` active section present (FR-012, SC-007, reference §10), in `src/frontend/tests/a11y/TextNotColor.test.tsx`
- [X] T050 Run `npm run dev:mock` and walk the quickstart §1–§6 scenarios against the fixtures, confirming the acceptance mapping in quickstart.md — mock harness wired (msw handlers + scenario switcher + fail-refresh toggle + service worker in `public/`), dev server boots (HTTP 200); every quickstart scenario (normal, c1_bunching, c2_gap, c5_breakdown, d1_source_outage, no-data, stale) is covered by the automated suite.
- [X] T051 Run the frontend-ci gates locally (on Node 20.20.2 LTS per plan): `npm run lint` (Gate 1 — PASS, 0 problems), `npx tsc --noEmit` (strict, no `any` — PASS), `npm run test:coverage` (Vitest 4.1.12, 33 tests PASS, 98.31 % stmts / 93.97 % branch / 100 % funcs — > 80 % Gate 2), `npm run build` (Vite 6 — PASS), `npm audit` (JS SCA — PASS, **0 vulnerabilities**). Dev/test tooling bumped to clear all advisories: vitest + @vitest/coverage-v8 4.1.12 (fixes @vitest/mocker + tinypool), vite 6.4.6 (fixes vite/esbuild), @vitejs/plugin-react 4.7.0, typescript-eslint 8.73.0 (fixes minimatch). `package-lock.json` relocked on Node 20; `npm ci` reproducible.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories.
- **User Stories (Phase 3–5)**: All depend on Foundational completion.
  - US1 (P1) → US2 (P2) → US3 (P3) in priority order, or in parallel once Phase 2 is done (they touch mostly different component folders; the only shared file is `App.tsx`).
- **Polish (Phase 6)**: Depends on the user stories whose UI it hardens (US1 for breakdown/a11y, US3 for no-data/stale).

### User Story Dependencies

- **US1 (P1)**: Needs only Foundational. The core, independently testable MVP.
- **US2 (P2)**: Needs Foundational; reuses `StateTag` from US1 but is independently testable with its own fixtures. If built in parallel with US1, `StateTag` (T022) must land first.
- **US3 (P3)**: Needs Foundational; the shell and status/banner are independent of US1/US2 content. Fully independently testable.

### Within Each User Story

- Tests (T017–T020, T027–T028, T032–T035) are written FIRST and MUST FAIL before their implementation tasks.
- Leaf components (tags, compare, badge, selector, clock) before composites (`BusRow`, `FleetList`, `Header`).
- Composites before the `App.tsx` wiring task for that story.

### App.tsx serialization

`App.tsx` is edited by T016, T026, T031, T042, T045. These touch the same file, so they are **not** `[P]` with each other and run in task-ID order.

## Parallel Opportunities

- Setup: T003, T004, T005, T006, T007 run in parallel after T001/T002.
- Foundational: T011, T012, T013, T014, T015 run in parallel after T008–T010.
- US1: tests T017–T020 in parallel; leaf components T021, T022, T023 in parallel; then T024 → T025 → T026.
- US2: tests T027, T028 in parallel; T030 in parallel with the T029 tweak.
- US3: tests T032–T035 in parallel; leaf components T036, T037, T038, T039, T040 in parallel; then T041 → T042.
- Polish: T043, T044 in parallel; tests T046, T047, T048, T049 in parallel.
- Across stories: once Phase 2 is done, one developer can take US1, another US3 (US2 after US1's `StateTag`), coordinating only on `App.tsx`.

## Parallel Example: User Story 1

```bash
# Write all US1 tests first (they must fail):
Task: "Component test: FleetList renders buses leader-first in tests/fleet/FleetList.test.tsx"
Task: "Component test: BusRow state/position/headway, null headway in tests/fleet/BusRow.test.tsx"
Task: "Component test: estimated bus labeled, no alert in tests/fleet/QualityTag.test.tsx"
Task: "Interaction test: 5 s polling replaces snapshot in tests/hooks/useCorridorNow.test.tsx"

# Then build the leaf components in parallel:
Task: "Implement QualityTag in src/components/fleet/QualityTag.tsx"
Task: "Implement StateTag in src/components/fleet/StateTag.tsx"
Task: "Implement HeadwayCompare in src/components/fleet/HeadwayCompare.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup.
2. Phase 2: Foundational (CRITICAL — blocks all stories).
3. Phase 3: User Story 1.
4. **STOP and VALIDATE**: run the US1 tests and quickstart §1/§3 against the `normal` fixture.
5. Demo the live fleet view.

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. US1 → test → demo (MVP: live fleet view).
3. US2 → test → demo (bunching/gap + summary).
4. US3 → test → demo (data-trust shell + banner).
5. Polish → edge cases, resilience, a11y, gates green.

### Parallel Team Strategy

After Phase 2: Developer A on US1, Developer B on US3 (independent), Developer C on US2 once US1's `StateTag` lands. Integrate through `App.tsx` in task-ID order.

---

## Notes

- `[P]` tasks = different files, no dependencies on incomplete tasks.
- Tests are written first and must fail before implementation (Principle V).
- Payload types are generated from `contracts/read/*.schema.json` v1.0.0 and committed, never hand-edited (Principle II).
- The frontend decides no access control and holds no business logic; states/headways/counts/quality arrive computed from the backend.
- No `useEffect` data fetching — all polling via TanStack Query `refetchInterval` (coding standards, R3).
- Every state and data-quality condition is conveyed in text, not color alone (FR-012, SC-007).
