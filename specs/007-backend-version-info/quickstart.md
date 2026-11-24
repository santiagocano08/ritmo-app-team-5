# Quickstart: Backend Version/Build Info Endpoint

Feature: `007-backend-version-info`

A validation/run guide proving the endpoint works end to end. It references the contract and data model rather than restating them; implementation code belongs to `/speckit.tasks` and the build phase.

- Contract: [`contracts/version-info.openapi.yaml`](./contracts/version-info.openapi.yaml)
- Response shape: [`data-model.md`](./data-model.md)
- Decisions: [`research.md`](./research.md)

## Prerequisites

- Python 3.12+ with the backend dependencies installed (FastAPI, Pydantic V2, Uvicorn, pytest) — the existing backend environment.
- The repo checked out on branch `007-backend-version-info`.
- No database required: the endpoint reads no data store (FR-006).

## Run the backend

From the repo root:

```bash
uvicorn src.api.main:app --reload --port 8000
```

Optionally set a source revision before starting (otherwise it reports `unknown`):

```bash
APP_REVISION="$(git rev-parse --short HEAD)" uvicorn src.api.main:app --port 8000
```

## Validation scenarios

### Scenario 1 — Running build reports all three fields (FR-001, FR-002, SC-001, SC-002)

```bash
curl -s http://localhost:8000/api/v1/version
```

Expected: HTTP 200 with exactly three keys and no others:

```json
{
  "app_version": "0.1.0",
  "read_contract_version": "1.0.0",
  "source_revision": "a1b2c3d"
}
```

Pass when: `read_contract_version` is `1.0.0`; `app_version` is non-empty; the body has no field beyond the three defined ones.

### Scenario 2 — No source revision falls back to `unknown` (FR-004, SC-003)

Start the backend with `APP_REVISION` unset or empty, then:

```bash
curl -s http://localhost:8000/api/v1/version
```

Expected: HTTP 200 with `"source_revision": "unknown"` and the request still succeeds.

### Scenario 3 — No data-store access (FR-006, SC-004)

Stop PostgreSQL (or point the backend at no DB) and request the endpoint again:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/version
```

Expected: `200`. The endpoint succeeds with the database down, demonstrating it performs no DB/cache read. The automated integration test additionally asserts no DB connection dependency is invoked while serving the route.

### Scenario 4 — Documented in OpenAPI (FR-009)

```bash
curl -s http://localhost:8000/openapi.json | grep -o '/api/v1/version'
```

Expected: the path `/api/v1/version` is present, with a `VersionInfo` response schema, so a client can be generated from it.

### Scenario 5 — Errors stay generic with a correlation id (FR-008, SC-005)

A 500 can only arise from an unexpected internal failure; it is served by the existing global handler, not the endpoint. Confirm the shape with the existing handler's contract: any 500 returns `{"error": "internal_server_error", "correlation_id": "<uuid>"}` and never a stack trace, file path, or internal structure.

## Automated checks (Gate 1 / Gate 2, Turn 1)

Run the backend test suite covering this feature:

```bash
pytest src/api/tests -q
```

The suite must include:
- **Unit** (`test_version_metadata.py`): the build-metadata reader returns the env revision when set and `unknown` when unset/empty; the read-contract constant is `1.0.0`.
- **Contract** (`test_version_contract.py`): the 200 response matches the fixed shape — exactly the three fields, no extras (`extra="forbid"`).
- **Integration** (`test_version_endpoint.py`): `GET /api/v1/version` returns 200 and the three fields; no database connection/dependency is used while serving the request.

Pass criteria for the gates:
- Coverage of the new code keeps total backend coverage > 80 % (Gate 2).
- Response-shape / Pydantic validation passes (Gate 1, Turn-1 subset).

## Out of scope (evolution)

Not validated here and deferred per `docs/turns-ritmo.md`: authentication/RBAC on the endpoint (Turn 2), full SAST/SCA in CI (Turn 2), surfacing the version in the dispatcher console (separate story), and readiness/dependency-health checks (liveness stays on `/healthz`).
