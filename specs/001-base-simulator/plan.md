# Implementation Plan: Turn-1 Run Environment and Base Simulator

**Branch**: `001-base-simulator` | **Date**: 2026-11-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-base-simulator/spec.md`

## Summary

This story builds the turn-1 backbone: a reproducible, curated reference-data
set for corridor C6-008 (direction 1, 5+2 buses, 5 s step); an isolated
three-container run environment (PostgreSQL, simulator/ingestion, health-only
API); a contract-validated ingestion path that lands valid events in immutable,
insert-only bronze and rejects/dedupes the rest; and a deterministic base
simulator whose events feed US-01. It directly mitigates the turn-1 Level 1 risk
(data integrity) and enforces Contract-First and isolated ingestion from the
first turn.

**Approach** (from `research.md`): Python 3.12 with `uv`; PostgreSQL 16 with
plain SQL init scripts; psycopg 3 with parameterized SQL (no ORM, no Alembic);
Pydantic V2 models **generated** from `contracts/turn1-events/` with
`datamodel-code-generator`; pytest with coverage > 80 %; a single Makefile.
Build order: reference data → run environment → ingestion into bronze → base
simulator. Kept light for a 4–5 hour human-review window and the 2026-11-24
workshop.

## Technical Context

**Language/Version**: Python 3.12+.

**Primary Dependencies**: `psycopg` 3 (binary), `pydantic` V2, `fastapi` +
`uvicorn` (API health only), `datamodel-code-generator` (dev, generates the
contract models), `pytest` + `pytest-cov`. Managed by `uv` (one `pyproject.toml`
+ `uv.lock`). Optional: `numpy` only if lognormal is awkward in pure stdlib
(default is pure-`random`).

**Storage**: PostgreSQL 16 only. Schemas `bronze` (insert-only `events` +
`rejections`), and `silver`/`gold` created empty for forward compatibility.
Reference data lives as files under `data/reference/` (<1 MB), consumed by the
simulator. No Redis, no PostGIS, no Alembic.

**Testing**: `pytest` + `pytest-cov`, coverage > 80 %. Tiers: `tests/contract/`
(contract examples), `tests/unit/`, `tests/integration/`. Contract examples in
`contracts/turn1-events/examples/` are the fixtures.

**Target Platform**: Linux containers via `docker-compose` (three services).
Developers on macOS/Linux.

**Project Type**: web-service backend (modular monolith precursor) — three
containers: `db`, `ingestion` (simulator + ingestion), `api` (health only).

**Performance Goals**: none in turn 1. The exercise fleet (5 + 2 buses, 5 s step)
is in scope; 1,000 events/s and P99 ≤ 500 ms are deferred (turn 3).

**Constraints**: deterministic simulator (same seed → byte-identical output);
bronze insert-only and idempotent on `source` + `event_id`; ingestion survives
the API being down (Principle III); reference data <1 MB and byte-identical on
rebuild; peak-hour trip ≈ 25 min ±20 %.

**Scale/Scope**: ~7 buses, 17 corridor segments, 5 s step, single direction.
No map, no metrics, no recommendations, no security turn-2 norms. Built to close
the turn-1 loop and ground the workshop.

> All `NEEDS CLARIFICATION` items are resolved in `research.md` (R1–R20).

## Constitution Check

*GATE: evaluated before Phase 0; re-checked after Phase 1 design.*

Constitution v1.1.0; turn 1 active per `docs/turns-ritmo.md` §3. The 5
NON-NEGOTIABLE Core Principles apply in every turn; the technical/security norms
and gates are adopted incrementally — only the turn-1 set is mandatory here.

| Principle | Status | Evidence |
|---|---|---|
| **I. Risk-First Order** | PASS | This story *is* the turn-1 Level 1 risk (data integrity). No adaptive-lane work starts before it. `docs/turns-ritmo.md` orders turn 1 first. |
| **II. Contract-First & Data Ownership** | PASS | The accepted contract `contracts/turn1-events/` v1.0.0 (ADR-0001/0002) is authoritative. Pydantic V2 models are **generated** from it (R3); no invented fields. Every event is validated at the boundary; bronze has an owning module. |
| **III. Isolated Ingestion & Deterministic Real Time** | PASS | Three separate containers; `ingestion` writes directly to bronze and keeps writing when `api` is down (FR-010, US-2). No Redis, no broker, no generative-AI or synchronous third-party calls on the path (the simulator→ingestion pipe is local and deterministic). |
| **IV. Unbreakable Human Gate** | N/A (no violation) | This story produces raw inputs only — no recommendations, no decisions, no on-road actions. The human gate has nothing to gate yet; nothing autonomous runs. |
| **V. Test-First & Automated Gates** | PASS | pytest with coverage > 80 %; contract tests use the contract examples; bronze immutability and isolation are integration-tested. Turn-1 gates only (Gate 1 schema, Gate 2 tests+coverage). |

**Turn-1 adopted norms** (`docs/turns-ritmo.md` §3.2):

- RNF-3.2.1/3.2.2 (Docker + docker-compose, ingestion isolated) — PASS: three
  services, ingestion isolated from `api`.
- RNF-3.3.1 (boundary validation; reject 100 % without a valid schema) — PASS:
  generated Pydantic V2 models with `extra='forbid'`; invalid → `422`-style
  rejection in `bronze.rejections`.
- Gate 1 (Pydantic schema validation only; no SAST in turn 1) — PASS.
- Gate 2 (unit + integration tests, coverage > 80 %; no SCA in turn 1) — PASS.
- Gate 4 (explicit dispatcher approval) — N/A (no recommendations in this story).
- No-cost security baseline — PASS: parameterized queries (R2), no secrets in
  the repository, error responses without stack traces.

**Deferred norms (Evolution — NOT blocking)**: Redis/`database-redis`,
PostGIS/geometry/TimescaleDB, 1,000 events/s, P99 ≤ 500 ms, SAST (Bandit), SCA
(pip-audit/Trivy), RBAC/JWT/MFA, mTLS, HMAC, secret manager, security headers,
silver/gold metrics, scenario injectors, decision engine, route diversion
(US-03), the web console. Recorded in `research.md` §Evolution and in each
contract's "Non-goals".

**Post-design re-check**: the Phase 1 artifacts (`data-model.md`,
`contracts/*`, `quickstart.md`) do not introduce any deferred norm as a
requirement and do not weaken a Core Principle. Bronze immutability + idempotency
are enforced by the unique constraint and tested; the simulator stays off the
persistence path (determinism is testable without a DB). **No violations.**
No Complexity Tracking entries are needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-base-simulator/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (interface contracts)
│   ├── README.md
│   ├── ingestion-boundary.md
│   ├── api-health.md
│   ├── reference-data-files.md
│   └── simulator-cli.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
pyproject.toml              # uv project: python >=3.12, deps + dev split, uv.lock
Makefile                    # generate | reference | up | down | test | lint | clean
docker-compose.yml          # services: db (postgres:16), ingestion (sim|ingest), api (fastapi)

src/
├── pulsoflota/             # shared library
│   ├── __init__.py
│   ├── config.py           # env-driven config (DB DSN, log level) — no secrets in repo
│   ├── db.py               # psycopg 3 connection helpers (parameterized SQL)
│   └── models/             # GENERATED Pydantic V2 models (datamodel-codegen) — do not edit
│       ├── __init__.py
│       └── turn1_events.py
├── reference/              # US-1 reference data build
│   ├── __init__.py
│   ├── build.py            # data/raw/ -> data/reference/ (deterministic, <1 MB)
│   └── sources.py          # source registry -> SOURCES.md
├── ingestion/              # US-3 ingestion service (boundary -> bronze)
│   ├── __init__.py
│   ├── validate.py         # envelope validation -> (ok | reason)  (deterministic, R12)
│   ├── bronze.py           # insert-only write + idempotency (source + event_id)
│   └── run.py              # entry: consume JSON-lines -> validate -> bronze
├── simulator/              # US-4 base simulator
│   ├── __init__.py
│   ├── model.py            # fleet, trip, segments, dwell, demand
│   ├── engine.py           # 5 s step, single seeded RNG, deterministic
│   └── main.py             # CLI: --seed S --duration D -> JSON-lines envelopes on stdout
└── api/                    # US-2 minimal API (health only)
    ├── __init__.py
    └── main.py             # FastAPI: GET /healthz -> {"status":"healthy"}

db/
└── init/                   # plain SQL init scripts (no Alembic), idempotent
    ├── 001_schemas.sql     # CREATE SCHEMA bronze, silver, gold
    ├── 002_bronze.sql      # bronze.events (insert-only) + bronze.rejections + UNIQUE(source,event_id)
    └── 003_reference.sql   # (optional) reference tables — see data-model.md; files are the default

data/
├── raw/                    # git-ignored raw sources (present locally)
└── reference/              # US-1 OUTPUT (built, committed, <1 MB, reproducible)
    ├── segments.csv
    ├── stops.csv
    ├── train_arrivals.csv
    ├── congestion_factor.csv
    ├── demand_params.csv
    └── SOURCES.md

tests/
├── unit/
│   ├── test_reference_build.py
│   ├── test_simulator_determinism.py
│   ├── test_simulator_capacity.py
│   ├── test_simulator_travel_time.py
│   └── test_ingestion_validate.py
├── contract/
│   └── test_contract_examples.py   # valid pass / invalid rejected with reasons
└── integration/
    ├── test_bronze_ingest.py       # valid -> bronze; invalid/dup -> rejections
    ├── test_bronze_immutable.py    # no UPDATE/DELETE across re-ingest
    ├── test_isolation.py           # stop api -> ingestion keeps writing
    └── test_health.py              # GET /healthz -> 200 {"status":"healthy"}
```

**Structure Decision**: a single Python project (one `pyproject.toml`, one
`src/` layout) with three container entry points, because the services share the
generated contract models and the DB layer, and the turn-1 volume is tiny. The
`ingestion` container bundles the simulator and ingestion behind a stdout-pipe
(the simplest deterministic transport that keeps the API off the capture path);
each is independently importable for tests. The authoritative event contract
stays at the repo root `contracts/turn1-events/`; the **generated** Pydantic
models live under `src/pulsoflota/models/` to avoid confusing the two. Reference
data is files (not tables) by default, consumed directly by the simulator; an
optional `003_reference.sql` is noted but not required for turn 1.

## Complexity Tracking

> No Constitution Check violations require justification — this section is
> intentionally empty. The design adds no fourth schema (rejections live in
> `bronze.rejections` per ADR-0001), no ORM, no broker, and no security turn-2
> controls. Deferred norms are recorded as Evolution, not built.

## Phases (executed)

- **Phase 0 — Research**: `research.md` (R1–R20). All `NEEDS CLARIFICATION`
  resolved with the simplest option that honors the constitution and turn scope.
- **Phase 1 — Design & Contracts**: `data-model.md`, `contracts/`
  (`README.md`, `ingestion-boundary.md`, `api-health.md`,
  `reference-data-files.md`, `simulator-cli.md`), `quickstart.md`.
- **Phase 2 — Tasks**: NOT in scope for `/speckit.plan`; produced by
  `/speckit.tasks`.

## Readiness

The plan is ready for `/speckit.tasks`. Open the handoff ("Create Tasks") to
break this into tasks, or run `/speckit.checklist` for a domain checklist.
