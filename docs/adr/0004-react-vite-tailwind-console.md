# ADR-0004: React + Vite + Tailwind CSS as an Allowed Dispatcher Console Stack

- Status: Proposed
- Date: 2026-11-21
- Decided by: pending. Requires the unanimous sign-off of the Turn Owner, the Architect
  (Software / Security) and the Dispatcher Representative (Constitution, Governance, Amendments)
- Turn: Turn 1 — Data and Minimal Loop (active)
- Amends: Constitution 1.1.0 → 1.2.0 (MINOR, compatible stack change), section "Mandatory
  technology stack"
- Addresses: Principle III (the console stays isolated from ingestion), Principle IV (the human
  confirmation click lives in the console), `frontend-web.md` requirements (map ≤ 2 s, alerts,
  approval with audit log, contingency mode)

## Context

The constitution allows three dispatcher console stacks: Streamlit, Dash, or HTML5/Jinja2 with
WebSockets. All three keep the system in Python.

The console has to show live fleet positions with ≤ 2 s latency, highlight headway deviations,
raise early bunching/gap alerts, present recommendations as non-binding suggestions behind an
explicit confirmation click, keep an audit trail, and switch to a contingency mode when the
backend fails. ADR-0003 already defines the read contract as three doors (query, push, command)
with JSON Schemas and fixtures, so the console can be built against a contract independent of the
backend implementation.

Options considered:

| Option | For | Against |
|---|---|---|
| Streamlit | Fastest prototype, pure Python | Reruns the script on each interaction; no native server push; awkward approval flows |
| Dash | Python, good charts, periodic updates | WebSockets need extensions; custom UI beyond its components is costly |
| HTML5/Jinja2 + WebSockets | Full control, native push, Python server | Interactive state (map, alerts, approvals) is hand-written JavaScript that grows hard to maintain |
| React + Vite + Tailwind | Component model fits a live interactive console; native WebSocket client; fast build; mature testing (Vitest, Testing Library) | Adds a second language, a Node toolchain and a JavaScript supply chain |

## Decision

Add **React + Vite + Tailwind CSS** as a fourth allowed console stack. The existing options stay
allowed. Conditions:

1. **API-only access.** The SPA talks to the backend only through its REST/WebSocket API. It never
   connects to PostgreSQL or Redis and never computes the service metric (P(board ≤ t), EWT,
   headway) itself.
2. **Contract-First.** TypeScript types for API payloads are generated from the backend OpenAPI
   document or from `contracts/read/*.schema.json`. Fixtures in `contracts/read/fixtures/` drive
   component tests and a mock mode until each endpoint exists.
3. **Authorization in the backend.** Hiding UI elements is not access control; every approval or
   command is authorized again by the backend.
4. **Isolated container.** The console is built to static files and served by its own non-root
   container (`pulsoflota-web`, UID 10001) with the mandatory security headers. No service in the
   ingestion path depends on it.
5. **Same gates.** ESLint in Gate 1, `npm audit` in Gate 2, Vitest coverage > 80 % for the
   console code, a committed `package-lock.json` installed with `npm ci`.
6. **Python stays the language** of the API, ingestion and data pipeline.

## Consequences

- The team maintains a Node toolchain and a JavaScript dependency tree; Gate 2 gains `npm audit`.
- CI needs a second job (lint, test and build of the console).
- Security headers, CSP and CORS between the SPA origin and the API must be designed when the
  first endpoint is exposed (backend-api steering; CORS and CSP enforcement are part of the
  security norms adopted in turn 2).
- Deferred norms keep their turns: SAST/SCA as blocking gates remain turn 2 per
  `docs/turns-ritmo.md`; this ADR only names the JavaScript tools they will use.

## Changed documents

`.specify/memory/constitution.md` (1.2.0), `AGENTS.md`, `docs/turns-ritmo.md` (0.1.2),
`.kiro/steering/frontend-web.md`, `security.md`, `testing-quality-gates.md`,
`deployment-containers.md`.
