# Gold read access — new objects

Read-only for every consumer. Data writes them in the cycle transaction (`run_cycle`); nobody else writes.
Columns and rules: [data-model.md](../data-model.md) E6 to E8. Schemas: `contracts/read/*.schema.json` v1.0.0
(unchanged).

## `gold.incident` and `gold.incident_current`

| What | How to read |
|---|---|
| Active incidents now | `SELECT doc FROM gold.incident_current WHERE active` |
| Incidents at a given snapshot | `SELECT doc FROM gold.incident WHERE snapshot_id = %s` |

`doc` is exactly `incident.schema.json`. `until` is null while active; `duration_s` is minutes × 60;
`reported_by` is `script` for the simulator and `dispatcher` for backend reports. Refresh pushes the
usual `gold_snapshot` notification; no new channel.

## `gold.instruction_status`

| What | How to read |
|---|---|
| Status of the hold of a recommendation | `SELECT status, ts_by_status, observed_dwell_s FROM gold.instruction_status WHERE rec_id = %s` |

No row while the order is pending. `status` is `executed` or `not_executed`; `ts_by_status` has one key
with the same name, as in `instruction.schema.json`. The backend merges this with its own `inst_id`,
`text`, `sent` and `received` by `rec_id`.

## `gold.recommendation_effect`

| What | How to read |
|---|---|
| Effect of a recommendation | `SELECT doc FROM gold.recommendation_effect WHERE rec_id = %s` |

`doc` is exactly `recommendation_effect.schema.json`. A row exists only after the horizon window closed.
`result` follows ADR-0003 gate decision 6 with the 30 s threshold from `config.effect_settings`.
`ewt_observed_s` is clamped at 0 (schema minimum). Lineage columns: `rules_version`, `max_bronze_id`,
`before_snapshot_id`, `after_snapshot_id`.

## Guarantees

- Same bronze, same reference time, same rules version: same rows (SC-012).
- Every `doc` validates against its read schema; no field outside it (FR-027).
- Reads never block the cycle (MVCC, rows replaced inside one transaction).
- The scenario truth is not reachable from any of these objects.
