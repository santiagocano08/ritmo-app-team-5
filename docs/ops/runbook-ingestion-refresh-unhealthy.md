# Runbook: ingestion or refresh is unhealthy

Use it when `ingestion` or `refresh` shows `unhealthy`, or when the dispatcher sees stale data. Run the
commands from the repository root. They print no credentials.

## 1. See the state

```text
docker compose ps
docker inspect --format '{{json .State.Health}}' "$(docker compose ps -q ingestion)"
docker inspect --format '{{json .State.Health}}' "$(docker compose ps -q refresh)"
docker compose logs --no-color --tail 50 ingestion
```

Check `db` first: if it is not `healthy`, every other symptom follows from it.

## 2. Read the freshness view

```text
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -x -c "SELECT * FROM ops.ingestion_health"'
```

| Column | Reading |
|---|---|
| `last_insert_age_s` | Seconds since the last bronze insert. Above 15: stale. NULL: bronze is empty. |
| `events_60s` | Events stored in the last minute. 0 together with a growing age means the feed stopped. |
| `rejections_60s` | Contract rejections only. Duplicates are not counted here. |
| `duplicates_60s` | `duplicate_event` rows. A burst means something replayed. |
| `rejection_rate_60s` | Rejections / (events + rejections). NULL when there was no traffic: it is not 0 % and not 100 %. |

## 3. Recover

### Database outage

Symptoms: `db` is stopped or unhealthy; `ingestion` logs `db_retry` lines (JSON, no credentials).

1. Start the database: `docker compose start db` and wait for `healthy` in `docker compose ps`.
2. Ingestion retries the same line (waits 1, 2, 4, then 5 s) for up to 120 s and logs one `db_recovered`
   line. No restart is needed.
3. If the window ended, ingestion logged `db_retry_exhausted` and exited: `docker compose up -d ingestion`.
   A restart replays the feed from the start; duplicates are discarded and counted apart from rejections.

### Stopped feed

Symptoms: `ingestion` is `running` but `unhealthy`; `events_60s` is 0 and the age keeps growing.

1. Confirm the simulator is the one stalled: `docker compose logs --tail 20 ingestion`.
2. A frozen simulator process (for tests) is resumed with
   `docker compose exec -T ingestion python - resume < scripts/drill/feed_control.py`
   (`stop` freezes it the same way).
3. A finite run that reached `SIM_DURATION_S` is `unhealthy` by design. Start a new run:
   `docker compose up -d --force-recreate ingestion`.

### Crashing ingestion

Symptoms: `RestartCount` of `ingestion` keeps growing.

1. Read the last exit reason: `docker compose logs --no-color --tail 100 ingestion`.
2. A non-retryable error (contract or data error in the code path) exits on purpose; do not loop the
   restart. Capture the log and escalate.
3. After a crash the container restarts and replays the stream. Check `duplicates_60s` in the view: they
   are expected and are not rejections.

### Stalled `refresh`

Symptoms: `refresh` is `unhealthy` (no gold snapshot in `REFRESH_HEALTH_MAX_AGE_S`, default 30 s).

1. Check the view first. If `events_60s` is 0 the feed stopped, and in `data` mode `refresh` stops with it.
   Fix the feed (above); `refresh` recovers on its own.
2. If the feed is fresh, read `docker compose logs --no-color --tail 50 refresh`, then
   `docker compose restart refresh`. Stopping `refresh` never stops ingestion.

## 4. Old volume: the view does not exist

The init scripts run only on a fresh volume. If the healthcheck prints `unhealthy: check failed` and the
view is missing, apply the script once, or reset a throwaway stack:

```text
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < src/data/db/init/006_ops.sql
```

or `docker compose down -v && docker compose up -d` (deletes the data volume of that project only).

## 5. Notes

- The probe runs every 5 s and one failed probe turns the service `unhealthy`; it can flap once if an insert
  is late. A single flap that recovers on the next probe needs no action.
- `unhealthy` appears within 15 s + one 5 s interval + the probe time after the last insert.

## 6. When to escalate

Escalate to the data owner when: `db` does not become `healthy` within 5 minutes; `db_retry_exhausted`
repeats after a restart; `rejections_60s` is above 0 for several minutes (contract rejections are real
bad data); `last_insert_age_s` stays above 15 with a healthy `db` and a running simulator; or anything
outside this runbook. Bring the output of sections 1 and 2.
