# Research — CI Gate, Ingestion Resilience and Freshness Signal

**Feature**: 003-ops-ci-reliability | **Turn**: 1 (active) | **Date**: 2026-11-20

Each entry has a **Decision**, a **Rationale** and the **Alternatives considered**. Numbers come from
the spec's drill baseline, from the repository, or from a measurement made while writing this plan
(the command is given). A number that is a design choice, not a measurement, is labeled **choice**.
A number that the plan could not measure yet is labeled **to measure** and names the phase that
measures it.

Inputs read: `spec.md` (with Clarifications), `specs/001-base-simulator/` and
`specs/002-silver-gold-baselines/` (plan, research, verification), `src/data/ingestion/{run,bronze,validate}.py`,
`src/data/refresh/health.py`, `src/data/db/init/*.sql`, `src/pulsoflota/{config,db}.py`,
`docker-compose.yml`, `Dockerfile`, `.dockerignore`, `.env.example`, `pyproject.toml`, `Makefile`,
the tests under `src/data/tests/` and `tests/`, ADR-0001/0002, the constitution, `docs/turns-ritmo.md`,
`.github/CODEOWNERS`.

---

## Facts from the existing code that shape this design

| Fact | Where | Consequence here |
|---|---|---|
| `ingestion` runs `sh -c "simulator \| python -m src.data.ingestion.run"`, `restart: unless-stopped`, image target `prod`, `PYTHONPATH=/app` | `docker-compose.yml` | A healthcheck can run `python -m src.data.ingestion.health` in the same container. Any exit of the pipe restarts both processes (the replay seen in drills F2 and F3). |
| `run.py` opens one autocommit connection; `connect_with_retry` allows 10 attempts, 2 s apart (about 20 s) and raises `RuntimeError`; any other `psycopg` error escapes `consume` and kills the process | `src/data/ingestion/run.py` | This is the F2 root cause. The 20 s start-up retry is also shorter than the 31 s drill outage. |
| `ingest()` validates first (`validate_envelope` returns a result, it does not raise), then inserts with `ON CONFLICT ON CONSTRAINT bronze_events_unique DO NOTHING RETURNING id`. A conflict becomes a `bronze.rejections` row with reason `duplicate_event` | `src/data/ingestion/bronze.py` | A bad event is a rejection and never an exception. Only database errors can escape. A retried line that was already committed becomes a duplicate (safe). |
| `consume` counts `duplicate_event` under the same `Counter` as contract rejections | `run.py` | Root cause of the false 65 % (971 ÷ (525 + 971) = 64.9 %). |
| `bronze.events.id` is `BIGSERIAL`; `arrival_ts` is `now()` at insert; indexes exist on `(event_type, event_ts)` and `(source, event_ts)` only. `bronze.rejections` has an index on `(reason, received_ts)` | `002_bronze.sql` | "Last insert" is read through the primary key (`ORDER BY id DESC LIMIT 1`). Window counts on `arrival_ts` are a sequential scan (R7). |
| The refresh healthcheck uses `clock_timestamp()`, `connect_timeout=3`, prints only `healthy` / `unhealthy: …` / `unhealthy: check failed`, exit 0 or 1; compose uses interval 10 s, timeout 5 s, retries 3, start period 40 s | `src/data/refresh/health.py`, `docker-compose.yml` | The ingestion healthcheck copies the module shape and the output rules, with its own numbers (R5). |
| Init scripts run only on a fresh volume; the test template DB applies `src/data/db/init/*.sql` in sorted order | `db_helpers.py`, 002 research R-notes | `006_ops.sql` appears in the test template automatically. A live stack needs `down -v` or a manual `psql -f` (R14). |
| `tests` service mounts only `tests/`, `src/data/tests/`, `contracts/`, `data/`, `specs/`, `docs/adr/`, `docker-compose.yml`, `.env.example`; `.dockerignore` excludes `docs/`, `specs/`, `scripts/`, `.github/` from the image | `docker-compose.yml`, `.dockerignore` | New tests that read the workflow, `docs/ops/` or `scripts/` need read-only mounts (R9, R12). |
| The 002 final Andon run of the CI-ready command: 422 passed, 4 skipped, 0 failed, coverage 91.97 %, 113 s | `specs/002-…/verification.md` | Reference for SC-002. Re-measure on this branch at the start of Phase 1 (the `src/data/` refactor came after). |
| The simulator, seed 42, 3,600 simulated seconds: 3,851 events, 1,439,431 bytes (about 373.8 B per event). At `--pace 1` (compose default) the run takes 720 s of wall time, about 5.35 events/s, about 2.0 KB/s | Measured for this plan: `uv run python -m src.data.simulator.main --seed 42 --duration 3600 \| wc -lc` | Sizes the pipe-buffer reasoning in R3 and the drill length in R12. |
| `.github/` contains only `CODEOWNERS`; no workflow exists; the remote default branch is `main` | `git ls-files`, `git branch -a` | The workflow is new. CODEOWNERS covers `/contracts/`, `/src/data/rules/`, `/docs/adr/` (relevant to the ADR addendum). |

---

## R1 — Retry defaults (FR-010)

**Decision** (all **choice**, justified below):

| Setting | Env var | Default | Rule |
|---|---|---|---|
| Initial wait | `INGESTION_RETRY_INITIAL_S` | `1` | first wait after a failure |
| Maximum wait per attempt | `INGESTION_RETRY_MAX_WAIT_S` | `5` | wait doubles each attempt, capped here |
| Total retry window | `INGESTION_RETRY_TOTAL_S` | `120` | measured on a monotonic clock from the first failure of an outage |
| Connection timeout per attempt | not configurable | `3` s | same value as the refresh healthcheck |

Backoff is exponential with factor 2 and **no jitter**: waits are 1, 2, 4, 5, 5, 5 … seconds. There
is a single ingestion process, so there is no thundering herd to spread, and a fixed schedule is
testable with a fake clock. The wait that would cross the window end is shortened so the last attempt
happens exactly at the window end; if it fails, ingestion logs the final error and exits 1.

Schedule of attempts after the first failure at t = 0 s: 1, 3, 7, 12, 17, 22, 27, 32, 37, … s. For
the drill (db stopped for 31 s, then `start`; the drill baseline gives the 31 s, not the restart
time) the first attempt that can succeed is the one after the database is ready. **Worst case after
the database is ready: one maximum wait (5 s) plus the connection time.** A full-window outage emits
about 26 `db_retry` lines (4 in the first 7 s, then one every 5 s up to 120 s).

**Rationale**:

- 120 s is 3.9 times the 31 s drill outage. That leaves room for the PostgreSQL start and crash
  recovery after `kill`, which the baseline did not record, without a magic number. A shorter window
  (60 s) covers the drill only 1.9 times; a longer one (300 s) delays the loud failure and the
  restart-and-replay that follows it.
- The 5 s cap bounds the recovery delay after the database returns. It must be well below the 15 s
  freshness threshold so SC-009 ("lag after F2 below 15 s") is reachable: the lag after recovery is
  at most the cap plus the connection time, plus the time to drain the buffered lines (R3).
- 1 s initial wait gives a fast first retry for a short blip (a connection reset) without a busy loop.

**Env var names**: `.env.example` uses `UPPER_SNAKE` with a service or domain prefix and a `_S`
suffix for seconds (`REFRESH_INTERVAL_S`, `REFRESH_HEALTH_MAX_AGE_S`, `SIM_PACE_S`). The new names
follow it with the prefix `INGESTION_`. Invalid values (not a number, ≤ 0, initial > max, max >
total) raise `RuntimeError` at start, before any line is read (same pattern as
`get_sim_planned_headway_s`).

**Alternatives considered**: reusing `connect_with_retry`'s 10 × 2 s (about 20 s, shorter than the
outage); full jitter (adds nothing with one client); a retry library such as `tenacity` (no new
dependency is justified: the loop is about 30 lines and must hold one specific line, R3); unlimited
retries (violates FR-012 "fail loudly").

---

## R2 — "Database unreachable" versus a data error (FR-009, FR-012)

**Decision**: retry only **connection-level** failures, decided by SQLSTATE:

- retryable: a `psycopg.OperationalError` (or `InterfaceError`) whose `sqlstate` is `None`
  (client-side: connection refused, DNS failure, timeout, connection lost, "connection is closed"),
  or in class `08` (connection exception), or equal to `57P01` (admin shutdown), `57P02` (crash
  shutdown) or `57P03` (cannot connect now, the server is starting). These are the codes PostgreSQL
  raises when `docker compose stop db` (fast shutdown), `kill db` (connection reset) or a restart
  in progress hits the client.
- not retryable, raised as today: everything else (`DataError`, `IntegrityError`,
  `ProgrammingError`, other `OperationalError` such as `53100` disk full or `57014` query canceled).
  Ingestion exits non-zero and the existing restart policy handles it.
- a bad **event** never reaches this logic: `validate_envelope` returns a result, and the rejection
  insert is a normal statement. Unchanged.

The generic `reason` in the log line comes from a fixed vocabulary, never from the exception text:
`db_unreachable` (no SQLSTATE), `db_connection_lost` (class 08), `db_shutting_down` (57P01, 57P02),
`db_starting` (57P03). The line also carries `sqlstate` (a 5-character code, not sensitive).
`str(exc)` is never logged: libpq messages include the host and port.

**Rationale**: `OperationalError` alone is too broad (it also covers disk full and query cancel,
which a retry would hide). A SQLSTATE allowlist keeps the loud-failure property for everything that is
not "the database is not there right now". Tests build each case with fakes (`psycopg.errors`
classes), and one integration test produces a real `57P01` with `pg_terminate_backend` on a
throwaway database.

**Alternatives considered**: retry every `psycopg.Error` (would loop on a permanent `ProgrammingError`
until the window ends and hide bugs); retry on message text (fragile, locale dependent); a connection
pool library (new dependency, more moving parts than one connection).

---

## R3 — Keeping the current line and the pipe intact (FR-009, FR-012, Assumptions)

**Decision**: the retry sits **around the single call that stores the current line**:

1. `consume` takes one line from stdin into a local variable and calls the ingest function.
2. On a retryable error the connection is closed, the line variable is **not** replaced, ingestion
   waits (R1), reconnects and calls the ingest function again with the **same** line.
3. Only after the line is stored does `consume` read the next line. Single thread, single reader: no
   line can be skipped or reordered.
4. While ingestion waits it does not read stdin. The kernel pipe fills and the simulator blocks on
   `write`. No event is dropped.
5. After a successful line the outage state (first-failure time, attempt counter) resets, and one
   `db_recovered` line is logged with the attempt count and the outage length. This line is not a
   retry; it exists so the drill and the post-mortem can state the real outage time. SC-005 counts
   only `db_retry` lines.

**Sizing (measured numbers, Linux default pipe capacity assumed, to measure in Phase 2 with
`F_GETPIPE_SZ` inside the container)**: the simulator writes about 2.0 KB/s at the compose pace. A
default Linux pipe holds 65,536 bytes, which is about 32.8 s of output. So the 31 s drill outage
nearly fits in the pipe and the simulator probably never blocks; an outage longer than about 33 s
blocks it and stalls its wall-clock pacing, as the spec accepts. Both cases are lossless and ordered.
After recovery ingestion drains the buffered lines at database speed, then follows the paced stream.

**Replay safety**: the line in flight may have been committed just before the connection died. The
retry then hits `ON CONFLICT DO NOTHING`, and the line is recorded as `duplicate_event`
(FR-013): not lost, not inserted twice in `bronze.events`. A rejected line (invalid event) retried after
a lost acknowledgement would add a second row to `bronze.rejections`; this needs the connection to
die between a commit and its reply, so it is bounded to at most one extra row per outage. Declared in
the plan's risks.

**Exact "no gap" check (spec Assumptions)**: on a fresh volume with a fixed seed, after recovery,
the list of `event_id` values in `bronze.events` ordered by `id` must equal the first *K* event ids of
the simulator's deterministic output for the same seed (K = row count). Row ids themselves are not
contiguous, because `ON CONFLICT DO NOTHING` consumes sequence values; the event-id order is the
contract. Plus: `RestartCount = 0` and an unchanged `StartedAt` for the `ingestion` container, and an
unchanged simulator PID (R6).

**Alternatives considered**: a bounded in-memory queue between reader and writer (new thread, can
lose lines at a crash, duplicates the pipe's own buffering); a persistent buffer (out of scope,
turn 3); letting the simulator resume (out of scope, spec).

---

## R4 — Duplicates are not rejections (FR-013, FR-014, Clarification Option A)

**Decision**: the data layer is unchanged: a duplicate is still a row of `bronze.rejections` with
reason `duplicate_event` (ADR-0001, ADR-0002). The **counting** changes:

- `consume` keeps a separate tally: keys `accepted`, one key per contract rejection reason, and
  `duplicates` (the reason `duplicate_event` no longer appears as a rejection reason in the tally).
- A `summarize(counts)` function returns `accepted`, `rejected` (sum of contract reasons),
  `by_reason`, `duplicates`, and `rejection_rate = rejected ÷ (accepted + rejected)`, or `null` when the
  denominator is 0 (not 0 %, not 100 %).
- The end-of-run log line and the `ops` view use the same definition (R7).

**Rationale**: it is the smallest change that satisfies SC-006 and keeps ADR and contract untouched.
`rejection.schema.json` already lists `duplicate_event`.

**Alternatives considered**: a separate `bronze.duplicates` table (rejected by the data owner,
Clarification Option A); dropping duplicates silently (loses the evidence the drill needed).

---

## R5 — Healthcheck timing for `ingestion` (FR-020 to FR-022, SC-008)

**Decision** (**choice**, in `docker-compose.yml`, documented in comments):

| Parameter | Value |
|---|---|
| `test` | `["CMD", "python", "-m", "src.data.ingestion.health"]` |
| `interval` | `5s` |
| `timeout` | `3s` |
| `retries` | `1` |
| `start_period` | `20s` |
| threshold `INGESTION_HEALTH_MAX_AGE_S` | `15` (fixed by the spec) |

**Why `retries: 1`**: Docker marks a container `unhealthy` after `retries` consecutive failed probes.
With the default 3 the service would turn unhealthy up to 15 + 3 × 5 = 30 s after the feed stops,
which breaks SC-008 ("within 15 s plus one healthcheck interval"). The 15 s threshold is already the
persistence filter, so one failed probe is enough. The cost: a single failed probe (for example a
database blip) shows `unhealthy` until the next successful probe, 5 s later. The signal is not wired
to any automatic restart, so a short flap does no harm. Consequence for the `refresh` pattern: refresh
uses retries 3 because its threshold is 30 s and its purpose differs; this story does not change it.

**Bound**: the last insert at time *t0*. The first probe that sees age > 15 s runs at most one
interval after *t0* + 15 s. **Detection ≤ 15 s + 5 s + probe duration** (probe duration is
below 1 s in normal operation, at most the 3 s timeout). Docker starts the next probe `interval`
after the previous one finishes, so "one interval" in practice means interval plus probe duration.
SC-008 is checked from `docker inspect` health log entries (`Start`, `End`, `ExitCode`), which carry the
exact probe times, against the last insert time read from the database. **Recovery**: the first probe
after an insert exits 0, and one success flips the status to `healthy`, so recovery is at most
interval + probe duration after the first insert.

**Why `start_period: 20s`**: the first event reaches bronze within seconds of the container start
(the container starts only after `db` is healthy). 20 s is a **choice** above that, much shorter
than the refresh's 40 s because ingestion has no warm-up computation. During the start period failed
probes do not count and a successful probe flips to `healthy` at once. **To measure in Phase 3**: time
from container start to first `healthy`; if it is above 15 s the value is raised. With empty bronze
after the start period the service is `unhealthy` (spec scenario 6).

**Why `timeout: 3s`**: matches `connect_timeout=3` in the probe; keeps a hung database from holding a
probe past the next interval.

**Alternatives considered**: `retries: 3` with a 3 s interval (probe load for no gain); a threshold
below 15 s (the spec fixes 15 s); an external watcher (a new service, forbidden).

---

## R6 — How to stop the feed in the live acceptance test (SC-008)

**Decision**: pause only the **simulator process** with `SIGSTOP`, resume with `SIGCONT`, by a helper
`scripts/drill/feed_control.py` that is piped into the container and finds the process by its exact
argument vector:

```text
docker compose exec -T ingestion python - stop   < scripts/drill/feed_control.py
docker compose exec -T ingestion python - resume < scripts/drill/feed_control.py
```

Matching rule: scan `/proc/<pid>/cmdline`, split on NUL, and select the process whose arguments after
the interpreter are exactly `-m src.data.simulator.main`. Two traps this avoids: PID 1 is
`sh -c "…simulator.main … | …ingestion.run"` and its command line contains the same text, and the helper
itself (`python -` plus an `exec` session) must not signal itself. The script is piped through stdin
because `scripts/` is excluded from the image by `.dockerignore`. The process runs as UID 10001 like
the `exec` session, so the signal is permitted, and no extra tool is needed (`procps`/`pkill` is not
in `python:3.12-slim`).

**Effects**: the simulator stops writing, ingestion blocks on an empty pipe (it is healthy and
waiting), the healthcheck keeps running and reports stale data, so the service turns `unhealthy`
exactly as it would if the real feed stopped. `SIGCONT` resumes the simulator; its pacing sleeps are
relative per step, so it does not burst to catch up. The ingestion container is never restarted.

**Rationale**: it reproduces the real situation (the feed goes quiet while the database is fine) and
is a documented, reversible method with no change to production code. It is also the method the
runbook gives for "stopped feed" practice.

**Alternatives considered**: `docker compose pause ingestion` (freezes the whole cgroup including the
healthcheck exec, so the probe cannot run; the Docker behavior for probes of a paused container is not
established here); `docker compose stop` (restarts nothing, but kills ingestion, which tests F3, not
a stalled feed); adding a test-only "pause" switch to the simulator (production code for a test).

---

## R7 — The `ops` view (FR-016 to FR-019)

**Decision**: new init script `src/data/db/init/006_ops.sql` creates schema `ops` (`IF NOT EXISTS`)
and the view `ops.ingestion_health` (`CREATE OR REPLACE VIEW`; idempotent like the other scripts). One
row, always (aggregates without `GROUP BY`). All times use the database clock via `clock_timestamp()`,
the same clock the refresh healthcheck uses. Columns (full definition in `data-model.md` and
`contracts/ops-ingestion-health.md`):

| Column | Definition | NULL when |
|---|---|---|
| `observed_at` | `clock_timestamp()` | never |
| `last_insert_age_s` | seconds from `arrival_ts` of the row with the highest `id` in `bronze.events` to `observed_at` | bronze is empty |
| `events_60s` | `count(*)` of `bronze.events` with `arrival_ts` in the last 60 s | never (0 when none) |
| `rejections_60s` | `count(*)` of `bronze.rejections` with `received_ts` in the last 60 s and `reason <> 'duplicate_event'` | never (0 when none) |
| `duplicates_60s` | same window, `reason = 'duplicate_event'` | never (0 when none) |
| `rejection_rate_60s` | `rejections_60s ÷ (events_60s + rejections_60s)` | the denominator is 0 |

`events_60s` is "events per minute" over the last 60 s window (spec (b)). The window is 60 s to match the constitution's
"rejection above 5 % within 1 min". "Not computable" is SQL `NULL`: a consumer cannot mistake it for 0
or 100 %. A duplicate never refreshes freshness (it is not a bronze insert), which is intended: a
replay of old data must look stale.

**Read-only**: a view with aggregates is not updatable; the schema holds no table (a test checks
`information_schema.tables` for the schema `ops`: only views). No derived storage, no write to
bronze, silver or gold (the existing static guard `test_no_bronze_writes` scans `rules`, `pipeline`,
`refresh`; a new test extends the same rule to `006_ops.sql` and `ingestion/health.py`).

**Cost**: `last_insert_age_s` uses the primary key (O(1)). The two 60 s counts have no `arrival_ts`
index on `bronze.events`, so they scan the table; `rejections` uses the existing
`(reason, received_ts)` index. At turn-1 scale (about 3,851 rows per simulated hour) this is
negligible. **To measure in Phase 3**: `EXPLAIN ANALYZE` of the view on 1 million synthetic rows in a
throwaway database. If it costs more than 50 ms (**choice**), the plan records an index on
`bronze.events(arrival_ts)` as evolution instead of adding it now, because changing `002_bronze.sql`
is a data-owner change and nothing needs it at this scale. The healthcheck does **not** read the
counts: it selects only `last_insert_age_s` (R8), so a probe stays cheap even if the counts grow.

**Alternatives considered**: `now()` instead of `clock_timestamp()` (transaction start time; fine for
one statement but diverges from the refresh pattern); a materialized view or a stats table (derived
storage, forbidden by FR-018); `ingested_at` instead of `arrival_ts` (same value; `arrival_ts` is the
contract's name).

---

## R8 — How the healthcheck reads the view (FR-020, FR-021, FR-023)

**Decision**: new module `src/data/ingestion/health.py`, same shape as `src/data/refresh/health.py`:
`get_max_age_s()` reads `INGESTION_HEALTH_MAX_AGE_S` (default 15, error on non-number or ≤ 0),
`last_insert_age_s(conn)` runs `SELECT last_insert_age_s FROM ops.ingestion_health` then rolls back,
`is_healthy(conn, max_age)` is `age is not None and age <= max_age`, and `main()` returns 0 or 1.
`psycopg.connect(dsn, connect_timeout=3)`; any exception prints `unhealthy: check failed`; no DSN, host
or exception text is printed. The module imports only `psycopg` and `src.pulsoflota.config`, never
`run.py`, the API or `refresh`, so ingestion still depends only on `db` (FR-023, Principle III). A
missing view (old volume, R14) is a failed check, reported without detail.

**Alternatives considered**: reading `max(arrival_ts)` directly (bypasses the signal the story
exposes; two definitions of freshness); an HTTP endpoint on ingestion (new surface, new dependency).

---

## R9 — The CI workflow (FR-001 to FR-008)

**Decision**: one file, `.github/workflows/ci.yml`, workflow name `CI`, three independent jobs (no
`needs`), runner `ubuntu-latest` for all.

| Job id and name | Steps | Fails when |
|---|---|---|
| `test` | checkout; `cp .env.example .env`; `docker compose version` (guard); run, unchanged, `docker compose --profile tools build tests && docker compose --profile tools run --rm tests`; on failure print `docker compose --profile tools logs --no-color` | any test fails or coverage < 80 % (gate comes from the compose command) |
| `contract` | checkout; `astral-sh/setup-uv` pinned to uv `0.9.5` (the version in the `Dockerfile`) with its cache on; `uv run --frozen --extra dev pytest src/data/tests/contract/test_read_fixtures.py -p no:cacheprovider --no-cov` | a fixture is invalid, has no matching schema, or a read schema is not valid draft 2020-12 |
| `build` | checkout; `cp .env.example .env`; `docker compose --profile tools build` | any service image fails to build |

- **Triggers**: `pull_request` (no branch filter, so a pull request into the stacked feature branches
  runs it too) and `push` to `main`. No `workflow_dispatch` (nothing needs it).
- **Permissions**: `contents: read` at workflow level. No secrets are referenced; `.env` is made from
  `.env.example` (FR-006). `.env` is git-ignored and `.dockerignore`d.
- **Concurrency**: group `ci-${{ github.workflow }}-${{ github.ref }}`; `cancel-in-progress` true for
  pull requests only (`github.event_name == 'pull_request'`), so a push to `main` is never cancelled.
- **Timeouts** (**choice**, adjust after the first runs): `test` 20 min (local run 113 s), `contract`
  10 min, `build` 15 min.
- **Docker Compose on the runner**: the `ubuntu-latest` image ships Docker Engine and the Compose v2
  plugin; the guard step `docker compose version` makes a missing plugin fail visibly at the start.
  **To verify at the first run** (Phase 1).
- **Contract job without Docker**: the existing test `test_read_fixtures.py` already implements FR-003
  (it fails when a fixture has no `<stem>.schema.json`, when validation fails, and when a read schema is
  invalid), and I ran the command locally: 33 passed. `--no-cov` is needed because `addopts` carries
  `--cov-fail-under=80`, which a single file cannot meet. Reusing the test avoids a second
  implementation of the same check. The lock file (`--frozen`) gives the same `jsonschema` and
  `rfc3339-validator` as the test image.
- **Caching**: only the `setup-uv` cache (one input line). No Docker layer cache: it needs buildx and a
  cache backend, which is not simple. First run slower, result identical (spec edge case).
- **Actions versions**: major tags (`actions/checkout@v4`, `astral-sh/setup-uv@v6`); confirm the
  current majors when writing the file. Pinning actions to commit SHAs is a supply-chain norm
  (A03) that turn 2 adopts; recorded as evolution.
- **Extensibility** (FR-007): jobs have no `needs` and no shared step state, so the DevOps owner adds
  `lint` and `security` jobs beside them. A unit test asserts the three job ids exist and have no `needs`.
- **Tests first**: `tests/unit/test_ci_workflow.py` (PyYAML, already a dev dependency) reads the
  workflow through a new read-only mount of `.github/workflows`. Parsing trap: YAML 1.1 reads the key
  `on` as boolean `True`; the test handles both keys.
- **Branch protection (FR-008)**: `docs/ops/ci-branch-protection.md` lists the three required status
  checks by job name (`test`, `contract`, `build`), the setting path (repository Settings, Branches
  (or Rulesets), rule for `main`, require status checks to pass before merging), and states it is a
  manual admin step that renaming a job breaks. Not configured by this change.

**Alternatives considered**: one job with three steps (fails FR-007 independence and hides which
check failed); running tests directly on the runner with a Postgres service container (a second way
to run the suite, drifts from the CI-ready command; FR-002 requires the command unchanged);
a custom fixture-validation script (duplicates `test_read_fixtures.py`); Docker layer caching (not
simple); a matrix of Python versions (the image fixes 3.12).

---

## R10 — Demonstrating SC-001, SC-002, SC-003 without leaving junk

**Decision**: six throwaway branches off the feature branch, each with one draft pull request **into
`feature/003-ops-ci-reliability`**, closed without merging and deleted after the run. Evidence (run
URL, job results, test counts, coverage) is written once into `specs/003-ops-ci-reliability/verification.md`.
Nothing from the probes is kept in the repository. The human pushes; the agents do not.

| Probe branch | Change | Expected result | Success criterion |
|---|---|---|---|
| `ci-probe/green` | an empty commit | `test`, `contract`, `build` green | SC-001, SC-002 (same test count and coverage as the local command) |
| `ci-probe/red-test` | one assertion made false in an existing test | `test` red, others green; the PR shows a failed required check | SC-001 |
| `ci-probe/low-coverage` | one new module under `src/` with enough untested statements to push coverage under 80 % (needed amount: more than `covered ÷ 0.80 − total` statements, from the green run's report) | `test` red on the coverage gate | SC-002 |
| `ci-probe/bad-fixture` | one required field removed from one existing fixture | `contract` red | SC-003 |
| `ci-probe/orphan-fixture` | one fixture file renamed so its stem has no schema (the count stays 18, so the failure proves the "no schema" path, not the count test) | `contract` red | SC-003 |
| `ci-probe/broken-build` | a wrong `COPY` path in the `Dockerfile` | `build` red | FR-004 |

After reverting the `red-test` probe commit the run goes green again (SC-001). "The merge is blocked"
(SC-001) needs branch protection, a manual admin step: the evidence records whether it was configured
and, if not, shows the red required check only.

---

## R11 — SLI, SLO and error budget proposal text (FR-026, spec "Freshness SLI")

**Decision**: the text lives in `docs/ops/sli-slo-proposal.md`, headed **PROPOSAL, not an adopted
norm**, for the constitutional amendment PR (out of scope here). Starting proposal, to be adjusted
with the Phase 4 drill numbers:

- **SLI** (as in the spec): at every healthcheck probe (every 5 s), the service is *fresh* if
  `last_insert_age_s ≤ 15` and *stale* otherwise. SLI = fresh probes ÷ total probes over a rolling window,
  counted only while a live feed is expected (excluded: the declared end of a finite simulator run,
  planned maintenance).
- **Proposed SLO**: 99 % of probes fresh over a rolling 28 days. **Error budget**: 1 % of the window =
  403 minutes (0.01 × 28 × 24 × 60 = 403.2). Other targets for comparison: 99.5 % = 201.6 min; 99.9 % =
  40.3 min.
- **Reasoning from measurements** (filled with the Phase 4 numbers): a 31 s database outage with the fix
  costs about 31 s + the recovery delay − the 15 s threshold of stale time, so a few such outages fit in
  the budget; an ingestion crash (F3) replays the seeded day from the start as duplicates and stays stale
  for about as long as the process had been running, which is minutes per crash and would consume the
  budget fast. That is the reason the simulator-resume gap is the first item of the evolution list.
- The final target is **chosen from the rerun**: this plan does not fix it in advance (spec).

**Alternatives considered**: an SLO on the rejection rate (the 5 % per minute alert is already a
constitutional norm, this story only exposes the signal); latency SLOs (turn 3 norm, deferred).

---

## R12 — The drill rerun (FR-027, SC-009)

> **Superseded in part by "Gate decisions" (2026-11-20) at the end of this file**, which wins over
> this section on: `SIM_DURATION_S` (not overridden), the sampling period (2 s, not 5 s), the F3 fault
> (kill of the exact-argv ingestion process, not `docker compose kill ingestion`), the windows, the
> metric columns (English header), the lag-reading rule and the removal of the comparability caveat.
> The text below is kept as the original reasoning.

**Decision**: a script `scripts/drill/run_drill.sh` (bash, host side, uses `docker compose` and
`docker compose exec -T db psql`; no new dependency) reproduces the faults of 2026-11-18 on the fixed
code and writes raw samples to a git-ignored `drill-out/` folder; the table goes into
`docs/ops/drill-rerun.md` (before column = the spec's Drill Evidence, after column = the rerun).

Faults, as in the baseline: **F1** `docker compose stop api`, 31 s, `start`; **F2**
`docker compose stop db`, 31 s, `start`; **F3** ~~`docker compose kill ingestion`~~ `kill -9` of the ingestion process selected by the exact-argv rule (superseded, see Gate decisions). Between faults the
script waits a settle period (value recorded in the report). Fresh volume (`down -v`, only under the drill's own project `pulsoflota-drill`) and the same seed
(42) at start. Because the default simulated day ends after 720 s of wall time (3,600 s at 5 s per second),
~~the drill sets `SIM_DURATION_S` large~~ **superseded: the drill does not override `SIM_DURATION_S`**; the
whole drill (about 329 s) fits in the default 720 s; `.env.example` defaults are not changed.

Measurements per fault, from the database clock and Docker: bronze row count before and after, number
of `duplicate_event` rows, contract rejections, `ops.ingestion_health` sampled every ~~5 s~~ **2 s (superseded)** (lag =
`now() - max(arrival_ts)` read from the tables, as in the baseline), `docker events --filter event=health_status` for `unhealthy` transitions,
`RestartCount` and `StartedAt` of `ingestion`, and the `db_retry` / `db_recovered` lines from
`docker compose logs`. Comparable to the baseline: rows intact, duplicates, false versus real
rejection rate (baseline 971 ÷ (525 + 971) = 65 %), lag after F2 (baseline **120 s**) and F3 lag
(baseline **209 s**, fixed lag-reading rule in Gate decisions), and alerts (baseline none).

**Expected, not assumed**: F1 unchanged. F2: no exit, no restart, no replay, lag below 15 s a few seconds after recovery. F3:
still restarts the pipe and replays the day as duplicates (simulator resume is out of scope), so the lag is reported
as measured and an `unhealthy` transition is expected. The rerun records actual numbers; a value that does not improve is
reported as such (SC-009).

**Comparability caveat (superseded)**: replaced by the Gate decisions, which reuse the original windows,
columns and sampling and fix one lag-reading rule for both columns.

**Alternatives considered**: a Python drill script (needs the Compose CLI anyway; bash is enough and
matches the commands used on 2026-11-18); running the drill in CI (needs a live stack for minutes; not
the Andon job).

---

## R13 — Turn scope and evolution (docs/turns-ritmo.md)

Adopted here, within turn 1: the 5 Core Principles, Gate 2 (made automatic), RNF-3.2.1/3.2.2, the
no-cost security items (parameterized SQL, no secrets, no stack traces or connection details in
outward text). **Deferred, recorded as evolution, not blocking**: SAST/SCA and lint jobs (Gate 1
tools, turn 2; DevOps owner), pinning actions by SHA and Trivy image scans (A03, turn 2), OpenTelemetry-
compatible logs and alert routing to SRE (A09, turn 2; the retry lines are plain JSON with a UTC
timestamp and no PII), Redis/`database-redis`, PostGIS, 1,000 events/s, persistent buffer and
contingency mode (turn 3), simulator resume mid-day, an `arrival_ts` index (R7), alerting on the
5 % rejection rate.

---

## R14 — Existing databases do not get the new schema

**Decision**: init scripts run only on an empty volume, so a stack started before this change has no
`ops` schema. The ingestion healthcheck then fails (reported as `unhealthy: check failed`). The runbook
and the quickstart give both fixes: `docker compose down -v` (loses data, fine for a simulator volume; in verification steps only under the dedicated project `pulsoflota-verify`, never on a developer's default project) or
apply the script to the running database with
`docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < src/data/db/init/006_ops.sql`
(idempotent, no data loss). No migration tool is added (turn-1 scope, same as 002).

**Alternatives considered**: creating the view at ingestion start (a service writing DDL, breaks
the "read-only view" and least-privilege spirit); Alembic (new dependency, out of scope).

---

## R15 — Dependencies

**Decision**: none added. Retry is stdlib (`time`, `json`, `datetime`), health uses `psycopg`, the
workflow test uses PyYAML and the contract job uses `jsonschema` and `rfc3339-validator`, all
already in the dev extra and locked in `uv.lock`. `pyproject.toml` and `uv.lock` are unchanged.

---

## Gate decisions (2026-11-20, data owner)

Answers to the two open questions of `plan.md`. Where they conflict with R6, R10 to R12 above, this
note wins.

1. **The original 2026-11-18 drill is available.** Its script, metrics, event log, restarts and
   rejections were copied to `.drill-input/` at the repository root. That folder is git-ignored
   (`.git/info/exclude`), local only, and is never committed. Consequences:
   - The rerun **reuses the same faults, observation windows and metric columns** as the original, so
     the before/after table is comparable. This replaces the R12 "comparability caveat" and the 5 s
     sampling: the sample period is **2 s**.
   - **Windows** (read from the original script and `eventos.log`): start, 45 s warm-up, F1 `stop api`
     30 s (measured 31 s), 25 s settle, F2 `stop db` 30 s (measured 31 s), 90 s settle, F3 `kill -9`
     of the ingestion process, 90 s observation, end. Total about 329 s, shorter than the 720 s default
     simulated day, so `SIM_DURATION_S` is **not** overridden.
   - **Metric columns** (one row every 2 s, header translated to English by the data owner, 2026-11-20; only the header line changes, data rows stay
     byte for byte): `t_s,events,max_event_ts,ingestion_lag_s,duplicates,other_rejections,ingestion,api,db`
     (old to new: `lag_ingesta_s` → `ingestion_lag_s`, `dup` → `duplicates`, `otros_rech` → `other_rejections`). Lag is
     `now() - max(arrival_ts)` in whole seconds, `-1` with empty bronze, `NA` while the database is
     down. The sampler reads the tables directly, not `ops.ingestion_health`, so the lag definition is
     the baseline's. New observations (health transitions, `db_retry` lines, restart counts) go to
     **separate files**, never extra columns.
   - **Repo versions**: `scripts/drill/run_drill.sh` is the original translated to English that runs on
     the real repo stack (not a copy), with the F3 kill target updated to `src.data.ingestion.run`;
     the baseline numbers go to `docs/ops/drill-baseline/` (`metrics.csv`, `events.log`,
     `rejections.txt`, `restarts.txt`) as the "before" data and the source of the table in
     `docs/ops/drill-rerun.md`. The baseline files are evidence: in the repo copies only the `metrics.csv` header line and the Spanish
     labels of `events.log` and `restarts.txt` are translated to English (file names too: `metrics.csv`,
     `events.log`, `rejections.txt`, `restarts.txt`); timestamps and values are unchanged, and
     `docs/ops/drill-baseline/README.md` says so. The originals stay in `.drill-input/`.
   - **Lag-reading rule (fixed, same for baseline and rerun)**: *lag after F2* = `ingestion_lag_s` of the
     last sample strictly before the F3 mark; *F3 lag* = `ingestion_lag_s` of the last sample of the
     observation window. On the baseline this gives **120 s** (t = 227 s, F3 mark at 228 s) and **209 s**
     (t = 316 s). The 2026-11-18 report quoted 125 s and 204 s, read a few seconds off (t=232 and t=312);
     the fixed rule is used for both columns, and 120 s / 209 s are the baseline numbers in SC-009, the
     quickstart, the tasks and the before/after table.
   - **F3 target**: the kill selects the ingestion process by the exact-argv rule of R6 (argv after the
     interpreter is exactly `-m src.data.ingestion.run`; never PID 1, never the helper, never a substring match).
   - **Isolation from the developer stack**: the original ran on a copy and ended with `down -v`. On the
     real repo the script must use its own Compose project name (`pulsoflota-drill`) so `down -v`
     cannot delete the developer's volume, and it refuses to start if another project's stack holds
     the published ports.
2. **`.github/workflows/` gets no CODEOWNERS entry for now.** Ownership is decided with the team in
   issue #5. `.github/CODEOWNERS` is not edited by this story.
