# Phase 1 Data Model: Backend Version/Build Info Endpoint

Feature: `007-backend-version-info`

This feature persists nothing. The only "entity" is the response payload, defined as a fixed-shape Pydantic V2 model. There is no table, view, or stored record (FR-006). This model is **not** a data contract under `contracts/read/`; it is an API response shape that reports an already-existing read-contract version (FR-003). No `docs/data-contract.md` impact.

## Entity: VersionInfo (response payload)

Read-only build description returned by `GET /api/v1/version`. Derived from build/packaging metadata, never from a persisted record.

| Field | Type | Required | Constraints / default | Source | Requirement |
|---|---|---|---|---|---|
| `app_version` | `str` | Yes | Non-empty. SemVer-shaped string (e.g. `0.1.0`). | Declared app/package version (`pyproject.toml` / `app.version`), via R2. | FR-002 |
| `read_contract_version` | `str` | Yes | Fixed literal `1.0.0` for this turn. | Single named constant tracking existing read contracts (R3). | FR-002, FR-003 |
| `source_revision` | `str` | Yes | Non-empty; defaults to `unknown` when the build captured no revision. | `APP_REVISION` env var via `config.py`; `unknown` when unset/empty (R1). | FR-002, FR-004 |

### Model rules

- **Fixed shape, no extra fields** (FR-005, SC-002): the model uses Pydantic V2 `model_config = ConfigDict(extra="forbid")` and declares only these three fields. Serialization returns exactly these keys, no more.
- **All fields always present** (SC-002): none is optional on output. When a value is unknown, the string `unknown` is emitted rather than `null` or an omitted key.
- **Deterministic for a given build** (spec edge case): all three values are resolved from build-time sources, so repeated requests to the same running build return identical bodies.
- **No persistence, no DB types**: this model is never written to or read from PostgreSQL. It is not mapped with `dict_row`/`class_row`; it is constructed in-process from config/app metadata.

### State transitions

None. The payload is static for the lifetime of a running build (no lifecycle, no mutable state).

## Relationship to existing read contracts

`read_contract_version` reports the version of the existing `corridor_now` / `source_status` read contracts (both pinned to `1.0.0` in `contracts/read/*.schema.json`). It only mirrors that value; it does not define, alter, or version any contract. If delivery ever appears to require a change under `contracts/`, work stops and an ADR is requested from the data-design owner (spec Assumptions, data-contracts steering).
