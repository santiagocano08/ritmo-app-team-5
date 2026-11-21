# Data Model — CI Gate, Ingestion Resilience and Freshness Signal

**Feature**: 003-ops-ci-reliability | **Date**: 2026-11-20

This story stores **no new data**. Bronze, silver, gold and `config` are unchanged. It adds one
schema with one read-only view, three in-memory shapes inside the ingestion process, and one
document-level concept (the SLI). Every object has an owner (Principle II).

## Owners

| Object | Kind | Owner module | Storage |
|---|---|---|---|
| `ops.ingestion_health` | read-only view | data (`src/data/db/init/006_ops.sql`) | none (computed on read) |
| `RetryPolicy` | in-memory value | data (`src/data/ingestion/retry.py`) | none |
| Retry log line | JSON line on stderr | data (`src/data/ingestion/retry.py`) | container log only |
| Ingestion tally and summary | in-memory value, one log line at end of run | data (`src/data/ingestion/run.py`) | none |
| Healthcheck result | exit code and one text line | data (`src/data/ingestion/health.py`) | Docker health state |
| CI workflow run | GitHub Actions run | DevOps owner for new jobs; data team for the three jobs of this story | GitHub |
| Drill report, post-mortem, runbook, SLI text | documents | data team | `docs/ops/` |

## E1 — `ops.ingestion_health` (view, schema `ops`)

Always exactly one row. Sources: `bronze.events`, `bronze.rejections` (read only). Time source: the
database clock, `clock_timestamp()` evaluated once per read.

| Column | Type | Definition | NULL means |
|---|---|---|---|
| `observed_at` | `timestamptz` | the database clock at read time | n/a (never NULL) |
| `last_insert_age_s` | `double precision` | `observed_at − arrival_ts` (seconds) of the `bronze.events` row with the highest `id` | bronze is empty: freshness unknown |
| `events_60s` | `bigint` | rows of `bronze.events` with `arrival_ts > observed_at − 60 s` | n/a (0 when none) |
| `rejections_60s` | `bigint` | rows of `bronze.rejections` with `received_ts > observed_at − 60 s` and `reason <> 'duplicate_event'` | n/a (0 when none) |
| `duplicates_60s` | `bigint` | same window, `reason = 'duplicate_event'` | n/a (0 when none) |
| `rejection_rate_60s` | `numeric` | `rejections_60s ÷ (events_60s + rejections_60s)` | the denominator is 0: not computable |

Rules:

- **Duplicates never count as rejections** (FR-014) and never refresh freshness (a duplicate is not a
  bronze insert).
- **NULL is "not computable"**, never 0 and never a made-up value (FR-017). A consumer must test for
  NULL.
- **Read-only** (FR-018): the schema contains views only. No `INSERT`, `UPDATE` or `DELETE` on any
  layer appears in `006_ops.sql` or in `health.py`. The view is not updatable (aggregates).
- The 60 s window is fixed (the constitution's "within 1 min"). It is not a setting.
- Access: no role or grant model exists in turn 1 (single database user); the view inherits that.
  Listed as evolution with RBAC (turn 2).

Validation points: view columns and NULL semantics are tested on a throwaway database with crafted
bronze rows (see [quickstart.md](quickstart.md)); the column list is the contract in
[contracts/ops-ingestion-health.md](contracts/ops-ingestion-health.md).

## E2 — `RetryPolicy` (in memory)

| Field | Type | Source | Default | Constraint |
|---|---|---|---|---|
| `initial_s` | float | `INGESTION_RETRY_INITIAL_S` | 1 | > 0 |
| `max_wait_s` | float | `INGESTION_RETRY_MAX_WAIT_S` | 5 | ≥ `initial_s` |
| `total_s` | float | `INGESTION_RETRY_TOTAL_S` | 120 | ≥ `max_wait_s` |

Derived: wait before attempt *n* (n ≥ 1) = `min(initial_s × 2^(n−1), max_wait_s)`, shortened so the
last attempt falls at `total_s`. Constant: connection timeout per attempt, 3 s. Invalid values stop the
process at start with a `RuntimeError` (no line is read).

State of one outage (reset after the first stored line following a failure): `outage_started`
(monotonic clock), `attempt` (count since the first failure).

### Retry classification (E2a)

Retryable: `OperationalError` or `InterfaceError` with `sqlstate` of `None`, class `08`, `57P01`, `57P02`,
or `57P03`. Everything else is raised unchanged. The reason vocabulary is fixed: `db_unreachable`,
`db_connection_lost`, `db_shutting_down`, `db_starting`.

## E3 — Retry log line (JSON on stderr)

Three event names, one line each, defined by
[contracts/ingestion-retry-log.schema.json](contracts/ingestion-retry-log.schema.json):

| Event | When | Fields (besides `ts`, `level`, `event`) |
|---|---|---|
| `db_retry` | after each failed attempt that will be retried | `attempt`, `wait_s`, `elapsed_s`, `reason`, `sqlstate` |
| `db_retry_exhausted` | the window ended; the process then exits 1 | `attempts`, `elapsed_s`, `window_s`, `reason`, `sqlstate` |
| `db_recovered` | the first line stored after a failure | `attempts`, `outage_s` |

`ts` is UTC. A line never contains a connection string, user, host, password, exception text or any
part of an event (FR-011, SC-005).

## E4 — Ingestion tally and summary (in memory, logged once at end of run)

| Field | Meaning |
|---|---|
| `accepted` | events stored in `bronze.events` |
| `by_reason` | contract rejections per reason (without `duplicate_event`) |
| `rejected` | sum of `by_reason` |
| `duplicates` | lines whose `(source, event_id)` was already in bronze |
| `rejection_rate` | `rejected ÷ (accepted + rejected)`, or `null` when the denominator is 0 |

This is the same definition as E1, over the whole run instead of 60 s (FR-014).

## E5 — Healthcheck result

Exit code `0` when `last_insert_age_s` is not NULL and ≤ `INGESTION_HEALTH_MAX_AGE_S` (default 15),
otherwise `1`. One output line: `healthy`, `unhealthy: no insert in the last N s`, or
`unhealthy: check failed` (database unreachable, view missing, bad setting at probe time). No DSN, host
or exception text is printed.

## E6 — Freshness SLI (document concept)

At each probe the service is *fresh* if `last_insert_age_s ≤ 15 s`, else *stale*. SLI = fresh probes ÷
total probes over a rolling window, counted while a live feed is expected. Not stored; the proposal text
is in `docs/ops/sli-slo-proposal.md`.

## State transitions

Ingestion connection state (per outage):

```text
CONNECTED --retryable error--> WAITING (log db_retry, close connection, wait)
WAITING   --wait elapsed-----> CONNECTING
CONNECTING--failure----------> WAITING            (if window not exhausted)
CONNECTING--failure----------> EXITED(1)          (window exhausted: log db_retry_exhausted)
CONNECTING--success + line stored--> CONNECTED    (log db_recovered, reset outage state)
CONNECTED --non-retryable error--> EXITED(1)      (unchanged behavior, loud)
```

Healthcheck state (Docker): `starting` (during the 20 s start period) → `healthy` on the first probe
that exits 0 → `unhealthy` after one failed probe → `healthy` on the next successful probe.

## Lineage and immutability

Bronze stays insert-only. A line retried after a lost acknowledgement is stored once in
`bronze.events` (the `ON CONFLICT` rule) and, at most, once more as a `duplicate_event` row in
`bronze.rejections`. The `ops` view reads, never writes. Gold lineage (`rules_version`,
`max_bronze_id`) is untouched.
