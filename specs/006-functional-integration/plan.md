# Implementation Plan: Functional Integration (Turn-1 Whole)

**Branch**: `006-functional-integration` | **Date**: 2026-11-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-functional-integration/spec.md`

## Summary

US-07 wires the already-delivered Turn-1 parts (database, ingestion, gold refresh, backend read
API, dispatcher console) into one deployable stack and validates it end to end. A single
`docker compose up` must bring up five healthy services; the React console, served as hardened
static assets behind a reverse proxy under one origin, reaches the real backend over its default
relative path (`/api/v1`), renders corridor C6-008 leader-first, and auto-refreshes about every
5 seconds — with the estimated-source, no-data and backend-interruption cases behaving as
specified.

The technical approach adds **no product behavior, contract or business logic** (FR-013). It
introduces exactly one new runtime unit — a `frontend` service that builds the existing
`src/frontend` SPA to static assets and serves them through a reverse proxy that also forwards
`/api/v1` to the `api` service — plus compose wiring, security headers, and reconciled
documentation. The committed read contract stays at version 1.0.0 and is consumed unchanged; any
live mismatch stops work and triggers a contract decision (FR-014).

## Technical Context

**Language/Version**: Python 3.12 (backend/ingestion/refresh, already built); TypeScript 5.6 +
React 19 on Vite 6 (frontend, already built). No application language code is written in this
story — the work is orchestration, packaging and docs.

**Primary Dependencies**: Existing — FastAPI + Pydantic V2 (`src/api`), psycopg 3, the Vite SPA in
`src/frontend` (TanStack Query, generated types). New (infrastructure only): a reverse proxy to
serve static assets and forward `/api/v1` (Nginx is the Turn-1 choice; see `research.md` R1), and
a multi-stage frontend Docker image.

**Storage**: PostgreSQL 16 (existing `db` service; SQLite not used here). No schema or data change.

**Testing**: Existing suites unchanged — pytest (`src/data/tests`, `tests`, coverage > 80 %) and
Vitest (`src/frontend`, coverage > 80 %). New verification is a documented end-to-end walkthrough
(`quickstart.md`) exercising the five validation cases (FR-015) and image/header inspection checks
(FR-009/FR-010/FR-012), plus the reverse-proxy config validated by `nginx -t` at build.

**Target Platform**: Linux containers via Docker + `docker-compose` (the Turn-1 MVP deployment
target). No orchestration platform beyond local compose (spec Assumptions; turn map §3.3).

**Project Type**: Web application — separate backend (`src/`, currently `src/api` + `src/data` +
`src/pulsoflota`) and frontend (`src/frontend`) services, orchestrated by one compose file.

**Performance Goals**: Console auto-refreshes about every 5 s (FR-005, SC-003); this is the inherited
Turn-1 console cadence, not the ≤ 2 s map SLO (deferred to turn 3). No throughput target is added.

**Constraints**: Same-origin topology is the default (console + backend reached through one origin;
no CORS config) (FR-011, Assumptions). Console loads from the real backend with no mock fixtures in
the request path (FR-003). Shipped console image runs as non-root UID 10001, contains only built
static assets, and sends the mandatory security headers while omitting stack-revealing ones
(FR-009/FR-010/FR-012). Backend responses must match contract version 1.0.0 with zero drift
(FR-014, SC-007).

**Scale/Scope**: One corridor (C6-008), five services, one dispatcher view. Integration + packaging
only; no new endpoints, screens or entities.

No open `NEEDS CLARIFICATION` items remain after Phase 0 (see `research.md`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Active turn: **Turn 1 — Data and Minimal Loop** (`docs/turns-ritmo.md` §3). Only Turn-1 norms are
gating; deferred norms are recorded under "Evolution" and MUST NOT block (constitution §Phased
Adoption).

### Core Principles (always apply, every turn)

- **I. Risk-First Order** — PASS. Integration/packaging mitigates the Turn-1 "validated-in-isolation"
  risk; it starts no adaptive-lane feature and introduces no Level-1 risk. Security hardening it adds
  (non-root, headers) only reduces risk.
- **II. Contract-First and Data Ownership** — PASS. No new data exchange is defined. The read
  contract (`contracts/read/*`, v1.0.0) is consumed unchanged; FR-014 mandates stop-and-decide on any
  live mismatch rather than editing the contract or generated types. No new persisted model.
- **III. Isolated Ingestion and Deterministic Real Time** — PASS. The `ingestion` service keeps its
  existing isolation (depends only on `db`, nothing depends on it). Adding a `frontend` service and a
  proxy does not place anything on the ingestion path or make the critical path depend on the web.
  Stopping `api` or `frontend` must still not stop `ingestion` (verified in `quickstart.md`).
- **IV. Unbreakable Human Gate** — PASS. This is a read-only console; no on-road command path is added
  or changed. No autonomous action.
- **V. Test-First and Automated Gates** — PASS. Existing coverage > 80 % gates on both services remain
  in force; the new frontend image build must pass `frontend-ci`. The story adds a documented E2E
  validation (FR-015) rather than new unit logic, which matches an integration story.

### Turn-1 adopted norms (gating)

- Containers from day one (Principle III), `docker-compose` with separate services — PASS; this story
  completes the service set by adding the `frontend` service the turn map already calls for.
- Per-service `healthcheck` in `docker-compose` and `backend-ci` / `frontend-ci` on every PR — PASS;
  the new `frontend` service gets a healthcheck and the console gate starts only after `api` is
  healthy (FR-002).
- Turn-1 no-cost security: parameterized queries, no secrets in the repo, error responses without
  stack traces — PASS; unchanged. This story additionally brings forward non-root UID 10001 and the
  mandatory HTTP security headers for the shipped console (FR-010/FR-012). These are *stricter* than
  the Turn-1 baseline, so adopting them early is allowed (a norm may be adopted earlier than its turn;
  only deferring past the assigned turn needs justification — turn map §7).

### Deferred norms touched (Evolution — non-blocking)

Per the turn map §3.3 these remain deferred and are recorded, not designed, here:

- TLS 1.3 / HSTS enforcement end to end, production reverse-proxy TLS termination — turn 2/3. The
  console emits the `Strict-Transport-Security` header (FR-012) but TLS termination itself is not set
  up in the Turn-1 local stack.
- `Trivy` image scan and GHCR image publishing as a release gate — not required for this story (spec
  Assumptions); `pip-audit` / `npm audit` SCA remain in force.
- RBAC / JWT / MFA, CORS/cross-origin topology, Redis, PostGIS, the ≤ 2 s interactive map — turns 2–3.

**Result: PASS — no unjustified violations. No entry in Complexity Tracking required.**

## Project Structure

### Documentation (this feature)

```text
specs/006-functional-integration/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (integration entities, no new persisted model)
├── quickstart.md        # Phase 1 output (end-to-end validation walkthrough)
├── checklists/          # Pre-existing
└── tasks.md             # /speckit.tasks output — NOT created here
```

No `contracts/` directory is generated for this feature: it exposes no new interface. The existing
`contracts/read/*` (v1.0.0) is the authority and is consumed unchanged (FR-013/FR-014). See
`research.md` R2 for the rationale.

### Source Code (repository root)

The target layout (`src/backend/`, `src/frontend/`) is not reorganized by this story (AGENTS.md: the
reorg is a destination, not Turn-1 work). Touched and added paths only:

```text
# Backend service — existing, UNCHANGED by this story
src/api/                 # FastAPI app (main.py, routers/corridor_read.py, reads/, deps.py)
src/data/                # ingestion, refresh, simulator, pipeline, rules
src/pulsoflota/          # shared db/config/models (read contract models)

# Frontend service — existing SPA, built and packaged by this story
src/frontend/
├── src/                 # React app (api/client.ts default base "/api/v1", hooks, components)
├── dist/                # Vite build output (produced in the image build stage)
├── package.json         # build script already present
└── vite.config.ts

# New infrastructure artifacts added by this story (implementation lives in /speckit.tasks)
src/frontend/Dockerfile  # multi-stage: Node build → static assets served by reverse proxy as non-root
deploy/                  # reverse-proxy config (serve dist, forward /api/v1 → api, security headers)
                         #   final directory name decided in tasks; see research.md R1/R3
docker-compose.yml       # add the `frontend` service + healthcheck + startup ordering on `api`
.env.example             # add the console API base / same-origin proxy default (FR-016)
README.md                # reconcile run instructions and service list (FR-016/FR-017)
AGENTS.md                # reconcile "no frontend yet" statement (FR-017) — doc reconciliation only
```

**Structure Decision**: Keep the current Turn-1 tree (`src/api`, `src/data`, `src/pulsoflota`,
`src/frontend`). This story is purely additive at the infrastructure layer: one new `frontend`
container image + reverse-proxy config, compose wiring, and documentation reconciliation. No
application source module is modified, matching FR-013 (no new behavior, contract or business logic).

## Complexity Tracking

> No constitution violations to justify. Section intentionally empty.
