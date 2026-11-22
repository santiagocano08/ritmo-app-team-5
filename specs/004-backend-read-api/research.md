# Phase 0 Research: US-05 — Backend Read API

All Technical Context items are resolved. The spec left no open `NEEDS
CLARIFICATION`; the research below records the design decisions and the few
implementation choices that needed a call.

## R1 — How the backend obtains the contract documents

**Decision**: Read the already-built contract JSON straight from the gold JSONB
columns. Resolve the latest snapshot once (Q0:
`SELECT snapshot_id ... FROM gold.snapshots ORDER BY as_of_ts DESC, max_bronze_id
DESC LIMIT 1`), then `SELECT doc FROM gold.corridor_now WHERE snapshot_id = %(id)s`
(Q2) and `SELECT doc FROM gold.source_status WHERE snapshot_id = %(id)s` (Q1). Each
endpoint resolves its own latest snapshot (the two endpoints are independent reads
in this story), but within a single response the `snapshot_id` is read once and
reused, per `docs/data-contract.md` §1.3 rule 3.

**Rationale**: The data pipeline already computes and validates each contract
document against the approved schema before storing it (`src/data/pipeline/gold.py`
builds `CorridorNowV100`/`SourceStatusV100` and persists `model_dump(mode="json")`
as JSONB). Re-deriving the objects in the API would duplicate business rules, risk
drift, and violate Principle II (single owning module). Serving `doc` keeps the data
layer the single owner and makes the API a thin, contract-faithful reader.

**Alternatives considered**:
- *Recompute from silver in the API* — rejected: duplicates rules, breaks data
  ownership, and is far more code and risk for no benefit.
- *Add an API-specific SQL view* — rejected: unnecessary; the `doc` column is the
  contract payload already. A view would be a data change requiring data-owner
  review for no gain.

## R2 — Endpoint shape, versioning and the "no data" response

**Decision**:
- `GET /api/v1/corridor/{corridor_id}/now` → 200 with the `corridor_now` v1.0.0 body.
- `GET /api/v1/corridor/{corridor_id}/source-status` → 200 with the `source_status`
  v1.0.0 body.
- Version under `/api/v1` (backend steering rule).
- **No data** (FR-008): when no snapshot exists, return **HTTP 200** with a
  well-formed, clearly distinguishable "no data" body rather than 404 or an error.
  For `source-status`, the contract itself already models this: `status: "no_data"`,
  `sources_down: []`, with `snapshot_id`/`as_of_ts` absent → return a distinct
  `{"status": "no_data", "corridor_id": ...}` envelope (see data-model.md "No-data
  response"). For `corridor_now`, which has no `no_data` enum, return a parallel
  `{"status": "no_data", "corridor_id": ...}` envelope documented in the OpenAPI as a
  distinct response variant. The two shapes are documented in contracts/.

**Rationale**: FR-008 requires a "well-formed, clearly distinguishable" no-data
response, not an opaque failure. `source_status` already has a first-class `no_data`
state in its contract, so we use it. `corridor_now` has no such state, so a sibling
no-data envelope (same `status: no_data` convention) is the least surprising, keeps
the client's handling uniform, and avoids inventing fields inside the `corridor_now`
contract (which would need an ADR). 200 is used because "no snapshot yet" is a normal
startup/empty-feed condition, not a client or server error.

**Alternatives considered**:
- *404 for no data* — rejected: 404 means "route/resource not found"; the corridor
  resource exists, there is simply no snapshot yet. 404 would be ambiguous with a
  mistyped corridor id.
- *Empty `corridor_now` with `buses: []`* — rejected: an empty-bus snapshot is a
  valid live state (night service), so it cannot double as "no data"; the two must be
  distinguishable (edge case in spec).
- *`corridor_id` path vs fixed constant* — path parameter kept for a clean REST shape
  and forward compatibility, but Turn 1 serves only `C6-008`; any other id yields the
  no-data response (there is no other corridor's gold data).

## R3 — Error handling and correlation id (FR-007, A10)

**Decision**: Reuse the existing global `Exception` handler in `src/api/main.py`,
which returns `{"error": "internal_server_error", "correlation_id": <uuid>}` with
status 500 and logs the real error server-side. The read endpoints add no
per-endpoint try/except that could leak detail; any DB/driver error bubbles to this
handler.

**Rationale**: FR-007 and the constitution (A10) forbid exposing stack traces, file
paths or PostgreSQL internals and require a `correlation_id`. The app already
implements exactly this; the feature only needs to not undermine it. This also keeps
SC-004 satisfied with no new code.

**Alternatives considered**:
- *Per-endpoint error formatting* — rejected: duplicates the global handler and risks
  inconsistent bodies.

## R4 — Connection management and dependency injection

**Decision**: Inject a psycopg 3 connection per request via FastAPI `Depends()`
(`src/api/deps.py`), built from `config.get_db_dsn()` and opened with
`psycopg.connect(dsn)` (reusing `src/pulsoflota/db.py`), using `row_factory=dict_row`
for the gold reads. The connection is closed at the end of the request. Reads are
`SELECT`-only and run in the default autocommit-less connection without an explicit
write transaction.

**Rationale**: Matches the coding standard (inject DB via `Depends()`, no global
client) and keeps the API read-only. A simple per-request connection is sufficient
for Turn-1 polling volume; a pool is an evolution item (no SLO adopted for the read
API in Turn 1). Using the existing helper avoids a second DB access style.

**Alternatives considered**:
- *psycopg connection pool* — deferred: not needed at Turn-1 volume; adds lifecycle
  complexity. Can be introduced later without changing the endpoint contract.
- *Shared global connection* — rejected: not safe across concurrent requests and
  against the DI standard.

## R5 — Test placement and fixtures

**Decision**: Place API tests in a new `src/api/tests/` package (`contract/`,
`integration/`, `unit/`) and reuse the existing gold-seeding fixtures and DB template
machinery under `src/data/tests/` (`conftest.py`, `db_helpers.py`, the
`d1_source_outage` and gold fixtures). Contract tests validate each response body
against `contracts/read/{corridor_now,source_status}.schema.json`. Integration tests
cover three states: healthy (`status: live`), source outage (`status: estimated`
with the stale bus in `sources_down`), and no-data (empty gold).

**Rationale**: Keeps API tests next to the API code while not duplicating the DB
fixture harness the data layer already maintains. Validating against the JSON Schema
(not just the Pydantic model) is what proves "only contract fields, nothing extra"
(SC-002) independently of the model.

**Alternatives considered**:
- *Mirror tests under `src/data/tests/`* — acceptable fallback if import paths for
  fixtures are cleaner there; decided at task time. Either keeps coverage in the same
  `backend-ci` run.
- *Mock the DB entirely* — rejected for integration: the value is proving the real
  gold `doc` serves cleanly; unit tests may still mock the resolver for error/no-data
  branches.

## R6 — Polling-only confirmation

**Decision**: No WebSocket/SSE and no `LISTEN gold_snapshot` in this feature. Clients
poll the two endpoints. The `docs/data-contract.md` §4 push flow is noted as Turn-3
evolution.

**Rationale**: The spec and the user's own instruction fix polling for this story;
the turn map defers real-time push to Turn 3 (Principle III deterministic real time
is about ingestion isolation, not about the read API pushing). Keeps scope minimal.

## Summary of resolved unknowns

| Item | Resolution |
|---|---|
| Source of contract bodies | gold `doc` JSONB (R1) |
| Latest-snapshot query | Q0 `ORDER BY as_of_ts DESC, max_bronze_id DESC LIMIT 1` (R1) |
| Endpoint paths / versioning | `/api/v1/corridor/{corridor_id}/{now,source-status}` (R2) |
| No-data behaviour | 200 + distinguishable `status: no_data` envelope (R2) |
| Error body | reuse global handler, `correlation_id`, no leakage (R3) |
| DB access | per-request psycopg 3 conn via `Depends()`, SELECT-only (R4) |
| Tests & fixtures | `src/api/tests/`, reuse data-layer gold fixtures, schema-validate (R5) |
| Transport | polling only; push deferred to Turn 3 (R6) |
