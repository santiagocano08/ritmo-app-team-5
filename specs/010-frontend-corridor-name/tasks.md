---
description: "Task list for US-12 — Real Corridor Name in Header"
---

# Tasks: Real Corridor Name in Header

**Feature**: US-12 — `feature/US-12-frontend-corridor-name`
**Input**: Design documents from `/specs/010-frontend-corridor-name/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/corridor-label.md, quickstart.md

**Tests**: INCLUDED. Tests are ON by default for this project (Spec Kit override); no explicit "no testing" opt-out exists in spec.md or the constitution. The feature also explicitly requests updating/adding Vitest + Testing Library tests (spec Assumptions, plan Build phase).

**Organization**: Tasks are grouped by user story (US1 = P1, US2 = P2) so each story is independently implementable and testable. US2 shares the same files as US1 (same component/helper), so US1 must land first; US2 adds the pre-snapshot branch and its test.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 or US2 (maps to spec.md user stories). Setup/Foundational/Polish have no story label.
- All paths are relative to the repository root. Frontend-only change under `src/frontend/`.

## Scope reminders (constitution, AGENTS.md Turn 1, steering)

- **Surgical edits**: only the files named below. No changes to `contracts/`, `src/frontend/src/api/generated/**`, or any backend (`src/api/`, `src/data/`, `src/pulsoflota/`).
- **Strict TypeScript, no `any`**; ESLint `--max-warnings 0`; `tsc --noEmit` clean.
- **No manual fetching / no `useEffect` for data / no query-data mutation** — data flows via the existing `useCorridorNow` TanStack Query hook (frontend-web + coding-standards steering).
- **English** code and identifiers; the user-visible direction text is the Spanish domain copy `Estación → barrio` as the contract pins it.
- **Adaptive lane, Turn 1**: inert button, single corridor `C6-008`, direction `1` only; corridor switching is out of scope.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the working environment; no project scaffolding is needed (existing frontend).

- [X] T001 Verify the frontend toolchain is ready: from `src/frontend/`, confirm dependencies are installed and the baseline is green (`npm run lint`, `npx tsc --noEmit`, `npx vitest run`) before making changes, per quickstart.md "Prerequisites".

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one shared, pure building block both stories depend on.

**⚠️ CRITICAL**: The helper is the single formatting source of truth; both US1 and US2 render through it. It must exist (and its tests must be written first and fail) before the component work.

- [X] T002 Write failing unit tests for the pure helper in `src/frontend/tests/shell/corridorLabel.test.ts`: assert `formatCorridorLabel("C6-008", 1)` returns exactly `"C6-008 · Estación → barrio"` (check C5; separator is middle dot `·` U+00B7 with a leading and trailing space, arrow `→` U+2192) and `formatCorridorLabel("C6-008", undefined)` returns exactly `"C6-008"` (check C6). Tests MUST fail (module does not exist yet).
- [X] T003 Implement the pure helper `formatCorridorLabel(corridorId: string, direction?: number): string` in `src/frontend/src/components/shell/corridorLabel.ts`, mirroring the colocated `statusDetail.ts` precedent. Rule (contracts/corridor-label.md L1/L2): `direction === 1` → `` `${corridorId} · Estación → barrio` ``; `direction` `undefined` or any value ≠ `1` → `corridorId`. Strict types, no `any`, no runtime validation. Run T002 — it MUST now pass.

**Checkpoint**: Helper exists, is unit-tested for both branches, and is ready for the component to consume.

---

## Phase 3: User Story 1 - See the real corridor named in the header (Priority: P1) 🎯 MVP

**Goal**: With a snapshot present (`corridor_id = "C6-008"`, `direction = 1`), the header corridor selector reads exactly `C6-008 · Estación → barrio`; `[Corredor piloto]` appears nowhere; the `CORREDOR` label, inert button and `▾` chevron keep their layout.

**Independent Test**: Render `CorridorSelector` (or the header) with `{ corridorId: "C6-008", direction: 1 }` and assert the button reads `C6-008 · Estación → barrio`, that `[Corredor piloto]` is absent, and that the `CORREDOR` label + button + `▾` are present and in place (checks C1, C3, C4; SC-001, SC-003, SC-004).

### Tests for User Story 1 (write FIRST, ensure they FAIL before implementation) ⚠️

- [X] T004 [US1] Update `src/frontend/tests/shell/Header.test.tsx`: drop the assertion on the old copy `Estación → casa`, and assert the header renders `C6-008 · Estación → barrio` when passed `corridorId="C6-008"` / `direction={1}` (invariant I4, check C1). Use `renderWithQuery()` from `src/frontend/tests/test-utils.tsx` if rendering through the hook; MSW is configured in `src/frontend/tests/setup.ts`. Test MUST fail against current code.
- [X] T005 [P] [US1] Create `src/frontend/tests/shell/CorridorSelector.test.tsx` with the snapshot-present case: render `<CorridorSelector corridorId="C6-008" direction={1} />`, assert the button text is `C6-008 · Estación → barrio` (C1), assert `[Corredor piloto]` is NOT present (C3, I1), and assert the `CORREDOR` label, the `<button type="button">` and the `▾` chevron (`aria-hidden="true"`) are present and in place (C4, I2). Tests MUST fail (typed props not yet accepted).

### Implementation for User Story 1

- [X] T006 [US1] Give `src/frontend/src/components/shell/CorridorSelector.tsx` typed props `interface CorridorSelectorProps { corridorId: string; direction?: number }` and render `formatCorridorLabel(corridorId, direction)` (from `./corridorLabel`) as the button's text node. Keep the exact existing `CORREDOR` label, inert `<button type="button">` (no `onClick`, no handler, no state — I3/FR-006) and the `▾` chevron `<span aria-hidden="true">` and their classes (I2/FR-005). Remove the hardcoded `[Corredor piloto] · Estación → casa` so `[Corredor piloto]` appears nowhere (FR-004, SC-003, I1). Strict types, no `any`.
- [X] T007 [US1] Extend `HeaderProps` in `src/frontend/src/components/shell/Header.tsx` with `corridorId: string` and `direction?: number`, and forward both straight to `<CorridorSelector corridorId={corridorId} direction={direction} />`. Do not alter the existing `status` / `statusDetail` / `stale` props. Strict types, no `any`.
- [X] T008 [US1] In `src/frontend/src/App.tsx` pass `corridorId={snapshot?.corridor_id ?? corridorId}` and `direction={snapshot?.direction}` to `<Header>`, where `snapshot = fleet.lastSnapshot` (`CorridorNow | null`, already present) and `corridorId` is the constant imported from `src/frontend/src/mocks/fixtures.ts` (`"C6-008"`). No new `useCorridorNow` call, no `useEffect`, no mutation of query data (reads only). Run T004 and T005 — they MUST now pass.

**Checkpoint**: Snapshot-present header reads `C6-008 · Estación → barrio`, placeholder is gone, layout unchanged. US1 is independently demonstrable (MVP).

---

## Phase 4: User Story 2 - Show a sensible corridor name before data arrives (Priority: P2)

**Goal**: Before the first snapshot arrives (and on the "snapshot then no data" edge case), the selector reads exactly `C6-008` with no direction suffix and never shows `[Corredor piloto]`.

**Independent Test**: Render `CorridorSelector` with `corridorId="C6-008"` and no `direction` (or `App` with no snapshot) and assert the button reads exactly `C6-008`, with no `· Estación → barrio` suffix and no placeholder (check C2; SC-002, FR-003).

> The pre-snapshot behaviour is already carried by the helper (T003) and the `?? corridorId` fallback (T008). US2 adds the explicit test that locks this state. It touches `CorridorSelector.test.tsx` (same file as T005), so it runs after US1 to avoid a file conflict.

### Tests for User Story 2 (write FIRST, ensure they FAIL before — behaviour is new only if T003/T008 were skipped) ⚠️

- [X] T009 [US2] Add the no-snapshot case to `src/frontend/tests/shell/CorridorSelector.test.tsx`: render `<CorridorSelector corridorId="C6-008" />` (no `direction`), assert the button text is exactly `C6-008` with no direction suffix (C2, FR-003), and assert `[Corredor piloto]` is NOT present (C3, I1).

### Implementation for User Story 2

- [X] T010 [US2] Confirm no code change is required: the id-only branch is produced by `formatCorridorLabel` (T003, `direction` undefined → `corridorId`) and the `snapshot?.corridor_id ?? corridorId` / `snapshot?.direction` wiring in `App.tsx` (T008). If T009 fails, fix the helper/wiring rather than adding new branching. No new files.

**Checkpoint**: Both pre-snapshot (`C6-008`) and snapshot-present (`C6-008 · Estación → barrio`) states are verified; the header never reverts to `[Corredor piloto]`.

---

## Phase 5: Polish & Cross-Cutting Concerns (Gates)

**Purpose**: Prove the frontend quality gate stays green (SC-005) and the placeholder is gone repo-wide (SC-003).

- [X] T011 Repo-wide placeholder check (SC-003): from the repo root run `grep -rn "\[Corredor piloto\]" src/frontend/src` and confirm zero matches.
- [X] T012 Coverage gate (Gate 2): from `src/frontend/`, run `npx vitest run --coverage` and confirm lines/functions/branches/statements are all ≥ 80 % (thresholds in `src/frontend/vite.config.ts`).
- [X] T013 [P] Lint (Gate 1): from `src/frontend/`, run `npm run lint` (ESLint `--max-warnings 0`) and confirm 0 warnings/errors.
- [X] T014 [P] Type check: from `src/frontend/`, run `npx tsc --noEmit` (strict) and confirm 0 type errors and no `any`.
- [X] T015 Build (Gate 2): from `src/frontend/`, run `npm run build` (`tsc` + `vite build`) and confirm static assets emit successfully.
- [X] T016 Run the quickstart.md validation scenarios end to end (manual smoke: pre-snapshot `C6-008`, snapshot `C6-008 · Estación → barrio`, inert button, no `[Corredor piloto]`), per `specs/010-frontend-corridor-name/quickstart.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup. BLOCKS both user stories (the helper is shared).
- **User Story 1 (Phase 3)**: depends on Foundational (needs `corridorLabel.ts`).
- **User Story 2 (Phase 4)**: depends on US1 — it edits `CorridorSelector.test.tsx` (created in T005) and relies on the `App.tsx` wiring from T008; sequencing avoids same-file conflicts.
- **Polish (Phase 5)**: depends on all desired stories being complete.

### Within Each User Story

- Tests are written FIRST and MUST FAIL before implementation.
- Helper (Phase 2) before component; component (`CorridorSelector`) before `Header`; `Header` before `App` wiring.

### Parallel Opportunities

- T005 (`[P]`) can be written in parallel with T004 — different files (`CorridorSelector.test.tsx` vs `Header.test.tsx`).
- T013 and T014 (`[P]`) run in parallel — independent commands, no file writes.
- T002/T003 (helper + its test) must land before any component task; US2's T009 must not run in parallel with T005 (same file).

---

## Parallel Example: User Story 1 tests

```bash
# After the helper (T002/T003) is in place, write the two failing test files together:
Task: "T004 [US1] Update tests/shell/Header.test.tsx (new copy, drop 'Estación → casa')"
Task: "T005 [P] [US1] Create tests/shell/CorridorSelector.test.tsx (snapshot-present case)"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup (T001).
2. Phase 2: Foundational helper + its tests (T002–T003).
3. Phase 3: User Story 1 (T004–T008).
4. **STOP and VALIDATE**: header reads `C6-008 · Estación → barrio`, no `[Corredor piloto]`, layout intact. This is a shippable increment.

### Incremental Delivery

1. Setup + Foundational → helper ready.
2. US1 → snapshot-present label + placeholder removed → demo (MVP).
3. US2 → lock the pre-snapshot `C6-008` state → demo.
4. Polish → run all gates (lint, types, coverage > 80 %, build) + quickstart smoke.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- `[Story]` maps each task to its spec.md user story for traceability.
- Verify every test fails before implementing (Principle V, Test-First).
- Data-contract impact: **none** — reads existing `corridor_id` / `direction` from the unchanged `CorridorNow` read contract (data-contracts steering).
- Agents do not commit/push; review and commit yourself (AGENTS.md).
