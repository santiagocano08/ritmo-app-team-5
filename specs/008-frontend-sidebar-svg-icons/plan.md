# Implementation Plan: Sidebar SVG Icons

**Branch**: `008-frontend-sidebar-svg-icons` | **Date**: 2026-11-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-frontend-sidebar-svg-icons/spec.md`

## Summary

Replace the five text-glyph icons in the dispatcher console sidebar (brand logo
plus three navigation entries and the logout link) with inline stroke SVG icons
that render identically across machines and match the approved design. The
change is confined to `src/frontend/src/components/shell/Sidebar.tsx`: each glyph
`<span>` becomes an inline `<svg aria-hidden="true">` built from the shapes,
sizes and logo colour in §4.1–4.3 of the US-06 desktop style spec. Labels,
`href`s, `aria-current` logic and existing Tailwind classes are kept verbatim.
No new icon dependency, no backend/contract/type changes. The existing frontend
quality gate (ESLint, `tsc --noEmit`, Vitest coverage > 80 %, Vite build) stays
green, with new assertions proving each entry/logout carries exactly one
decorative `<svg>` and no glyph remains.

## Technical Context

**Language/Version**: TypeScript 5.6 (strict), React 19, JSX via `@vitejs/plugin-react`

**Primary Dependencies**: React 19.0.0, Vite 6, TailwindCSS 3.4; no new dependency added

**Storage**: N/A (presentational frontend change; no persisted data)

**Testing**: Vitest 4.1 + Testing Library (jsdom), coverage provider `v8`

**Target Platform**: Modern browsers (dispatcher console SPA served as static assets)

**Project Type**: Web application — frontend service (`src/frontend/`), Adaptive lane

**Performance Goals**: N/A for this change — no real-time path touched; icons are static inline SVG, no runtime cost regression

**Constraints**: Strict TypeScript (no `any`); ESLint `--max-warnings 0` with `@typescript-eslint/no-explicit-any` as error; Vitest coverage thresholds lines/functions/branches/statements ≥ 80 % enforced in `src/frontend/vite.config.ts`; inline SVG only (no icon library); SVG JSX attributes camelCased (`strokeWidth`, `strokeLinecap`, `strokeLinejoin`); icons `aria-hidden="true"`; labels/`href`/`aria-current`/Tailwind classes unchanged

**Scale/Scope**: Single component file changed; 5 icon positions (logo + 3 nav items + logout); 2 existing test files touched (assertions added)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.4.0. Turn 1 active, Adaptive lane (dispatcher web console). The
feature is a presentational frontend change with no data, contract, ingestion or
auth surface.

| Principle / Norm | Relevance | Status |
|---|---|---|
| I. Risk-First Order | No new Level-1 risk; no security/data-integrity surface touched | PASS (n/a) |
| II. Contract-First & Data Ownership | No data exchange, no schema, no generated types changed (FR-009) | PASS (n/a) |
| III. Isolated Ingestion & Deterministic Real Time | Frontend-only; real-time/ingestion path untouched | PASS (n/a) |
| IV. Human-in-the-Loop | No AI, no on-road action, no command surface | PASS (n/a) |
| V. Test-First & Automated Gates | Existing tests kept green; new decorative-icon assertions added; coverage > 80 % held | PASS |
| Gate 1 (SAST/contract) | ESLint runs; no Pydantic contract involved | PASS |
| Gate 2 (CI/coverage/SCA) | `frontend-ci`: ESLint, `tsc --noEmit`, Vitest > 80 %, Vite build; no new dependency so no SCA delta | PASS |
| Security (A01/A05 frontend) | No access-control decision in frontend; no SQL; no secrets | PASS (n/a) |
| Frontend-web steering | Match design tokens from `global-desing-styles.md` / US-06 spec; decorative `aria-hidden` icons; no new tokens invented | PASS |

**Turn scope (docs/turns-ritmo.md)**: Turn 1 — the console shows fleet state and
headway with no geographic map. This feature only restyles the existing sidebar
and introduces nothing deferred (no PostGIS, map, Redis, RBAC, etc.). In scope.

**Result**: PASS. No violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/008-frontend-sidebar-svg-icons/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created here)
```

No `contracts/` directory is generated: this feature exposes no new interface,
API, or data contract (FR-009). See research.md decision R4.

### Source Code (repository root)

```text
src/frontend/
├── src/
│   └── components/
│       └── shell/
│           └── Sidebar.tsx        # ONLY source file changed
├── tests/
│   ├── shell/
│   │   └── Sidebar.test.tsx       # add decorative-SVG + no-glyph assertions
│   └── a11y/
│       └── TextNotColor.test.tsx  # must stay green (aria-current unchanged)
├── vite.config.ts                 # coverage gate (unchanged)
└── package.json                   # lint/test/build scripts (unchanged)
```

**Structure Decision**: Web application, frontend service only. The change is a
surgical edit to the single presentational component
`src/frontend/src/components/shell/Sidebar.tsx`, with test assertions added in
the two existing test files under `src/frontend/tests/`. No files are created or
moved; no backend (`src/api/`, `src/data/`, `src/pulsoflota/`) path is touched.

## Complexity Tracking

> Not applicable — Constitution Check passed with no violations.
