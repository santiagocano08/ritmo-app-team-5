# feat(integration): package the frontend and validate the project as one functional whole (US-07)

> RITMO Turn 1 — "Data and minimal loop". Lane: Disciplined. Risk level: 3.
> Governed by `docs/turns-ritmo.md` §3, `.kiro/steering/deployment-containers.md`,
> ADR-0004 (React multi-stage image) and the constitution.

## Context and problem

US-05 delivered the backend read API and US-06 delivered the dispatcher console
(`src/frontend/`), but the two have only ever been validated **separately**:

- The frontend (US-06) was verified against **msw mock fixtures** derived from the
  `contracts/read/` schemas. No end-to-end run against the live US-05 backend
  (`GET /api/v1/corridor-now`, `GET /api/v1/source-status`) was ever exercised.
- The frontend was **not packaged**: `docker-compose.yml` currently runs
  `db`, `ingestion`, `api`, `refresh` and `tests` only — there is **no
  `pulsoflota-frontend` service, no frontend Dockerfile and no reverse proxy**.
  (US-06 listed the compose service in its scope but its `tasks.md` did not
  generate it, so it was deferred.)

This ticket closes the loop. It makes the project a **functional whole**: all
Turn-1 services running together under `docker-compose`, with the dispatcher
console reaching the real backend over HTTP and showing live corridor state,
validated end to end. It is the integration story for Turn 1, not new product
behavior — it introduces no new features, contracts or business logic; it wires,
packages and verifies what US-05 and US-06 already built.

## User story

As the operations team, I want the whole Turn-1 system — ingestion, backend read
API, database, and dispatcher console — to run together under `docker-compose` and
be validated end to end, so a dispatcher can open the console against the real
backend and see live corridor C6-008 state, and so the project is a deployable,
functional whole rather than parts tested in isolation.

## Scope (Turn 1)

### A. Package the frontend as the `pulsoflota-frontend` service

- [ ] **Multi-stage frontend Dockerfile (ADR-0004):** a Node build stage runs
      `npm ci` + `vite build`; the final stage serves only the static `dist/`
      from a non-root web server image (**UID 10001**). No Node runtime, source or
      `node_modules` in the final image.
- [ ] Add the **`pulsoflota-frontend`** service to `docker-compose.yml` (keeping
      the existing `db` / `ingestion` / `api` / `refresh` services) with a
      `healthcheck` and `depends_on` the backend being healthy.
- [ ] **Reverse proxy** (Nginx/Traefik, hardened, least privilege) serving the
      static assets and proxying `/api/*` to the backend under one origin, so the
      console's default relative API base (`/api/v1`) works without CORS.
- [ ] **HTTP security headers** on the served assets per `security.md`
      (CSP, HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`) and
      removal of stack-revealing headers (`Server`, `X-Powered-By`, versions).
- [ ] The backend `API_BASE` / console `VITE_API_BASE_URL` wiring is documented:
      same-origin via the proxy by default; a cross-origin override path is noted
      (and the backend would then need CORS — out of scope unless chosen).

### B. End-to-end integration validation (the functional whole)

- [ ] `docker compose up` brings up `db` + `ingestion` + `api` + `refresh` +
      `pulsoflota-frontend` together; all services report healthy.
- [ ] With the simulator/gold data producing corridor C6-008 snapshots, the
      console loaded in a browser against the **real backend** shows the fleet
      leader-first with state/headway/quality and auto-refreshes every ~5 s — no
      mocks in the path.
- [ ] A documented **end-to-end validation walkthrough** (extending
      `specs/005-dispatcher-console/quickstart.md` §2–§4, or a new integration
      quickstart) that exercises: live snapshot render, ~5 s refresh, `estimated`
      source status (no alert), `no_data` (empty corridor), and stale/recovery by
      stopping and restarting the `api` service.
- [ ] The generated frontend contract types still match the backend's live
      responses (schema_version assertion holds against real data, no drift).

### C. Update project documentation

- [ ] Update the project docs — the **`README`** first — to describe the full
      integrated setup: how to configure and run the whole stack with
      `docker compose up` (the `db` / `ingestion` / `api` / `refresh` /
      `pulsoflota-frontend` services), the required environment variables
      (including `VITE_API_BASE_URL` / the same-origin proxy default), service
      ports and healthchecks, and how to open the dispatcher console against the
      real backend.
- [ ] Keep the documentation consistent with what actually ships: reconcile any
      `README` / `docs` / `AGENTS.md` claims about the service list, the
      `src/frontend/` layout and how to run the system so they match the delivered
      compose setup (no stale "no frontend yet" statements).

## Out of scope (deferred / evolution)

- Any new UI feature, panel or endpoint — this is integration only.
- Recommendations panel / approve-discard (US-02), map, WebSocket push,
  ≤ 2 s refresh — later turns.
- RBAC / JWT / auth UI — Turn 2. The frontend never decides access control.
- GHCR image publishing and Trivy image scan gates — intermediate target
  (ADR-0005), not an MVP blocker for this story unless the team pulls them in.
- Kubernetes / Helm / GitOps — future/evolution production target.
- Cross-origin CORS deployment topology (default is same-origin via the proxy).

## Contracts consumed / produced

| Contract | Version | Direction |
|---|---|---|
| `corridor_now.schema.json` | 1.0.0 | backend response → frontend consumes |
| `source_status.schema.json` | 1.0.0 | backend response → frontend consumes |

**No contract changes.** If live backend responses do not match the committed
v1.0.0 schemas, **stop** and request an ADR from `data-design` (CODEOWNERS of
`contracts/`) rather than editing the contract or the generated types.

## Acceptance criteria

- **Given** `docker compose up` with gold data for C6-008, **when** all services
  start, **then** `db`, `ingestion`, `api`, `refresh` and `pulsoflota-frontend`
  all report **healthy**.
- **Given** the stack is up, **when** a dispatcher opens the console in a browser,
  **then** it loads against the real backend (no mocks), shows the fleet
  leader-first with state/headway/quality, and refreshes every ~5 s.
- **Given** `source_status` is `estimated`, **when** rendered live, **then** the
  affected bus shows "Estimated" and **no** alert is raised.
- **Given** the corridor has no current snapshot, **when** the console polls,
  **then** it shows the no-data state (not an error).
- **Given** the `api` service is stopped and restarted, **when** polls fail then
  succeed, **then** the console shows a non-blocking stale indicator and recovers
  without a reload or crash.
- **Given** the final frontend image, **when** inspected, **then** it runs as a
  non-root user (UID 10001), contains only static `dist/` (no Node/source), and
  serves the required security headers.
- **Given** a new contributor and the updated `README`, **when** they follow it,
  **then** they can configure environment variables and run the whole stack with
  `docker compose up` and reach the console against the real backend, with no
  stale docs claiming the frontend does not exist.

## Gates to pass

- `frontend-ci` still green (ESLint, `tsc --noEmit`, Vitest + coverage > 80 %,
  Vite build, `npm audit`) — unchanged by integration.
- `backend-ci` still green — unchanged by integration.
- `docker compose up` healthy for all services; end-to-end walkthrough passes.
- Non-root (UID 10001) frontend image and mandatory security headers verified.

## Dependencies

- **Blocked by US-05** (backend read API) and **US-06** (dispatcher console).
  US-07 integrates and packages what both delivered; it starts only after both
  are merged.

## RITMO workflow

- Branch: `feature/US-07-functional-integration`.
- Flow: Plan → Specify → Build → Verify → Review. One story on its own branch.
