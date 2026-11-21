# Contract: Ingestion Boundary

**Authority**: `contracts/turn1-events/` (v1.0.0) + ADR-0001 + ADR-0002.
This document references the authoritative schemas; it does not redefine them.

## Purpose

Every event the simulator (or a crafted-event test) emits is validated at this
boundary before it touches the bronze store. Valid events land in immutable
`bronze.events`; invalid or duplicate events land in `bronze.rejections` with a
reason. This is the turn-1 data-integrity mechanism (Principle II, RNF-3.3.1).

## Input

A single event **envelope** as defined by `envelope.schema.json`:

```
{ schema_version, event_id (uuid), event_type (enum of 6),
  source (≥1 char), event_ts (date-time UTC),
  [arrival_ts (date-time UTC)],            # optional; overwritten by ingestion
  payload (object, shape per event_type) }
```

`event_type` selects the payload schema via the contract `oneOf`:
`bus_position`, `stop_arrival`, `stop_departure`, `rider_arrival`,
`driver_confirmation`, `incident_report`. The base simulator emits only the first
four; the boundary still accepts all six (forward-compatible).

## Validation (strict)

Enforced by the **generated** Pydantic V2 models (`src/pulsoflota/models/`,
from `contracts/turn1-events/*.schema.json`):

- `additionalProperties: false` → `model_config(extra='forbid')`: any
  undeclared field is rejected (`undeclared_field`).
- `schema_version` must be `"1.0.0"` else `unsupported_schema_version`.
- `event_type` must be in the enum else `unknown_event_type`.
- `event_id` must be a UUID else `invalid_uuid`.
- `event_ts` (and `arrival_ts` if present) must be date-time else
  `invalid_timestamp`.
- Missing required field → `missing_required_field`; wrong type → `wrong_type`;
  value out of range → `value_out_of_range`.
- `rider_arrival`: `train_trip_id` required when `origin == "train"`,
  forbidden otherwise (the contract `if/then/else`).

## Output

- **Valid** → `INSERT` into `bronze.events` with `arrival_ts = now()` stamped by
  ingestion (overwriting any value sent). See `data-model.md` E3.
- **Invalid** → `INSERT` into `bronze.rejections` with the matching `reason`
  (enum) and `original_message` stored as-is. See `data-model.md` E4.
- **Duplicate** (`source` + `event_id` already in `bronze.events`) → the
  unique-constraint violation is caught and recorded in `bronze.rejections`
  with reason `duplicate_event`. Bronze is unchanged. Idempotent: re-ingesting
  the same batch leaves bronze, silver and gold unchanged.

## Reason enum (contract `rejection.schema.json`)

`missing_required_field`, `wrong_type`, `value_out_of_range`,
`unknown_event_type`, `unsupported_schema_version`, `undeclared_field`,
`invalid_uuid`, `invalid_timestamp`, `duplicate_event`.

The deterministic mapping from a Pydantic `ValidationError` to a reason lives in
`src/ingestion/validate.py` (R12). No LLM judges data.

## Calling shapes

- **Container**: the simulator writes JSON-lines to stdout; the ingestion reader
  (`python -m src.ingestion.run`) consumes stdin, validates, writes to bronze.
- **Library / tests**: `src.ingestion.bronze.ingest(conn, envelope_dict)`
  validates and persists a single envelope, returning an `IngestResult`
  (`accepted` | `rejected` with reason). Used by the contract and integration
  tests with crafted events, without the live simulator.

## Non-goals (this story)

- No HTTP endpoint on the real-time path (the API service is health-only).
- No HMAC, no checksum, no fare-collection anti-fraud (turn 2, evolution).
- No source-outage "Estimated" state (later story; only idempotency is in
  scope).
