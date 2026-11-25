---
description: "Task list for feature: Sidebar SVG Icons (US-11)"
---

# Tasks: Sidebar SVG Icons

**Input**: Design documents from `/specs/008-frontend-sidebar-svg-icons/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md

**Branch**: `feature/US-11-frontend-sidebar-svg-icons` · Turn 1 · Adaptive lane (dispatcher web console)

**Tests**: INCLUDED. The project overrides stock Spec Kit and defaults test tasks ON; the spec also
requires the accessibility check to keep passing (SC-003) and the frontend gate to stay green
(SC-005). No opt-out statement exists in spec.md or the constitution. Test assertions are written and
run (and must fail against the current glyph markup) before the implementation edit.

**Organization**: Tasks are grouped by user story so each story is independently verifiable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2)
- Exact file paths are included in every task

## Path Conventions

Web application, frontend service only. All paths are relative to the repository root
`/Users/santiagocano/Documents/EAFIT_projects/RITMO/`. Working directory for all `npm` commands is
`src/frontend/`. No backend path (`src/api/`, `src/data/`, `src/pulsoflota/`) is touched.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the toolchain and baseline are green before changing anything. No new project
scaffolding is created (surgical edit to an existing component).

- [X] T001 Verify frontend dependencies are installed with `npm ci` in `src/frontend/` (confirm no new dependency is added — FR-009); do not modify `src/frontend/package.json` or `src/frontend/package-lock.json`.
- [X] T002 Establish the green baseline by running `npm run lint`, `npm run build`, and `npm run test:coverage` from `src/frontend/` and recording that all pass (ESLint `--max-warnings 0`, `tsc --noEmit` strict, Vitest coverage > 80 %, Vite build).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Read and confirm the authoritative icon values and the current component shape that both
stories build on.

**⚠️ CRITICAL**: Complete before touching test or source files.

- [X] T003 Confirm the authoritative icon specs from `specs/008-frontend-sidebar-svg-icons/research.md` (R2) and §4.1–4.3 of `tickets/US-06-frontend-home/US-06-escritorio-estilos.md`: logo pulse `path d="M2 12h4l3-8 4 16 3-8h6"` 26×26 `stroke="#FBBF24"`; menu items 20×20 `stroke="currentColor"` (*Central en vivo*=pulse, *Alertas*=bell, *Plan del día*=calendar); *Cerrar sesión*=exit 18×18 `stroke="currentColor"`; all `strokeWidth={2}`, `strokeLinecap="round"`, `strokeLinejoin="round"`, `fill="none"`, `aria-hidden="true"`.
- [X] T004 Read the current `NavItem` shape and the five glyphs (`⬳ ◉ ✚ ▦ ⇥`) in `src/frontend/src/components/shell/Sidebar.tsx` and confirm which values are preserved verbatim: `section`, `label`, `href`, `aria-current` logic and existing Tailwind classes (FR-007, FR-008; data-model.md `NavItem` table).

**Checkpoint**: Icon values and preserved fields confirmed — story work can begin.

---

## Phase 3: User Story 1 - Consistent sidebar icons across machines (Priority: P1) 🎯 MVP

**Goal**: Replace all five sidebar text glyphs (logo + three nav items + logout) with inline stroke
SVGs that render identically across machines and match the design reference.

**Independent Test**: Render the sidebar; confirm the logo shows the pulse SVG in `#FBBF24` at 26×26,
each of the three nav entries and the logout link shows exactly one `<svg>`, and no glyph from
`⬳ ◉ ✚ ▦ ⇥` remains anywhere in the sidebar (`container.textContent`).

### Tests for User Story 1 ⚠️

> Write these assertions FIRST and run them — they MUST FAIL against the current glyph markup before T008.

- [X] T005 [P] [US1] In `src/frontend/tests/shell/Sidebar.test.tsx`, add an assertion (for `activeSection="live_central"`) that each of the three nav links (*Central en vivo*, *Alertas*, *Plan del día*) and the *Cerrar sesión* link contains exactly one `<svg>` element (FR-002, FR-003; SC-001).
- [X] T006 [P] [US1] In `src/frontend/tests/shell/Sidebar.test.tsx`, add an assertion that the rendered sidebar contains no residual glyph — `container.textContent` excludes each of `⬳`, `◉`, `✚`, `▦`, `⇥` (FR-006; SC-001), and that the logo renders one `<svg>` (pulse) (FR-001).

### Implementation for User Story 1

- [X] T007 [US1] In `src/frontend/src/components/shell/Sidebar.tsx`, change the `NavItem.icon` field type from `string` to `ReactNode` (imported from `react`), with no `any` (strict TS; research.md R3, data-model.md `NavItem` table).
- [X] T008 [US1] In `src/frontend/src/components/shell/Sidebar.tsx`, replace the five glyph `<span>`s with inline `<svg>` icons: logo pulse `path d="M2 12h4l3-8 4 16 3-8h6"` 26×26 `stroke="#FBBF24"`; `NAV_ITEMS` icons 20×20 `stroke="currentColor"` (pulse / bell / calendar in that order); *Cerrar sesión* exit 18×18 `stroke="currentColor"`; every icon `fill="none"`, `strokeWidth={2}`, `strokeLinecap="round"`, `strokeLinejoin="round"`, `aria-hidden="true"`; keep each `label`, `href`, `aria-current` logic and existing Tailwind classes verbatim (FR-001–FR-004, FR-007; depends on T007).
- [X] T009 [US1] Run `npm run test:coverage` from `src/frontend/` and confirm the T005/T006 assertions now pass and coverage stays > 80 % (SC-005; research.md R5 — inline markup keeps the file covered).

**Checkpoint**: Sidebar renders six inline SVG icons with zero residual glyphs — US1 verifiable independently.

---

## Phase 4: User Story 2 - Accessible, label-preserving navigation (Priority: P2)

**Goal**: Guarantee the new icons are decorative (ignored by assistive technology) and every visible
label and the active-entry indication are unchanged.

**Independent Test**: Run the accessibility check; confirm it passes, every `<svg>` is
`aria-hidden="true"`, the labels read exactly as before, and the active entry keeps
`aria-current="page"`.

### Tests for User Story 2 ⚠️

> Write/confirm these assertions and run them before the decorative-attribute verification in T012.

- [X] T010 [P] [US2] In `src/frontend/tests/shell/Sidebar.test.tsx`, strengthen the nav/logout `<svg>` assertions so each matched `<svg>` carries `aria-hidden="true"` (FR-005; SC-004), and confirm the existing label assertions (*Central en vivo*, *Alertas*, *Plan del día*, *Cerrar sesión*) remain unchanged (FR-007).
- [X] T011 [P] [US2] Confirm `src/frontend/tests/a11y/TextNotColor.test.tsx` is left unchanged and still asserts `aria-current="page"` on the active section (FR-008; SC-003); add no glyph-specific coupling that the icon swap would break.

### Implementation for User Story 2

- [X] T012 [US2] In `src/frontend/src/components/shell/Sidebar.tsx`, verify every icon added in T008 (logo, three nav items, logout) carries `aria-hidden="true"` and that no label text, `href`, or `aria-current` logic was altered by the icon swap (FR-005, FR-007, FR-008).
- [X] T013 [US2] Run `npm run test:coverage` from `src/frontend/` and confirm `Sidebar.test.tsx` and `TextNotColor.test.tsx` both pass (decorative icons + unchanged labels + active indication intact; SC-003, SC-004).

**Checkpoint**: Icons decorative, labels and active state preserved — US1 and US2 both verifiable.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Final gate verification across the whole frontend change.

- [X] T014 Run `npm run lint` from `src/frontend/` and confirm 0 warnings/errors (ESLint `--max-warnings 0`, `no-explicit-any` = error) — FR-009, SC-005.
- [X] T015 Run `npm run build` from `src/frontend/` and confirm `tsc --noEmit` (strict) and `vite build` both succeed (SC-005).
- [X] T016 Execute the full `specs/008-frontend-sidebar-svg-icons/quickstart.md` validation: all automated checks green and manual scenarios 1–5 confirmed (consistent icons, cross-machine consistency, active state intact, decorative to AT, labels unchanged).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS both stories.
- **User Story 1 (Phase 3)**: Depends on Foundational. Delivers the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational; builds on the icon markup produced by US1 (T008). Independently verifiable, but in practice sequential because both stories edit the same file.
- **Polish (Phase 5)**: Depends on US1 and US2 being complete.

### User Story Dependencies

- **US1 (P1)**: No dependency on other stories.
- **US2 (P2)**: Verifies attributes on the icons US1 introduces. The two stories share one source file (`Sidebar.tsx`) and one primary test file (`Sidebar.test.tsx`), so they are not editable in true parallel.

### Within Each User Story

- Test assertions are written and run (MUST FAIL for US1) before the source edit.
- `NavItem.icon` retype (T007) precedes the glyph→SVG swap (T008).
- Verification run (T009 / T013) closes each story.

### Parallel Opportunities

- Setup T001 and the baseline capture T002 are sequential (baseline needs installed deps).
- Within US1, T005 and T006 are both assertions in `Sidebar.test.tsx` — marked [P] as logically independent additions, but if one editor touches the file they are applied together.
- Within US2, T010 (strengthen `Sidebar.test.tsx`) and T011 (confirm `TextNotColor.test.tsx`) touch different files → genuinely parallelizable.
- Across stories: limited. Both edit `Sidebar.tsx`; run US1 then US2.

---

## Parallel Example: User Story 2

```bash
# Different files → can run in parallel:
Task T010: "Strengthen aria-hidden assertions in src/frontend/tests/shell/Sidebar.test.tsx"
Task T011: "Confirm aria-current assertion unchanged in src/frontend/tests/a11y/TextNotColor.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1 Setup → 2. Phase 2 Foundational → 3. Phase 3 US1.
4. **STOP and VALIDATE**: six inline SVG icons render, no residual glyph, coverage > 80 %.
5. This is a shippable MVP: the visual defect (font-dependent glyphs) is resolved.

### Incremental Delivery

1. Setup + Foundational → ready.
2. US1 → inline SVG icons replace glyphs → validate → demo (MVP).
3. US2 → confirm decorative + labels/active-state preserved → validate.
4. Polish → full gate (lint + build + quickstart).

### Notes

- [P] = different files, no dependency on incomplete work.
- Both stories are a single surgical edit to `Sidebar.tsx` plus assertions in two existing test files; no files are created or moved (plan.md Structure Decision).
- Verify the US1 assertions fail against the current glyph markup before T008, per Test-First (Principle V).
- Agents do not commit/push; review and commit yourself (AGENTS.md).
