# ADR-0003: Turn 1 Read Contract

- Status: Accepted
- Date: 2026-11-17
- Decided by: data owner, 2026-11-18
- Turn: Turn 1 — Data and Minimal Loop (active)
- Addresses: Principle II (Contract-First and Data Ownership), Principle IV (Human Gate — the
  dispatcher approves every regulation action), RF-2.1, RF-2.2, RF-2.3 (alerts and recommendations
  with dispatcher approval), turn-1 risk (data integrity: malformed or inconsistent data contaminates
  the metric and the recommendations displayed on the console)

## Context

ADR-0001 and ADR-0002 define the write path: simulator events flow into bronze, silver and gold over
PostgreSQL `LISTEN/NOTIFY`. The backend and frontend teams now need a stable read contract — the
exact shape of every object the backend produces and exposes — so they can build against fixtures
before the pipeline exists.

Turn 1 covers one corridor (C6-008), one direction, five active buses (B-101..B-105) and two
reserve buses (B-106/B-107), with stops P-883..P-900 at known distances along the route.

This ADR defines:

- the **responsibility boundary** between data, backend and frontend;
- the **three communication doors** (query / push / command);
- the **seven read schemas** and one **command-event schema** in `contracts/read/`;
- the **versioning rule** for read schemas;
- the **fixture scenarios** that implement-code and tests use.

No code (Python, SQL, Pydantic) is written here. `implement-code` derives all Pydantic V2 models
from the approved JSON Schemas with no invented fields.

## Responsibility boundary

| Layer | Owns | Does NOT own |
|---|---|---|
| **Data** (gold views) | Bus states, headways, data quality flag, travel-time forecasts (M1), demand forecast (M2), EWT projection, `snapshot_id`, `rules_version` | Recommendation decisions, roles, session, API expiry, conflict detection |
| **Backend** | Decision engine (cases C1/C2/C5/D1), `rec_id`, `expires_ts`, `conflicts_with`, `rank`, role-based filtering, REST/WebSocket/SSE API, writing command events to bronze | Computing headways or EWT from raw bronze; direct writes to silver/gold |
| **Frontend** | Formatting, localisation, colour, units display | Any business logic; access control decisions |

The backend never writes to silver or gold state tables. When the dispatcher acts, the backend
inserts a `command_event` into bronze; the pipeline recomputes silver/gold and notifies via
`LISTEN/NOTIFY`.

## Options considered (max. 3)

1. **One versioned schema per read object, in `contracts/read/`, parallel to `contracts/turn1-events/`.**
   - Pros: same conventions as the write contract; each object evolves independently; `implement-code`
     derives Pydantic models from them; no invented fields; directly testable with fixtures.
   - Cons: eight schema files to maintain; a change to a shared sub-object (e.g. `bus_entry`) must
     be updated in multiple schemas.

2. **Single "corridor snapshot" schema that bundles all objects.**
   - Pros: one file; always consistent internally.
   - Cons: a frontend screen that only needs `source_status` must receive the full snapshot; schema
     becomes a monolith; breaking one field breaks every consumer.

3. **OpenAPI response schemas only, no JSON Schema files.**
   - Pros: single artefact for API documentation.
   - Cons: not usable for the DataOps contract gate (Gate 1 runs JSON Schema); no standalone
     fixture validation; couples the data contract to the HTTP API design.

## Decision

Adopt **option 1**: one JSON Schema (draft 2020-12) per read object, in `contracts/read/`. The
schemas are the source of truth; Pydantic V2 models and OpenAPI response schemas are derived from
them by `implement-code`. All schemas carry a top-level `schema_version` field (SemVer string,
turn 1 value `"1.0.0"`).

### Three communication doors

| Door | Mechanism | Turn 1 | Who calls it |
|---|---|---|---|
| **Query** | REST GET | Backend reads gold views and assembles response objects | Frontend, internal backend engine |
| **Push** | PostgreSQL `LISTEN/NOTIFY` → backend forwards over WebSocket or SSE | Backend subscribes to `NOTIFY` on the gold channel; frontend subscribes to the backend WebSocket/SSE; nobody polls every second | Frontend live panel |
| **Command** | Backend inserts a `command_event` into bronze; pipeline recomputes silver/gold | Dispatcher action (approve / discard / incident / confirmation) → REST POST → backend writes `command_event` | Backend only; never frontend direct write |

Redis Pub/Sub is deferred to turn 3; `LISTEN/NOTIFY` is the turn-1 push transport (ADR-0001).

### Conventions (all schemas)

- **Timestamps:** UTC ISO-8601 (`date-time` format), e.g. `"2026-11-24T08:00:00Z"`.
- **Durations:** seconds, integer or number, field suffix `_s`.
- **Ratios:** `0.0`–`1.0`, field suffix `_ratio` where ambiguous.
- **Distances:** meters, field suffix `_m`.
- **Field names:** `snake_case` English. The frontend formats for display.
- **`schema_version`:** present on every top-level read object; version `"1.0.0"` in turn 1.
- **`additionalProperties: false`** on every object (strict, same as write contract).

### Schema inventory

| File | Turn-1 screen | Produced by |
|---|---|---|
| `source_status.schema.json` | US-03 — data quality status | Data (gold view) |
| `corridor_now.schema.json` | US-04 — live fleet panel | Data (gold view) |
| `decision_inputs.schema.json` | US-05 internal — backend engine input | Data (gold view, internal) |
| `recommendation.schema.json` | US-05 — dispatcher recommendation | Backend (decision engine) |
| `instruction.schema.json` | US-10 — driver instruction status | Backend |
| `recommendation_effect.schema.json` | US-11 — effect measurement | Data (gold view) |
| `incident.schema.json` | US-12 — active incidents | Data (gold view) + Backend |
| `command_event.schema.json` | Bronze write — dispatcher actions | Backend → bronze |

### Key field decisions (turn 1)

**`source_status`**
- `status` enum: `live` (last event within 2 min), `estimated` (no report > 2 min, no alert),
  `no_data` (no event ever received). Mirrors ADR-0001 source-outage rule.
- `sources_down` lists per-bus outages with `since` timestamp so the frontend can show elapsed time.

**`corridor_now` — bus entry**
- `distance_along_m` is the single position field (no geometry, turn 1). Increases monotonically
  towards P-900 (5119.4 m).
- `headway_ahead_s`: gap in seconds to the bus ahead (higher `distance_along_m`, further along the route); `headway_planned_s`: 600 s
  at peak (the planned value from reference data, not recomputed here).
- `bus_state` enum: `leader` (furthest-ahead bus, `headway_ahead_s` is null), `regular`, `bunched` (gap < 0.5 ×
  planned), `gap` (gap > 1.5 × planned), `broken_down`.
- `data_quality` mirrors the per-bus `status` from `source_status` at bus level: `live` or
  `estimated`.
- Array is ordered by `distance_along_m` **descending** (leader first).
**`decision_inputs`**
- Extends `corridor_now` data with M1 travel-time forecast per segment and M2 demand forecast for
  the next 15 min window. These fields are internal to the backend decision engine; they are never
  sent to the frontend directly.
- `resources`: free reserve buses and free drivers (turn-1 fleet: B-106, B-107 as reserve).
- `active_incidents`: list of `inc_id` strings referencing current `incident` objects.

**`recommendation`**
- Produced by the backend decision engine; data persists it in the gold layer for lineage.
- Cases: `C1` (bunching → hold), `C2` (gap → adjust departure), `C5` (breakdown → reserve
  dispatch), `D1` (source outage → no alert, information only).
- `action.type` enum: `hold`, `adjust_departure`, `reserve_dispatch`.
- `rank` 1–3: priority among concurrent recommendations (1 = highest).
- `status` lifecycle: `proposed` → `applied` or `discarded` (dispatcher decision, Principle IV)
  or `expired` (past `expires_ts` with no action).
- `lineage.snapshot_id` references the `corridor_now` snapshot that triggered the recommendation.
- `conflicts_with`: list of `rec_id` strings the backend detects as mutually exclusive.
- Principle IV is enforced architecturally: no backend path applies a recommendation without an
  explicit dispatcher `command_event` with `action: "apply"`.

**`instruction`**
- Sent to the driver after the dispatcher approves a recommendation.
- `status` lifecycle: `sent` → `received` | `no_confirmation` | `radio` → `executed` |
  `not_executed`.
- `executed` is determined by data: dwell at target stop within ±15 s of the instructed duration.
  The backend does not self-declare execution; it reads the gold `instruction` view.
- `ts_by_status`: object mapping each status value to the timestamp it was entered, so the full
  lifecycle is auditable.

**`recommendation_effect`**
- Simple before/after comparison: headway and EWT observed after the recommendation window versus
  expected.
- `result` enum: `worked` (EWT improved), `partial` (headway improved but EWT did not), `did_not_work`
  (neither improved), `no_data` (insufficient observations).

**`incident`**
- `duration_s` is nullable (`null` = unknown duration, e.g. a breakdown of unspecified length).
- `until` is nullable for the same reason; set when the incident is closed.
- `reported_by`: `"dispatcher"` (via UI command) or `"script"` (simulator injection, as in
  `incident_report.schema.json`). Keeps alignment with the write contract.
- `inc_id` is a UUID string, same convention as `rec_id`.

**`command_event`**
- The backend is the only writer. The envelope reuses `source: "backend"` and the
  `turn1-events` envelope structure where it fits (same `schema_version`, `event_id`, `event_ts`
  fields). `event_type` takes three new values: `decision`, `incident_report` (backend-initiated,
  reusing the existing write payload shape), `confirmation`.
- `decision` payload: `rec_id`, `action` (`apply` | `discard`), `user_id`, `ts`.
- `confirmation` payload: `inst_id`, `status` (same enum as `instruction.status`), `ts`.
- The `incident_report` payload reuses `incident_report.schema.json` from `contracts/turn1-events/`
  without duplication.

### Versioning rule (read contracts)

Same as the write contract (ADR-0002): a **breaking change** (new required field, removed field,
type change, tighter constraint) requires a new major version and a new ADR. A **non-breaking**
addition (new optional field) is a minor bump and both versions are accepted. There is never a
silent edit of a published contract.

## Consequences

- **Easier:** backend and frontend can build against fixtures before the pipeline exists; Gate 1
  schema validation covers both write and read contracts; `implement-code` has no ambiguity about
  field names or types; the responsibility boundary prevents backend from computing headways from
  raw bronze (data owns that).
- **Harder:** eight schemas to keep coherent; a change to a shared sub-object must be updated in
  each schema that uses it; the `command_event` schema must stay aligned with the existing
  `turn1-events` envelope.

## Affected contract

`contracts/read/*` — **v1.0.0 (new)**. No existing contract is modified.

## Evolution

- Push transport upgraded from `LISTEN/NOTIFY` to Redis Pub/Sub (turn 3).
- `corridor_now` gains lat/lon geometry fields and PostGIS types (turn 3).
- `decision_inputs` gains full anomaly detection signals: out-of-order, impossible position,
  bursts (turn 3).
- `command_event` gains HMAC signature field (turn 2).
- Role-based field filtering in the read API (turn 2 RBAC).
- `recommendation` gains `diversion` action type and both-direction corridor support (turn 4).

## Gate decisions

The following decisions were confirmed by the data owner at the contract and data architecture gate
(2026-11-18). They are binding for `implement-code` and all future turns unless a new ADR overrides
them.

1. **`headway_ahead_s` semantics:** gap in seconds to the bus ahead (the bus with higher
   `distance_along_m`, i.e. further along the route). `null` for the leader bus (no bus ahead).
   Applies to `corridor_now.schema.json`.

2. **Broken-down bus headway:** a bus with `bus_state: "broken_down"` has `headway_ahead_s: null`.
   It is excluded from headway calculations; the gap opens around it and is detected via the buses
   behind and ahead, not from the broken-down bus itself.

3. **`incident.duration_s` nullable scope:** `duration_s` is nullable only in `incident.schema.json`
   and in the `command_event` incident payload (sources: dispatcher UI and simulator, both of which
   may not know duration at report time). It is not nullable in `corridor_now` or any silver/gold
   aggregate that derives a duration after the fact.

4. **`command_event` bronze table:** backend command events are written to `bronze.events` with
   `source: "backend"`. They share the same bronze table as simulator/IoT events; the `source` field
   distinguishes them. No separate `bronze.command_events` table is created in turn 1.

5. **`rec_id` and `inc_id` format:** both are UUID v4 strings, same convention as `event_id` in the
   write contract. No human-readable prefix (`REC-`, `INC-`) is used in turn 1. If a prefix is
   needed for operator-facing UIs, it is a display concern for the frontend, not a schema change.

6. **`recommendation_effect.result` thresholds:** `worked` requires EWT improvement ≥ 30 s
   (`ewt_expected_s − ewt_observed_s ≥ 30`). `partial` covers improvement > 0 s and < 30 s, or
   headway improved but EWT did not. The 30 s floor avoids noise in the metric and is the
   hypothesis threshold validated with the dispatcher. This threshold is encoded in the
   `recommendation_effect.schema.json` description and enforced in the rules engine.

7. **`decision_inputs` audience:** `decision_inputs.schema.json` is internal to the backend
   decision engine and is never exposed to the frontend directly. Promoting it to a public endpoint
   in a future turn requires a new ADR and data-owner approval (CODEOWNERS).

8. **`action.duration_s` per action type:** the sign and range constraints are:
   - `hold`: integer or number, 0–90 s (positive delay at stop). Never null, never negative.
   - `adjust_departure`: integer or number, −600–600 s (negative = depart earlier, positive = depart
     later). Never null.
   - `reserve_dispatch`: always `null` (no duration concept for a depot dispatch).
   These constraints are enforced by the `if/then/else` conditional in `recommendation.schema.json`
   and must be reproduced identically in the Pydantic V2 model.

## Amendment 2026-11-22 (story 005, data owner)

No field of any read schema changes. Only the meaning of EWT changes: `gold.service_metric` (and the EWT inside `decision_inputs`) is now computed from the headways between consecutive reported departures **at each stop** over a trailing 15-minute window, and it is computable from 5 headways (`config.corridor_settings.min_stop_headways`). The spatial snapshot EWT is withdrawn because it jumped when a bus left the terminal. `corridor_now.distance_along_m` already had `maximum: 5119.4`; story 005 enforces it at ingestion. See `docs/data-contract.md` v0.3 Q4 and §5.

## Amendment 2026-11-23 (issue #42, data owner)

The turn-1 fleet grows to **7 buses in service (`B-101`..`B-107`) and 4 in reserve (`B-108`..`B-111`)**, and the
planned headway drops from 600 s to 420 s. Every `bus_id` enum now lists `B-101`..`B-111`; the reserve-only enum of
`decision_inputs.resources.reserve_free` lists `B-108`..`B-111`. The change is additive (old ids stay valid, no field
or meaning changes), so `schema_version` stays `1.0.0`; the data contract moves to v0.5. Where the text above says
`B-101`..`B-107`, five active buses or B-106/B-107 as reserve, read the fleet of this amendment.
