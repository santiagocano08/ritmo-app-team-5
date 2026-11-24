# feat(frontend): dispatcher console — fleet state and headway (US-06)

> RITMO Turn 1 — "Data and minimal loop". Lane: Disciplined. Risk level: 2.
> Governed by `docs/turns-ritmo.md` §3 and the constitution.

## Context and problem

Turn 1 closes the minimal loop detect → recommend → approve → execute → measure, but there
is no dispatcher-facing UI yet: `src/frontend/` does not exist. The dispatcher currently has
no way to see live fleet state or spot bunching/gaps. This ticket creates the React 19 console
that consumes the backend read API (Ticket 1) over REST with **polling** (no geographic map in
Turn 1). Recommendations and the approve/discard UI are a separate story (Ticket 3).

## User story

As a dispatcher, I want to see the live state of corridor C6-008's fleet — each bus, its
headway vs. plan, and its data quality — so I can detect bunching and gaps.

## Scope (Turn 1)

- [ ] New `src/frontend/` app: React 19 + TypeScript (`strict: true`, no `any`) + Vite + Tailwind CSS.
- [ ] Fleet view: list of buses from `corridor_now`, ordered leader-first, showing `bus_state`
      (leader / regular / bunched / gap / broken_down), `headway_ahead_s` vs `headway_planned_s`,
      `distance_along_m`, and per-bus `data_quality` (live / estimated).
- [ ] Corridor summary: `buses_in_service`, `n_bunched`, `n_gaps`.
- [ ] Source-status banner: overall `live` / `estimated` / `no_data`; estimated buses shown as
      "Estimated" **without** raising an alert (D1 behavior).
- [ ] **Polling** every 5 s (matching the simulator step) via TanStack Query; all HTTP goes through
      the `openapi-ts`-generated client. No `useEffect` data fetching, no manual `fetch`.
- [ ] Served as static assets behind a reverse proxy; added as the `pulsoflota-frontend` service
      in `docker-compose` with a healthcheck.

## Out of scope (deferred / evolution)

- Recommendations panel and approve/discard actions — **Ticket 3** (US-02, Gate 4).
- Geographic / interactive map and ≤ 2 s refresh — Turn 3 (US-06 full).
- WebSocket / live push — Turn 3. Turn 1 is polling-only.
- Login, RBAC, any auth UI — Turn 2. The frontend never decides access control.
- Route diversion UI (US-03), Metro ridership, P(board ≤ t) prioritization — Turn 4.
- Historical charts, direction 2, short-turning.

## Contracts consumed

| Contract | Version | Source |
|---|---|---|
| `corridor_now.schema.json` | 1.0.0 | `GET /api/v1/corridor-now` |
| `source_status.schema.json` | 1.0.0 | `GET /api/v1/source-status` |

Types are generated from the backend OpenAPI; the frontend is not a second source of truth.

## Acceptance criteria

- **Given** the backend serves a `corridor_now` snapshot, **when** the console loads, **then** it
  shows each bus leader-first with its state and headway, and refreshes every 5 s.
- **Given** a bus is `bunched` (or `gap`), **when** the snapshot updates, **then** that bus is
  visually distinguished and reflected in the `n_bunched` / `n_gaps` summary.
- **Given** `source_status` is `estimated` with a bus in `sources_down`, **when** rendered, **then**
  the bus shows "Estimated" and **no** alert is raised.
- **Given** the backend is briefly unreachable, **when** a poll fails, **then** the UI shows a
  non-blocking "stale data" indicator and retries, without crashing.

## Gates to pass

- `frontend-ci`: ESLint, `tsc --noEmit`, Vitest, Vite build, JS SCA (`npm audit`).
- Coverage **> 80 %**.

## Dependencies

- **Blocked by Ticket US-05** (backend read API). The OpenAPI client is generated from its endpoints.

## RITMO workflow

- Branch: `feature/US-06-frontend-console`.
- Flow: Plan → Specify → Build → Verify → Review. One story on its own branch.
