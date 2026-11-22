# Implementation Plan: US-05 — Backend Read API for Live Corridor State

**Branch**: `004-backend-read-api` | **Date**: 2026-11-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-backend-read-api/spec.md`

## Summary

Expose the existing gold-layer read objects for corridor C6-008 as two read-only
HTTP endpoints so the dispatcher console and other read clients can see reliable
live fleet state:

- `GET /api/v1/corridor/{corridor_id}/now` → latest `corridor_now` v1.0.0 snapshot.
- `GET /api/v1/corridor/{corridor_id}/source-status` → latest `source_status` v1.0.0.

Technical approach: add a thin read layer to the existing FastAPI app
(`src/api/main.py`). Each request resolves the latest snapshot once (data-contract
Q0: `ORDER BY as_of_ts DESC, max_bronze_id DESC LIMIT 1`) and then reads the
pre-built contract document straight out of the gold JSONB column
(`gold.corridor_now.doc` / `gold.source_status.doc`, Q1/Q2). The gold documents are
already validated against the approved contracts by the data pipeline, so the API
does not recompute any business rule — it serves what gold produced. Access is
polling-only; no WebSocket/SSE, no RBAC/JWT, no history/pagination (all deferred by
the turn map). Database access is psycopg 3 with parameterized SQL injected via
FastAPI `Depends()`. This is a read-only consumer of the data contract, so it adds
**no contract impact** (no new or changed field; see data-model.md).

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: FastAPI, Pydantic V2, psycopg 3 (with `dict_row`). Reuses
the generated read models `src/pulsoflota/models/read/{corridor_now,source_status}.py`.

**Storage**: PostgreSQL (gold schema, read-only SELECT). SQLite is not used by this
feature; the gold JSONB read objects are a PostgreSQL concern.

**Testing**: pytest — contract tests (response validates against the approved JSON
Schemas), integration tests against a gold-seeded template DB (reusing
`src/data/tests/` fixtures: healthy, `d1_source_outage`, no-data), unit tests for
the latest-snapshot resolver and error/no-data mapping. Coverage > 80 % (Gate 2).

**Target Platform**: Linux server container (`pulsoflota-backend` service in
`docker-compose`), behind a reverse proxy.

**Project Type**: Web service (backend REST API). Frontend is a separate service and
is out of scope for this feature.

**Performance Goals**: Not a real-time-critical path. Polling read; two small point
reads per request (latest snapshot + one gold doc). No throughput/latency SLO is
adopted for the read API in Turn 1 (the ≤ 2 s map refresh and ingestion SLOs are
deferred — see turn map).

**Constraints**:
- Read-only against gold; MUST NOT write or modify bronze/silver/gold (FR-005).
- Responses expose only contract-defined fields, `extra="forbid"` (FR-003/FR-004).
- Errors return a generic body with a `correlation_id`, no stack trace / file path /
  internal store detail (FR-007). Already provided by the app's exception handler.
- "No data" is a well-formed, distinguishable response, not an opaque failure (FR-008).
- psycopg 3 parameterized SQL only; no ORM, no string-built SQL.

**Scale/Scope**: One corridor (C6-008), direction 1, latest snapshot only. Two
endpoints. Turn 1 exercise fleet (5 + 2 buses).

## Active Turn & Scope

Per `docs/turns-ritmo.md` (v0.1.3), **Turn 1 — Data and minimal loop** is active.
This feature adopts only Turn-1 norms:

- The 5 NON-NEGOTIABLE Core Principles.
- Error responses without stack traces; parameterized queries; no secrets in repo
  (the no-cost security baseline).
- Gate 1 (Pydantic schema validation of the served contract) and Gate 2 (unit +
  integration tests, coverage > 80 %).
- Frontend/backend split: this is backend-only; the frontend consuming it is a
  separate story.

### Evolution (deferred — NOT designed here)

These are recorded as evolution and MUST NOT block this feature:

- **RBAC / JWT / RS256 cookies / MFA / IDOR 403** (Turn 2). The endpoints are
  read-only and expose no per-user or per-tenant sensitive data in Turn 1.
- **Real-time push** via WebSocket/SSE and the `LISTEN gold_snapshot` flow (Turn 3);
  Turn 1 is polling-only.
- **Security headers, SAST/SCA image scan, Redis** (Turns 2/3).
- **History, filtering, pagination, rate limiting, caching headers** (not in any
  Turn-1 scope for this story; FR-010).
- **Freshness SLO / error-budget and `age_s` staleness gating** (Turn 3). Turn 1
  serves the latest snapshot as-is; the `source_status.status` field already carries
  the live/estimated/no_data signal.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution v1.4.0, scoped to Turn-1 adopted norms.

| Principle / Gate | Applies in Turn 1 | Status | Notes |
|---|---|---|---|
| I. Risk-First Order | Yes | PASS | Feature sits on top of the already-mitigated Turn-1 data-integrity work; it starts no adaptive-lane work and introduces no unmitigated Level-1 risk. Read-only, no write path. |
| II. Contract-First & Data Ownership | Yes | PASS | Serves the already-approved `corridor_now`/`source_status` v1.0.0 contracts via the generated Pydantic models. **No contract change.** No new persisted model. Data-owner review still applies if anything under `contracts/` changes (it will not). |
| III. Isolated Ingestion & Deterministic Real Time | Yes | PASS | The read API is a separate concern from ingestion; it only SELECTs from gold and never touches the ingestion container or the critical path. No LLM / synchronous external call anywhere. |
| IV. Human-in-the-Loop | Yes (vacuous) | PASS | Read-only: issues no recommendation and no on-road action. No autonomy introduced. |
| V. Test-First & Automated Gates | Yes | PASS (planned) | Contract + integration + unit tests planned; coverage > 80 %; Gate 1 schema validation and Gate 2 CI are satisfied by the test plan. |
| Gate 1 — Contract & Static Analysis | Yes | PASS (planned) | Served responses validated against JSON Schema; Bandit-clean (parameterized SQL, no secrets). |
| Gate 2 — Integration & Supply Chain | Yes | PASS (planned) | pytest + coverage in `backend-ci`. No new dependency added. |
| Gate 3 — Data Gate (DataOps) | Deferred/ingestion-only | N/A | Not an ingestion feature; no packet validation path. |
| Gate 4 — Value & Operational Safety | Turn close (human) | N/A here | No recommendation/diversion; dispatcher value validated at turn close, not a per-PR gate for a read endpoint. |

**Security notes (Turn-1 baseline, enforced):**
- A05 injection: psycopg 3 parameterized SQL only, DSN injected via `Depends()`.
- A10 errors: generic body + `correlation_id`; existing global handler reused; the
  "no data" path returns a well-formed typed body, never a 500.
- No secrets in code; DSN from `DATABASE_URL` (existing `config.get_db_dsn()`).

**Result: PASS — no unjustified violations. Complexity Tracking table is empty.**

## Data Contract Impact

Per the data-owner rule (`.kiro/steering/data-contracts.md`): this feature is a
read-only consumer. It affects **no** silver/gold table, metric, rule, decision
model, command event, reference data or simulator. It reads the existing gold
objects through their approved schemas. **No contract impact; no version bump; no
new field.** The query shapes it depends on (Q0, Q1, Q2) are documented in
`docs/data-contract.md` §3 and are unchanged. See `research.md` R1 and `data-model.md`.

## Project Structure

### Documentation (this feature)

```text
specs/004-backend-read-api/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI for the two read endpoints)
│   └── read-api.openapi.yaml
└── tasks.md             # /speckit.tasks output (NOT created here)
```

### Source Code (repository root)

Current Turn-1 backend tree is `src/api/` (FastAPI app) + `src/pulsoflota/` (shared
DB/config/models); the target `src/backend/` reorganization is deferred per AGENTS.md
and the turn map, so this feature stays in the current tree.

```text
src/
├── api/
│   ├── main.py                  # existing app; mount the v1 corridor router
│   ├── deps.py                  # NEW: DB connection dependency (Depends)
│   └── routers/
│       ├── __init__.py          # NEW
│       └── corridor_read.py     # NEW: the two read endpoints + response wiring
├── pulsoflota/
│   ├── db.py                    # existing psycopg 3 helper (reused)
│   ├── config.py                # existing get_db_dsn() (reused)
│   └── models/read/
│       ├── corridor_now.py      # existing generated model (reused, unchanged)
│       └── source_status.py     # existing generated model (reused, unchanged)
└── api/reads/                   # NEW: gold read queries (Q0/Q1/Q2) as parameterized SQL
    └── gold_reads.py            # latest-snapshot resolver + per-object fetch

src/api/tests/                   # NEW test package for the API (or src/data/tests mirror)
├── contract/
│   └── test_read_api_contract.py     # response validates against JSON Schema
├── integration/
│   └── test_read_api_endpoints.py    # healthy / d1_source_outage / no-data against gold
└── unit/
    └── test_latest_snapshot_resolver.py
```

**Structure Decision**: Extend the existing FastAPI app in `src/api/` with a
versioned router (`/api/v1`) and a small gold-read module, reusing the existing
psycopg 3 helper, config and generated read models. No move to `src/backend/` (that
reorg is deferred). Exact test package placement (`src/api/tests/` vs a mirror under
`src/data/tests/`) is settled in research R5.

## Complexity Tracking

> No Constitution Check violations. Table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
