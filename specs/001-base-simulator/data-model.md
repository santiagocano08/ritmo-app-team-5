# Data Model — Turn-1 Run Environment and Base Simulator

**Feature**: 001-base-simulator | **Turn**: 1 (active) | **Date**: 2026-11-17

Defines the entities this feature persists and consumes. The authoritative
event message shape is the accepted contract `contracts/turn1-events/` v1.0.0
(ADR-0001, ADR-0002); this document does **not** redefine it — it describes how
those contract messages map to PostgreSQL storage and how the reference data and
the in-memory simulator state are shaped. Storage is PostgreSQL 16 only, plain
SQL init scripts, no ORM, no migrations.

## Layering (ADR-0001)

- **bronze** — immutable, insert-only raw events that passed boundary
  validation. The only source of truth for replay and audit. Rejections live in
  `bronze.rejections` (a table *inside* the bronze schema, not a fourth schema).
- **silver** / **gold** — created by the init scripts (empty) for forward
  compatibility, but **not populated in this story** (out of scope). Their tables
  are stubbed so later stories do not need a schema-creation PR.

## Entities

### E1 — Reference data set (files, not tables)

Curated, reproducible inputs under `data/reference/` (<1 MB), built from
`data/raw/` by `src/reference/build.py` (`make reference`). Consumed by the
simulator and the fixtures. Not bronze; loaded as files.

| File | Key columns | Source (raw) | FR |
|---|---|---|---|
| `segments.csv` | `segment_id` (1..17), `from_name`, `length_m`, `free_flow_kmh`, `slope_pct` | `plata/tramos_c6008_s1_osm.csv` | FR-002 |
| `stops.csv` | `stop_id` (`P-<objectid>`), `stop_name`, `distance_along_m`, `segment_id` | `metro_capas/paradas_alimentadoras.geojson` (real C6-008 stops) + `rutas_alimentadoras.geojson` (direction-1 line) — see R6 | FR-003, FR-008 |
| `train_arrivals.csv` | `train_trip_id`, `arrival_time`, `service_id` (weekday) | `metro/GTFS-Metro_de_Medellin_2025.zip` | FR-004 |
| `congestion_factor.csv` | `hour` (0..23), `congestion_factor` (mean SIMM speed ÷ corridor free-flow speed; 0.43–0.56 sanity band) | `plata/simm_corredor_c6008.csv` + `tramos_c6008_s1_osm.csv` (`v_libre_kmh`, length-weighted) — see R7 | FR-005 |
| `demand_params.csv` | `hour` (0..23), `metro_line_a_shape`, plus constant `feeder_share_basin6` | `metro/Afluencia_Metro_2025.xlsx` (hourly shape), `medata/pasajeros_movilizados_mensual_metro_de_medellin.csv` (basin 6 vs line A) — see R9 | FR-006 |
| `SOURCES.md` | one line per file: source URL, license, download date, transformation | build | FR-007 |

**Validation rules**: segments = exactly 17, direction 1, ordered; congestion
factor computed as mean SIMM speed ÷ length-weighted corridor free-flow speed
(the 0.43–0.56 band is an expected sanity check — values outside it emit a
warning and are kept as computed, per R7); stops are the real C6-008 stops with
`P-<objectid>` ids (R6); `SOURCES.md` line per file. Two builds are byte-identical
(FR-001). A missing required raw source fails the build with a named message.

### E2 — Simulated event (envelope, contract-defined)

The contract envelope. **Fields are fixed by the contract; the simulator emits
exactly these, and Pydantic V2 models are generated from the schemas — no
invented fields (R3).**

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string enum `["1.0.0"]` | yes | Turn 1 accepts only `1.0.0`. |
| `event_id` | string UUID v4 | yes | Idempotency key part 2. Deterministic from seed (R13). |
| `event_type` | string enum (6) | yes | Base simulator emits 4: `bus_position`, `stop_arrival`, `stop_departure`, `rider_arrival` (R16). |
| `source` | string | yes | Turn 1: `"simulator"`. |
| `event_ts` | string date-time UTC | yes | Event time; used in all calculations. |
| `arrival_ts` | string date-time UTC | no | Stamped by ingestion on receipt; overwritten, never sent by source. |
| `payload` | object | yes | Shape per `event_type` via the contract `oneOf`. |

Payloads (see the contract schemas for the exact fields and constraints):

- **bus_position** — `bus_id` (B-101..B-107), `operator`, `trip_id`,
  `direction` (1), `distance_along_m` (≥0), `speed_kmh` (0–120),
  `schedule_deviation_s` (int), `doors_open` (bool), `occupancy` (0–40).
- **stop_arrival / stop_departure** — `bus_id`, `trip_id`, `stop_id`,
  `boarded`, `alighted`, `rejected`, `occupancy` (0–40).
- **rider_arrival** — `stop_id`, `direction` (1), `origin` (`train`|`street`),
  `destination_stop_id`, `train_trip_id` (required iff `origin == "train"`,
  forbidden otherwise — conditional rule).

### E3 — Bronze event store (`bronze.events`)

Insert-only landing table for valid events. The envelope is stored with the
payload as JSONB and the idempotency/timestamp columns extracted for constraints
and queries.

```sql
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE bronze.events (
    id             BIGSERIAL PRIMARY KEY,          -- bronze row id (lineage)
    source         TEXT        NOT NULL,
    event_id       UUID        NOT NULL,
    schema_version TEXT        NOT NULL,
    event_type     TEXT        NOT NULL,
    event_ts       TIMESTAMPTZ NOT NULL,
    arrival_ts     TIMESTAMPTZ NOT NULL,            -- stamped by ingestion
    payload        JSONB       NOT NULL,
    ingested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT bronze_events_unique UNIQUE (source, event_id)
);

-- hot path lookups
CREATE INDEX ON bronze.events (event_type, event_ts);
CREATE INDEX ON bronze.events (source, event_ts);
```

**Rules** (enforced in code + tested):

- Insert-only. No `UPDATE`, no `DELETE` (FR-016). Application issues only
  `INSERT`; `test_bronze_immutable` asserts invariance across re-ingest.
- Idempotent on `(source, event_id)`: a duplicate insert raises the unique
  constraint; caught and routed to `bronze.rejections` with reason
  `duplicate_event` (FR-015).
- Two timestamps: `event_ts` (from the message) and `arrival_ts` (stamped by
  ingestion). All calculations use `event_ts` (ADR-0001).
- `arrival_ts` is overwritten by ingestion even if the source sent one.

### E4 — Bronze rejections (`bronze.rejections`)

Record of every event rejected at the boundary (schema failure) or discarded as
a duplicate (idempotency). Matches `rejection.schema.json`.

```sql
CREATE TABLE bronze.rejections (
    id               BIGSERIAL PRIMARY KEY,
    original_message JSONB,                          -- original message as-is
    reason           TEXT        NOT NULL,
    received_ts      TIMESTAMPTZ NOT NULL,
    CONSTRAINT bronze_rejections_reason_chk CHECK (
        reason IN (
          'missing_required_field','wrong_type','value_out_of_range',
          'unknown_event_type','unsupported_schema_version',
          'undeclared_field','invalid_uuid','invalid_timestamp',
          'duplicate_event'
        )
    )
);

CREATE INDEX ON bronze.rejections (reason, received_ts);
```

- `original_message` stored as-is (it already failed validation).
- `reason` constrained to the contract enum (R12).
- Rejections are append-only in practice; no contract rule forbids their
  deletion, but turn 1 leaves them insert-only for the audit.

### E5 — Bus (in-memory simulator state, not persisted)

- `bus_id`: `B-101`..`B-107` (contract enum).
- `capacity`: 40.
- `status`: `in_service` (B-101..B-105) or `reserve` (B-106..B-107). Reserve buses
  are in the roster but never dispatched in this story (R16).
- Runtime state: current `trip_id`, `distance_along_m`, `occupancy`,
  `speed_kmh`, `doors_open`, `schedule_deviation_s`.

### E6 — Trip (in-memory simulator state, not persisted)

- A direction-1 run over the ordered 17 segments and the ordered stops of
  C6-008.
- `trip_id`: stable string (e.g. `C6-008-AM-001`), deterministic from the seed.
- Produces the event sequence: `bus_position` every 5 s + `stop_arrival` /
  `stop_departure` at each stop + `rider_arrival` per boarding attempt.

### E7 — Silver / gold schemas (stubs)

```sql
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
```

Empty in this story. Later stories add `silver.*` (deduped positions, per-bus
current state with the "Estimated" flag, dwell events) and `gold.*` (headway,
mean wait, EWT) with `rules_version` + `max_bronze_id` lineage columns. Created
now only so the init script is forward-compatible.

## State transitions (turn-1 subset)

```
Simulator (seeded)
   │  emits envelope (event_type ∈ {bus_position, stop_arrival,
   │                                stop_departure, rider_arrival})
   ▼
Ingestion boundary (Pydantic V2, generated from contract)
   │
   ├─ valid  ──► bronze.events  (INSERT; UNIQUE(source,event_id))
   │                              └─ duplicate ──► bronze.rejections (duplicate_event)
   └─ invalid ──► bronze.rejections (reason ∈ contract enum)
```

- A bus that does not report for >2 min becomes "Estimated" and raises no alert
  (ADR-0001) — **deferred** to a later story (out of scope here; only basic
  idempotency is in scope per the spec).
- No `UPDATE`/`DELETE` on bronze. Silver/gold recomputed from bronze in later
  stories.

## Lineage

- `bronze.events.id` is the lineage anchor (`max_bronze_id` on future gold rows).
- `bronze.rejections` carries the original message and reason for audit.
- Reference data is not bronze; it is descriptive input with `SOURCES.md`
  lineage (R10).
