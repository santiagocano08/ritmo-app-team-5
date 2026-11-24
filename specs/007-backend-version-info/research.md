# Phase 0 Research: Backend Version/Build Info Endpoint

Feature: `007-backend-version-info` · Branch `007-backend-version-info`

The Technical Context left one genuine unknown (how the source-revision is captured) plus a few design choices worth recording. Each is resolved below.

## R1 — How the source-revision identifier is captured at build time

**Decision**: Read the source revision from an environment variable (`APP_REVISION`) resolved through `src/pulsoflota/config.py`. The variable is injected at build/packaging time (e.g. a Docker build arg set from the git SHA that becomes an env value in the image). When the variable is unset or empty, the reader returns the literal `unknown`.

**Rationale**:
- Matches the project's existing pattern: `config.py` is already the single home for environment-driven configuration, with helpers that apply safe defaults (`get_log_level`, `get_sim_seed`, etc.). Adding one reader there keeps the "single source of truth, not inline in the handler" requirement (FR-007) satisfied with zero new machinery.
- No new dependency and no filesystem/VCS access at request time, so the endpoint stays read-only and cheap (FR-006).
- Absent-value fallback to `unknown` directly satisfies FR-004 / SC-003 and the "metadata-less builds still succeed" assumption, so local runs without the build arg work.

**Alternatives considered**:
- *Shell out to `git rev-parse` at request time* — rejected: adds process-spawn latency, requires git + the repo inside the runtime image, and fails on a shipped image with no `.git`. Also pulls a subprocess call onto the request path.
- *Read a generated version file baked into the image* — workable but heavier than an env var; it needs a build step that writes the file and a file read at runtime. The env var covers the same need with less surface and reuses the established config pattern.
- *Hard-code the revision in the handler* — rejected: violates FR-007 (single build-time source of truth, not inline).

## R2 — Where the application version comes from

**Decision**: Report the backend application version from a single declared source. Use the version already declared for the FastAPI app / package (`version = "0.1.0"` in `pyproject.toml`, mirrored by `FastAPI(..., version="0.1.0")` in `src/api/main.py`). Expose it through `config.py` / the app metadata rather than re-typing a literal in the version router.

**Rationale**:
- The project already declares `0.1.0` in two places (`pyproject.toml` and `main.py`). Reading from the app/package rather than introducing a third literal keeps one source of truth and avoids drift (FR-007).
- No new dependency; the FastAPI app object already carries `app.version`.

**Alternatives considered**:
- *Independent constant in the version router* — rejected: creates a third place to update and risks drift from `pyproject.toml` / `main.py`.
- *`importlib.metadata.version(...)`* — valid for an installed distribution, but in the Turn-1 source tree the app is run from source; reading the already-declared app version is simpler and deterministic. Can be revisited if packaging changes.

## R3 — Read-contract version value and no-contract-change guarantee

**Decision**: Report the read-contract version as the fixed string `1.0.0`, sourced from a single named constant that states it tracks the existing `corridor_now` / `source_status` read contracts. The feature does **not** add, modify, or imply any JSON Schema under `contracts/` and records "no data-contract impact".

**Rationale**:
- The existing read contracts (`contracts/read/corridor_now.schema.json`, `source_status.schema.json`) pin `schema_version` to `1.0.0` for Turn 1. Reporting the same literal keeps the endpoint a pure mirror of an existing version (FR-003).
- The data-contracts steering and `data-profile-development` rule require stopping and requesting an ADR if a new contract field is needed. This feature needs none: it reads build metadata only, touches no silver/gold table, metric, or rule. Explicitly "no contract impact" per the data-owner rule.

**Alternatives considered**:
- *Derive the read-contract version dynamically from the schema files at runtime* — rejected: adds a file read on the request path and over-engineers a value that is fixed for the whole turn (YAGNI). A single named constant is clearer and deterministic (SC-002 identical repeated responses).

## R4 — Error handling

**Decision**: Add no endpoint-local error handling. Let any unhandled error bubble to the existing global exception handler in `src/api/main.py`, which returns `{"error": "internal_server_error", "correlation_id": <uuid>}` with status 500 and logs the real error server-side.

**Rationale**:
- The handler already exists and already meets FR-008 / SC-005 (generic body, `correlation_id`, no stack trace/path/internals). The spec Assumptions explicitly say to reuse it unchanged. `corridor_read.py` follows the same "no local error handling" convention, so this matches existing practice.

**Alternatives considered**:
- *Custom try/except in the router* — rejected: duplicates behavior the global handler already provides and risks diverging error shapes.

## R5 — Routing, versioning, and documentation

**Decision**: Mount the endpoint on the existing app under the `/api/v1` prefix via an `APIRouter`, mirroring `corridor_read.py`, and give the route an explicit `response_model` and `summary` so it appears in the generated OpenAPI (`/openapi.json`, `/docs`). Path: `GET /api/v1/version`.

**Rationale**:
- Backend-api steering mandates `/api/v1/...` versioning. Declaring `response_model` makes FastAPI enforce the fixed shape and auto-document it, satisfying FR-005 and FR-009 (client code can be generated if ever needed).

**Alternatives considered**:
- *Top-level `/version` (no `/api/v1`)* — rejected: violates the backend versioning convention. `/healthz` sits at the root because it is an infra liveness probe, not an API resource; build metadata is an API resource and belongs under `/api/v1`.

## Resolved unknowns

All `NEEDS CLARIFICATION` markers from Technical Context are resolved: R1 fixes source-revision capture (env var via `config.py`, `unknown` fallback). No open clarifications remain for Phase 1.
