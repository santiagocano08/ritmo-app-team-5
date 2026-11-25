---
description: "Task list for US-10: sidebar section switching with placeholder"
---

# Tasks: Sidebar Section Switching with Placeholder

**Input**: Design documents from `/specs/008-sidebar-section-switching/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-sections.md, quickstart.md

**Tests**: Included (project default; constitution Principle V, Test-First). Tests in each phase MUST be written first and MUST FAIL before the implementation tasks of that phase start.

**Organization**: Grouped by user story. Both stories are P1; US1 (switch to a placeholder section) is the MVP, US2 (return to the live fleet view) builds on the section state introduced in US1.

**Scope guard**: frontend only (`src/frontend/`). No router library (FR-009). No backend, `contracts/`, generated-type or hook changes (FR-010). Existing Tailwind tokens only.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story the task belongs to (US1, US2)
- All paths are relative to the repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the US-06 console shell baseline is green before any change.

- [X] T001 Install dependencies with `npm ci` and run the baseline `frontend-ci` commands (`npm run lint`, `npx tsc --noEmit`, `npm run test:coverage`, `npm run build`) in `src/frontend/`; record that all pass before editing (no file changes)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The single section list and the controlled `Sidebar` that both stories need (contract `SECTIONS` + S1–S6).

**⚠ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for Foundational (write first, must fail) ⚠

- [X] T002 [P] Update `src/frontend/tests/shell/Sidebar.test.tsx`: pass a `vi.fn()` `onSelect` prop in both existing renders, and add cases for contract S1 (one `<a href>` per `SECTIONS` entry, in order *Central en vivo*, *Alertas*, *Plan del día*, inside `<nav aria-label="Secciones">`), S2 (render with `activeSection="alerts"`: exactly that link has `aria-current="page"` and classes `bg-surface text-sidebar`; the others have no `aria-current` and `text-sidebar-inactive`), S3 (clicking *Plan del día* with `@testing-library/user-event` calls `onSelect("day_plan")` once and `window.location.hash` stays unchanged; Tab-focusing an item and pressing Enter calls `onSelect` with its id), S4 (clicking the already active item calls `onSelect` with the same id), S5 (clicking *Cerrar sesión* `#logout` never calls `onSelect`), S6 (logo and user footer still render)
- [X] T003 [P] Update the `Sidebar` render in `src/frontend/tests/a11y/TextNotColor.test.tsx` to pass the new required `onSelect={vi.fn()}` prop (import `vi` from `vitest`), keeping its `aria-current="page"` assertion unchanged

### Implementation for Foundational

- [X] T004 Create `src/frontend/src/components/shell/sections.ts` exporting `type SectionId = "live_central" | "alerts" | "day_plan"`, `interface SectionDef` (`readonly id: SectionId; readonly label: string; readonly icon: string; readonly href: string; readonly hasContent: boolean`) and `export const SECTIONS: readonly SectionDef[]` with, in this order: `{ id: "live_central", label: "Central en vivo", icon: "◉", href: "#live", hasContent: true }`, `{ id: "alerts", label: "Alertas", icon: "✚", href: "#alerts", hasContent: false }`, `{ id: "day_plan", label: "Plan del día", icon: "▦", href: "#plan", hasContent: false }`. Rules (data-model.md): "The list order is the sidebar order", "The list is a `readonly` constant; it is never mutated at runtime", "The *Gestor* entry (*Indicadores de calidad*) is out of scope"
- [X] T005 Refactor `src/frontend/src/components/shell/Sidebar.tsx` into a controlled component with props `{ activeSection: SectionId; onSelect: (section: SectionId) => void }`: remove the local `ActiveSection` type and `NAV_ITEMS` array, map over `SECTIONS` from `./sections`, keep the existing `<a href>` markup and active/inactive classes, and add an `onClick` handler that calls `event.preventDefault()` then `onSelect(section.id)` (research R2). Leave logo, user footer and the `#logout` link untouched (depends on T004)

**Checkpoint**: T002 and T003 pass; `npx tsc --noEmit` fails only in `src/frontend/src/App.tsx` (missing `onSelect`), which US1 fixes.

---

## Phase 3: User Story 1 - Switch to a section that is not built yet (Priority: P1) 🎯 MVP

**Goal**: Clicking *Alertas* or *Plan del día* highlights that item (only), sets the `h1` to its label and replaces the fleet view with the style spec §7 placeholder, while header, badge and banner stay visible.

**Independent Test**: In `npm run dev:mock`, click *Alertas*, then *Plan del día*: one highlighted item, matching `h1`, dashed placeholder with «Contenido de la sección: se define en las próximas historias.», header and banner still shown, URL hash unchanged.

### Tests for User Story 1 (write first, must fail) ⚠

- [X] T006 [P] [US1] Create `src/frontend/tests/status/SectionPlaceholder.test.tsx` covering contract P1 (`data-testid="section-placeholder"` with text exactly «Contenido de la sección: se define en las próximas historias.») and P2 (element has classes `flex flex-1 items-center justify-center rounded-card border-2 border-dashed border-border-placeholder p-6 text-center text-[15px] text-text-secondary`)
- [X] T007 [P] [US1] Create `src/frontend/tests/shell/SectionSwitching.test.tsx` rendering `App` with `renderWithQuery` from `src/frontend/tests/test-utils.tsx` and the MSW server from `src/frontend/tests/setup.ts`; cover spec US1 scenarios 1–3 and contract A2, A4, A5: wait for the fleet (`B-105` from the normal fixture), click *Alertas* → `h1` «Alertas», only *Alertas* has `aria-current="page"`, `section-placeholder` present, `B-105` and the stale indicator absent, header badge and `DataStateBanner` still rendered; click *Plan del día* → same checks with «Plan del día»; click *Plan del día* again → nothing changes (edge case); a multi-switch loop asserts exactly one `aria-current` link and `h1` equal to its text after every click (SC-001)

### Implementation for User Story 1

- [X] T008 [P] [US1] Create `src/frontend/src/components/status/SectionPlaceholder.tsx`: a no-props presentational component rendering a `div` with `data-testid="section-placeholder"`, classes `flex flex-1 items-center justify-center rounded-card border-2 border-dashed border-border-placeholder p-6 text-center text-[15px] text-text-secondary`, and the text «Contenido de la sección: se define en las próximas historias.» (research R6: no shared frame abstraction with `EmptyState`)
- [X] T009 [US1] Modify `src/frontend/src/App.tsx`: add `const [activeSection, setActiveSection] = useState<SectionId>("live_central")` (A1, FR-007); resolve the active `SectionDef` from `SECTIONS`; pass `activeSection` and `onSelect={setActiveSection}` to `Sidebar`; render the `h1` from the active section's `label` (A2); inside `<main>` render the existing `StaleIndicator` + `EmptyState` / `CorridorSummary` + `FleetList` block only when `hasContent` is `true` (A3, R4), otherwise `SectionPlaceholder` only (A4). Keep `useCorridorNow`, `useSourceStatus`, `Header` and `DataStateBanner` unconditional with today's props (A5, A6, research R3) (depends on T005, T008)

**Checkpoint**: T002, T003, T006, T007 pass; existing `StaleRecovery`, `NoData`, fleet and summary suites stay green unchanged. US1 is deliverable as the MVP.

---

## Phase 4: User Story 2 - Return to the live fleet view (Priority: P1)

**Goal**: From any placeholder section, clicking *Central en vivo* restores the fleet view and summary, and live data keeps refreshing at the usual 5 s interval with no reload.

**Independent Test**: In `npm run dev:mock`, go to *Plan del día*, then *Central en vivo*: fleet list and summary return and `/api/v1/corridor/.../now` requests keep arriving every ~5 s in DevTools → Network.

### Tests for User Story 2 (write first, must fail if US1 regressed) ⚠

- [X] T010 [US2] Extend `src/frontend/tests/shell/SectionSwitching.test.tsx` with spec US2 scenarios 1–2 and contract A1, A3, A6: on first render *Central en vivo* is the only `aria-current` link, `h1` reads «Central en vivo» and `B-105` is shown; after *Plan del día* → *Central en vivo*, the fleet (`B-105`) and summary are shown again and the placeholder is gone; count `/now` requests with an MSW `server.events.on("request:start", ...)` listener (removed in cleanup) and assert a new request arrives after returning, using real timers, `waitFor` with `{ timeout: 7000 }` and a per-test timeout of 20 000 ms, following `src/frontend/tests/status/StaleRecovery.test.tsx` (SC-003) (depends on T007)
- [X] T011 [US2] In `src/frontend/tests/shell/SectionSwitching.test.tsx`, add the stale-while-away edge case: override the `/now` handler with `server.use(...)` to fail while on *Alertas*, assert the header badge / `DataStateBanner` reflect the degraded state on the placeholder section, then restore and return to *Central en vivo* and assert the fleet view shows the current state (FR-008) (depends on T010)

### Implementation for User Story 2

- [X] T012 [US2] If T010 or T011 fail, fix only `src/frontend/src/App.tsx` so the live branch re-renders from the cached snapshot and the query hooks stay mounted in every section (research R3); no changes to `src/frontend/src/hooks/` (depends on T009, T010, T011)

**Checkpoint**: Both stories pass independently; switching never stops polling.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Gates, manual validation and visual review.

- [X] T013 Run `npm run lint`, `npx tsc --noEmit`, `npm run test:coverage` (80 % lines/functions/branches/statements thresholds in `src/frontend/vite.config.ts`) and `npm run build` in `src/frontend/`; all must pass (SC-005)
- [X] T014 Verify scope with `git diff --stat`: only `src/frontend/src/App.tsx`, `src/frontend/src/components/shell/sections.ts`, `src/frontend/src/components/shell/Sidebar.tsx`, `src/frontend/src/components/status/SectionPlaceholder.tsx` and the test files under `src/frontend/tests/` changed; no edits to `src/api/`, `src/data/`, `src/pulsoflota/`, `contracts/` or generated types (FR-010), no router dependency in `src/frontend/package.json` (FR-009)
- [X] T015 Run the manual checks 1–7 from `specs/008-sidebar-section-switching/quickstart.md` with `npm run dev:mock` in `src/frontend/` (first load, Alertas, Plan del día, re-click, return with polling, keyboard Enter, single `aria-current`)
- [X] T016 Visual review (SC-004) of the placeholder against `docs/designs/mockups/escritorio/UXUI03-escritorio.png` and `tickets/US-06-frontend-home/US-06-escritorio-estilos.md` §7: border 2 px dashed `#A3ACB9`, radius 12 px, padding 24 px, text `#4A5361` 15 px, centered on both axes, filling the remaining height

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none.
- **Foundational (Phase 2)**: after Setup; blocks both stories. T002/T003 before T004/T005; T004 before T005.
- **US1 (Phase 3)**: after Foundational. T006/T007 before T008/T009; T008 before T009.
- **US2 (Phase 4)**: after US1 (it reuses the `activeSection` state from T009 and the test file from T007).
- **Polish (Phase 5)**: after US1 and US2.

### Dependency graph

```text
T001 → {T002, T003} → T004 → T005 → {T006, T007} → T008 → T009 → T010 → T011 → T012 → T013 → T014 → {T015, T016}
```

### User Story Dependencies

- **US1 (P1)**: depends only on Foundational.
- **US2 (P1)**: depends on US1's `App` section state; verifiable on its own through its scenarios once US1 is in place.

### Within Each Phase

- Tests are written first and MUST FAIL before the implementation tasks in the same phase.
- `sections.ts` before `Sidebar`; `SectionPlaceholder` before `App`.

### Parallel Opportunities

- T002 and T003 (different test files).
- T006 and T007 (different test files); T008 can start alongside them once its test T006 is written.
- T015 and T016 (manual checks).

---

## Parallel Example: Foundational

```bash
Task: "Update Sidebar tests for S1–S6 in src/frontend/tests/shell/Sidebar.test.tsx"
Task: "Pass onSelect in src/frontend/tests/a11y/TextNotColor.test.tsx"
```

## Parallel Example: User Story 1

```bash
Task: "SectionPlaceholder P1–P2 test in src/frontend/tests/status/SectionPlaceholder.test.tsx"
Task: "App switching integration test in src/frontend/tests/shell/SectionSwitching.test.tsx"
# then
Task: "Create src/frontend/src/components/status/SectionPlaceholder.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Phase 1 Setup → Phase 2 Foundational.
2. Phase 3 US1 → run T013 gates → manual quickstart steps 1–4.
3. Stop and validate: the two placeholder sections behave like the design.

### Incremental Delivery

1. Foundational + US1 → MVP (navigation matches design).
2. US2 → proves return to live and continued polling (SC-003).
3. Polish → gates, scope check, manual and visual review, then open the PR for `feature/US-10-frontend-sidebar-sections` (issue #52).

---

## Notes

- `tests/a11y/TextNotColor.test.tsx` also renders `Sidebar`; it is not listed in plan.md but must pass the new required `onSelect` prop (T003).
- Branch naming: the current branch is `feature/US-10-frontend-sidebar-sections`, matching the ticket; plan.md's "`feature/US-10`" risk row no longer applies.
- Agents do not commit; review and commit with Conventional Commits, e.g. `feat(frontend): switch sidebar sections with placeholder (US-10)`.
