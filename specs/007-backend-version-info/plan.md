# Implementation Plan: Backend Version/Build Info Endpoint

**Branch**: `007-backend-version-info` | **Date**: 2026-11-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-backend-version-info/spec.md`

## Summary

Expose one read-only HTTP endpoint on the existing FastAPI backend that reports three build-time facts about the running backend: its application version, the read-contract version it targets (fixed `1.0.0`), and a source-revision identifier (`unknown` when the build captured none). The endpoint queries no database or cache, returns a fixed-shape Pydantic V2 response documented in OpenAPI, and reuses the existing global exception handler (generic body + `correlation_id`). Values come from a single build-time source of truth, not inline literals in the handler. This is a Turn-1, Disciplined-lane diagnostic slice that exercises the full RITMO loop with near-zero risk.

## Technical Context

**Language/Version**: Python 3.12+ (backend), per AGENTS.md / constitution.

**Primary Dependencies**: FastAPI, Pydantic V2, Uvicorn — all already present in the backend (`src/api/`, `src/pulsoflota/`). No new runtime dependency.

**Storage**: None for this feature. The endpoint reads no table, view, cache, or snapshot (FR-006). PostgreSQL remains the project store but is untouched here.

**Testing**: pytest + FastAPI `TestClient`, matching `src/api/tests/` (unit / integration / contract layout already in use).

**Target Platform**: Linux container (`pulsoflota-backend`) behind a reverse proxy, run via `docker-compose` in Turn 1.

**Project Type**: Web service (REST backend). Frontend is out of scope for this story (spec Assumptions).

**Performance Goals**: Not latency-sensitive; this endpoint is off the real-time critical path. A single request returns a small constant JSON body with no I/O.

**Constraints**:
- Read-only, zero data-store access (FR-006, SC-004).
- Fixed response shape, no extra/free-form fields (FR-005, SC-002).
- Values from a single build-time source of truth, not inline (FR-007).
- Errors expose no stack trace/path/internals; carry a `correlation_id` (FR-008, SC-005).
- Unauthenticated in this turn; RBAC/JWT deferred to Turn 2 (FR-010, turn map).

**Scale/Scope**: One endpoint, one response model, one build-time metadata reader. Intended callers: operators and contributors validating the Turn-1 stack (not riders, not the dispatcher UI).

**Source-revision capture (resolved in research, see R1)**: read from an environment variable injected at build/packaging time; absent/empty → `unknown`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution v1.4.0. The 5 Core Principles apply in every turn; other norms apply per the Turn-1 column of `docs/turns-ritmo.md`.

| Principle / Gate | Applies? | Assessment |
|---|---|---|
| **I. Risk-First Order** | Yes | No Level-1 risk introduced. The slice is read-only build metadata with no data-integrity or security surface. Does not start ahead of any unmitigated Level-1 risk. **PASS** |
| **II. Contract-First & Data Ownership** | Yes | A response contract (Pydantic V2 + OpenAPI) is defined before implementation (FR-005, FR-009). Reports the *existing* read-contract version `1.0.0`; defines, alters, implies **no** data contract (FR-003). No silver/gold table, view, metric, or rule is touched → **no `docs/data-contract.md` impact** (data-contracts / data-profile-development rule). **PASS** |
| **III. Isolated Ingestion & Deterministic Real Time** | Yes | Endpoint is off the real-time path, makes no synchronous call to GenAI or third parties, performs no ingestion. **PASS** |
| **IV. Unbreakable Human Gate** | N/A | No AI/automation, no on-road regulation action. Nothing to gate. **PASS (not applicable)** |
| **V. Test-First & Automated Gates** | Yes | Plan prescribes unit + contract + integration tests before implementation; coverage > 80 % (Gate 2). Contract gate = Pydantic/response-shape validation (Gate 1, Turn-1 subset). **PASS** |
| **Gate 1 — Contract & Static Analysis** (Turn 1: Pydantic schema validation) | Yes | Response model validated; `tsc`/ESLint N/A (no frontend change). Full SAST (Bandit/ESLint) deferred to Turn 2. **PASS** |
| **Gate 2 — Integration & Supply Chain** (Turn 1: unit/integration tests, coverage > 80 %) | Yes | Covered by the test plan. SCA/Trivy image scan deferred to Turn 2. **PASS** |
| **Gate 3 — DataOps** | Deferred (Turn 3) | No ingestion path. Recorded as evolution, not a blocking finding. **N/A** |
| **Gate 4 — Value & Operational Safety** | Partial | No diversion/AI. Value hypothesis = diagnostics; validated by the quickstart run. **PASS** |
| **Security — errors/exceptions (A10, Turn-1 no-cost baseline)** | Yes | Reuses the existing generic 500 handler with `correlation_id`; no stack trace/path/internals exposed (FR-008). **PASS** |
| **Security — RBAC/JWT (A01/A07)** | Deferred (Turn 2) | Endpoint is unauthenticated build metadata this turn (FR-010); recorded as evolution. Not a blocking finding in Turn 1. **N/A** |

**Result**: PASS. No unjustified violations. No entries required in Complexity Tracking.

### Evolution (deferred norms, not designed here)

Per the Turn-1 map, these are explicitly out of scope and recorded as evolution rather than designed now:
- **RBAC / JWT / MFA** on the endpoint (Turn 2). The endpoint stays unauthenticated this turn.
- **Full SAST (Bandit/ESLint) and SCA (`pip-audit`, Trivy image scan)** in CI (Turn 2).
- **Surfacing the version in the dispatcher console / frontend** (separate, out-of-scope story).
- **Readiness/dependency-health checks**; liveness remains the existing `/healthz` endpoint.
- **Structured OpenTelemetry JSON logs / SRE alerting** (Turn 2/3).

## Project Structure

### Documentation (this feature)

```text
specs/007-backend-version-info/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI fragment for the endpoint)
│   └── version-info.openapi.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

The feature extends the existing Turn-1 backend tree (`src/api/`, `src/pulsoflota/`) — it does not add a new service. Target `src/backend/` reorganization is future per AGENTS.md and is not performed here.

```text
src/
├── api/
│   ├── main.py                     # existing FastAPI app; include the new router
│   ├── routers/
│   │   ├── corridor_read.py        # existing
│   │   └── version.py              # NEW: GET version endpoint, mounted under /api/v1
│   └── tests/
│       ├── contract/
│       │   └── test_version_contract.py    # NEW: response shape == contract
│       ├── integration/
│       │   └── test_version_endpoint.py    # NEW: route behavior, no DB access
│       └── unit/
│           └── test_version_metadata.py    # NEW: build-metadata reader + unknown fallback
└── pulsoflota/
    ├── config.py                   # existing env-reader module; add source-revision reader
    └── models/
        └── read/
            └── version_info.py     # NEW: Pydantic V2 response model (fixed shape)
```

**Structure Decision**: Reuse the existing Turn-1 backend. The router lives in `src/api/routers/version.py` and is mounted on the existing app via `app.include_router(...)` under the `/api/v1` prefix (matching `corridor_read.py`). The response model lives alongside the other read models in `src/pulsoflota/models/read/`. The build-time values are read through `src/pulsoflota/config.py` (the project's single home for environment-driven configuration), which satisfies "single source of truth, not inline in the handler" (FR-007). No new package, service, or dependency is introduced.

## Complexity Tracking

> No Constitution Check violations. Nothing to justify.
