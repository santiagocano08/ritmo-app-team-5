# Phase 1 Data Model: US-05 — Backend Read API

This feature **persists nothing** and **defines no new domain entity**. It is a
read-only consumer of existing, already-approved contract objects. This document
describes the shapes it reads and serves, the gold tables it reads from, and the
API-only "no data" envelope. **No contract change, no version bump, no new field.**

See `docs/data-contract.md` §3 (Q0/Q1/Q2) for the authoritative query and example
output, and `.kiro/steering/data-contracts.md` for the data-owner rule.

## Served entities (owned by the data layer, reused as-is)

### Corridor-now snapshot — `corridor_now` v1.0.0

- **Schema**: `contracts/read/corridor_now.schema.json` (`additionalProperties:
  false`).
- **Model**: `src/pulsoflota/models/read/corridor_now.py` → `CorridorNowV100`
  (reused, unchanged).
- **Fields** (contract-defined only): `schema_version` ("1.0.0"), `snapshot_id`
  (UUID), `as_of_ts` (UTC datetime), `corridor_id` (str, Turn 1 "C6-008"),
  `direction` (1), `buses` (array of bus entries, leader first), `summary`
  (`buses_in_service`, `n_bunched`, `n_gaps`).
- **Bus entry**: `bus_id` (B-101…B-107), `direction` (1), `prev_stop_id`,
  `next_stop_id`, `distance_along_m` (0–5119.4), `headway_ahead_s` (≥0 or null for
  leader / broken_down), `headway_planned_s` (≥1), `bus_state`
  (leader|regular|bunched|gap|broken_down), `data_quality` (live|estimated), `ts`.
- **Source**: `SELECT doc FROM gold.corridor_now WHERE snapshot_id = %(snapshot_id)s`.

### Source status — `source_status` v1.0.0

- **Schema**: `contracts/read/source_status.schema.json` (`additionalProperties:
  false`).
- **Model**: `src/pulsoflota/models/read/source_status.py` → `SourceStatusV100`
  (reused, unchanged).
- **Fields**: `schema_version` ("1.0.0"), `snapshot_id` (UUID), `as_of_ts`,
  `status` (live|estimated|no_data), `sources_down` (array of `{bus_id, since}`).
- **Freshness rule (FR-006)**: a bus silent > 2 min is already classified by the
  gold builder as `estimated` and listed in `sources_down`, raising no alert. The API
  serves this as-is; it does not recompute staleness.
- **Source**: `SELECT doc FROM gold.source_status WHERE snapshot_id = %(snapshot_id)s`.

### Correlation identifier (error responses only)

- Opaque UUID attached to 5xx error bodies (`correlation_id`), produced by the
  existing global exception handler. Ties a failed request to a server-side log
  record without exposing internal state. Not a persisted entity.

## Gold tables read (SELECT-only, never written)

| Table | Columns used | Purpose |
|---|---|---|
| `gold.snapshots` | `snapshot_id`, `as_of_ts`, `max_bronze_id` | Resolve the latest snapshot (Q0). |
| `gold.corridor_now` | `snapshot_id`, `doc` | Serve `corridor_now` body (Q2). |
| `gold.source_status` | `snapshot_id`, `doc` | Serve `source_status` body (Q1). |

No `INSERT`/`UPDATE`/`DELETE` anywhere. Bronze is never touched (FR-005).

## Latest-snapshot resolution

```
Q0: SELECT snapshot_id, as_of_ts
    FROM gold.snapshots
    ORDER BY as_of_ts DESC, max_bronze_id DESC
    LIMIT 1;
```

- Both ordering keys are mandatory (data-contract §3 rule 2).
- Within one response, resolve once and reuse the `snapshot_id` for the object read
  (never mix "latest" across separate queries — data-contract §3 rule 3).
- Returns zero rows ⇒ the "no data" path.

## No-data response (API-only envelope, FR-008 / FR-011)

Not a contract object and not persisted — an API presentation of "no snapshot yet".
Returned with **HTTP 200** so it is clearly distinguishable from both a live empty
snapshot and an error. It is a **sibling envelope**, returned alongside (not inside)
the `corridor_now` contract document; it is not a mutation of, or an extra field
added to, that contract, so it does not violate the contract-fields-only rule of
FR-003/FR-004. The same envelope covers a request for an **unknown/unsupported
corridor** (any corridor other than C6-008 this turn): the requested corridor id is
echoed back and no distinct error status is introduced (FR-011).

- `source-status` (contract already models it):
  ```json
  { "status": "no_data", "corridor_id": "C6-008", "sources_down": [] }
  ```
- `now` (sibling envelope, no field invented inside the `corridor_now` contract):
  ```json
  { "status": "no_data", "corridor_id": "C6-008" }
  ```

Both documented as a distinct response variant in
`specs/004-backend-read-api/contracts/read-api.openapi.yaml`.

## Validation rules enforced at the boundary

- Response bodies validate against the approved JSON Schemas; `extra="forbid"`
  guarantees no invented/extra field (FR-003, FR-004, SC-002).
- If gold cannot populate a contract-required field, the gold build would already
  have failed validation; the API does not invent or default a value. Such a case is
  a blocking data-contract issue to escalate (spec Assumptions), not a silent default.

## State / lifecycle

None. Each request is a stateless point read of the single latest snapshot (FR-010:
no history, filtering or pagination).
