# Implementation Plan: Dispatcher Console — Fleet State and Headway

**Branch**: `005-dispatcher-console` | **Date**: 2026-11-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-dispatcher-console/spec.md`

## Summary

US-06 (Turn 1) delivers the first `src/frontend/` code: a read-only React 19 + TypeScript + Vite + Tailwind single-page app that shows corridor C6-008's live fleet state. It renders the fleet ordered leader-first with per-bus state, position, actual-vs-planned headway and data quality; a corridor summary (in service, bunched, gaps); an overall source-status indicator with an explanatory banner for `estimated`/`no_data`; and the dispatcher navigation shell (sidebar, corridor selector, clock, data-state badge, user identity). The view refreshes by polling the backend read API (US-05, feature 004) every ~5 s, and degrades gracefully to a stale-data indicator when a refresh fails.

Technical approach: consume the already-approved read contracts (`contracts/read/corridor_now.schema.json` and `source_status.schema.json`, both v1.0.0) as the single source of truth. Generate TypeScript types from those JSON Schemas rather than hand-writing them (Contract-First, Principle II). Fetch strictly through a generated/typed API client wrapped in TanStack Query with a 5 s `refetchInterval`; no `useEffect` fetching, no business logic in the frontend (states, headways and quality all arrive computed from the backend). Before/without a running backend, the component tests and a mock mode run off the fixtures in `contracts/read/fixtures/`.

The visual and interaction design follows the authoritative desktop styling reference in the ticket folder: `tickets/US-06-frontend-home/US-06-escritorio-estilos.md` and the mockup `tickets/US-06-frontend-home/mockup-base-escritorio.png`. That reference specifies the US-03 navigation shell (dark-navy 248 px sidebar, 68 px white header with corridor selector + status badge + clock, user footer, optional alert banner) down to exact colors, typography (Inter + Space Grotesk), spacing and ARIA roles. In the mockup the main area is a dashed placeholder labelled "content defined in later stories" — US-06 is that later story: it fills the placeholder region with the fleet list, corridor summary and per-bus rows, styled consistently with the reference's palette and type scale (the reference styles the shell, not the fleet content, so the fleet components extend the same design language). The shell matches the reference exactly; new fleet components reuse its tokens.

## Technical Context

**Language/Version**: TypeScript 5.x (strict), React 19. Node 20 LTS for tooling. (Backend stays Python 3.12+; this feature adds no Python.)

**Primary Dependencies**: Vite, React 19, Tailwind CSS, TanStack Query (server-state + polling), a generated OpenAPI/JSON-Schema typed client (`openapi-typescript`/`openapi-fetch` or equivalent). Fonts: Inter (400/500/600/700) and Space Grotesk (500/700) per the styling reference. Testing: Vitest + Testing Library; `msw` (or fixture-backed fetch) for mock mode.

**Visual reference (authoritative)**: `tickets/US-06-frontend-home/US-06-escritorio-estilos.md` + `tickets/US-06-frontend-home/mockup-base-escritorio.png`. Desktop artboard 1280×800, fixed-width layout. Tailwind theme tokens derive from the reference palette (below).

**Storage**: None in the frontend. The SPA never touches PostgreSQL/Redis; all state comes from the backend read API over HTTP.

**Testing**: Vitest + React Testing Library, coverage > 80 % on console code (Gate 2). Component/interaction tests driven by `contracts/read/fixtures/*`.

**Target Platform**: Modern desktop browsers. Built to static assets, served by the `pulsoflota-frontend` container (non-root UID 10001) behind a reverse proxy.

**Project Type**: Web application frontend (SPA), separate service from the backend (`src/frontend/` vs `src/backend/`, currently `src/api/`).

**Performance Goals**: Fixed poll cadence ~5 s (matches the simulator step and SC-002). No sub-2 s refresh and no streaming in Turn 1 (deferred). A refresh completing within one cadence satisfies SC-001/SC-002.

**Constraints**: Read-only (no commands, no auth UI; the "Cerrar sesión" / logout link in the shell is presentational per the reference, not auth this turn). Information conveyed in text as well as color (FR-012/SC-007, accessibility; reference §10: `role="status"` badge, `role="alert"` banner, `aria-current="page"`, decorative icons `aria-hidden`). Non-blocking stale-data behavior on backend unreachability (FR-010/SC-006). No map/geometry; position shown as distance-along-corridor value. Desktop fixed-width layout (1280×800 artboard) matching the styling reference.

**Scale/Scope**: One corridor (C6-008, direction 1), fleet of 5 + 2 buses. Single dispatcher view; ~1 screen with 4 regions (shell, fleet list, summary, status/banner).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Turn 1 is active (`docs/turns-ritmo.md`): Adaptive Lane, console shows fleet state + headway, no geographic map. The 5 Core Principles always apply; Turn 1 adopts Gate 1 (ESLint + schema validation), Gate 2 (Vitest + coverage > 80 %), and the "security that costs nothing extra" baseline. Deferred norms must not be treated as blocking findings.

| Principle / Gate | Applies here | Verdict |
|---|---|---|
| I — Risk-First Order | Turn 1 is a Level 1 (data-integrity) turn; this is an Adaptive-Lane read-only view that depends on the already-built read API (004). It mitigates no new Level 1 risk and starts nothing adaptive ahead of a risk. | PASS |
| II — Contract-First & Data Ownership | Frontend types are generated from `contracts/read/*.schema.json` v1.0.0; no hand-written payload types, no invented fields. Frontend owns formatting/units/color only (per `contracts/read/README.md`). No data-contract change (consumer only). | PASS |
| III — Isolated Ingestion & Deterministic Real Time | Frontend is a separate service; it never sits on the ingestion/decision path and never blocks it. Pure consumer of a read endpoint. | PASS |
| IV — Unbreakable Human Gate | Console is observation-only this story; no recommendations, no commands, no autonomous action. Nothing to gate. | PASS (N/A) |
| V — Test-First & Automated Gates | Vitest + Testing Library, coverage > 80 % on console code, driven by contract fixtures; `frontend-ci` (ESLint, `tsc --noEmit`, Vitest, Vite build). | PASS (plan-level) |
| Gate 1 — Contract & Static Analysis | ESLint (SAST for JS) + schema-derived types validated against fixtures. | Adopted (Turn 1) |
| Gate 2 — Integration & Supply Chain | `frontend-ci`: ESLint, `tsc --noEmit`, Vitest coverage > 80 %, Vite build, `npm audit`; committed `package-lock.json`, installed with `npm ci`. | Adopted (Turn 1) |
| Security baseline | Frontend decides no access control (none exists this turn); static build served non-root with mandatory headers at the proxy/container; no secrets in code. | PASS |

**Deferred (evolution), not gated this story**: real-time push (WebSocket/SSE) and sub-2 s refresh; geographic/interactive map; RBAC/JWT/auth UI; recommendations and approve/discard (Human-in-the-Loop UI); multi-corridor, second direction, short-turning; historical charts and manager-role views; full security headers hardening, image scan (Trivy) and JS SCA beyond `npm audit`.

**Result**: PASS — no violations, Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/005-dispatcher-console/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (frontend consumer contract notes)
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

This feature creates the `src/frontend/` tree (first frontend code in the repo). The backend read API it consumes already exists under `src/api/` (served as `/api/v1/corridor/{corridor_id}/{now,source-status}`).

```text
src/frontend/
├── index.html
├── package.json                 # pinned deps; package-lock.json committed
├── vite.config.ts
├── tsconfig.json                # strict: true, no any
├── tailwind.config.ts
├── .eslintrc.cjs
└── src/
    ├── main.tsx                 # app bootstrap, QueryClientProvider
    ├── App.tsx                  # shell + console composition
    ├── api/
    │   ├── generated/           # types generated from contracts/read/*.schema.json
    │   └── client.ts            # typed read client (base URL, no-data envelope handling)
    ├── hooks/
    │   ├── useCorridorNow.ts    # TanStack useQuery, refetchInterval ~5s
    │   └── useSourceStatus.ts   # TanStack useQuery, refetchInterval ~5s
    ├── components/
    │   ├── shell/               # Sidebar (logo, nav items, user footer), Header
    │   │                        #   (CorridorSelector, StatusBadge, Clock), DataStateBanner
    │   ├── fleet/               # FleetList, BusRow, HeadwayCompare, StateTag, QualityTag
    │   ├── summary/             # CorridorSummary (in service / bunched / gaps)
    │   └── status/              # StaleIndicator, EmptyState
    ├── styles/                  # Tailwind theme tokens from the styling reference (palette, type scale)
    └── mocks/                   # fixture-backed mock mode (reuses contracts/read/fixtures)

src/frontend/tests/              # Vitest + Testing Library; fixtures from contracts/read/fixtures/*
```

**Structure Decision**: Web-application frontend. The SPA lives in `src/frontend/` as the `pulsoflota-frontend` service (separate from the backend), matching the constitution's target layout and Turn-1 split. Data fetching is isolated in `hooks/` (TanStack Query), presentation in `components/`, and all payload types in `api/generated/` from the approved schemas — satisfying SRP from the coding standards and Contract-First from Principle II. The `components/shell/` tree mirrors the styling reference's structure (sidebar → logo / nav items / user footer; header → corridor selector / status badge / clock; alert banner); the data-state badge and banner bind to the same source-status signal (see data-model.md).

**Design tokens (from the styling reference — Tailwind theme)**:

| Token | Value | Used for |
|---|---|---|
| app bg | `#F4F6F9` | application background |
| surface | `#FFFFFF` | header, active nav item |
| text primary / secondary | `#12161C` / `#4A5361` | body / labels |
| border / placeholder border | `#DDE1E7` / `#A3ACB9` | separators / empty-state outline |
| link | `#1D4ED8` (hover `#1E3A8A`) | links |
| sidebar bg | `#14213D` | sidebar |
| sidebar item inactive / active | text `#E2E8F0` / bg `#FFFFFF` text `#14213D` | nav items |
| logo accent | `#FBBF24` | pulse icon |
| sidebar divider / avatar / role text | `#2B3A5C` / `#CBD5E1` | footer |
| status live | bg `#DCFCE7` text `#166534` | badge + banner (live) |
| status estimated | bg `#FEF3C7` text `#78350F` | badge + banner (estimated) |
| status no-data | bg `#FEE2E2` text `#991B1B` | badge + banner (no_data) |

Fonts: Inter (body, nav, labels) and Space Grotesk (brand, h1, clock). Fixed sizes: header 68 px, nav item 44 px, sidebar 248 px; radii 8 / 12 / 999 px. Exact type scale and per-element specs live in the reference and are the source of truth for the implementation; this table captures the tokens so `/speckit.tasks` and Build do not re-derive them.

## Complexity Tracking

> No Constitution Check violations. No entries required.
