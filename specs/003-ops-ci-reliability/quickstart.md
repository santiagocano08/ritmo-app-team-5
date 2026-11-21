# Quickstart — validating 003-ops-ci-reliability

A run and validation guide. Each phase starts with failing tests (red) and ends with the checks below
green. Interfaces are in [contracts/](contracts/README.md), values and reasons in
[research.md](research.md), shapes in [data-model.md](data-model.md). No implementation code here.

## Prerequisites

- Docker with Compose v2, `uv` 0.9.5, a clone on branch `feature/003-ops-ci-reliability`.
- `cp .env.example .env` (the file is git-ignored). `POSTGRES_PASSWORD` keeps its placeholder for local runs.
- Commands run from the repository root. Targeted runs use `--no-cov` (the coverage gate is for the
  whole suite).
- Agents never commit or push; the human commits each phase and pushes the probe branches of Phase 1.

## Dedicated compose project for verification

Live checks start, stop and reset a stack. Never run them on your default project: `down -v` would delete
your volume. Use a dedicated project name for every live check (the drill uses `pulsoflota-drill`):

```text
export COMPOSE_PROJECT_NAME=pulsoflota-verify
```

The live tests (`-m live`) skip themselves unless `-m live` is passed and this variable is set. Clean up
with `docker compose down -v` **under this project only**, or plain `docker compose down` without `-v`.

## The Andon check (end of every phase)

```text
docker compose --profile tools build tests && docker compose --profile tools run --rm tests
```

Expected: 0 failed, coverage above 80 %, and the number of passed tests never lower than the previous
phase plus the new tests. Record the counts in `specs/003-ops-ci-reliability/verification.md`. Start
Phase 1 by recording the baseline on this branch (the 002 end state was 422 passed, 4 skipped, 91.97 %).

---

## Phase 1 — CI (US1, FR-001 to FR-008)

**Red first**: `tests/unit/test_ci_workflow.py` (workflow exists; triggers; three independent jobs with
the stated ids; the test job holds the unchanged command; no `secrets.` reference; `contents: read`;
concurrency; the `tests` service mounts `.github/workflows`) and `tests/unit/test_ops_docs.py` for the
branch-protection doc.

**Green**:

```text
uv run pytest tests/unit/test_ci_workflow.py tests/unit/test_ops_docs.py -q --no-cov
uv run --frozen --extra dev pytest src/data/tests/contract/test_read_fixtures.py -p no:cacheprovider --no-cov
docker compose --profile tools build        # the build job, locally
```

Expected: tests pass; the contract run shows 33 passed; the build exits 0.

**On GitHub (human)**: push the branch and open the pull request; then the probes of research R10 (one
throwaway branch and one draft pull request each, base `feature/003-ops-ci-reliability`).

| Probe | Expected |
|---|---|
| `ci-probe/green` | `test`, `contract`, `build` green; same passed/skipped count and coverage as the local Andon run (SC-002) |
| `ci-probe/red-test` | `test` red; revert the commit and the run is green again (SC-001) |
| `ci-probe/low-coverage` | `test` red on the coverage gate (SC-002) |
| `ci-probe/bad-fixture`, `ci-probe/orphan-fixture` | `contract` red (SC-003) |
| `ci-probe/broken-build` | `build` red (FR-004) |

Close the pull requests without merging, delete the branches, and write run URLs and results into
`verification.md`. Whether branch protection was configured (so the merge is blocked) is recorded as it is.

Phase 1 is done when the local Andon run is green and the green probe is green on GitHub.

---

## Phase 1b — Publish and pin (US1 addition, FR-029, FR-030; added 2026-11-21)

**Red first**: `tests/unit/test_ci_workflow.py` (publish job) and `tests/unit/test_container_pins.py`
(exact base versions, OCI labels). Expected failures: no `publish` job; `python:3.12-slim` and
`postgres:16` are floating tags; labels missing.

**Green** (one command at a time):

```text
uv run pytest tests/unit/test_ci_workflow.py tests/unit/test_container_pins.py -q --no-cov
docker build --target prod --build-arg REVISION=dryrun0000 --build-arg SOURCE_URL=https://github.com/OWNER/REPO -t pulsoflota-prod-dryrun .
docker image inspect pulsoflota-prod-dryrun --format '{{json .Config.Labels}}'
docker image rm pulsoflota-prod-dryrun
```

Expected: tests pass; the build exits 0; the labels show `source`, `revision=dryrun0000` and
`title=pulsoflota`. Then the host suite, the Andon command and `docker compose --profile tools build`
(unchanged behavior). Nothing is pushed. The remote `publish` run appears only after #4, #6 and #9 reach
`main`, and may need the owner to allow Actions to write packages (plan, "Plan-level additions").

---

## Phase 2 — Ingestion resilience (US2, FR-009 to FR-015)

**Red first** (unit, no database): retry policy defaults and invalid values; backoff sequence 1, 2, 4,
5, 5 with a fake clock; the last wait is shortened to the window end; classification (`None`, class
`08`, `57P01`, `57P02`, `57P03` retry; `DataError`, `IntegrityError`, `53100` do not); the same line is
retried and the next line is not read before it is stored; no skipped or reordered line; exhaustion
raises, logs `db_retry_exhausted` and exits non-zero; exactly one `db_retry` line per failed attempt,
valid against the log schema, with no password, host, DSN or event content; tally separates duplicates
from rejections; `rejection_rate` is `null` for an empty denominator; the `.env.example` and compose
entries exist.

**Red first** (integration, throwaway database): a real `pg_terminate_backend` between two lines gives
`57P01`, ingestion reconnects, and the stored `event_id` order equals the input order; a replayed line is
counted as a duplicate, bronze rows are unchanged, and the duplicate row has reason `duplicate_event`.

**Green**:

```text
uv run pytest src/data/tests/unit/test_ingestion_run.py src/data/tests/unit/test_ingestion_retry.py \
  src/data/tests/integration/test_ingestion_outage.py tests/unit/test_env_example.py -q --no-cov
```

**Live check (SC-004, SC-005)**, from the host (needs the Docker CLI; skipped inside the `tests`
container and in CI):

```text
export COMPOSE_PROJECT_NAME=pulsoflota-verify
docker compose down -v && docker compose up -d --build db ingestion    # dedicated project only
# wait about 60 s, then:
uv run pytest src/data/tests/integration/test_ingestion_outage_live.py -m live -q --no-cov -s
```

The test records the highest bronze row and the `RestartCount` and `StartedAt` of `ingestion`, stops `db`
for 30 s, starts it, waits for new rows, then asserts: no exit and no restart, the simulator PID is
unchanged, rows keep growing, the `event_id` order equals the first *K* event ids of the seeded
simulator output, no replay from the start, and every retry line is valid JSON without credentials.
Finish with `docker compose down -v` under `pulsoflota-verify`. Also measure here and write into `verification.md`: the pipe capacity inside the container
(`F_GETPIPE_SZ`) and the bytes per event, which confirm or correct research R3.

Phase 2 is done when the unit and integration tests and the Andon run are green and the live check passes.

---

## Phase 3 — Freshness view and healthcheck (US3, FR-016 to FR-023)

**Red first**: `006_ops.sql` objects exist (schema `ops`, view `ops.ingestion_health`, no base table in
the schema); the view on crafted bronze rows (empty, one fresh row, a stale row, mixed rejections and
duplicates, duplicates only, empty window, rows older than 60 s); the healthcheck module (empty bronze
unhealthy, fresh healthy, stale unhealthy, default and override of the threshold, unreachable database
unhealthy without detail, view missing unhealthy); compose test for the `ingestion` healthcheck values
(interval 5s, timeout 3s, retries 1, start period 20s, `CMD python -m src.data.ingestion.health`),
`INGESTION_HEALTH_MAX_AGE_S` passed with default 15, and ingestion still depending only on `db`; the
ADR-0001 addendum sentence; `test_schema_init.py` lists the `ops` schema and view; the write guard
covers `006_ops.sql` and `health.py`. The `tests` service gets the read-only `./scripts` mount in this
phase (it is needed by the `feed_control` test), not in Phase 4. The ADR addendum is checked in the
container only as a sentence; "one added content line, at most the blank separator" is the host check
below.

**Green**:

```text
uv run pytest src/data/tests/integration/test_ingestion_health_view.py src/data/tests/integration/test_ingestion_health.py \
  src/data/tests/unit/test_compose_ingestion.py src/data/tests/integration/test_schema_init.py \
  src/data/tests/unit/test_no_bronze_writes.py -q --no-cov
git diff --numstat docs/adr          # host check: one content line added (plus at most the blank separator, 002 precedent), none removed
```

**Live check (SC-007, SC-008)**:

```text
export COMPOSE_PROJECT_NAME=pulsoflota-verify
docker compose down -v && docker compose up -d --build db ingestion    # dedicated project only
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -x -c "SELECT * FROM ops.ingestion_health"
uv run pytest src/data/tests/integration/test_ingestion_feed_live.py -m live -q --no-cov -s
```

The live test reads the view (freshness below 15 s, positive `events_60s`), freezes the simulator with
`scripts/drill/feed_control.py stop`, polls `docker inspect` health log until `unhealthy`, and asserts
the delay from the last insert is at most 15 s + one 5 s interval + the probe duration (the spec's "15 s plus one healthcheck interval", with the probe duration measured and stated). It then resumes the feed and
asserts `healthy` within one interval plus the probe duration after the first new insert. Also record in
`verification.md`: the time from container start to the first `healthy` (confirms the 20 s start period)
and `EXPLAIN ANALYZE` of the view on 1 million synthetic rows in a throwaway database (R7).

Existing database: apply the script instead of resetting the volume:
`docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < src/data/db/init/006_ops.sql`.

Phase 3 is done when the tests, the Andon run and the live check are green.

---

## Phase 4 — Documentation and drill rerun (FR-024 to FR-027)

**Red first**: `tests/unit/test_ops_docs.py` checks that `docs/ops/` holds the post-mortem with its
seven sections (summary, timeline, impact, root causes, what went well, actions mapped to US1 to US3,
lessons), the runbook (state, freshness view, recovery for database outage, stopped feed, crashing
ingestion, stalled `refresh`, escalation), the SLI/SLO text marked as a proposal with an error budget, the
branch-protection note, and the drill table; the baseline files (`tests/unit/test_drill_baseline.py`: English
header, rows unchanged, no Spanish label) and the static checks of `scripts/drill/run_drill.sh`
(`tests/unit/test_drill_script.py`). The `scripts` mount already exists since Phase 3, where
`tests/unit/test_drill_feed_control.py` (T029) checks that `feed_control.py` selects only the simulator
process in a fake `/proc` tree (not PID 1, not itself). The `docs/ops` and `.github/workflows` mounts
come from Phase 1.

**Green**: `uv run pytest tests/unit/test_ops_docs.py tests/unit/test_drill_baseline.py tests/unit/test_drill_script.py tests/unit/test_drill_feed_control.py -q --no-cov`,
then the Andon run.

**Drill rerun (final acceptance)**:

```text
bash scripts/drill/run_drill.sh        # own Compose project, fresh volume, seed 42, faults F1, F2, F3, same windows as 2026-11-18, one sample every 2 s
```

The script writes raw samples to `drill-out/` (git-ignored). Copy the results into the before/after
table of `docs/ops/drill-rerun.md` and compare with the baseline (SC-009):

Lag-reading rule, the same for both columns: *lag after F2* = `ingestion_lag_s` of the last sample strictly
before the F3 mark; *F3 lag* = `ingestion_lag_s` of the last sample of the observation window. The
2026-11-18 report quoted 125 s and 204 s, read a few seconds off (t=232 and t=312); the fixed rule is used
for both columns. The baseline CSV header is the English one (`t_s,events,max_event_ts,ingestion_lag_s,duplicates,other_rejections,ingestion,api,db`).

| Metric | Baseline | Rerun |
|---|---|---|
| Ingestion survives F2 (no exit, no restart) | died, restarted | measured |
| Lag after F2 | 120 s (t = 227 s) | measured, expected below 15 s |
| F3 lag | 209 s (t = 316 s) | measured, reported as is |
| Duplicates counted as rejections | 971 (65 %) | 0 as rejections; duplicates reported on their own |
| Real rejection rate | not available | measured |
| Alerts or `unhealthy` transitions | none | at least one, measured |
| Bronze integrity | 525 of 525 | measured |

A value that does not improve is written down as it is.

**Last step**: a person who did not run the drill follows the runbook on a live stack, reads the
freshness view, freezes and resumes the feed, and recovers; their notes go into `verification.md`
(SC-010). Update the SLO proposal with the measured stale times.

Phase 4 is done when the docs tests, the Andon run and the drill table are complete.
