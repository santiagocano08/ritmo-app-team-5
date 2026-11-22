# Phase 1 — Data Model: Functional Integration (Turn-1 Whole)

Feature: `006-functional-integration` · Spec: [spec.md](./spec.md) · Research: [research.md](./research.md)

**This story introduces no new persisted data model and no new message contract** (FR-013). The
entities below are the integration-level objects the spec names (spec §Key Entities). The two data
payloads the console consumes are **existing** and governed by the committed contract at version
1.0.0 — they are referenced here, not redefined (FR-014, Principle II).

---

## Consumed data contracts (existing, unchanged — v1.0.0)

Authority: `contracts/read/` at the repository root. The console's TypeScript types are generated
from these schemas, not hand-written (Contract-First). Any live mismatch stops work and triggers a
contract decision (FR-014); it is never silently edited here.

### Corridor snapshot — `corridor_now` (v1.0.0)

- **Schema**: `contracts/read/corridor_now.schema.json`
- **Served by**: `GET /api/v1/corridor/{corridor_id}/now` (`src/api/routers/corridor_read.py`)
- **Consumer**: console `getCorridorNow()` → `useCorridorNow` hook → fleet/summary components
- **What the console reads**: the fleet ordered leader-first, each bus with state, headway and
  quality (FR-004). `schema_version` MUST equal `1.0.0` (asserted client-side).
- **No-data sibling**: HTTP 200 `{ "status": "no_data", "corridor_id": ... }` — distinct from an
  error, drives the no-data UI state (FR-007).
- **Unchanged by this story**: consumed as-is; no field added, removed or reinterpreted.

### Source status — `source_status` (v1.0.0)

- **Schema**: `contracts/read/source_status.schema.json`
- **Served by**: `GET /api/v1/corridor/{corridor_id}/source-status`
- **Consumer**: console `getSourceStatus()` → `useSourceStatus` hook
- **What the console reads**: per-bus/corridor data source indicator. An `estimated` source drives
  the "Estimated" label and MUST NOT raise an alert (FR-006).
- **No-data sibling**: HTTP 200 `{ "status": "no_data", "corridor_id": ..., "sources_down": [] }`.
- **Unchanged by this story**.

---

## Integration entities (configuration/runtime, not persisted rows)

These describe the shape of the integrated system this story assembles. They live in compose, the
frontend image and docs — not in the database.

### Service in the stack

A running unit of the Turn-1 system with a health status and a startup position.

| Service | Role | Health status source | Startup ordering | Isolation note |
|---------|------|-----------------------|------------------|----------------|
| `db` | PostgreSQL 16 persistence | `pg_isready` | first (no deps) | — |
| `ingestion` | simulator → ingestion reader | bronze-freshness probe | after `db` healthy | nothing depends on it (Principle III) |
| `refresh` | gold snapshot recompute loop | gold-freshness probe | after `db` healthy | off the capture path |
| `api` | FastAPI read API | `GET /healthz` 200 | after `db` healthy | stopping it never stops `ingestion` |
| `frontend` *(new)* | reverse proxy serving SPA + `/api/v1` forward | proxy local index 200 | **after `api` healthy** (FR-002) | adds no dependency onto `ingestion` |

- **Invariant (Principle III)**: stopping `api` or `frontend` MUST NOT stop `ingestion`. The new
  `frontend → api` ordering edge does not touch `ingestion`.
- **Health rule (FR-002)**: every service reports a health status; the console starts only after
  `api` is healthy.
- **Count rule (SC-001)**: a single command brings up all five; 100 % report healthy.

### Shipped console artifact

The packaged, deployable console image produced by this story.

| Attribute | Required value | Requirement |
|-----------|----------------|-------------|
| Runtime user | non-root UID 10001 | FR-010, SC-005 |
| Contents | built static assets only — no build runtime, source or dependency tree | FR-009, SC-005 |
| Origin | served under one origin that forwards `/api/v1` to `api` | FR-011 |
| Security headers present | `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` | FR-012, SC-005 |
| Headers absent | `Server`, `X-Powered-By`, any stack/version-revealing header | FR-012, SC-005 |
| Base image | pinned to an exact patch tag | reproducibility (research R3) |

### Console runtime configuration (environment)

| Setting | Default | Meaning | Requirement |
|---------|---------|---------|-------------|
| Console API base / same-origin proxy default | `/api/v1` (relative) | console reaches the backend through the same origin; no CORS | FR-011, FR-016 |
| `VITE_API_BASE_URL` | unset (→ relative `/api/v1`) | overridable only for non-default topologies | research R1 |

Documented in `.env.example` and the README (FR-016). No secret is added (Turn-1 no-secrets rule).

---

## State transitions — console display states (existing behavior, validated here)

The console already implements these transitions; this story validates them end to end against the
real backend (it adds no new state).

```text
                 backend 200 + schema 1.0.0 + snapshot
   (start) ─────────────────────────────────────────────▶ LIVE (fleet leader-first, ~5s refresh)
      │                                                        │
      │ backend 200 + no_data envelope                         │ poll fails (unreachable / non-2xx)
      ▼                                                        ▼
   NO-DATA (distinct from error, FR-007)              STALE indicator (non-blocking, FR-008)
                                                               │ later poll succeeds
                                                               ▼
                                                        recover to LIVE (no reload, no crash)
```

- **Estimated source** (FR-006): within LIVE, a bus whose source is `estimated` renders with the
  "Estimated" label and raises no alert. Not a separate screen state.
- **Schema mismatch** (FR-014): a body whose `schema_version != 1.0.0` is a stop-and-decide event,
  surfaced as a failure — not a silent downgrade.

## Validation rules (traceability)

| Rule | Source | Where validated |
|------|--------|-----------------|
| Fleet ordered leader-first with state/headway/quality | FR-004 | quickstart case 1 |
| Auto-refresh ~5 s | FR-005 | quickstart case 2 |
| Estimated source → label, no alert | FR-006 | quickstart case 3 |
| No-data state distinct from error | FR-007 | quickstart case 4 |
| Poll fail → stale indicator → self-recover | FR-008 | quickstart case 5 |
| Live responses match contract v1.0.0, zero drift | FR-014, SC-007 | quickstart contract check |
| No mock fixtures in the request path | FR-003, SC-002 | quickstart case 1 / image inspection |
