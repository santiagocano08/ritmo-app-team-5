# Turn 1 Event Contract (v1.0.0)

Message contract for the turn-1 simulator/ingestion pipeline on corridor C6-008 (Prado station,
direction 1, 5 + 2 buses, 5 s step). See **ADR-0001** (layers and ingestion semantics) and
**ADR-0002** (contract decision). These schemas are JSON Schema draft 2020-12; Pydantic V2 models
are derived from them by `implement-code` (no invented fields).

## Files in this contract

| File | What it validates |
|---|---|
| `envelope.schema.json` | The common envelope; selects the payload schema via `oneOf`. |
| `bus_position.schema.json` | `bus_position` payload. |
| `stop_arrival.schema.json` | `stop_arrival` payload. |
| `stop_departure.schema.json` | `stop_departure` payload. |
| `rider_arrival.schema.json` | `rider_arrival` payload (conditional `train_trip_id`). |
| `driver_confirmation.schema.json` | `driver_confirmation` payload. |
| `incident_report.schema.json` | `incident_report` payload. |
| `rejection.schema.json` | The `bronze.rejections` table record. |

The envelope `$ref`s the per-event-type schemas by relative file name, so all files in this
directory must be resolvable together.

## Idempotency rule

The idempotency key is **`source` + `event_id`**. Bronze has a unique constraint on this pair. A
second insert with the same key is discarded and recorded in `bronze.rejections` with reason
`duplicate_event`. Re-ingesting the same batch leaves bronze, silver and gold unchanged.

## Versioning rule

A **breaking change** (new required field, removed field, type change, tighter constraint) requires
a **new major version** (`2.0.0`); the ADR at that time states whether the previous version is still
accepted or explicitly rejected. A **non-breaking** change (new optional field) is a **minor bump**
(`1.1.0`) and both versions are accepted. There is never a silent edit of a published contract.

## Examples

Valid and invalid examples live in `examples/valid/` and `examples/invalid/`.
