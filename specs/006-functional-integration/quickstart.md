# Phase 1 — Quickstart & End-to-End Validation: Functional Integration (Turn-1 Whole)

Feature: `006-functional-integration` · Spec: [spec.md](./spec.md) ·
Plan: [plan.md](./plan.md) · Data model: [data-model.md](./data-model.md)

This is the validation/run guide for the integrated Turn-1 stack. It proves the five services come
up healthy, the console reaches the real backend under one origin, and the five validation cases
(FR-015) behave as specified. It contains no implementation code — the image, proxy config and
compose wiring are built in `/speckit.tasks`.

> Commands assume the repository root. The exact service name (`frontend`) and the proxy config
> directory are fixed in the implementation tasks; adjust if tasks choose different final names.

---

## Prerequisites

- Docker Engine + `docker compose`.
- A `.env` file created from `.env.example` with `POSTGRES_PASSWORD` set (the stack refuses to
  start otherwise). The committed defaults use `REFRESH_CLOCK=data` so the simulator/gold path
  drives corridor C6-008.
- No extra tooling for the demo path: the console loads from the real backend, not from mocks.

## One-command start (FR-001, SC-001)

```bash
cp .env.example .env            # then set POSTGRES_PASSWORD
docker compose up --build       # brings up db, ingestion, refresh, api, frontend
```

**Expected**: five services build/start; after the start-up period all report healthy.

```bash
docker compose ps              # STATUS column shows (healthy) for db, ingestion, refresh, api, frontend
```

Pass criterion (SC-001): 100 % of the five services report healthy. The `frontend` container
reaches a healthy status only after `api` is healthy (FR-002).

---

## Open the console against the real backend

Open the console origin in a browser (the port the `frontend` service publishes; stated in the
README after FR-016 reconciliation, e.g. `http://localhost:8080`).

**Expected**: the page loads from the same origin that also forwards `/api/v1` to the backend. In
the browser network panel, the corridor requests go to the relative path `/api/v1/corridor/C6-008/...`
and are served through the proxy — no cross-origin request, no mock worker (`msw`) in the path
(FR-003, FR-011, SC-002).

---

## The five validation cases (FR-015, SC-004)

### Case 1 — Live snapshot render (FR-004, SC-002)

- **Do**: with the stack healthy, view the console.
- **Expect**: the C6-008 fleet renders ordered leader-first, each bus showing state, headway and
  quality, populated from the live backend. No mock fixtures involved.

### Case 2 — ~5-second auto-refresh (FR-005, SC-003)

- **Do**: watch the console without interacting; observe repeated `/api/v1/corridor/C6-008/now`
  requests in the network panel.
- **Expect**: the displayed state refreshes automatically about every 5 seconds; values advance as
  the simulator/refresh loop commits new snapshots.

### Case 3 — Estimated source, no alert (FR-006)

- **Do**: drive or wait for the source-outage condition so a bus reports an `estimated` source
  (the `d1_source_outage` scenario; see `contracts/read/fixtures/d1_source_outage/source_status.json`
  for the expected shape).
- **Expect**: that bus is labelled "Estimated"; no alert is raised.

### Case 4 — No-data state (FR-007)

- **Do**: query the backend for a corridor with no current snapshot, or observe the console before
  the first gold snapshot exists:

  ```bash
  curl -s http://localhost:8000/api/v1/corridor/C6-008/now | jq .
  # no-snapshot response: {"status":"no_data","corridor_id":"C6-008"}
  ```

- **Expect**: the console shows an explicit no-data state, visibly distinct from an error state.

### Case 5 — Backend interruption and self-recovery (FR-008)

- **Do**: interrupt the backend, then restore it:

  ```bash
  docker compose stop api        # polls begin to fail
  # observe the console
  docker compose start api       # polls succeed again
  ```

- **Expect**: while `api` is down the console shows a non-blocking **stale** indicator (it does not
  crash or blank out); when `api` returns, the console recovers on its own with no page reload. The
  `frontend` and `ingestion` containers stay up throughout.

### Contract-drift check (FR-014, SC-007)

- **Do**: compare the live response shape against the committed v1.0.0 fixtures.

  ```bash
  curl -s http://localhost:8000/api/v1/corridor/C6-008/now | jq .schema_version   # must be "1.0.0"
  ```

- **Expect**: `schema_version` is `1.0.0` and the body validates against
  `contracts/read/corridor_now.schema.json`. On any mismatch: **stop** and raise a contract decision;
  do not edit the contract or the generated types.

---

## Ingestion-isolation check (Principle III)

- **Do**: with the stack up, stop the web layer and confirm ingestion keeps running.

  ```bash
  docker compose stop api frontend
  docker compose ps              # ingestion still (healthy); db still (healthy)
  ```

- **Expect**: `ingestion` is unaffected by stopping `api`/`frontend`. Restart them and the console
  recovers.

---

## Shipped-image inspection (FR-009, FR-010, FR-012, SC-005)

Run against the built console image (no source, no Node runtime inside).

```bash
# 1. Non-root UID 10001
docker compose exec frontend id        # uid=10001 ...  (FR-010)

# 2. Only built static assets — no source, no node_modules, no Node binary
docker compose exec frontend sh -c 'ls -la; command -v node || echo "no node runtime"'   # (FR-009)

# 3. Mandatory security headers present, stack-revealing headers absent
curl -sI http://localhost:8080/        # inspect headers below  (FR-012)
```

**Expected headers present** (verbatim): `Content-Security-Policy: default-src 'self'; script-src
'self'; object-src 'none';`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`,
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` — on both the static index and the
proxied `/api/v1` responses.
**Expected absent**: no `Server` header at all (the Alpine `headers-more` module clears it; the
upstream `uvicorn` banner is hidden by `proxy_hide_header`), no `X-Powered-By`, no FastAPI/Nginx
version string.

Pass criterion (SC-005): non-root, assets-only, all required headers present, zero stack-revealing
headers — no exceptions.

> Note: `dist/mockServiceWorker.js` is present as a static file (emitted by the `msw` package's
> `workerDirectory` config) but is **never registered** — the console starts the mock worker only
> under `VITE_ENABLE_MOCKS=true`, which the shipped image never sets. No mock is in the request path
> (FR-003). `curl` is shown for a human running the checks; inside the container use
> `wget -qO- -S` (the image has `wget`, not `curl`).

---

## Documentation walkthrough (FR-016, FR-017, SC-006)

- **Do**: hand the updated `README.md` to someone unfamiliar with the project and have them follow
  it end to end — configure `.env` (including the console API base / same-origin proxy default),
  run the one-command start, open the console against the real backend.
- **Expect**: they succeed using only the README, with service ports and health checks documented,
  and they find no statement anywhere (README, docs, agent context) claiming the frontend does not
  exist.

---

## Existing automated gates (unchanged, must still pass)

```bash
docker compose --profile tools run --rm tests      # backend pytest + coverage > 80 %
cd src/frontend && npm ci && npm run lint && npm test && npm run build   # frontend-ci equivalents
```

These remain the Turn-1 Gate 1/Gate 2 checks; this story adds the console image build to the
frontend path but changes no test logic.
