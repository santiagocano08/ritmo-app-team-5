---
inclusion: auto
name: backend-api
description: When working on the PulsoFlota Python API/backend (FastAPI/Flask) - REST/WebSocket endpoints, RBAC middleware, JWT authentication, error handling, correlation_id and Pydantic validation.
---

# Backend API — PulsoFlota

Guidance for the control center's Python API/backend (`pulsoflota-backend`
service): FastAPI (or Flask) + Pydantic V2.

> Target folder: `src/backend/`. The current Turn-1 tree is not yet reorganized
> into it — backend code sits in `src/api/` (FastAPI app), `src/data/`
> (ingestion, pipeline, rules, simulator) and `src/pulsoflota/` (shared
> DB/config/models). Check `docs/turns-ritmo.md` for the active turn.

## Structure and routing

- The backend (`src/backend/`) is a **separate service** from the React frontend
  (`src/frontend/`). It holds all business logic, metric calculation and
  authorization, and exposes REST + WebSocket endpoints. The frontend consumes
  this API and never decides access control.
- Version the API under `/api/v1/...`.

## Access control (A01) — always in the backend

- Authenticate the caller and check permissions through RBAC in the middleware
  **before** running business logic.
- IDOR is forbidden: reading/modifying someone else's resource (e.g.
  `/api/v1/buses/{bus_id}` from another basin) MUST return `403 Forbidden` and
  log a security alert.
- Authorization is evaluated **only in the backend**. The frontend never decides
  access and hiding buttons is never the only mechanism.
- Multi-tenant isolation: telemetry from private consortia is logically
  isolated; an operator cannot access competitors' raw telemetry.

## Authentication and sessions (A07)

- JWT signed with `RS256`, expiry ≤ 15 min, sent only in `HttpOnly`, `Secure`,
  `SameSite=Strict` cookies.
- MFA (TOTP) mandatory for administrators and basin supervisors.
- Brute-force protection: lock any account or IP for 15 min after 5 consecutive
  failed attempts.

## Validation and data

- Requests/responses validated with Pydantic V2; invalid ones are rejected with
  `422 Unprocessable Entity`. Schema and inter-module contract definitions live in
  `data-contracts.md`.
- Database access is **psycopg 3 with parameterized SQL only** — no ORM, no
  SQLAlchemy, no Alembic. SQL string concatenation is forbidden (A05 injection
  baseline). See `src/pulsoflota/db.py`.

## Errors and exceptions (A10)

- Never expose stack traces, local paths (`/workspace/...`) or internal
  PostgreSQL structures.
- HTTP 500 → standardized generic message + `correlation_id` recorded in the
  logs. Validation errors → `422`.

## Configuration

- `DEBUG=False` enforced in staging/production; Swagger/ReDoc not exposed in
  production without prior authentication.

## References

- Full OWASP Top 10 (2025) matrix (HTTP headers, cryptography, secrets, supply
  chain, STRIDE, logs/PII): `security.md`.
- Telemetry schemas and validation: `data-contracts.md`.
