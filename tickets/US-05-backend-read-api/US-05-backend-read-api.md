# feat(backend): read API for live corridor state (US-05)

> RITMO Turn 1 — "Data and minimal loop". Lane: Disciplined. Risk level: 2.
> Governed by `docs/turns-ritmo.md` §3 and the constitution.

## Context and problem

The gold layer already produces the corridor snapshots, and the read contracts are defined
and fixtured in `contracts/read/` (`corridor_now`, `source_status`). But the backend only
exposes `GET /healthz`: there is no HTTP surface that serves these contracts. The dispatcher
console (Ticket 2) cannot be built until the backend serves them.

This ticket exposes the existing gold data as a small read-only REST API. Recommendations and
the Human-in-the-Loop decision path are handled in a separate story (Ticket 3).

## User story

As the dispatcher console (and any read client), I need HTTP endpoints that serve the live
fleet state and data-source status for corridor C6-008, so the dispatcher can see reliable
corridor state.

## Scope (Turn 1)

- [ ] `GET /api/v1/corridor-now` → latest `corridor_now` snapshot (contract v1.0.0).
- [ ] `GET /api/v1/source-status` → latest `source_status` (contract v1.0.0).
- [ ] Pydantic V2 response models derived **from the approved JSON Schema** in `contracts/read/`.
      No invented fields.
- [ ] All DB access via psycopg 3, parameterized SQL only, `dict_row`/`class_row` mapping.
- [ ] Read endpoints are read-only against gold; no writes to bronze.
- [ ] Error responses carry a `correlation_id` and never leak stack traces (reuse the existing handler).
- [ ] `tsc`-friendly OpenAPI: endpoints documented so the frontend can generate its client
      via `openapi-ts`.

## Out of scope (deferred / evolution)

- Recommendations endpoint and the approve/discard decision path — **Ticket 3** (US-02, Gate 4).
- WebSocket / Server-Sent Events (real-time push) — Turn 3. Turn 1 is polling-only.
- RBAC, JWT, auth of any kind — Turn 2.
- Redis, PostGIS, geometry, geographic coordinates.
- Pagination, filtering, historical queries — only "latest snapshot" is needed.
- Rate limiting, caching headers.

## Contracts consumed / produced

| Contract | Version | Direction |
|---|---|---|
| `corridor_now.schema.json` | 1.0.0 | response |
| `source_status.schema.json` | 1.0.0 | response |

No contract changes are expected. If any field is missing, **stop** and request an ADR
from `data-design` (CODEOWNERS of `contracts/`).

## Acceptance criteria

- **Given** gold has a current snapshot, **when** `GET /api/v1/corridor-now`, **then** the
  response validates against `corridor_now.schema.json` v1.0.0 and reflects the latest snapshot.
- **Given** a bus has not reported for > 2 min, **when** `GET /api/v1/source-status`, **then**
  `status` is `estimated` and the bus appears in `sources_down`, with **no** alert implied.
- **Given** any unhandled error, **when** a request fails, **then** the response is a generic error
  body with `correlation_id` and **no** stack trace.

## Gates to pass

- `backend-ci`: ruff, mypy, Bandit, pytest + coverage **> 80 %**, pip-audit.
- Parameterized SQL only (A05 baseline); no secrets in code or `.env`.

## Dependencies

- None

## RITMO workflow

- Branch: `feature/US-05-backend-read-api`.
- Flow: Plan → Specify → Build → Verify → Review. One story on its own branch.
