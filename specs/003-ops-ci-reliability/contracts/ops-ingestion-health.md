# Contract — `ops.ingestion_health` and the ingestion healthcheck

Owner: data. Status: proposed for this story. Defined in `src/data/db/init/006_ops.sql` (Phase 3).

## The view

`SELECT * FROM ops.ingestion_health;` returns exactly one row.

| Column | Type | Meaning | NULL |
|---|---|---|---|
| `observed_at` | `timestamptz` | database clock at read time | never |
| `last_insert_age_s` | `double precision` | seconds since the last row was inserted into `bronze.events` (by `arrival_ts` of the highest `id`) | bronze is empty |
| `events_60s` | `bigint` | events inserted in the last 60 s | never |
| `rejections_60s` | `bigint` | contract rejections in the last 60 s, **without** `duplicate_event` | never |
| `duplicates_60s` | `bigint` | `duplicate_event` rows in the last 60 s | never |
| `rejection_rate_60s` | `numeric` | `rejections_60s ÷ (events_60s + rejections_60s)` | denominator is 0 |

Guarantees:

1. Read-only. The schema `ops` contains views only; the view writes nothing and stores nothing.
2. Time comes from the database clock (`clock_timestamp()`), not from the caller.
3. NULL is the only "not computable" value. A consumer never receives 0 or 100 % for an empty
   denominator.
4. Duplicates are excluded from the rejection count and rate everywhere, and reported on their own.
5. Column names and meanings are stable. Adding a column is compatible; renaming or removing one needs
   an update of this file and of the healthcheck test.

Example, healthy live stack: `last_insert_age_s` 0.4, `events_60s` 320, `rejections_60s` 0,
`duplicates_60s` 0, `rejection_rate_60s` 0. Example, empty bronze: `last_insert_age_s` NULL,
`events_60s` 0, `rejection_rate_60s` NULL.

## The healthcheck

Command: `python -m src.data.ingestion.health` inside the `ingestion` container.

| Aspect | Value |
|---|---|
| Setting | `INGESTION_HEALTH_MAX_AGE_S`, default 15 (number greater than 0) |
| Healthy | `last_insert_age_s` is not NULL and ≤ the setting; exit 0, prints `healthy` |
| Unhealthy | NULL, or above the setting: exit 1, prints `unhealthy: no insert in the last N s` |
| Failure | database unreachable, view missing, any other error: exit 1, prints `unhealthy: check failed` |
| Output rule | never prints the DSN, host, user, password or exception text |
| Reads | `ops.ingestion_health.last_insert_age_s` only |
| Depends on | `db` only. Not on the API, the console or `refresh` (FR-023) |

Compose settings: `interval 5s`, `timeout 3s`, `retries 1`, `start_period 20s` (reasons in
[research.md](../research.md) R5). Docker status: `starting` during the start period, `healthy` on the
first probe with exit 0, `unhealthy` after one failed probe, `healthy` again on the next success.

Bound (SC-008): after the last insert, `unhealthy` is reached within 15 s + one interval (5 s) + the
probe duration. Recovery to `healthy` is within one interval + the probe duration after the first new insert.

## Reading it by hand

```text
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -x -c "SELECT * FROM ops.ingestion_health"
docker inspect --format '{{json .State.Health}}' "$(docker compose ps -q ingestion)"
```
