# Data Model — Scenario Injectors, Hold Loop and Effect Table

**Feature**: 004-scenario-injectors | **Date**: 2026-11-21

Existing layers are unchanged: bronze is insert-only, silver tables and the three existing gold objects
keep their shape. This story adds objects in the simulator process (memory and a truth sink), two `config`
tables and three `gold` tables (one init script, `007_scenarios.sql`). Every object has an owner
(Principle II). All SQL is parameterized; none of it writes to bronze.

## Owners

| Object | Kind | Owner module | Storage |
|---|---|---|---|
| Scenario file | JSON input | data, `src/data/simulator/scenarios/config.py` | file in the image or test fixtures |
| Scenario truth record | JSON line | data, `scenarios/truth.py` | `SIM_TRUTH_PATH` file or stderr; **never** in a schema the pipeline reads |
| Injected event | contract event | data, simulator | bronze (like any event) |
| Seed recommendation | reference data (demo and test) | data, `src/data/seeds/recommendations.json` and `pipeline/seeds.py` | file + `config.seed_recommendation` |
| Hold order, hold board | in-memory | data, `scenarios/holds.py` | none |
| `decision` command event | bronze row | **backend** (data only reads) | `bronze.events` |
| `config.effect_settings` | settings, one row | data | PostgreSQL |
| `gold.incident` | gold object per snapshot | data, `pipeline/incidents.py` | PostgreSQL |
| `gold.instruction_status` | gold object, rebuilt each cycle | data, `pipeline/holds.py` | PostgreSQL |
| `gold.recommendation_effect` | gold object, rebuilt each cycle | data, `pipeline/effects.py` | PostgreSQL |

## E1 — Scenario file (input)

JSON array; each element has a `type` discriminator. All objects forbid extra fields.

| `type` | Fields (all required) | Ranges |
|---|---|---|
| `C1` | `id`, `start_s`, `bus`, `stop`, `extra_s` | `300 < extra_s <= 600`; `stop` in P-884..P-899 |
| `C2` | `id`, `start_s`, `bus`, `delay_s` | `300 < delay_s <= 600` |
| `C5` | `id`, `start_s`, `bus`, `duration_s` | `0 < duration_s <= 300` |
| `D1_SILENCE` | `id`, `start_s`, `bus`, `duration_s` | `duration_s >= 1` |
| `D1_DUPLICATES` | `id`, `start_s`, `count` | `1 <= count <= 1000` |

Common: `id` unique non-empty string; `start_s` integer `>= 0`; `bus` in B-101..B-105. Validation rules
(overlap, unknown names) are in [research.md](research.md) R1 and the user-facing note in
[contracts/scenario-config.md](contracts/scenario-config.md).

## E2 — Scenario truth record (hidden)

One JSON object per line.

| Field | Type | Meaning |
|---|---|---|
| `scenario_id` | string | the `id` of the scenario, or `hold:<rec_id>` for a hold record |
| `type` | string | `C1`, `C2`, `C5`, `D1_SILENCE`, `D1_DUPLICATES`, `HOLD` |
| `params` | object | the validated parameters (no event content) |
| `bus`, `stop` | string or null | affected bus and stop |
| `fired` | boolean | false when the start time was never reached or the precondition never held |
| `effective_ts` | string (UTC) or null | event time of the step in which it took effect |
| `follower_gap_s`, `target_reached` | number, boolean (C1 only) | departure gap at the C1 stop and whether it is below 300 s; null until known |
| `event_ids` | array of UUID (D1_DUPLICATES only) | the repeated events |
| `rec_id`, `hold_s`, `complied` | UUID, number, boolean (HOLD only) | the seeded draw result |

No secret, no PII, no event payload. Rows exist only in the sink.

## E3 — Seed recommendation (`config.seed_recommendation`)

Reference data for the demo and tests; removed when the recommendation door exists (spec Open
integration items). Loaded from `src/data/seeds/recommendations.json` (a JSON array of objects shaped as
`contracts/read/recommendation.schema.json`) by `pipeline/seeds.py` at refresh start and in the compute
CLI, DELETE + INSERT in one transaction (like `load_reference`).

| Column | Type | Notes |
|---|---|---|
| `rec_id` | `UUID` primary key | from the document |
| `doc` | `JSONB NOT NULL` | the full recommendation, validated by the generated `Recommendation` model before insert |

Only entries with `action.type = "hold"` are used by this story. Entries are rejected at load when the
schema fails (a hold above 90 s cannot be loaded).

## E4 — `config.effect_settings` (one row)

| Column | Type | Value | Source |
|---|---|---|---|
| `id` | `BOOLEAN PRIMARY KEY CHECK (id)` | true | single-row guard |
| `worked_threshold_s` | `NUMERIC NOT NULL CHECK (worked_threshold_s > 0)` | 30 | ADR-0003 gate decision 6 |

Seed `ON CONFLICT DO NOTHING`. The planned headway stays in `config.corridor_settings`
(`headway_planned_s` = 600). The cap 90 s and the ±15 s tolerance are constants in `rules/holds.py`
(contract numbers, one definition, like `ESTIMATED_AFTER_S`).

## E5 — Hold order and board (in memory)

`Order`: `rec_id`, `bus_id`, `stop_id`, `hold_s` (0 to 90), `from_s` (simulated seconds, or minus infinity),
`until_s`, `cancelled` flag, `complies` (result of the seeded draw). `HoldBoard`: thread-safe map
`(bus_id, stop_id) → [Order]` plus the set of seen `rec_id` and counters (`ignored_unknown`,
`ignored_discard`). The engine reads it; the poller writes it.

## E6 — `gold.incident` (per snapshot)

| Column | Type | Notes |
|---|---|---|
| `snapshot_id` | `UUID NOT NULL REFERENCES gold.snapshots` | |
| `inc_id` | `UUID NOT NULL` | bronze `event_id` of the report |
| `active` | `BOOLEAN NOT NULL` | `until` is null |
| `doc` | `JSONB NOT NULL` | exactly `incident.schema.json` v1.0.0 (`additionalProperties: false`) |
| `rules_version` | `TEXT NOT NULL` | 1.1.0 |
| `max_bronze_id` | `BIGINT NOT NULL` | |

Primary key `(snapshot_id, inc_id)`. View `gold.incident_current`: the rows of the newest snapshot of the
current rules version. Doc fields: `schema_version` "1.0.0", `inc_id`, `type`, `target_id`, `duration_s`
(minutes × 60), `since`, `until` (null while `since <= as_of < end`), `reported_by`.

## E7 — `gold.instruction_status` (rebuilt each cycle)

| Column | Type | Notes |
|---|---|---|
| `rec_id` | `UUID PRIMARY KEY` | key the backend joins on |
| `bus_id` | `TEXT NOT NULL` | |
| `stop_id` | `TEXT NOT NULL` | |
| `hold_s` | `NUMERIC NOT NULL` | requested hold (from the seed) |
| `observed_dwell_s` | `NUMERIC` | null when no visit ran |
| `status` | `TEXT NOT NULL CHECK (status IN ('executed','not_executed'))` | |
| `ts_by_status` | `JSONB NOT NULL` | exactly one key, `executed` or `not_executed`, an RFC 3339 UTC time |
| `rules_version`, `max_bronze_id` | `TEXT`, `BIGINT NOT NULL` | lineage of the producing cycle |

`status` and `ts_by_status` are checked in tests against `instruction.schema.json`. No row exists while an
order is pending. State rules are in research R5.

**Transitions**: `(none)` → `executed` | `not_executed`. A row never goes back to none, and a later cycle
with the same bronze gives the same row.

## E8 — `gold.recommendation_effect` (rebuilt each cycle)

| Column | Type | Notes |
|---|---|---|
| `rec_id` | `UUID PRIMARY KEY` | |
| `doc` | `JSONB NOT NULL` | exactly `recommendation_effect.schema.json` v1.0.0 |
| `before_snapshot_id` | `UUID` | snapshot used for `headway_before_s` (null if none) |
| `after_snapshot_id` | `UUID` | snapshot used for headway after and EWT observed (null if none) |
| `rules_version`, `max_bronze_id` | `TEXT`, `BIGINT NOT NULL` | lineage of the producing cycle |

Doc fields and rules: `headway_before_s`, `headway_after_s`, `headway_planned_s` (600, from config),
`ewt_expected_s`, `ewt_observed_s` (clamped at 0), `result` in `worked | partial | did_not_work | no_data`
(research R7). A row exists only when a snapshot at or after `T0 + horizon_s` exists.

## Relationships

```text
bronze.events (decision, source=backend) ──┐
config.seed_recommendation (rec_id) ───────┼─► gold.instruction_status (rec_id)
silver.stop_visits (arrival, departure) ───┘            │
silver.incidents ──► gold.incident (per snapshot)       ▼
gold.snapshots / gold.corridor_now / gold.service_metric ──► gold.recommendation_effect (rec_id)
                                                        (before/after snapshot ids = lineage)
simulator process: scenario file ─► injectors ─► events ─► (stdout) ─► ingestion ─► bronze
                                  └► truth sink (file or stderr)   ✗ never read by the pipeline
bronze.events (decision) ─► poller (read-only) ─► HoldBoard ─► engine (hold at arrival)
```

## Validation rules (summary)

- Scenario file: strict schema, ranges and overlap rule; failure before the first event.
- Seed file: `recommendation.schema.json`; `hold` duration 0 to 90 s.
- Incident, effect: generated Pydantic models built from the existing read schemas; extra fields are
  impossible (`additionalProperties: false`, FR-027).
- Instruction status: enum and `ts_by_status` keys checked against `instruction.schema.json`.
- Determinism: all rebuilds depend only on bronze, silver, `config` and stored snapshots; the same inputs
  give the same rows (SC-012).
