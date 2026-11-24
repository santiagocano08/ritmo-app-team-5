# Tasks: Tab Title Shows Data State

**Input**: `/specs/008-tab-title-data-state/` (plan.md, spec.md, research.md, data-model.md, quickstart.md)

**Tests**: Included (FR-004; spec and constitution do not opt out). Write them first and confirm they FAIL before implementation.

**Format**: `- [ ] T### [P?] [US?] Description with file path`

## Phase 1: Setup

No new project structure or dependencies are needed (frontend only, existing stack).

- [X] T001 Confirm `src/frontend/src/hooks/`, `src/frontend/tests/hooks/` and `src/frontend/src/components/shell/StatusBadge.tsx` exist, and that `src/frontend/index.html` is left untouched (FR-005)

## Phase 2: Foundational

No blocking prerequisites. No contract impact (`docs/data-contract.md` and `contracts/` untouched).

## Phase 3: User Story 1 - See the data state from the tab title (Priority: P1) 🎯 MVP

**Goal**: `document.title` shows `PulsoFlota · En vivo`, `PulsoFlota · Estimado` or `PulsoFlota · Sin datos`, matching the header badge.

**Independent Test**: Render with `live`, `estimated`, `no_data` and an unrecognized status in turn and read `document.title`.

### Tests for User Story 1 (write first, must FAIL)

- [X] T002 [US1] Create `src/frontend/tests/hooks/useTabTitle.test.tsx` (Vitest + Testing Library, `renderHook`): `live` → `PulsoFlota · En vivo`; `estimated` → `PulsoFlota · Estimado`; `no_data` → `PulsoFlota · Sin datos`; unrecognized value (cast, e.g. `'bogus' as never`) → `PulsoFlota · Sin datos`; `rerender` with a new status changes `document.title` without reload (FR-002)

### Implementation for User Story 1

- [X] T003 [US1] Export the existing `LABELS` map as `STATUS_LABELS` in `src/frontend/src/components/shell/StatusBadge.tsx` (update its internal usages; behavior unchanged)
- [X] T004 [US1] Create `src/frontend/src/hooks/useTabTitle.ts` exporting `tabTitle(status)` (returns `` `PulsoFlota · ${STATUS_LABELS[status]}` ``, falling back to `STATUS_LABELS.no_data` when the value is not a key of `STATUS_LABELS`) and `useTabTitle(status: SourceStatusValue)` that assigns `document.title` in a `useEffect` (depends on T003)
- [X] T005 [US1] Call `useTabTitle(status)` in `src/frontend/src/App.tsx` using the same resolved `status` that feeds the header badge (`no_data` before the first response) (depends on T004)

**Checkpoint**: Tab title matches the badge in all three states.

## Phase 4: Polish

- [X] T006 Run the frontend checks in the Node container without `-e TZ` and fix any failure: `docker run --rm -v "$PWD":/repo -w /repo/src/frontend node:22.11.0-alpine sh -c './node_modules/.bin/vitest run && ./node_modules/.bin/eslint src tests --ext .ts,.tsx --max-warnings 0 && ./node_modules/.bin/tsc --noEmit'`; confirm existing `StatusBadge` tests pass, coverage stays above 80 % and `src/frontend/index.html` is unchanged

## Dependencies & Execution Order

- T001 → T002 → T003 → T004 → T005 → T006.
- T002 is written first and must fail (the hook does not exist yet). T003 and T002 touch different files and may be done in either order, but T004 needs T003.
- No parallel tasks: the feature is 1 hook, 1 export and 1 call site.

## Implementation Strategy

MVP is User Story 1, the only story. Write the failing test, export the labels, add the hook, wire it into `App`, then run the container checks. Do not commit or push.
