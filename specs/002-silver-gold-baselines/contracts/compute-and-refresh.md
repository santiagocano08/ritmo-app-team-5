# `compute` CLI and `refresh` service

Both run the same cycle function (`src/pipeline/cycle.py`). It takes `as_of_ts` as an argument
(FR-004), runs the one-transaction cycle (research R4–R6) and returns the `snapshot_id`, or nothing
when the snapshot already existed.

## `python -m src.pipeline.compute` (Phase 2; it stays even if Phase 4 is cut)

| Argument | Meaning |
|---|---|
| `--as-of TS` | compute one snapshot at UTC time `TS` (ISO-8601) |
| `--from TS --to TS [--step S]` | replay: one snapshot every `S` seconds (default 5) in `[from, to]` |
| `--no-notify` | skip `pg_notify` (bulk replays) |

Reads `DATABASE_URL` and `LOG_LEVEL` from the environment, like the 001 entry points. Prints one
JSON line per snapshot (`snapshot_id`, `as_of_ts`, `max_bronze_id`, `status`). Exit code 0 on
success; non-zero after the first failed cycle, which leaves nothing published.

## `refresh` compose service (Phase 4, cuttable)

| Setting | Source | Default | Meaning |
|---|---|---|---|
| `DATABASE_URL` | `.env` | — (required) | same DSN as the other services |
| `LOG_LEVEL` | `.env` | `INFO` | |
| `REFRESH_INTERVAL_S` | `.env` | `5` | tick period (FR-036) |
| `REFRESH_CLOCK` | `.env` | `wall` in code; `.env.example` and compose set `data` for the simulator demo | reference-time source (research R3, DECIDED). `data`: `as_of_ts = max(event_ts)` of non-backend bus reports (falls back to the wall clock while there are none). `wall`: current UTC, for real telemetry; FR-004 applies to this mode. The `compute` CLI ignores it and always takes `--as-of`. |

Behaviour:

- One cycle per tick. A tick that falls inside a running cycle is skipped (FR-039).
- A failed cycle logs one structured JSON error line (error class, correlation id, no traceback in
  any outward message) and the loop continues (FR-040).
- The service loads the reference tables from `data/reference/` at start.
- No other service depends on `refresh`. `ingestion` keeps writing when it is stopped (FR-041).
