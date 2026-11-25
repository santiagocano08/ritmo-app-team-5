# Implementation Plan: Sidebar Section Switching with Placeholder

**Branch**: `feature/US-10` (ticket names `feature/US-10-frontend-sidebar-sections`) | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/008-sidebar-section-switching/spec.md`
(ticket `tickets/US-10-frontend-sidebar-sections/`, GitHub issue #52).

## Summary

The dispatcher console sidebar shows three sections, but only *Central en vivo* works. This
story makes *Alertas* and *Plan del día* selectable: the clicked item gets the active style and
`aria-current="page"`, the `h1` shows its label, and the main area shows the style-spec §7
placeholder. Returning to *Central en vivo* shows the fleet view, which never stopped polling.

Approach: one `useState<SectionId>` in `App.tsx`; `Sidebar` becomes a controlled component
(`activeSection` + `onSelect`); a shared `SECTIONS` list feeds both the sidebar and the title;
a new presentational `SectionPlaceholder`. Data hooks stay mounted in `App`, so polling, the
header badge and the banner work in every section. Frontend only; no router, backend, contract
or generated-type change.

## Technical Context

**Language/Version**: TypeScript 5.6 (strict), React 19.0

**Primary Dependencies**: React 19, TanStack Query 5.59 (existing polling hooks), Tailwind CSS 3.4 (existing tokens). No new dependencies.

**Storage**: N/A (in-memory UI state only)

**Testing**: Vitest 4.1 + Testing Library 16 + `@testing-library/user-event` 14 + MSW 2.6 (all present); coverage v8, 80 % thresholds in `vite.config.ts`

**Target Platform**: Modern desktop browsers; static build served by the `frontend` Nginx container

**Project Type**: Web application (frontend SPA of a frontend/backend split); this story touches the frontend only

**Performance Goals**: Section switch is a synchronous re-render (no network); live data refresh keeps its 5 s interval (SC-003)

**Constraints**: No router library (FR-009); no backend/contract/generated-type change (FR-010); existing Tailwind tokens only; ticket timebox ≈ one or two components plus tests

**Scale/Scope**: 3 sections, 1 role (*Despachador*); ~4 source files and ~3 test files

No `NEEDS CLARIFICATION` items. Design choices are recorded in [research.md](./research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Active turn: **Turn 1 — Data and minimal loop** (`docs/turns-ritmo.md` §3). Lane: Adaptive.

| Principle / norm | Applies? | Assessment | Result |
|------------------|----------|------------|--------|
| I. Risk-First Order | Yes | Adaptive-lane UI story in Turn 1. Turn 1's Level 1 risk (data integrity) is addressed by the delivered disciplined-lane stories (contracts, ingestion, D1 faults). This story adds no data path and does not affect that mitigation. The ticket assigns it to the active turn. | PASS |
| II. Contract-First | No data exchange changes | No REST/WebSocket payload, `contracts/read/*` schema or generated type changes (FR-010). The UI component interfaces are documented in `contracts/ui-sections.md` before implementation anyway. | PASS (N/A) |
| III. Isolated Ingestion / deterministic real time | No | Frontend-only change; ingestion container and critical path untouched. | PASS (N/A) |
| IV. Human Gate | No | No recommendation or regulation action involved. | PASS (N/A) |
| V. Test-First and Automated Gates | Yes | Tests are specified per contract item (S1–S6, P1–P2, A1–A6) and written before the code in the task order; `frontend-ci` (ESLint, `tsc --noEmit`, Vitest coverage > 80 %, Vite build) must stay green. | PASS |
| Gate 1 (Turn 1: schema validation only) | No schemas changed | ESLint still runs in `frontend-ci`. | PASS |
| Gate 2 (tests + coverage > 80 %) | Yes | Covered by Principle V row. | PASS |
| Gate 4 (dispatcher approval) | No | No recommendation flow. | PASS (N/A) |
| Security "zero-cost" baseline | Marginal | No new inputs, endpoints or secrets. Section switching is cosmetic; the frontend still decides no access control. | PASS |
| Coding standards | Yes | No `useEffect` fetching, no `any`, small components, immutable `readonly` section list, no new abstractions beyond one data module. | PASS |

**Result: PASS. No violations; Complexity Tracking is empty.**

### Evolution (deferred, not blocking in Turn 1)

- Role-based menus and the *Gestor* variant (*Indicadores de calidad*): Turn 2, RBAC. The
  `SECTIONS` list is the natural place to filter by role later; the backend must still enforce
  access.
- Real content for *Alertas* and *Plan del día*: later stories.
- Line icons for the sidebar items: US-11.
- Deep-linking / reload persistence of the section (hash or router): not required now; can be
  layered on `App` state without changing the `Sidebar` contract.
- JS SCA / SAST hardening of `frontend-ci` (Turn 2) and the frontend image scan (Trivy): not
  affected by this story.

## Project Structure

### Documentation (this feature)

```text
specs/008-sidebar-section-switching/
├── plan.md              # This file
├── research.md          # Phase 0: decisions R1–R7
├── data-model.md        # Phase 1: Section, Active section, transitions
├── quickstart.md        # Phase 1: validation guide
├── contracts/
│   └── ui-sections.md   # Phase 1: Sidebar / SectionPlaceholder / App UI contract
├── checklists/
│   └── requirements.md  # From /speckit.specify
└── tasks.md             # Phase 2 (/speckit.tasks, not created here)
```

### Source Code (repository root)

```text
src/frontend/
├── src/
│   ├── App.tsx                                  # MODIFY: useState<SectionId>, h1 from SECTIONS, branch <main> content
│   └── components/
│       ├── shell/
│       │   ├── sections.ts                      # NEW: SectionId type + readonly SECTIONS list
│       │   └── Sidebar.tsx                      # MODIFY: controlled (activeSection, onSelect), maps SECTIONS, preventDefault
│       └── status/
│           └── SectionPlaceholder.tsx           # NEW: style spec §7 placeholder
└── tests/
    ├── shell/
    │   ├── Sidebar.test.tsx                     # MODIFY: pass onSelect; add S2–S5 cases
    │   └── SectionSwitching.test.tsx            # NEW: App integration (A1–A6, US1/US2, SC-001, SC-003)
    └── status/
        └── SectionPlaceholder.test.tsx          # NEW: P1–P2
```

**Structure Decision**: Current Turn-1 tree, `src/frontend/` only. New files follow existing
folders (`components/shell`, `components/status`, mirrored under `tests/`). Untouched: hooks,
`api/`, `mocks/`, backend (`src/api`, `src/data`, `src/pulsoflota`), `contracts/`.

## Phase 0 — Research (done)

See [research.md](./research.md). Key decisions:

- **R1** Local `useState` in `App`; no router, no hash listener, no context.
- **R2** Keep `<a href>` links (style spec §10, native keyboard activation); `preventDefault`
  so the URL never shows a hash a reload would ignore.
- **R3** Data hooks stay unconditional in `App`, so polling, badge and banner keep working in
  every section.
- **R4** `StaleIndicator` / `EmptyState` belong to the live section only.
- **R5** One `SECTIONS` list feeds sidebar and `h1` (SC-001).
- **R6** `SectionPlaceholder` with existing tokens; no shared frame abstraction with `EmptyState`.
- **R7** Unit tests for `Sidebar` and `SectionPlaceholder`; one MSW-backed `App` integration test.

## Phase 1 — Design (done)

- [data-model.md](./data-model.md): `Section` (static), `activeSection` (UI state), transitions.
- [contracts/ui-sections.md](./contracts/ui-sections.md): `SECTIONS`, `Sidebar` props and
  behaviors S1–S6, `SectionPlaceholder` P1–P2, `App` composition A1–A6.
- [quickstart.md](./quickstart.md): `frontend-ci` commands, mock-mode manual checks, visual review.

### Constitution Check (post-design)

Re-evaluated against the Phase 1 artifacts: no backend, data contract, ingestion or
recommendation surface was introduced; one new data module (`sections.ts`) and one
presentational component. All rows above remain **PASS**.

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| `onSelect` becomes a required `Sidebar` prop | Existing `Sidebar.test.tsx` fails to type-check | Update both renders in the same task; `App` is the only other caller. |
| Integration test for continued polling is slow or flaky (5 s interval) | CI time / intermittent failure | Use the existing pattern from `StaleRecovery.test.tsx` (real timers, `waitFor` timeout ≈ 7 s, per-test timeout 20 s) and an MSW `request:start` counter instead of asserting on rendered values. |
| Coverage drop from the new branch in `App` | Gate 2 fails | Integration test exercises both branches; placeholder has its own unit test. |
| Branch name differs from ticket (`feature/US-10` vs `feature/US-10-frontend-sidebar-sections`) and setup script reports `008-sidebar-section-switching` | Traceability only | No action in this plan; the user may rename before opening the PR. |

## Complexity Tracking

No violations to justify.
