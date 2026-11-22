# Phase 0 Research: Dispatcher Console — Fleet State and Headway

The Technical Context had no open `NEEDS CLARIFICATION`: the stack is fixed by the constitution, the data shapes are fixed by the already-approved read contracts, and the visual design is fixed by the authoritative desktop styling reference in the ticket folder (`tickets/US-06-frontend-home/US-06-escritorio-estilos.md` + `mockup-base-escritorio.png`). This document records the decisions that shape the design so Phase 1 and `/speckit.tasks` are unambiguous.

## R1 — Payload types: generated from the read contracts, not hand-written

- **Decision**: Generate the TypeScript types for `corridor_now` and `source_status` from `contracts/read/corridor_now.schema.json` and `contracts/read/source_status.schema.json` (v1.0.0) with `openapi-typescript` (JSON-Schema → TS) or the backend's OpenAPI document. Commit the generated output under `src/frontend/src/api/generated/`.
- **Rationale**: Principle II (Contract-First) and `frontend-web` steering require generated types; the schemas are the single source of truth and `README.md` restricts the frontend to formatting/units/color. Hand-writing types would drift and could introduce fields the contract does not define.
- **Alternatives considered**: Hand-written interfaces (rejected: drift, violates Contract-First); Zod schemas authored by hand (rejected: duplicates the JSON Schema that already exists as the source of truth).

## R2 — Backend endpoints and the no-data envelope

- **Decision**: Consume the two US-05 endpoints exactly as built:
  - `GET /api/v1/corridor/C6-008/now` → `corridor_now` v1.0.0, or a 200 no-data envelope `{"status":"no_data","corridor_id":"C6-008"}`.
  - `GET /api/v1/corridor/C6-008/source-status` → `source_status` v1.0.0 (which can itself carry `status:"no_data"`), or a 200 envelope `{"status":"no_data","corridor_id":"C6-008","sources_down":[]}`.
  The client treats the no-data envelope as a first-class, non-error state and maps it to the no-data UI (status indicator + banner + empty counts), per FR-006/FR-007/FR-013 of this spec and FR-008/FR-011 of 004.
- **Rationale**: 004 already serves these shapes (`specs/004-backend-read-api/plan.md`, `quickstart.md`). The console must not invent a new contract; it reads what the backend returns.
- **Alternatives considered**: Treating empty gold as an HTTP error (rejected: the backend deliberately returns 200 + a distinguishable body; the console mirrors that).

## R3 — Refresh mechanism: TanStack Query polling at ~5 s

- **Decision**: One `useQuery` per endpoint with `refetchInterval: 5000` and `refetchIntervalInBackground: false`; `keepPreviousData` so the last snapshot stays visible while a refresh is in flight or fails. No `useEffect`-based fetching.
- **Rationale**: Turn 1 is polling-only at the simulator's 5 s step (spec Assumptions, SC-002); the coding standards mandate TanStack Query (`useQuery`/`useMutation`) and forbid `useEffect` fetching. `keepPreviousData` plus the query `error`/`isError` flag implements FR-010/FR-014/SC-006 (retain last snapshot, show stale indicator, retry next cadence) with no custom retry loop.
- **Alternatives considered**: `setInterval` + `fetch` in a `useEffect` (rejected: violates coding standards, reinvents retry/caching); WebSocket/SSE push (rejected: deferred to Turn 3 per the turn map).

## R4 — Stale vs no-data vs estimated: three independent signals

- **Decision**: Model three distinct conditions and never conflate them:
  1. **Stale (transport)** — the last refresh failed to reach the backend. Keep the last snapshot, show a non-blocking "stale data" indicator, retry next cadence. Driven by the TanStack query error state, not by contract data.
  2. **Source status (data trust)** — `live` / `estimated` / `no_data` from `source_status.status`. Drives the status indicator and the explanatory banner (banner shown only for `estimated` and `no_data`).
  3. **Per-bus estimated** — `data_quality: "estimated"` on a bus labels that bus; it never raises an alert on its own.
- **Rationale**: FR-006/FR-007/FR-008/FR-010 describe different causes with different UI; collapsing them would mislabel a transport hiccup as a data-trust problem. `estimated` is explicitly a non-alert state (FR-008/SC-005; `source_status.schema.json` note "no alert raised").
- **Alternatives considered**: A single "health" enum (rejected: loses the stale-vs-estimated distinction and the "estimated never alerts" guarantee).

## R5 — Leader-first ordering and headway comparison

- **Decision**: Render `corridor_now.buses` in the array order the backend provides (already sorted by `distance_along_m` descending — leader first per the schema). Do not re-sort. Show `headway_ahead_s` vs `headway_planned_s`; when `headway_ahead_s` is `null` (leader, or a broken-down bus), present the bus without a headway comparison (spec edge case "single bus / leader only").
- **Rationale**: The contract defines ordering and the `null` semantics; the frontend only formats. Re-sorting would duplicate backend logic (Principle II) and risk disagreeing with it.
- **Alternatives considered**: Client-side sorting by distance (rejected: duplicates backend ownership of state/order).

## R6 — Accessibility: text, not color alone

- **Decision**: Every operational state (leader/regular/bunched/gap/broken_down), data-quality flag (live/estimated) and source status renders a text label (and/or an ARIA label) alongside any color treatment. Color is redundant, never the sole carrier of meaning.
- **Rationale**: FR-012 and SC-007 require it; it is also a baseline WCAG expectation for a supervisory console.
- **Alternatives considered**: Color-only badges (rejected: fails FR-012/SC-007).

## R7 — Navigation shell per the US-03 desktop styling reference

- **Decision**: Build the shell to match the authoritative styling reference `tickets/US-06-frontend-home/US-06-escritorio-estilos.md` and mockup `mockup-base-escritorio.png`: a 248 px dark-navy (`#14213D`) sidebar with the PulsoFlota logo (amber `#FBBF24` pulse icon + Space Grotesk 20/700 wordmark), the dispatcher nav items (Central en vivo / Alertas / Plan del día, Inter 15/600, 44 px rows, 8 px radius, active item white-on-navy with `aria-current="page"`), and a bottom-anchored user footer (36 px avatar "UD", "Usuario demo" / "Despachador", "Cerrar sesión" link). A 68 px white header (`#FFFFFF`, bottom border `#DDE1E7`) holds, left, the corridor selector (label "CORREDOR" + button "[Corredor piloto] · Estación → casa" + chevron) and, right, the status badge (`role="status"` pill with a 10 px dot, label and detail) and the clock (Space Grotesk 22/700). The data-state badge binds to R4's source status; identity/role and the logout link are presentational only — the console decides no access control this turn.
- **Rationale**: The spec names the US-03 desktop styling spec as authoritative for the shell; the ticket folder provides it in full (`<nav aria-label="Secciones">`, exact palette, type scale, spacing and ARIA roles in §10). Matching it keeps US-06 consistent with the established design system instead of inventing one. The reference labels are Spanish (domain UI strings, consistent with the AGENTS.md note that `docs/` identifiers stay as defined); code identifiers remain English.
- **Alternatives considered**: Designing the shell from FR-011 alone (rejected now that the authoritative reference is available); gating sections by role in the frontend (rejected: no auth this turn, frontend never decides access).

## R9 — Fleet content styling (the mockup placeholder region)

- **Decision**: The styling reference's main area is a dashed placeholder labelled "Contenido de la sección: se define en las próximas historias." US-06 is that story: it replaces the placeholder with the fleet list, corridor summary and per-bus rows inside the same `<main>` (flex:1, 28 px padding, h1 "Central en vivo" in Space Grotesk 26). The new fleet components are styled with the reference's existing tokens — surface `#FFFFFF`, borders `#DDE1E7`, text `#12161C`/`#4A5361`, radii 8/12 px — and reuse the three status colors (live `#DCFCE7`/`#166534`, estimated `#FEF3C7`/`#78350F`, no-data/attention `#FEE2E2`/`#991B1B`) for the bus state and quality tags, always paired with a text label (R6).
- **Rationale**: The reference styles the shell, not the fleet content (which did not exist at US-03). Extending its palette/type scale keeps one coherent design language without inventing new colors, and reusing the status palette for bunched/gap/broken-down/estimated tags keeps the data-trust and operational-state cues visually consistent. Exact pixel treatment of the fleet rows is an implementation detail for Build, anchored to these tokens.
- **Alternatives considered**: A separate ad-hoc palette for the fleet (rejected: visual drift from the reference); keeping the dashed placeholder (rejected: US-06 explicitly fills it).

## R8 — Mock mode and test data from the approved fixtures

- **Decision**: Drive component/interaction tests and a pre-backend mock mode from `contracts/read/fixtures/{normal,c1_bunching,c2_gap,c5_breakdown,d1_source_outage}/` (`corridor_now.json` + `source_status.json` present in every scenario). Use `msw` (or an equivalent fetch stub) to serve them, including the no-data envelope and a simulated failed refresh.
- **Rationale**: `frontend-web` steering says fixtures drive component tests and mock mode before an endpoint exists. The five scenarios map directly to the spec's acceptance scenarios and edge cases (bunching, gap, breakdown, estimated/source-outage, empty/no-data), giving deterministic coverage toward the > 80 % Gate 2 threshold.
- **Alternatives considered**: Ad-hoc inline test data (rejected: diverges from the contract and the shared fixtures); a live backend in unit tests (rejected: slow, non-deterministic, and blocks tests on 004 being up).

## Resolved unknowns

| Topic | Resolution |
|---|---|
| Payload types | Generated from `contracts/read/*.schema.json` v1.0.0 (R1) |
| Endpoints / no-data | `/api/v1/corridor/C6-008/{now,source-status}`, 200 no-data envelope (R2) |
| Refresh | TanStack Query `refetchInterval: 5000`, `keepPreviousData` (R3) |
| Stale vs estimated vs no-data | Three independent signals (R4) |
| Ordering / headway null | Trust backend order; no comparison when `headway_ahead_s` null (R5) |
| Accessibility | Text + ARIA alongside color (R6; reference §10 roles) |
| Shell | Match `tickets/US-06-frontend-home/US-06-escritorio-estilos.md` + mockup (R7) |
| Test data | Shared contract fixtures via `msw` (R8) |
| Fleet styling | Extend the reference tokens into the main-area placeholder region (R9) |
