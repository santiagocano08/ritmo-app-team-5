# Quickstart & Validation: US-05 — Backend Read API

A validation/run guide that proves the two read endpoints work end to end against a
gold-seeded database. No implementation code here; see `plan.md`, `data-model.md` and
`contracts/read-api.openapi.yaml`.

## Prerequisites

- Docker + `docker-compose` (the Turn-1 stack: PostgreSQL, simulator/ingestion,
  `pulsoflota-backend`).
- `DATABASE_URL` set in `.env` (copy from `.env.example`, set `POSTGRES_PASSWORD`).
- A populated gold layer: run the simulator/refresh cycle at least once so
  `gold.snapshots`, `gold.corridor_now` and `gold.source_status` have rows. Seed 42
  with ~20 simulated minutes reproduces the example outputs in
  `docs/data-contract.md` §3.

## Run the stack

```bash
docker-compose up -d database ingestion backend
# wait for the healthcheck, then confirm the API is live:
curl -s http://localhost:8000/healthz
# → {"status":"healthy"}
```

## Scenario 1 — Latest corridor state (US-05.1, FR-001/003/010, SC-001/002)

```bash
curl -s http://localhost:8000/api/v1/corridor/C6-008/now | jq .
```

Expected: a body matching `contracts/read/corridor_now.schema.json` v1.0.0 —
`schema_version: "1.0.0"`, a `snapshot_id`, `corridor_id: "C6-008"`, `direction: 1`,
`buses` ordered leader first, and a `summary`. **No field outside the contract.**

Validate it conforms (the contract test does this automatically; manual check):

```bash
curl -s http://localhost:8000/api/v1/corridor/C6-008/now > /tmp/now.json
python -c "import json,jsonschema; \
  s=json.load(open('contracts/read/corridor_now.schema.json')); \
  jsonschema.validate(json.load(open('/tmp/now.json')), s); print('valid')"
```

## Scenario 2 — Source status and a stale bus (US-05.2, FR-002/004/006, SC-003)

```bash
curl -s http://localhost:8000/api/v1/corridor/C6-008/source-status | jq .
```

Expected (all buses healthy): `status: "live"`, `sources_down: []`.

To exercise the stale case, replay the `d1_source_outage` fixture (a bus silent
> 2 min). Expected: `status: "estimated"`, the stale bus present in `sources_down`
with its `since` timestamp, and **no alert implied** by the response.

## Scenario 3 — No data (edge case, FR-008)

With an empty gold layer (fresh DB, no snapshot yet):

```bash
curl -s http://localhost:8000/api/v1/corridor/C6-008/now            # → 200 {"status":"no_data","corridor_id":"C6-008"}
curl -s http://localhost:8000/api/v1/corridor/C6-008/source-status  # → 200 {"status":"no_data","corridor_id":"C6-008","sources_down":[]}
```

Both return HTTP 200 with a distinguishable no-data body, never a 500 or a malformed
response.

## Scenario 4 — Error safety (FR-007, SC-004)

Force an internal failure (e.g. stop the database while the backend runs) and request
an endpoint:

```bash
curl -s -o /tmp/err.json -w "%{http_code}\n" http://localhost:8000/api/v1/corridor/C6-008/now
cat /tmp/err.json   # → {"error":"internal_server_error","correlation_id":"<uuid>"}
```

Expected: HTTP 500 with a generic body carrying a `correlation_id`. **No stack trace,
file path or PostgreSQL detail** in the body. The matching `correlation_id` appears in
the backend logs.

## Scenario 5 — Typed client generation (SC-005)

```bash
curl -s http://localhost:8000/openapi.json > /tmp/openapi.json
# generate a typed client (illustrative):
npx openapi-typescript /tmp/openapi.json -o /tmp/client.d.ts
```

Expected: a client developer can generate types for both endpoints from the published
OpenAPI without inspecting server internals or guessing field names.

## Automated gates (CI — Gate 1 & Gate 2)

```bash
# contract + integration + unit tests for the read API
pytest src/api/tests -q
# full suite with coverage (> 80 % required)
pytest --cov=src --cov-report=term-missing
```

- **Gate 1**: responses validate against the JSON Schemas; Bandit clean (parameterized
  SQL only, no secrets).
- **Gate 2**: `backend-ci` runs ruff, mypy, Bandit, pytest + coverage > 80 %.

## Pass criteria

- [ ] Scenario 1 returns a schema-valid `corridor_now` v1.0.0 body (SC-002).
- [ ] Scenario 2 reports `estimated` and names the stale bus with no alert (SC-003).
- [ ] Scenario 3 returns the distinguishable 200 no-data body (FR-008).
- [ ] Scenario 4 returns a generic error + `correlation_id`, no leakage (SC-004).
- [ ] Scenario 5 generates a typed client from the OpenAPI (SC-005).
- [ ] No endpoint writes to any table (FR-005); bronze untouched.
- [ ] Coverage > 80 % and `backend-ci` green (Gate 2).
