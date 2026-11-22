# Turn 1 Read Contract (v1.0.0)

How the backend reads and writes this contract: see `docs/data-contract.md` (ADR-0006, ADR-0007).

Read schemas for the turn-1 dispatcher console (corridor C6-008, direction 1). These are the
objects the backend exposes and data persists; Pydantic V2 models are derived from them by
`implement-code`. See **ADR-0003** for the full design rationale.

## Responsibility boundary

| Layer | Owns |
|---|---|
| **Data** (gold views) | Bus states, headways, data quality, travel-time forecasts (M1), demand forecast (M2), EWT, `snapshot_id`, `rules_version` |
| **Backend** | Decision engine, `rec_id`, `expires_ts`, `conflicts_with`, `rank`, role filtering, REST/WebSocket/SSE API, writes `command_event` to bronze |
| **Frontend** | Formatting, localisation, colour, units display — nothing else |

## Three communication doors

| Door | Mechanism | Turn 1 transport |
|---|---|---|
| **Query** | REST GET — backend reads gold views and returns a response object | HTTP |
| **Push** | Backend subscribes to PostgreSQL `LISTEN/NOTIFY`; forwards over WebSocket or SSE to the frontend. Nobody polls every second. | `LISTEN/NOTIFY` → WebSocket/SSE |
| **Command** | Dispatcher action → REST POST → backend writes a `command_event` to bronze → pipeline recomputes silver/gold → push notifies the frontend. The backend never writes directly to silver or gold state tables. | HTTP POST → bronze insert |

## Schema files

| File | Screen | Produced by |
|---|---|---|
| `source_status.schema.json` | US-03 — data quality status | Data (gold view) |
| `corridor_now.schema.json` | US-04 — live fleet panel | Data (gold view) |
| `decision_inputs.schema.json` | US-05 internal — backend engine input | Data (gold view, internal only) |
| `recommendation.schema.json` | US-05 — dispatcher recommendation | Backend (decision engine) |
| `instruction.schema.json` | US-10 — driver instruction status | Backend |
| `recommendation_effect.schema.json` | US-11 — effect measurement | Data (gold view) |
| `incident.schema.json` | US-12 — active incidents | Data (gold view) + Backend |
| `command_event.schema.json` | Bronze write — dispatcher actions | Backend → bronze |

All schemas are JSON Schema draft 2020-12 with `additionalProperties: false`.

## Versioning rule

Same rule as `contracts/turn1-events/`: a **breaking change** (new required field, removed field,
type change, tighter constraint) requires a new major version and a new ADR. A **non-breaking**
addition (new optional field) is a minor bump; both versions are accepted. There is never a silent
edit of a published contract.

## Fixtures

Demo scenario fixtures live in `fixtures/<scenario>/`. Each fixture file is a valid instance of
its schema with realistic, internally consistent values. Use them in tests and as front-end mocks.

| Scenario | Directory | Demonstrates |
|---|---|---|
| Normal operation | `fixtures/normal/` | All 5 buses live, headways near 600 s |
| D1 — source outage | `fixtures/d1_source_outage/` | B-103 estimated (> 2 min no report); no alert raised |
| C1 — bunching | `fixtures/c1_bunching/` | B-102/B-103 bunching; hold recommendation proposed and applied; effect measured |
| C5 — breakdown | `fixtures/c5_breakdown/` | B-104 broken down; incident active; reserve B-106 dispatched |
| C2 — gap | `fixtures/c2_gap/` | B-104 running ahead; two gaps; adjust-departure recommendation proposed |

Each scenario directory contains only the objects relevant to that scenario; `source_status.json`
and `corridor_now.json` are present in every scenario.
