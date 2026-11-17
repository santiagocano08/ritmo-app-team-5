# ADR-0002: Turn 1 Event Contract

- Status: Accepted
- Decided by: data owner, 2026-11-17
- Date: 2026-11-17
- Turn: Turn 1 — Data and Minimal Loop (active)
- Addresses: Principle II (Contract-First and Data Ownership), RNF-3.3.1 (boundary validation; reject 100 % of packets without a valid schema), turn-1 risk (data integrity: malformed, duplicated or missing data contaminates the metric and the recommendations)

## Context

The turn-1 simulator publishes six event types every 5 s for the C6-008 corridor. To reject
malformed data at the boundary (RNF-3.3.1) and to evolve safely, the message contract must be
explicit, versioned and strict (no undeclared fields). Field names are English `snake_case` for the
repository (AGENTS.md); the OMD still uses Spanish identifiers and a lat/lon model, which is noted
as a non-blocking reconciliation item for the docs owner.

## Options considered (max. 3)

1. **Common envelope + discriminated per-event-type payload (`oneOf`).**
   - Pros: shared fields declared once; per-type payload strictly validated; one version point;
     adding an event type is additive.
   - Cons: a discriminator adds a little complexity.
2. **Flat schema per event type (shared fields repeated in each).**
   - Pros: dead simple.
   - Cons: shared fields drift across 6 schemas; versioning per schema; weaker consistency.
3. **Single polymorphic schema with a type tag and all fields optional.**
   - Pros: one file.
   - Cons: allows malformed combos (fields of other types); weak validation — bad for integrity.

## Decision

Adopt **option 1**. One envelope carries the shared metadata; `event_type` selects the payload
schema via `oneOf`. All schemas are JSON Schema (draft 2020-12) in `contracts/turn1-events/`;
Pydantic V2 models are derived from them by `implement-code` (no invented fields).

### Envelope

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string (enum `["1.0.0"]`) | yes | Message contract SemVer. Turn 1 accepts only `1.0.0`. |
| `event_id` | string (UUID v4) | yes | Unique per event. Idempotency key = `source` + `event_id`. |
| `event_type` | string (enum of 6) | yes | Discriminator selecting the payload schema. |
| `source` | string | yes | Producing source. Turn 1: `"simulator"`. |
| `event_ts` | string (date-time, UTC) | yes | Event time; used in calculations. |
| `arrival_ts` | string (date-time, UTC) | no | Set by ingestion on receipt; not sent by the source. |
| `payload` | object | yes | Shape per `event_type` (see schemas). |

Event types: `bus_position`, `stop_arrival`, `stop_departure`, `rider_arrival`,
`driver_confirmation`, `incident_report`.

### Rejection reasons

`missing_required_field`, `wrong_type`, `value_out_of_range`, `unknown_event_type`,
`unsupported_schema_version`, `undeclared_field`, `invalid_uuid`, `invalid_timestamp`,
`duplicate_event`. Rejections are recorded in `bronze.rejections` per `rejection.schema.json`
(`original_message`, `reason`, `received_ts`).

### Versioning rule

A **breaking change** (new required field, removed field, type change, tighter constraint) requires
a **new major version** (`2.0.0`); the ADR at that time states whether the previous version is still
accepted or explicitly rejected. A **non-breaking** change (new optional field) is a **minor bump**
(`1.1.0`) and both versions are accepted. Patch bumps are clarifications only. There is never a
silent edit of a published contract.

### OMD identifier mapping (non-blocking note for the docs owner)

| This contract (turn 1) | OMD object / field | Note |
|---|---|---|
| `bus_id` (`B-101`..`B-107`) | `Vehiculo.id_vehiculo` (UUID) | Turn 1 uses stable string ids, not UUIDs. |
| `operator` | `Vehiculo.id_operador` | Same concept. |
| `direction` (1) | (not in OMD) | Turn 1 is direction 1 only. |
| `distance_along_m` | `EventoTelemetria.latitud` / `longitud` | Turn 1 uses distance along the corridor (meters), no geometry. |
| `speed_kmh` | `EventoTelemetria.velocidad_kmh` | Same. |
| `occupancy` (int 0–40) | `EventoTelemetria.nivel_ocupacion` (float 0.0–1.0) | Turn 1 stores the absolute count; the ratio is derived in silver if needed. |
| `event_ts` | `EventoTelemetria.timestamp` | Moved to the envelope. |
| `trip_id`, `stop_id` | `RutaEstandar` / `Estacion` | Corridor C6-008, 17 segments, direction 1. |
| `instruction_id`, `status` | `PropuestaRegulacion` | Driver confirmation of a dispatch instruction. |

**Non-blocking note for the docs owner:** the OMD uses Spanish identifiers and a lat/lon +
occupancy-ratio model; turn 1 uses English `snake_case`, `distance_along_m` and an absolute
`occupancy` count. Reconciliation (rename OMD identifiers vs. keep Spanish; lat/lon vs. distance;
float vs. integer occupancy) stays open for the docs owner but does not block implementation; the
turn-1 contract is authoritative.

## Consequences

- **Easier:** strict boundary validation rejects malformed data early; one version point enables safe
  evolution; English `snake_case` matches the code.
- **Harder:** divergence from the OMD model needs reconciliation; adding fields needs version
  discipline; the simulator must emit exactly these fields.

## Affected contract

`contracts/turn1-events/*` — **v1.0.0 (new)**. Companion to ADR-0001.

## Evolution

- lat/lon + PostGIS geometry and the OMD occupancy ratio (turn 3).
- Fare-collection events with HMAC signature (turn 2).
- Additional event types in later turns (new minor versions unless breaking).

## Gate decisions

Decided by the data owner at the contract and data architecture gate, 2026-11-17:

- **`bus_id` is a string** (`B-101`..`B-107`), not a UUID — decided.
- **`distance_along_m`** (distance along the corridor in meters, no geometry) — decided.
- **`occupancy` is an integer 0–40** (absolute count), not the OMD float 0.0–1.0 — decided.
- **`arrival_ts` is optional and overwritten by ingestion** — decided.
- **OMD identifier reconciliation stays open** as a non-blocking note for the docs owner; it does
  not block implementation (the turn-1 contract is authoritative).
