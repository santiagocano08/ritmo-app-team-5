# Contracts — Dispatcher Console (US-06)

This feature **defines no new data contract**. It is a read-only consumer of the already-approved Turn-1 read contracts. This folder records the consumer-side interface the console binds to, so `/speckit.tasks` and the implementation have an unambiguous target. The authoritative schemas live in the repository `contracts/read/` directory and must not be copied or edited here.

## Consumed backend contracts (source of truth)

| Contract (repo root) | Version | Backend endpoint (US-05 / feature 004) | Used by |
|---|---|---|---|
| `contracts/read/corridor_now.schema.json` | 1.0.0 | `GET /api/v1/corridor/{corridor_id}/now` | Fleet list, summary, per-bus state/headway/quality |
| `contracts/read/source_status.schema.json` | 1.0.0 | `GET /api/v1/corridor/{corridor_id}/source-status` | Status indicator, data-state badge, banner |

`corridor_id` is `C6-008` this turn. Any other corridor returns the no-data envelope (feature 004, FR-011).

## No-data envelope (API-level sibling, feature 004 FR-008/FR-011)

Returned at **HTTP 200** when gold is empty or the corridor is unsupported. It is not part of the `corridor_now` contract document; the client handles it as a distinct, non-error case.

```json
// GET /api/v1/corridor/C6-008/now           → 200
{ "status": "no_data", "corridor_id": "C6-008" }

// GET /api/v1/corridor/C6-008/source-status → 200
{ "status": "no_data", "corridor_id": "C6-008", "sources_down": [] }
```

## Error body (feature 004 FR-007)

An unhandled backend failure returns HTTP 500 with a generic body and no internals:

```json
{ "error": "internal_server_error", "correlation_id": "<uuid>" }
```

The console treats a 500 (or any unreachable-backend / malformed-body outcome) as a failed refresh: it keeps the last snapshot and shows the non-blocking stale indicator (FR-010).

## Type generation contract (Principle II)

- TypeScript payload types are **generated** from the two JSON Schemas above (e.g. `openapi-typescript`) into `src/frontend/src/api/generated/`. They are committed, never hand-edited.
- The client asserts `schema_version === "1.0.0"` on every body and surfaces a mismatch instead of rendering unknown data.
- The frontend reads only the contract-defined fields and the API-level envelope/error shapes above — nothing else (`data-profile-review` contract rule; `contracts/read/README.md` responsibility boundary: frontend owns formatting/units/color only).

## Component ↔ data binding (consumer interface)

| UI region | Reads | Spec requirement |
|---|---|---|
| Fleet list / `BusRow` | `CorridorNow.buses[]` (order as received) | FR-001, FR-002, FR-003, FR-005 |
| State tag | `Bus.bus_state` (+ text, not color alone) | FR-004, FR-012 |
| Headway compare | `Bus.headway_ahead_s` vs `headway_planned_s` (null ⇒ no compare) | FR-002 |
| Corridor summary | `CorridorNow.summary` | FR-005 |
| Status indicator / badge | `SourceStatus.status` | FR-006 |
| Data-state banner | `SourceStatus.status ∈ {estimated, no_data}` only | FR-007, FR-008 |
| Stale indicator | TanStack query error with retained snapshot | FR-010 |
| Empty state | `summary.buses_in_service === 0` or no-data envelope | FR-013 |

## Mock-mode contract (tests & pre-backend)

Component tests and mock mode serve the shared fixtures via `msw` (or a fetch stub); no fixtures are duplicated here.

| Scenario | Fixture dir (repo root) | Proves |
|---|---|---|
| Normal | `contracts/read/fixtures/normal/` | Leader-first fleet, live status, no banner (US1, FR-001/FR-006/FR-007) |
| Bunching | `contracts/read/fixtures/c1_bunching/` | Bunched buses distinguished; summary counts (US2, FR-004/FR-005) |
| Gap | `contracts/read/fixtures/c2_gap/` | Gap buses distinguished; gap count (US2) |
| Breakdown | `contracts/read/fixtures/c5_breakdown/` | `broken_down` bus shown, `headway_ahead_s` null handled (edge case) |
| Source outage | `contracts/read/fixtures/d1_source_outage/` | `estimated` status + banner; estimated bus labeled, no alert (US3, FR-008/SC-005) |
| No data | synthesized no-data envelope (above) | Empty state, zero counts, no-data banner (FR-013) |
| Stale | simulated failed refresh over a prior fixture | Last snapshot retained + stale indicator, recovers next cadence (FR-010/SC-006) |

## Contract impact

No change to `docs/data-contract.md`, `contracts/read/`, `contracts/turn1-events/` or any data ADR. Consumer-only feature.
