---
inclusion: auto
name: frontend-web
description: When working on the dispatcher web console (React 19 + TypeScript + Vite + Tailwind) - interactive map, headway and congestion visualization, Human-in-the-Loop UI and contingency mode.
---

# Dispatcher Web Console — PulsoFlota

## Stack

- React 19 + TypeScript + Vite + Tailwind CSS single-page application (ADR-0004),
  the `pulsoflota-frontend` service in **target folder `src/frontend/`**. It is a
  **separate service** from the Python backend (`src/backend/`) and belongs to the
  **Adaptive Lane** (see `ritmo-workflow.md`).

> Target state: there is no frontend code yet in the Turn-1 tree. Check
> `docs/turns-ritmo.md` for what the active turn requires (in turn 1 the console
> shows fleet state and headway, no geographic map).

### React + Vite + Tailwind console

- The SPA reads and writes only through the backend REST/WebSocket API. It never
  connects to PostgreSQL or Redis, and it never computes the service metric
  itself: P(board ≤ t), EWT and headway come from the backend.
- Contract-First (Principle II): TypeScript types for API payloads are generated
  from the backend OpenAPI document or from `contracts/read/*.schema.json`, not
  written by hand. Fixtures in `contracts/read/fixtures/` drive component tests
  and the mock mode used before an endpoint exists.
- Hiding a button is not access control: every approval or command is
  authorized again in the backend.
- Build output is static files. The serving container runs as non-root
  (UID 10001) and sends the mandatory security headers (see `security.md`).
- Tests: Vitest + Testing Library; coverage > 80 % applies to the console code.
- Lint: ESLint (Gate 1). Dependencies: committed `package-lock.json`,
  installed with `npm ci`; `npm audit` in Gate 2 (see `security.md` A03).

## Design reference (UX/UI)

- The authoritative visual reference is `docs/designs/global-desing-styles.md`:
  design tokens (colour palette, semantic status pairs, typography — Inter +
  Space Grotesk), spacing/border/radius scale, global components (sidebar,
  status badge, alert banner, buttons, tables, chips, corridor diagram),
  motion and accessibility rules. Match these tokens; do not invent new ones.
- `docs/designs/resumen-historias.md` summarizes the UX/UI story set and its
  mockups: `docs/designs/mockups/{escritorio,celular,historias}/UXUI-NN-*.png`.
- **Two numbering schemes, do not conflate them:** `tickets/US-NN` are the
  implementation stories wired to GitHub issues; `docs/designs/` uses
  **`UXUI-NN`** for the design stories. They do not map one-to-one. A ticket may
  cite a `UXUI-NN` mockup as its visual source (e.g. US-06 implements the
  console whose desktop style spec lives in
  `tickets/US-06-frontend-home/US-06-escritorio-estilos.md`, derived from
  `UXUI-03`).

## Real-time interactive map

- Up-to-date geospatial position of every active bus in the corridor.
- Position refresh latency ≤ 2 s (validate with 100 simulated buses).

## Headway and regularity

- Compute and show the headway between consecutive vehicles on each standard
  route.
- Highlight deviations > ±15 % from the schedule.

## Road congestion

- Ingest traffic flow speed per segment and classify congestion with a color
  code:
  - **Green:** free flow.
  - **Yellow:** moderate.
  - **Red:** congested.

## Human-in-the-Loop (Principle IV, NON-NEGOTIABLE)

- Early fleet desynchronization alerts at least 3 min before *bunching* or a
  *gap* consolidates.
- Regulation recommendations (holding, early departure, reserve injection,
  diversion) are shown as **non-binding suggestions**.
- No command is sent to the fleet without an explicit **human confirmation
  click** from the dispatcher.
- Keep an audit log of authorized diversions (for compensation and contract
  compliance with operators).

## Contingency diversions

- Show the diversion recommendation on the map with the suggested route, the
  extra distance and the projected change in the service indicator.

## Contingency

- If the control center or the web app fails, the console switches to a local
  contingency mode based on predefined static dispatch plans.

## Access control

- The frontend must **not** be the only access-control mechanism; authorization
  is evaluated in the backend. See `security.md` (A01) and `backend-api.md`.
