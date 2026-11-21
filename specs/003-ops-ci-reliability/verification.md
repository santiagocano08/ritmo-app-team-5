# Verification: 003-ops-ci-reliability

Branch `feature/003-ops-ci-reliability`. Times are UTC, 2026-11-21.

## Baseline (T001)

Phase 1 start: 04:23:18. Command (Andon, unchanged):
`docker compose --profile tools build tests && docker compose --profile tools run --rm tests`

Result: **422 passed, 4 skipped, 0 failed**, coverage **91.97 %**, 120.20 s (124 s with build).
Same as the 002 end state.

## Red confirmation (T004)

`uv run pytest tests/unit/test_ci_workflow.py tests/unit/test_ops_docs.py -q --no-cov`
before implementation: 2 failed, 10 errors. Reasons: `workflow not found: .github/workflows/ci.yml`
and `doc not found: docs/ops/ci-branch-protection.md`, plus the missing compose mounts. No import or
syntax errors.

## Action versions (T006)

Confirmed with `git ls-remote --tags` on 2026-11-21: latest major tags are `actions/checkout` v7
and `astral-sh/setup-uv` v7 (research R9 had written v4 / v6 as a placeholder, to be confirmed).
The workflow uses `actions/checkout@v7` and `astral-sh/setup-uv@v7` with uv `0.9.5`. These could not
be exercised here; the first GitHub run (T010) will show whether they work. Pinning to commit SHAs is
deferred to turn 2 (R9).

## Local equivalents of the jobs (T008)

| Job | Command | Result |
|---|---|---|
| contract | `uv run --frozen --extra dev pytest src/data/tests/contract/test_read_fixtures.py -p no:cacheprovider --no-cov` | 33 passed |
| build | `docker compose --profile tools build` | exit 0 |

## Phase 1 verification (T009)

| Step | Command | Result |
|---|---|---|
| 1 | host `uv run pytest` (04:26:12 to 04:30:04) | 437 passed, 1 skipped, 0 failed, coverage 91.97 %, 231 s |
| 2 | Andon command (04:30:09 to 04:32:20) | 434 passed, 4 skipped, 0 failed, coverage 91.97 %, 116 s |
| 3 | `uv run pytest tests/unit/test_ci_workflow.py tests/unit/test_ops_docs.py -q --no-cov` | 12 passed |
| 3 | contract command | 33 passed |
| 3 | `docker compose --profile tools build` | exit 0 |

Passed count: Andon 434 = 422 baseline + 12 new tests. Host has 1 skipped instead of 4 because the
host environment runs tests the container skips.

Untouched check: `git status --short` shows only `docker-compose.yml` (3 added lines, two read-only
mounts and a comment), `.github/workflows/`, `docs/ops/`, the two new tests and spec files. No change
to `contracts/`, `bronze.py`, `validate.py`, init scripts, `CODEOWNERS`, `docs/adr`, `.drill-input/`
or `drill-out/`.

Rework: none. No test was weakened. No new dependency (PyYAML is already in the `dev` extra).
No secret is used by the workflow; `.env` was never printed.

End of Phase 1: 04:32:25. T010 (push, probes P1 to P3) is a human task and is not done.

### Phase 1 addendum: first GitHub runs and the coverage fix (T010, 2026-11-21)

Probe evidence from GitHub (probes closed without merging, branches deleted):

| Probe | PR | Run | Result |
|---|---|---|---|
| P1 first run of the feature branch | #9 | 44898773797 | `test` red: 418 passed, 20 skipped, coverage 69.90 % < 80 % (this finding). `contract` and `build` green was not re-checked after the fix; P1 green is pending the push of this fix |
| P2 `ci-probe/red-test` | #10 | 44898793966 | `test` red on `test_same_inputs_give_the_same_id`; `contract` and `build` green. As expected |
| P3 `ci-probe/bad-fixture` | #11 | 44898798832 | `contract` red ("'schema_version' is a required property", 8 s); `build` green. As expected |

Cause of the red `test` in #9: `src/data/tests/unit/test_reference_build.py` (16 tests) skips when `data/raw/` is
absent. `data/raw/` (37 MB of downloaded sources) is git-ignored, so in CI `src/data/reference/build.py`
(290 lines) and `src/data/reference/sources.py` (24 lines) read 0 %. Locally the files exist, so the gap was
invisible.

Fix (data owner, 2026-11-21): both modules are offline ETL that builds the committed `data/reference/*.csv`
once and does not run in the stack. They are added to `[tool.coverage.run] omit` in `pyproject.toml` with a
one-line justification. Their tests stay and run wherever `data/raw/` exists. No other omit entry changed;
`--cov-fail-under=80` unchanged. Test first: `tests/unit/test_coverage_config.py` pins the exact omit list
(it failed before the change) and the 80 % floor.

Emulation of CI with `data/raw` hidden (empty temporary directory mounted read-only over it, developer files
untouched): `docker compose --profile tools run --rm -v "$(mktemp -d)":/app/data/raw:ro tests` gives
**483 passed, 21 skipped, 0 failed, coverage 94.75 %**. The Andon command with the real `data/raw` gives
499 passed, 5 skipped, coverage 94.75 % (the omitted modules do not change the figure). The GitHub run
reported 418 passed, 20 skipped at the Phase 1 commit (before Phase 2 tests); the new GitHub totals will be known
after the next push.

T010: P2 and P3 done and as expected; P1 green pending the push of this fix. Branch protection: not
configured by this change.

## Phase 2: ingestion survives a database outage (T011 to T024)

Start 05:35 UTC, end 05:55 UTC, 2026-11-21. Tasks T011 to T024 done (T024 included, it was on the cut list).

### Red confirmation (T017)

`uv run pytest src/data/tests/unit/test_ingestion_run.py src/data/tests/unit/test_ingestion_retry.py src/data/tests/unit/test_compose_ingestion.py src/data/tests/integration/test_ingestion_outage.py tests/unit/test_env_example.py -q --no-cov`
before implementation: 3 collection errors (module `src.data.ingestion.retry` missing, `summarize` and the
`retrier` argument missing); the two modules that import cleanly failed with `KeyError` on the missing
`INGESTION_RETRY_*` entries in `.env.example` and the compose file. No syntax errors.

### Phase 2 verification (T023)

| Step | Command | Result |
|---|---|---|
| 1 | targeted command above, `--no-cov` | 63 passed |
| 2 | host `uv run pytest` (05:43 to 05:47) | 492 passed, 2 skipped, 0 failed, coverage 93.06 %, 253 s |
| 3 | Andon: `docker compose --profile tools build tests && docker compose --profile tools run --rm tests` (05:47 to 05:49) | 489 passed, 5 skipped, 0 failed, coverage 93.06 %, 118 s |
| 4 | `COMPOSE_PROJECT_NAME=pulsoflota-verify POSTGRES_PORT=55432 docker compose down -v && ... up -d --build db ingestion`, wait 60 s, then `uv run pytest src/data/tests/integration/test_ingestion_outage_live.py -m live -q --no-cov -s` | 1 passed (35 s); `down -v` afterwards, under the dedicated project only |

Coverage: `retry.py` 100 % (85 statements), `run.py` 96 % (lines 75 to 76: the `finally` branch when no connection was opened). Passed count: Andon 489 = 434 (Phase 1) + 55 new.

Live check evidence (dedicated project, `db` stopped 30 s): no ingestion restart (`RestartCount` and `StartedAt`
unchanged), same simulator PID, bronze grew again, stored `event_id` order equals the first K events of
`--seed 42`. The ingestion log showed 8 `db_retry` lines per outage and one `db_recovered` (`attempts` 8,
`outage_s` about 32.1), no credentials in them.

### T024 measurements (live stack)

Pipe capacity of the ingestion stdin pipe, `F_GETPIPE_SZ`: **65,536 B** (same as the kernel default).
Bytes per event: 1,439,431 B / 3,851 events = **373.8 B**. Both confirm research R3 (about 32.8 s of
buffer at about 2.0 KB/s); no correction needed.

### Untouched check

`git status --short`: modified `.env.example`, `docker-compose.yml` (3 added lines), `src/data/ingestion/run.py`,
`src/pulsoflota/config.py`, `src/data/tests/unit/test_ingestion_run.py`, `tests/unit/test_env_example.py`;
new `src/data/ingestion/retry.py` and four test files. No change to `contracts/`, `bronze.py`, `validate.py`,
init scripts, `docs/adr`, `.github/`, `CODEOWNERS`, `.kiro/`, `.specify/`, `.drill-input/` (empty, not
tracked) or `drill-out/`.

### Rework and incidents

- Test-side mistakes fixed before the green runs: the fake ingest in `test_ingestion_run.py` compared lines
  with their trailing newline; two tests compared `UUID` objects with `str`. No test was weakened.
- The first host full run ended with 492 passed and 1 setup error in `tests/unit/test_ops_docs.py`
  (it passes alone). In the same minute the Docker daemon had stopped by itself (the next full run saw
  "connection refused" on port 5432). I restarted Docker Desktop with `open -a Docker`, waited for the
  default stack to be healthy and reran the host suite: 492 passed, 0 errors. The cause of the daemon stop
  was not investigated.
- At the end the default stack shows `refresh` as `unhealthy` (it restarted with Docker). Not touched.
- Known limit: if the connection drops after the event INSERT committed but before the reply arrived, the
  retried line is recorded as `duplicate_event` (the event itself is stored once, so no data is lost or
  duplicated; only the duplicates counter is off by one).

### Phase 2 rework: wrong password was retried (verifier finding)

`psycopg.connect` with a wrong password raises `OperationalError` with `sqlstate None`, so `classify()` returned
`db_unreachable` and the 120 s retry window ran. Now an authentication failure is not retried: `is_auth_failure()`
in `retry.py` matches SQLSTATE 28P01/28000 or the libpq text ("password authentication failed",
"authentication failed") by looking at `exc.args`, without `str(exc)`; the text is only compared, never stored.
`Retrier.run` writes one line `{"event": "db_auth_failed", "reason": "db_auth_failed", "sqlstate": ...}` and raises
`AuthFailed("db_auth_failed")`; `run.py` exits with status 1 and logs nothing else (no traceback, no host, user,
password, connection string or exception text). The log schema `ingestion-retry-log.schema.json` gained the
`db_auth_failed` variant (a new `oneOf` entry; the other variants and the reason enum are unchanged).
Tests first (seen failing on the missing `AuthFailed`/`is_auth_failure`): detection with the real message shape,
no retry (one call, no sleep), one schema-valid line, no-leak assertions on the line and on the exception, and
the same through `main` in `test_ingestion_run.py`. The existing no-leak test is unchanged and passes.

### Final runs after both fixes (one at a time)

| Command | Result |
|---|---|
| host `uv run pytest` (DATABASE_URL pointing at the local db) | 502 passed, 2 skipped, 0 failed, coverage 94.75 %; `retry.py` 100 %, `run.py` 96 % |
| Andon `docker compose --profile tools build tests && ... run --rm tests` | 499 passed, 5 skipped, 0 failed, coverage 94.75 % |
| CI emulation with `data/raw` hidden | 483 passed, 21 skipped, 0 failed, coverage 94.75 % |

A first host run without `DATABASE_URL` in the shell skipped 186 integration tests (coverage 78.5 %); that was my
environment, not the change, and the run above was repeated with the variable set from `.env` (not printed).

## Phase 1b: publish the image and pin base images

Start 2026-11-21 11:47 UTC, end 2026-11-21 about 12:00 UTC. No image was pushed.

### Red run (T059)

`uv run pytest tests/unit/test_ci_workflow.py tests/unit/test_container_pins.py -q --no-cov` → 10 failed, 13 passed.
Failures for the stated reasons: no `publish` job (jobs, `if`, permissions, tags, login), mount of `Dockerfile`
missing, floating `python:3.12-slim`, `postgres:16`, `ARG REVISION` and OCI labels missing. No import or syntax error.

### Green runs (T064), one at a time

| # | Command | Result |
|---|---|---|
| 1 | `uv run pytest tests/unit/test_ci_workflow.py tests/unit/test_container_pins.py tests/unit/test_ops_docs.py -q --no-cov` | 24 passed |
| 2 | host `uv run pytest` (DATABASE_URL from `.env`, not printed) | 514 passed, 2 skipped, 0 failed, coverage 94.75 % (end of Phase 2: 502 passed) |
| 3 | Andon `docker compose --profile tools build tests && docker compose --profile tools run --rm tests` | 511 passed, 5 skipped, 0 failed, coverage 94.75 % (previous: 499 passed) |
| 4 | `docker compose --profile tools build` | exit 0; `docker compose config` shows `image: postgres:16.11` for `db` |

### Local dry-run (T065), nothing pushed

- `docker build --target prod --build-arg REVISION=dryrun0000 --build-arg SOURCE_URL=https://github.com/santiagocano08/ritmo-app-team-5 -t pulsoflota-prod-dryrun .` → labels
  `{"org.opencontainers.image.revision":"dryrun0000","org.opencontainers.image.source":"https://github.com/santiagocano08/ritmo-app-team-5","org.opencontainers.image.title":"pulsoflota"}`
- `docker run --rm --entrypoint id pulsoflota-prod-dryrun` → `uid=10001(appuser)`.
- Build without `--build-arg` → `revision=unknown`. Image removed afterwards.

### Untouched check (T066)

Changed: `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `docs/ops/ci-branch-protection.md`,
`tests/unit/test_ci_workflow.py`, new `tests/unit/test_container_pins.py`, and files in `specs/003-ops-ci-reliability/`
(`tasks.md`, `verification.md`). Nothing else: no change to `contracts/`, `bronze.py`, `validate.py`, init scripts,
`.github/CODEOWNERS`, `.drill-input/`, `drill-out/`, `docs/adr`, `.kiro/`, `.specify/`.

### Rework

- T056 replaced the Phase 1 test "no job has `needs`" with "only `publish` has `needs`" as tasks.md asks.
- First T065 attempt failed because of my zsh quoting (`$B` was not word-split); repeated with explicit arguments.
- Not shown here: the remote `publish` run (T067, human task).

## Phase 3: freshness view and healthcheck (US3, T025 to T038)

Start 2026-11-21 about 11:58 UTC (tests first), end 12:13 UTC (all UTC, approximate to the minute).

### Red run (T031)

`uv run pytest src/data/tests/integration/test_ingestion_health_view.py src/data/tests/integration/test_ingestion_health.py src/data/tests/unit/test_compose_ingestion.py src/data/tests/integration/test_schema_init.py src/data/tests/unit/test_no_bronze_writes.py tests/unit/test_drill_feed_control.py tests/unit/test_env_example.py -q --no-cov`
Before implementation: `test_ingestion_health.py` failed at collection (`cannot import name 'health' from src.data.ingestion`); the other modules gave 24 failed, 39 passed. The failures were the missing view (`ops.ingestion_health`), missing healthcheck and `INGESTION_HEALTH_MAX_AGE_S` in compose and `.env.example`, missing `006_ops.sql`/`health.py`, missing `scripts/drill/feed_control.py` and the missing ADR addendum. No syntax errors. `test_view_is_not_updatable` passed early because the missing relation also raises; it is meaningful once the view exists.

### Green runs (T037), one at a time

| # | Command | Result |
|---|---|---|
| 1 | the T031 command, `--no-cov` | 74 passed |
| 2 | `git diff --numstat docs/adr` | `2 0`: one content line plus one blank separator line (002 precedent, SC-011), nothing removed |
| 3 | host `uv run pytest` (DATABASE_URL from `.env`, not printed), 12:02 to 12:06 | 544 passed, 3 skipped, 0 failed, coverage 94.91 %, 234 s (end of Phase 1b: 514 passed) |
| 4 | Andon `docker compose --profile tools build tests && docker compose --profile tools run --rm tests`, 12:06 to 12:08 | 541 passed, 6 skipped, 0 failed, coverage 94.91 %, 130 s (previous: 511 passed) |
| 5 | live, dedicated project: `COMPOSE_PROJECT_NAME=pulsoflota-verify POSTGRES_PORT=55432 docker compose down -v && ... up -d --build db ingestion`, wait 45 s, `SELECT * FROM ops.ingestion_health`, then `uv run pytest src/data/tests/integration/test_ingestion_feed_live.py -m live -q --no-cov -s` | 1 passed (26 s); `down -v` afterwards under the same project |

Coverage of the new module: `src/data/ingestion/health.py` is exercised by `test_ingestion_health.py` (both suites include it; total stays 94.91 %).

Live view reading (healthy stack): `last_insert_age_s` 0.008, `events_60s` 257, `rejections_60s` 0, `duplicates_60s` 0, `rejection_rate_60s` 0.

Live freeze (SC-008): after `SIGSTOP` of the simulator the first failed probe ended **20.3 s** after the last insert. Bound: 15 s + 5 s interval + probe duration (0.36 s measured) = 20.36 s. Resuming returned the status to `healthy`; `RestartCount` and `StartedAt` were unchanged.

Existing-volume path (R14), same dedicated project on a fresh volume: `DROP SCHEMA ops CASCADE` (stands in for a volume created before `006_ops.sql`) turned ingestion `unhealthy`; `docker compose exec -T db psql ... < src/data/db/init/006_ops.sql` and the status was `healthy` within 3 s (one probe).

Observation worth knowing for the drill (not a defect): restarting the `ingestion` container replays the seeded stream, so bronze receives only `duplicate_event` rows until the replay passes the stored point, and the status stays `unhealthy` meanwhile. That is the F3 behavior the spec declares (replay is reported, not fixed), and the view shows it as `duplicates_60s` > 0 with a stale `last_insert_age_s`.

### T038 measurements (cut-list task, done)

- Start to first `healthy` on a fresh stack: **6 s** after `docker compose up` returned (the container was already created and started). Below 15 s, so `start_period: 20s` stays and nothing changed.
- `EXPLAIN ANALYZE SELECT * FROM ops.ingestion_health` on 1,000,000 synthetic bronze rows (throwaway database `pf_explain`, dropped afterwards, rows spread over 10,000 s): planning 0.53 ms, **execution 117.9 ms**. This is above 50 ms, so, per R7, the `arrival_ts` index is recorded as **evolution** and not added. At the drill volume (about 4 events/s, a few thousand rows) the cost is negligible; the healthcheck itself reads one column, but the view computes all counts.

### Note for the K8s chart owner

The `ops.ingestion_health` view works the same under Kubernetes (it lives in the database); the ingestion healthcheck applies to compose only, because the chart runs ingestion as a Job.

### Untouched check (Phase 3)

Changed: `.env.example`, `docker-compose.yml` (ingestion env var and healthcheck, `./scripts` read-only mount in `tests`), `docs/adr/0001-data-layers-and-ingestion-semantics.md` (the allowed addendum, T035), `specs/003-ops-ci-reliability/tasks.md` and `verification.md`, `src/data/tests/integration/test_schema_init.py`, `src/data/tests/unit/test_compose_ingestion.py`, `src/data/tests/unit/test_no_bronze_writes.py`, `tests/unit/test_env_example.py`. New: `src/data/db/init/006_ops.sql`, `src/data/ingestion/health.py`, `scripts/drill/feed_control.py`, `src/data/tests/integration/test_ingestion_health_view.py`, `src/data/tests/integration/test_ingestion_health.py`, `src/data/tests/integration/test_ingestion_feed_live.py`, `tests/unit/test_drill_feed_control.py`. No change to `contracts/`, `bronze.py`, `validate.py`, `001` to `005` init scripts, `.github/CODEOWNERS`, `.github/workflows/`, `.drill-input/`, `drill-out/`, `.kiro/`, `.specify/`. The default stack was not stopped or recreated; the live checks used `pulsoflota-verify` only.

### Rework and decisions

- The first existing-volume attempt was invalid: my zsh variable holding the psql command was not word-split, so `DROP SCHEMA` never ran. Repeated with a shell function.
- The first "start to healthy" measurement followed a container restart and was contaminated by the replay described above; it was repeated on a fresh stack.
- The ADR addendum wording is mine (data owner to confirm, CODEOWNERS `/docs/adr/`): "Addendum 2026-11-21: a fifth schema, `ops`, holds read-only views over bronze for operations (ingestion freshness). It holds no tables and no secrets."

## Phase 4: documentation and drill rerun (T039 to T055)

Times are UTC, 2026-11-21. The first Phase 4 command was not timestamped; the drill started at 12:18:49Z and
the last suite finished at 12:31:44Z.

### Red run (T042)

`uv run pytest tests/unit/test_ops_docs.py tests/unit/test_drill_baseline.py tests/unit/test_drill_script.py -q --no-cov`
before any implementation: 19 failed, 1 passed (the branch-protection test). Reasons: "doc not found" for the
four new documents, "baseline file not found" for `docs/ops/drill-baseline/`, "script not found" for
`scripts/drill/run_drill.sh`. No import or syntax errors.

### Drill rerun (T050), one valid run

- Command: `bash scripts/drill/run_drill.sh` (project `pulsoflota-drill`, own volume). Start 12:18:49Z, end
  12:24:22Z (333 s). The default stack (ports 5432 and 8000) stayed up and was not touched; the script's port
  guard passed with the drill ports 55432 and 58000 (non-default, the script's defaults).
- Marks (s): F1 52 and 83, F2 109 and 139, F3 229, END 320, CLEANED 333. Baseline: 51, 82, 107, 138, 228, 318, 329.
- One run only; it was valid (stack started, all eight marks written, project removed at the end, nothing left
  running under `pulsoflota-drill`).
- Raw files stay in `drill-out/` (ignored, never staged). `.drill-input/` was not read by the script and not changed.

### Numbers (T051), read with the fixed rule (helper functions of `tests/unit/test_ops_docs.py`)

| Item | Value |
|---|---|
| Bronze rows before F2 (t = 106 s) / after F2 (t = 144 s) / at F3 mark / end | 508 / 698 (backlog stored, order kept) / 1144 / 1154 |
| `RestartCount`, `StartedAt` of ingestion across F2 | 0, `12:18:56.59Z` before and after (unchanged) |
| `RestartCount` after F3 | 1, `StartedAt` `12:22:39.79Z` (F3 kills the process; the container restarts and replays) |
| `db_retry` lines / `db_recovered` | 8 lines (attempts 1 to 8, waits 1, 2, 4, then 5 s), one `db_recovered` with `outage_s` 32.093 |
| Credentials in retry lines | none: every line has only `ts`, `level`, `event`, `attempt`, `wait_s`, `elapsed_s`, `reason`, `sqlstate` |
| Lag after F2 (last sample strictly before the F3 mark, t = 228 s) | 1 s (baseline 120 s) |
| F3 lag (last sample, t = 320 s) | 90 s (baseline 209 s) |
| Duplicates / contract rejections | 468 at the end of the run counting the whole drill (458 at t = 320 s) / 0 |
| Real rejection rate | 0 % (0 / (1154 + 0)) |
| `unhealthy` transitions (`health_events.log`) | ingestion `unhealthy` 12:20:43.6Z, `healthy` 12:21:15.9Z (F2); `unhealthy` 12:22:55.9Z, not recovered at the end of observation (F3) |
| Bronze integrity | `1154,1154` (`count(*)` equals `count(distinct event_id)`) |

Two readings stated as they are: the F3 lag only fell because F2 no longer leaves a lag before F3 (209 - 120 = 89 s
in the baseline against 90 - 1 = 89 s now); F3 still restarts and replays.

### Documents (T043 to T049, T052, T053)

`docs/ops/drill-baseline/` (data rows of `metrics.csv` byte for byte equal to the original, checked with
`diff` and by test), `post-mortem-2026-11-18-drill.md`, `runbook-ingestion-refresh-unhealthy.md`,
`sli-slo-proposal.md` (headed PROPOSAL, measured stale times filled in), `drill-rerun.md` (no TBD).

### Green runs (T055), one at a time

1. `uv run pytest tests/unit/test_ops_docs.py tests/unit/test_drill_baseline.py tests/unit/test_drill_script.py tests/unit/test_drill_feed_control.py -q --no-cov`: 26 passed.
2. Host suite `uv run pytest` (12:25:35Z to 12:29:35Z, 239.5 s): **563 passed, 3 skipped, 0 failed**, coverage 94.91 %.
3. Andon `docker compose --profile tools build tests && docker compose --profile tools run --rm tests` (12:29:39Z to 12:31:44Z, 121.8 s): **559 passed, 7 skipped, 0 failed**, coverage 94.91 %. The extra 4 skips are the host-only tests (`live` and the `.drill-input` comparison).
4. ADR: Phase 4 changes nothing under `docs/adr` (`git diff --numstat HEAD -- docs/adr` is empty). The single ADR change of the feature is the Phase 3 commit `3aaa315`: `2 0` (one content line plus one blank separator, 002 precedent), nothing removed.
5. Untouched check: `git diff HEAD` shows no change to `contracts/`, `src/`, `.github/`, `docker-compose.yml`, `Dockerfile`, `docs/adr`, `.github/CODEOWNERS`. Changed or new files are only those listed in the report. No `.drill-input/` or `drill-out/` in `git status` (both ignored).

### Rework and decisions

- `.gitignore` ignores `*.log`, which silently excluded `docs/ops/drill-baseline/events.log` from `git status`. Added the exception `!docs/ops/drill-baseline/*.log` and `drill-out/`.
- The script uses non-default ports (55432 and 58000) and aborts only when those are taken, so it can run next to the default stack (data owner instruction); T041's "another stack running" is covered by that port check.
- T054 (independent walk-through of the runbook) not done: it needs a person who did not run the drill. Cut-list item; SC-010 is covered by the content test only.

### SC-001 to SC-011 evidence map

| SC | Evidence |
|---|---|
| SC-001 | Phase 1 verification (T009), PR #9, #10 probes (T010, P2 red) |
| SC-002 | Baseline (T001), Phase 1 addendum, every phase suite run; this phase 94.91 % |
| SC-003 | T008 (33 passed, 18 fixtures) and probe P3 (PR #11) |
| SC-004 | Phase 2 live outage test (T023) and this drill: F2 no restart, 8 retries, recovery 32.1 s, rows grow, 1154 of 1154 |
| SC-005 | Phase 2 log-schema tests and the rerun `retry_lines.log` (no credentials) |
| SC-006 | Phase 2 tally tests; rerun: 468 duplicates reported apart, 0 rejections |
| SC-007 | Phase 3 live check (T037) |
| SC-008 | Phase 3 live feed test (T037); rerun `unhealthy` transitions |
| SC-009 | `docs/ops/drill-rerun.md` and the numbers above |
| SC-010 | `tests/unit/test_ops_docs.py`; walk-through (T054) not done |
| SC-011 | Suites above; ADR diff in item 4 |
