# Phase 0 — Research: Functional Integration (Turn-1 Whole)

Feature: `006-functional-integration` · Spec: [spec.md](./spec.md) · Plan: [plan.md](./plan.md)

The Technical Context carried no unresolved `NEEDS CLARIFICATION`; this feature consumes finished
parts. The decisions below pin the few integration/packaging choices the story leaves open and
record why no new contract is created. All are constrained to Turn-1 norms (`docs/turns-ritmo.md`).

---

## R1 — How to serve the console under one origin that also forwards the backend

**Decision**: Package the built SPA (`src/frontend/dist`) into a container that runs a reverse
proxy serving the static assets and forwarding requests on the default relative API path
(`/api/v1`) to the `api` service by its compose service name. Use **Nginx** as the Turn-1 proxy.

**Rationale**:
- The console client already defaults to the relative base `/api/v1` when `VITE_API_BASE_URL` is
  unset (`src/frontend/src/api/client.ts`: `resolveBaseUrl()`). Same-origin serving therefore needs
  no code change and no CORS configuration, satisfying FR-011 directly.
- The constitution names the frontend as "built static files behind a reverse proxy
  (Nginx/Traefik)". Nginx is the simpler of the two for a single static site plus one upstream
  proxy pass, and it serves static assets and adds response headers without extra components — the
  least machinery that meets FR-009/FR-011/FR-012.
- A reverse proxy keeps the browser talking to one origin while the backend stays a separate service
  (Principle V service split preserved).

**Alternatives considered**:
- *Traefik*: label-driven routing is convenient for many dynamic services but is heavier than needed
  for one static site and one upstream; its value (service discovery, ACME) targets later turns.
- *Serve static assets from FastAPI (`StaticFiles`)*: collapses the service split, puts the web on
  the backend process, and muddies Principle V; rejected.
- *CORS from a dev server / separate origin*: the spec makes cross-origin explicitly out of scope and
  same-origin the default (Assumptions); rejected for Turn 1.

---

## R2 — Whether this story defines any interface contract

**Decision**: Create **no** new contract and no `contracts/` directory for this feature. The
existing read contract `contracts/read/corridor_now.schema.json` and
`contracts/read/source_status.schema.json` at **version 1.0.0** is the authority and is consumed
unchanged. Pin the consumer's expectation to `schema_version == "1.0.0"` (already enforced by
`client.ts` `EXPECTED_SCHEMA_VERSION`).

**Rationale**:
- FR-013 forbids introducing any new data contract; FR-014 requires the live backend to match
  v1.0.0 and mandates stop-and-request-a-decision on any mismatch rather than editing the contract
  or generated types. Generating a contract here would contradict the spec and Principle II's
  "define before implementation" (there is nothing new to define).
- The plan prompt says to create `contracts/` only if the project exposes a *new* interface; this
  story exposes none.

**Alternatives considered**:
- *Re-emit the v1.0.0 schema into the feature's `contracts/`*: duplicates the single source of truth
  and risks drift; rejected. Reference the repo-root `contracts/read/` instead.

---

## R3 — Security hardening of the shipped console image (non-root, headers, minimal content)

**Decision**: Build the console with a multi-stage Dockerfile: a Node build stage runs
`npm ci` + `npm run build`, and a final runtime stage contains only the reverse proxy plus the
built `dist/` assets, running as **non-root UID 10001**. The proxy sends the four mandatory security
headers and omits stack-revealing ones:
- `Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none';`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- remove/hide `Server`, `X-Powered-By` and any version-revealing headers.

**Rationale**:
- Mirrors the proven backend image pattern (root `Dockerfile`: UID/GID 10001, `USER appuser`,
  multi-stage, pinned base) so the console meets the same Turn-1 baseline without inventing a new
  one.
- The header set is taken verbatim from `security.md` A02 and the constitution's Infrastructure
  norm, satisfying FR-012 and SC-005. A multi-stage build leaves no Node runtime, source or
  `node_modules` in the shipped image, satisfying FR-009.
- CSP `script-src 'self'` is compatible with a Vite production build (hashed asset files, no inline
  scripts by default); confirm no inline script/style is emitted, else add hashed/nonce allowances —
  flagged as a validation step in `quickstart.md`, not a contract change.

**Alternatives considered**:
- *Single-stage image with Node present*: ships the build runtime and source tree, violating FR-009;
  rejected.
- *Root user*: violates FR-010 and `security.md` A02; rejected.
- *Pin the base proxy image loosely (`nginx:latest`)*: breaks reproducibility; pin to an exact patch
  tag like the Python base (feature 003 R17). Adopted: exact pin.

---

## R4 — Startup ordering and health gating across the five services

**Decision**: Give the `frontend` service a `healthcheck` and make it start only after `api` reports
healthy, using compose `depends_on: { api: { condition: service_healthy } }`. Keep every existing
dependency as-is: `ingestion`, `api` and `refresh` each depend only on `db` healthy; nothing depends
on `ingestion`. The `frontend` healthcheck probes the proxy's local served index (HTTP 200), not the
backend, so a backend blip does not flap the frontend container.

**Rationale**:
- FR-002 requires each service to report health and the console to start only after the backend is
  healthy. `depends_on: service_healthy` is the compose-native mechanism, already used by `api`,
  `ingestion` and `refresh` against `db`.
- Probing the proxy locally (not the upstream) keeps FR-008's runtime behavior — a mid-session
  backend outage shows a non-blocking stale indicator in the UI — separate from container health,
  so the browser recovers without a container restart (the recovery logic lives in the console's
  polling hook, unchanged).
- Principle III isolation is preserved: adding `frontend → api` ordering does not add any
  dependency onto `ingestion`.

**Alternatives considered**:
- *No frontend healthcheck*: fails FR-002's "each started service MUST report a health status";
  rejected.
- *Frontend healthcheck that probes the backend through the proxy*: couples frontend container
  health to backend availability and would flap on the deliberate interruption test (FR-008/SC-004);
  rejected.

---

## R5 — Which data drives the end-to-end validation

**Decision**: Drive validation with the existing simulator/gold path for corridor C6-008
(`REFRESH_CLOCK=data`, the committed default in `.env.example`), reusing the five validation cases
the console story already defines. Map each spec case to an observable outcome in `quickstart.md`:
live snapshot render, ~5 s refresh, estimated source (no alert), no-data state, and backend
interruption + self-recovery.

**Rationale**:
- Spec Assumptions state gold/simulator data producing C6-008 snapshots is available and that the
  five cases are inherited target behavior. The compose `ingestion` + `refresh` services already
  produce gold snapshots the `api` reads; no new data tooling is needed.
- The estimated-source and no-data cases already have contract fixtures
  (`contracts/read/fixtures/d1_source_outage/`, `.../normal/`) that match what the live backend
  emits, so the validator can compare live output shape against the committed v1.0.0 fixtures
  (supports FR-014/SC-007 drift check) without adding mocks to the request path (FR-003).

**Alternatives considered**:
- *Inject mock fixtures into the browser for the demo*: violates FR-003 (no mock fixtures in the
  request path) and SC-002; rejected. Mock mode (`dev:mock`) stays a dev-only affordance, excluded
  from the shipped image and the validation path.

---

## R6 — Documentation reconciliation scope

**Decision**: Reconcile the README first (full integrated run instructions, env settings including
the console API base / same-origin proxy default, service ports, health checks, how to open the
console against the real backend), then correct stale "no frontend yet" statements in project docs
and agent context (README, docs, AGENTS.md). Treat this as documentation reconciliation only — no
normative or governing-document change.

**Rationale**:
- FR-016/FR-017 and SC-006 require the README and docs to match what actually ships (five services,
  a real `src/frontend`, one-command start). AGENTS.md currently says "there is no frontend code
  yet" and "no frontend yet", which the delivered setup contradicts.
- Reconciling AGENTS.md's factual statement about the tree is a doc fix, not a constitution
  amendment; the constitution and turn map already anticipate the `src/frontend` service.

**Alternatives considered**:
- *Leave AGENTS.md untouched*: fails FR-017/SC-006 ("finds no documentation claiming the frontend
  does not exist"); rejected. (The plan command itself writes only under `specs/`; the AGENTS.md and
  README edits are implementation tasks, surfaced here and scheduled in `/speckit.tasks`.)

---

## Resolved unknowns summary

| # | Topic | Decision |
|---|-------|----------|
| R1 | Same-origin serving | Nginx reverse proxy: static `dist/` + `/api/v1` proxy_pass to `api` |
| R2 | New contract? | None; consume `contracts/read/*` v1.0.0 unchanged, stop-and-decide on drift |
| R3 | Image hardening | Multi-stage build, non-root UID 10001, assets-only, mandatory headers, pinned base |
| R4 | Startup/health | `frontend` healthcheck + `depends_on api: service_healthy`; ingestion isolation kept |
| R5 | Validation data | Existing simulator/gold C6-008 (`REFRESH_CLOCK=data`), no mocks in the path |
| R6 | Docs | README-first reconciliation; remove stale "no frontend yet" statements |

No `NEEDS CLARIFICATION` remains. Proceed to Phase 1.
