# Tasks: Tab Title Data State

**Input**: `/specs/008-tab-title-data-state/` (plan.md, spec.md, research.md, data-model.md, quickstart.md)

**Tests**: Included (default ON; neither spec nor constitution opts out). Tests MUST be written and MUST FAIL before implementation.

**Format**: `- [ ] T### [P?] [US?] Description with file path`

**Path base**: `src/frontend/` (Vite SPA, Vitest + Testing Library, jsdom).

**Runtime note**: Node is not on the host. Run frontend commands in the Node container:
`docker run --rm -v "$PWD":/repo -w /repo/src/frontend node:22.11.0-alpine sh -c './node_modules/.bin/vitest run && ./node_modules/.bin/eslint src tests --ext .ts,.tsx --max-warnings 0 && ./node_modules/.bin/tsc --noEmit'`
Run without `-e TZ`; the feature formats no dates, so results are zone-independent (UTC).

## Phase 1: Setup

No new dependencies or structure. Nothing to do.

## Phase 2: Foundational

- [X] T001 Export the badge label table: change `STATUS_LABELS` to a named export (`export const STATUS_LABELS`) in `src/frontend/src/components/shell/StatusBadge.tsx`, keeping the labels `En vivo`, `Estimado`, `Sin datos` for `live`, `estimated`, `no_data` unchanged. Badge rendering must not change.

**Checkpoint**: Label table is importable by the hook.

## Phase 3: User Story 1 - See the data state from the browser tab (Priority: P1) 🎯 MVP

**Goal**: `document.title` equals `PulsoFlota · <badge label>` and follows the header badge state.

**Independent Test**: Render the console (or hook) with `live`, `estimated`, `no_data` in turn; the title is `PulsoFlota · En vivo`, `PulsoFlota · Estimado`, `PulsoFlota · Sin datos`, matching the badge.

### Tests for User Story 1 (write first, must FAIL)

- [X] T002 [P] [US1] Hook test in `src/frontend/tests/hooks/useDocumentTitle.test.tsx` using `renderHook`: for each of `live`, `estimated`, `no_data`, `document.title` is `PulsoFlota · ` + `STATUS_LABELS[status]` (FR-001..003); after `rerender` with a new status the title updates without remount (FR-005).
- [X] T003 [P] [US1] App-level test in `src/frontend/tests/shell/App.title.test.tsx` (reuse helpers in `src/frontend/tests/test-utils.tsx`): with no response yet the title is `PulsoFlota · Sin datos` (FR-003); after a snapshot with each source status the title equals the text shown by the header `StatusBadge` (FR-004, SC-001, SC-003).

### Implementation for User Story 1

- [X] T004 [US1] Create `src/frontend/src/hooks/useDocumentTitle.ts`: `useDocumentTitle(status: SourceStatusValue): void`, a `useEffect` keyed on `status` that sets `document.title = \`PulsoFlota · ${STATUS_LABELS[status]}\`` (import `STATUS_LABELS` from `../components/shell/StatusBadge`). Strict types, no `any`, no comments.
- [X] T005 [US1] Call `useDocumentTitle(status)` in `src/frontend/src/App.tsx` with the same `status` value (from `resolveSourceStatus`) passed to the header `StatusBadge`. Leave the static title in `src/frontend/index.html` as `PulsoFlota · Central en vivo` (FR-006).
- [X] T006 [US1] Run the Node-container command above (vitest, eslint `--max-warnings 0`, `tsc --noEmit`) and confirm T002/T003 pass and coverage of the new hook is > 80 %.

**Checkpoint**: User Story 1 works and is independently testable.

## Phase 4: Polish

- [X] T007 Walk through `specs/008-tab-title-data-state/quickstart.md` and confirm each step matches; confirm `git diff` touches only `StatusBadge.tsx`, `App.tsx`, the new hook and the two test files (no contract or backend change).

## Dependencies & Execution Order

- T001 → T004 → T005 → T006 → T007.
- T002 and T003 are [P] (different files) and need only T001's export to compile; write them before T004 and confirm they fail.

## Parallel Example

```text
T002 Hook test in tests/hooks/useDocumentTitle.test.tsx
T003 App test in tests/shell/App.title.test.tsx
```

## Implementation Strategy

MVP is User Story 1, the only story: T001, tests (fail), T004–T005, then T006 verify. Stop and validate; no later increments.
