# feat(backend): expose version / build info endpoint (US-08)

> RITMO Turn 1 — "Data and minimal loop". Lane: Adaptive. Risk level: 1.
> Governed by `docs/turns-ritmo.md` §3 and the constitution.

## Context and problem

The backend currently exposes `GET /healthz` (liveness) and the US-05 read API
(`/api/v1/corridor-now`, `/api/v1/source-status`), but there is no way to tell
**which version of the backend is running** or **which read-contract version it
serves**. During integration and end-to-end validation (US-07) and when
diagnosing drift between the console's generated types and the live responses,
operators and contributors have no single place to read the running app version
and the contract version it targets.

This ticket adds a tiny, read-only version/build-info endpoint. It introduces no
business logic, touches no data contracts and reads nothing from the database.
It is a small, low-risk story to exercise the full RITMO loop end to end.

## User story

As an operator or contributor validating the Turn-1 stack, I want a single HTTP
endpoint that reports the running backend version and the read-contract version
it serves, so I can confirm which build is live and detect contract drift
without inspecting the container.

## Scope (Turn 1)

- [ ] `GET /api/v1/version` → a small JSON body with:
      `app_version` (the backend package/app version),
      `contract_version` (the `corridor_now` / `source_status` read-contract
      version the backend targets, `1.0.0`),
      and `commit` (short git SHA if available at build time, otherwise `"unknown"`).
- [ ] Pydantic V2 response model for the body; no invented or free-form fields.
- [ ] Endpoint is **read-only** and does **not** touch the database, Redis or
      any gold/bronze table.
- [ ] Values come from a single source of truth (app metadata / an env var set
      at build time), not hard-coded in the route handler.
- [ ] Error responses (if any) carry a `correlation_id` and never leak stack
      traces (reuse the existing handler).
- [ ] Endpoint documented in OpenAPI so the frontend can generate its client via
      `openapi-ts` if it ever needs it.

## Out of scope (deferred / evolution)

- Any health/readiness logic beyond liveness (dependency checks, DB ping) —
  keep `/healthz` as is.
- Auth / RBAC on the endpoint — Turn 2. The endpoint is unauthenticated read-only
  build metadata.
- Surfacing the version in the dispatcher console UI — separate UI story if ever
  wanted.
- Metrics, tracing, uptime, resource usage — not build info.

## Contracts consumed / produced

| Contract | Version | Direction |
|---|---|---|
| `version` (new, local response model) | 1.0.0 | response |

No changes to the `corridor_now` / `source_status` data contracts. The
`contract_version` field only **reports** the version the backend already
targets; it does not define or alter a data contract. If this seems to require a
`contracts/` change, **stop** and request an ADR from `data-design`.

## Acceptance criteria

- **Given** the backend is running, **when** `GET /api/v1/version`, **then** the
  response is `200` with `app_version`, `contract_version` (`"1.0.0"`) and
  `commit`, validating against the response model.
- **Given** no git SHA is available at build time, **when** `GET /api/v1/version`,
  **then** `commit` is `"unknown"` and the request still succeeds.
- **Given** the endpoint is called, **when** it runs, **then** it issues **no**
  database or Redis query.
- **Given** any unhandled error, **when** a request fails, **then** the response
  is a generic error body with `correlation_id` and **no** stack trace.

## Gates to pass

- `backend-ci`: ruff, mypy, Bandit, pytest + coverage **> 80 %**, pip-audit.
- No secrets in code or `.env`; no database access from the handler.

## Dependencies

- None (the existing error handler and FastAPI app are already in place).

## RITMO workflow

- Branch: `feature/US-08-backend-version-info`.
- Flow: Plan → Specify → Build → Verify → Review. One story on its own branch.
