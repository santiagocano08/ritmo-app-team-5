# Implementation Plan: Real Corridor Name in Header

**Branch**: `feature/US-12-frontend-corridor-name` | **Date**: 2026-11-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-frontend-corridor-name/spec.md`

**Note**: This file is produced by the `/speckit.plan` command. It stops after Phase 1 design; `/speckit.tasks` generates `tasks.md`.

## Summary

Replace the hardcoded mockup text `[Corredor piloto] · Estación → casa` in the header's corridor selector with the real corridor name derived from live data. When a snapshot is present (`corridor_id = C6-008`, `direction = 1`) the selector reads `C6-008 · Estación → barrio`; before the first snapshot arrives it reads the configured id `C6-008` alone. The `CORREDOR` label, the inert button and the chevron (`▾`) layout are unchanged, and `[Corredor piloto]` no longer appears anywhere.

Technical approach (frontend only, Turn 1, Adaptive lane, surgical edits): add a small pure formatting helper colocated in `src/frontend/src/components/shell/` (mirroring the existing `statusDetail.ts` precedent), give `CorridorSelector` a typed prop, thread `snapshot?.corridor_id ?? corridorId` and `snapshot?.direction` from `App.tsx` through `Header.tsx` (extending `HeaderProps`). Data already flows through the `useCorridorNow` TanStack Query hook in the composition root — no new fetching, no `useEffect`, no mutation of query data.

## Technical Context

**Language/Version**: TypeScript 5.x (strict mode, no `any`), React 19, Node for build tooling only.

**Primary Dependencies**: React 19, Vite, Tailwind CSS, `@tanstack/react-query` (already wired via `useCorridorNow`). Tests: Vitest + `@testing-library/react` + jsdom; MSW configured in `tests/setup.ts`.

**Storage**: N/A (frontend-only; no persistence, no contract or generated-type changes).

**Testing**: Vitest + Testing Library. `renderWithQuery()` from `tests/test-utils.tsx` wraps TanStack Query. Coverage thresholds enforced in `src/frontend/vite.config.ts` (lines/functions/branches/statements ≥ 80 %).

**Target Platform**: Browser SPA (`pulsoflota-frontend`), built to static assets.

**Project Type**: Web application — frontend change only. Backend (`src/api/`, `src/data/`, `src/pulsoflota/`) is untouched.

**Performance Goals**: N/A for this feature (no real-time path, no ingestion). Rendering a label is not on any latency SLO.

**Constraints**: Strict TypeScript, ESLint `--max-warnings 0`, `tsc --noEmit` clean, Vitest coverage > 80 %, Vite build green. No changes to `contracts/`, `src/frontend/src/api/generated/**`, or any backend code. No new runtime dependency. The selector button stays inert (no `onClick`). `[Corredor piloto]` must occur zero times after the change.

**Scale/Scope**: One configured corridor (`C6-008`), one direction (`1` → `Estación → barrio`). Three files changed + one new helper + tests. Corridor switching is explicitly out of scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Active turn: **Turn 1 — Data and minimal loop** (`docs/turns-ritmo.md`). This story is a frontend presentation change in the **Adaptive lane**.

| Principle / norm | Applies? | Assessment |
|---|---|---|
| I. Risk-First Order | Yes | No Level 1 (security / data integrity) risk is introduced or left unmitigated. Pure presentation change over data already fetched. PASS. |
| II. Contract-First & Data Ownership | Yes | Consumes the existing `CorridorNow` read contract (`contracts/read/`, generated type `corridor-now.ts`). `direction: 1` and `corridor_id` are read as the contract defines them. No contract or schema change, no new persisted model. PASS. |
| III. Isolated Ingestion & Deterministic Real Time | N/A | No ingestion or real-time-path code touched; data already arrives via the existing hook. PASS (not engaged). |
| IV. Human-in-the-Loop | Yes | Button stays inert; no regulation action, no command to the fleet, no new autonomy. PASS. |
| V. Test-First & Automated Gates | Yes | Plan requires updating the existing Header test and adding `CorridorSelector` + helper unit tests for both states and the absence of `[Corredor piloto]`; coverage stays > 80 %. Gate 1 (ESLint) + Gate 2 (Vitest coverage, `tsc`, build) via `frontend-ci`. PASS once tests are written in the Build phase. |

Frontend-web steering: types come from the generated OpenAPI/contract type (satisfied — reading `CorridorNow`), the frontend never decides access control (satisfied — inert label), no direct DB/Redis access (satisfied). Data-contracts steering: the data-contract-impact review is **"no contract impact"** — the feature only reads existing published fields (`corridor_id`, `direction`) and changes no silver/gold table, metric, rule, decision model, command event, reference data, or simulator output.

**Result: PASS. No violations. Complexity Tracking not required.**

### Turn-scope note (evolution, not in scope)

Direction values other than `1`, corridor switching, a corridor dropdown/menu, and multi-corridor display are deferred (Turn 1 carries a single corridor and `direction: 1` only, per `docs/turns-ritmo.md` and the generated type JSDoc). The helper maps `direction === 1` to `Estación → barrio`; any other/absent direction yields the id-only label, which is the correct Turn-1 behaviour and leaves room for later directions without speculative code.

## Project Structure

### Documentation (this feature)

```text
specs/010-frontend-corridor-name/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (UI/display contract for this feature)
│   └── corridor-label.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
src/frontend/
├── src/
│   ├── App.tsx                                 # CHANGE: pass corridorId/direction into <Header>
│   ├── components/
│   │   └── shell/
│   │       ├── Header.tsx                       # CHANGE: extend HeaderProps, forward props to CorridorSelector
│   │       ├── CorridorSelector.tsx             # CHANGE: typed props, render formatted label (keep layout)
│   │       ├── corridorLabel.ts                 # NEW: pure helper formatCorridorLabel(corridorId, direction?)
│   │       └── statusDetail.ts                  # (precedent for a colocated pure shell helper)
│   └── mocks/fixtures.ts                         # unchanged (source of `corridorId = "C6-008"`)
└── tests/
    ├── shell/
    │   ├── Header.test.tsx                       # CHANGE: assert new copy, drop "Estación → casa"
    │   └── CorridorSelector.test.tsx             # NEW: both states + absence of "[Corredor piloto]"
    ├── shell/corridorLabel.test.ts               # NEW (optional): direct unit tests for the helper
    └── test-utils.tsx                            # unchanged (renderWithQuery)
```

**Structure Decision**: Web application, frontend-only change under `src/frontend/`. The single pure formatting concern is isolated into a colocated helper (`corridorLabel.ts`) so it is unit-testable without rendering and keeps `CorridorSelector` focused on presentation (SRP, matching the existing `statusDetail.ts` pattern in the same folder). Data continues to flow from the composition root (`App.tsx`) down through `Header.tsx`; components receive plain props and do no fetching.

## Complexity Tracking

> Not required — Constitution Check passed with no violations.
