# Implementation Plan: CI Gate, Ingestion Resilience and Freshness Signal

**Branch**: `feature/003-ops-ci-reliability` (stacked on `refactor/src-data-layout` → `feature/002-silver-gold-baselines` → `feature/001-base-simulator`; none merged) | **Date**: 2026-11-20 | **Spec**: [spec.md](spec.md) (approved, committed, Clarifications included: FR-013 = Option A)

**Input**: Feature specification from `/specs/003-ops-ci-reliability/spec.md`

**Note**: `setup-plan.sh` was not executable (permission denied), so it was run with `bash`. It
reported the feature as `003-ops-ci-reliability`; the git branch is `feature/003-ops-ci-reliability`.
`.specify/extensions.yml` does not exist, so no before-plan or after-plan hooks apply.

## Summary

Close the three gaps found by the 2026-11-18 drill. (1) A GitHub Actions workflow with three
independent jobs (`test`, `contract`, `build`) stops the line on a red build. (2) Ingestion retries
connection-level database errors on the **same line**, with bounded exponential backoff (1 s, 2 s, 4 s,
then 5 s, within a 120 s window), so a 31 s outage no longer kills the `simulator | ingestion` pipe or
triggers a replay; duplicates are tallied apart from rejections. (3) A read-only view
`ops.ingestion_health` exposes freshness, events per minute, the real rejection rate and duplicates over
60 s, and a healthcheck on `ingestion` (interval 5 s, retries 1, threshold 15 s) turns it `unhealthy` when
data stops. Documentation (post-mortem, runbook, SLI/SLO proposal) and a rerun of drills F1, F2, F3
close the story.

**Approach** (from [research.md](research.md)): no new service, dependency, table or contract. Retry is
a small stdlib module around the one call that stores the current line, so the pipe gives backpressure
and nothing is lost or reordered. The healthcheck copies the 002 `refresh` pattern. The CI contract job
reuses the existing fixture test, and the test job runs the existing CI-ready command unchanged. Four
phases, each ending green and committable on its own: CI, resilience, freshness, documentation plus
drill rerun.

## Technical Context

**Language/Version**: Python 3.12+ (unchanged).

**Primary Dependencies**: unchanged. `psycopg` 3 for retry and health; PyYAML, `jsonschema` and
`rfc3339-validator` (already in the dev extra) for tests. No `pyproject.toml` or `uv.lock` change
(research R15).

**Storage**: PostgreSQL 16 only. One new schema `ops` with one view; no table, no derived storage.
Bronze is insert-only and untouched (FR-015).

**Testing**: pytest + pytest-cov, tests first, throwaway database per module (002 R10). Unit tests for
retry, classification, tally and config; integration tests for the view, the healthcheck and a real
`57P01`; live tests (`-m live`, host only) for the outage and the feed stop. Gate 2: coverage above 80 %
through the unchanged CI-ready command.

**Target Platform**: Linux containers via `docker-compose` (existing `db`, `ingestion`, `api`,
`refresh`, `tests`); GitHub Actions `ubuntu-latest` for CI.

**Project Type**: operations story inside the existing single Python project: one workflow file, one
init script, two small ingestion modules, edits to `run.py`, config, compose and `.env.example`, plus
documents and drill scripts.

**Performance Goals**: measured, not assumed. Detection within 15 s + one 5 s interval + probe duration
(SC-008). Recovery after the database returns within the 5 s wait cap plus connection time. The view's
cost is measured on 1 million synthetic rows in Phase 3 (research R7). No throughput SLO (turn 3).

**Constraints**: PostgreSQL only; no new service, broker, buffer or simulator resume; bronze
insert-only; no ADR change except one addendum line to ADR-0001; no change to `contracts/`; the CI test
job calls the existing command unchanged; lint and security jobs are out of scope (DevOps owner);
retry logs contain no connection details; healthcheck prints no connection details; ingestion depends
only on `db`.

**Scale/Scope**: 1 corridor, 5 + 2 buses, about 5.35 events/s and about 2.0 KB/s at the compose pace
(3,851 events and 1,439,431 bytes per simulated hour); one ingestion process; one workflow with three jobs.

## Key decisions (numbers and where they are justified)

| Decision | Value | Research |
|---|---|---|
| Retry initial / max wait / total window | `1` s / `5` s / `120` s, factor 2, no jitter, 3 s connect timeout; window is 3.9 × the 31 s drill outage; recovery delay at most 5 s plus connect time; about 26 `db_retry` lines in a full window | R1 |
| What is retried | `OperationalError` / `InterfaceError` with SQLSTATE `None`, class `08`, `57P01`, `57P02`, `57P03`; everything else raises; a bad event is a rejection, never an exception | R2 |
| Holding the line | the retry wraps the call that stores the current line; stdin is not read while waiting; the pipe gives backpressure; about 65,536 B pipe ≈ 32.8 s at 2.0 KB/s (to measure) | R3 |
| Duplicates | stay in `bronze.rejections` as `duplicate_event`; counted as `duplicates`, excluded from rejection count and rate in logs, summary and view | R4 |
| Healthcheck | `interval 5s`, `timeout 3s`, `retries 1`, `start_period 20s`, threshold `15` s; `retries 1` is needed because the default 3 would allow 30 s | R5 |
| Stopping the feed | `SIGSTOP` / `SIGCONT` to the process whose argv is exactly `-m src.data.simulator.main`, through `scripts/drill/feed_control.py` piped into `docker compose exec -T ingestion python -` | R6 |
| `ops` view | one row, `clock_timestamp()`, 60 s windows, NULL for "not computable"; the healthcheck reads only `last_insert_age_s` | R7, R8 |
| CI | one workflow, three independent jobs on `ubuntu-latest`; `test` = unchanged command; `contract` = existing fixture test through `uv run --frozen`; `build` = `docker compose --profile tools build`; `pull_request` + `push` to `main`; concurrency cancels PR runs only; setup-uv cache only | R9 |
| Demonstration | six throwaway branches and draft PRs into the feature branch, evidence in `verification.md`, nothing kept in the repo | R10 |
| SLI/SLO proposal | fresh probes ÷ probes; proposed 99 % over 28 days, error budget 403 min; marked as a proposal; final target chosen from the rerun | R11 |
| Drill rerun | `scripts/drill/run_drill.sh`; same faults, windows and metric columns as the original drill, sample every 2 s; baseline data in `docs/ops/drill-baseline/`; table in `docs/ops/drill-rerun.md` | R12 + Gate decisions |

## Constitution Check

*GATE: evaluated before Phase 0; re-checked after Phase 1 design (below).*

Constitution v1.1.0; turn 1 active (`docs/turns-ritmo.md` §3). The five Core Principles apply; other
norms only as adopted in §3.2.

| Principle | Status | Evidence |
|---|---|---|
| **I. Risk-First Order** | PASS | Mitigates the turn-1 Level 1 risk (data integrity and availability of capture): a database outage no longer replays the day as duplicates, and duplicates no longer inflate the rejection rate. Disciplined lane. No adaptive-lane feature is included. |
| **II. Contract-First & Data Ownership** | PASS | Interfaces are defined before code in [contracts/](contracts/README.md): the `ops.ingestion_health` columns and NULL semantics, the retry log line (JSON Schema), the workflow job contract and the new env vars. Every object has an owner ([data-model.md](data-model.md)). The `ops` schema stores nothing. The event contract and `contracts/` are untouched. |
| **III. Isolated Ingestion & Deterministic Real Time** | PASS (strengthened) | Ingestion keeps capturing through a database outage; the healthcheck depends only on `db` (no API, console or `refresh`), asserted by a compose test. No LLM or third-party call on the path. The CI and drill tools sit outside the runtime path. |
| **IV. Unbreakable Human Gate** | PASS (nothing to gate) | No recommendation, rule or on-road action is added; the story only exposes signals. |
| **V. Test-First & Automated Gates** | PASS | Each phase starts with failing tests ([quickstart.md](quickstart.md)). The story makes Gate 2 automatic on every pull request and push to `main`; coverage stays above 80 % through the unchanged command. |

**Turn-1 adopted norms (§3.2)**: RNF-3.2.1 / 3.2.2 (compose, ingestion isolated): PASS. RNF-3.3.1
(boundary validation of 100 % of packets): unchanged; retry sits after validation and never accepts an
invalid event. Gate 1 (schema validation only): PASS, the log schema and the existing read fixtures are
validated, and the `contract` job runs the latter on every change. Gate 2: PASS, now automatic. Gate 4:
N/A. Security baseline: parameterized SQL only, no secrets in the repository or in the workflow, no
connection details, stack traces or event content in retry logs or in the healthcheck output.

**Deferred norms (Evolution, not blocking)**: SAST/SCA and lint jobs (Gate 1 tools and the SCA part of
Gate 2, turn 2, DevOps owner), pinning actions by SHA and image scans (A03, turn 2), OpenTelemetry-
compatible logs and alert routing (A09, turn 2), Redis, PostGIS, 1,000 events/s, persistent buffer and
contingency mode (turn 3), simulator resume mid-day, `arrival_ts` index (only if R7 measurement asks
for it), alerting on the 5 % per minute rejection condition (the view exposes the signal only), RBAC and
grants on `ops` (turn 2). Listed in research R13.

**Post-design re-check**: the design adds no deferred norm as a requirement and weakens no principle.
Points checked explicitly:

1. The new schema `ops` is a fifth schema. ADR-0001 gets the one-line addendum the spec asks for
   (FR-019), in the style of the `config` addendum. The view holds no data and no secrets. The change
   falls under CODEOWNERS (`/docs/adr/`), so the data owner approves it.
2. Duplicates stay in `bronze.rejections` (Option A): ADR-0001, ADR-0002 and the rejection schema are
   unchanged. Only counting changes.
3. The `db_recovered` log line is a small addition beyond the spec's list of lines (retry and final
   error). It is justified because the post-mortem and the drill need the real outage time, it is not
   a retry (SC-005 counts `db_retry` lines only), and it carries no sensitive field.
4. Structured retry logs are plain JSON with a UTC timestamp. The OpenTelemetry-compatible format is a
   turn-2 norm and is recorded as evolution, not built now.
5. SC-011 says the ADR diff is "exactly one added line". The 002 addendum added the sentence plus one
   blank separator line (2 lines in `--numstat`). The plan follows that precedent: one content line and
   the same blank separator, nothing removed. See risk 8.

**No violations; Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/003-ops-ci-reliability/
├── spec.md                         # approved
├── plan.md                         # this file
├── research.md                     # Phase 0 output (R1–R15)
├── data-model.md                   # Phase 1 output
├── quickstart.md                   # Phase 1 output (per-phase validation)
├── contracts/                      # Phase 1 output (feature-local interfaces)
│   ├── README.md                   # index + new environment variables
│   ├── ops-ingestion-health.md     # the view and the healthcheck
│   ├── ingestion-retry-log.schema.json
│   └── ci-workflow.md
├── checklists/requirements.md      # exists
├── tasks.md                        # /speckit.tasks (not created here)
└── verification.md                 # written during implementation (evidence per phase)
```

### Source code and repository files (to be touched)

New:

```text
.github/workflows/ci.yml                               # Phase 1
docs/ops/ci-branch-protection.md                       # Phase 1 (FR-008)
src/data/ingestion/retry.py                            # Phase 2: policy, classification, backoff, JSON log lines
src/data/ingestion/health.py                           # Phase 3: freshness healthcheck
src/data/db/init/006_ops.sql                           # Phase 3: schema ops + view ops.ingestion_health
scripts/drill/feed_control.py                          # Phase 3: SIGSTOP/SIGCONT of the simulator (piped into the container)
scripts/drill/run_drill.sh                             # Phase 4: F1, F2, F3 and sampling
docs/ops/post-mortem-2026-11-18-drill.md               # Phase 4 (FR-024)
docs/ops/runbook-ingestion-refresh-unhealthy.md        # Phase 4 (FR-025)
docs/ops/sli-slo-proposal.md                           # Phase 4 (FR-026)
docs/ops/drill-rerun.md                                # Phase 4 (FR-027, before/after table)
docs/ops/drill-baseline/                               # Phase 4: metrics.csv, events.log, rejections.txt, restarts.txt (2026-11-18 "before" data)
tests/unit/test_ci_workflow.py                         # Phase 1
tests/unit/test_ops_docs.py                            # Phase 1 and 4
tests/unit/test_drill_feed_control.py                  # Phase 3
src/data/tests/unit/test_ingestion_retry.py            # Phase 2
src/data/tests/unit/test_compose_ingestion.py          # Phase 2 and 3
src/data/tests/integration/test_ingestion_outage.py            # Phase 2 (real 57P01, throwaway DB)
src/data/tests/integration/test_ingestion_outage_live.py       # Phase 2 (-m live, host only)
src/data/tests/integration/test_ingestion_health_view.py       # Phase 3
src/data/tests/integration/test_ingestion_health.py            # Phase 3
src/data/tests/integration/test_ingestion_feed_live.py         # Phase 3 (-m live, host only)
specs/003-ops-ci-reliability/verification.md           # evidence
```

Modified:

```text
src/data/ingestion/run.py                              # retry around the stored line; tally and summary; exit code
src/pulsoflota/config.py                               # four getters with validation
docker-compose.yml                                     # ingestion: 4 env vars + healthcheck; tests: read-only mounts
.env.example                                           # 4 new variables with defaults
docs/adr/0001-data-layers-and-ingestion-semantics.md   # one addendum line (+ blank separator)
.gitignore                                             # drill-out/ (only if not already ignored; .drill-input/ is already in .git/info/exclude)
src/data/tests/unit/test_ingestion_run.py              # updated for the new retry and tally behavior (red first)
src/data/tests/integration/test_schema_init.py         # adds schema ops and the ADR addendum check
src/data/tests/unit/test_no_bronze_writes.py           # scan also covers 006_ops.sql and ingestion/health.py
tests/unit/test_env_example.py                         # four new variables
```

Not touched: `contracts/`, `src/data/ingestion/bronze.py` and `validate.py` (the duplicate marker
already exists as `IngestResult.reason`), `src/data/refresh/`, `.dockerignore`, `Dockerfile`,
`pyproject.toml`, `uv.lock`, `.github/CODEOWNERS` (see open question 2).

**Structure Decision**: keep the existing layout (`src/data/ingestion/` for ingestion code,
`src/data/db/init/` for DDL, `tests/unit` for repository-level checks, `src/data/tests/` for data
tests). New top-level folders: `docs/ops/` and `scripts/drill/` (the latter already sits next to
`scripts/tasks_to_issue.py`). The `tests` service gains read-only mounts for `.github/workflows`,
`docs/ops` and `scripts`, as 002 did for `specs` and `docs/adr`; the command of the `tests` service
is not changed.

## Phases

Each phase: tests first, implementation, then the Andon check (the CI-ready command) green, then the
human commits. Phase *n* does not depend on Phase *n+1*; the suggested order protects each step with the
previous one.

### Phase 1 — CI as the Andon (US1, P1)

Goal: FR-001 to FR-008, SC-001 to SC-003.

1. Record the baseline Andon run on this branch (counts, coverage, time).
2. Red: `tests/unit/test_ci_workflow.py` and the branch-protection check in `test_ops_docs.py`; add the
   read-only mounts for `.github/workflows` and `docs/ops` to the `tests` service.
3. Write `.github/workflows/ci.yml` (research R9) and `docs/ops/ci-branch-protection.md`.
4. Green: the quickstart Phase 1 commands, then the Andon run.
5. Human: commit, push, open the PR, run the six probes of research R10, record evidence.

Exit: local Andon green; workflow structure test green; first remote run green (all three jobs).
Commit message: `ci: run tests, contract fixtures and compose build on every PR`.

### Phase 2 — Ingestion survives a database outage (US2, P2)

Goal: FR-009 to FR-015, SC-004 to SC-006.

1. Red, unit: retry policy and config validation; backoff sequence and window shortening with a fake
   clock; classification table; same-line retry without skip or reorder; exhaustion and exit code; log
   lines valid against the schema and free of secrets; tally and summary (duplicates apart, `null`
   rate); `.env.example` and compose entries. Update `test_ingestion_run.py` where the old
   `connect_with_retry` contract (10 × 2 s, `RuntimeError`) is replaced.
2. Red, integration: real `57P01` through `pg_terminate_backend` on a throwaway database; duplicate
   counted apart, bronze unchanged.
3. Implement `retry.py`, edit `run.py` and `config.py`; add the four variables to `.env.example` and the
   `ingestion` service environment.
4. Green: unit and integration tests, then the Andon run; then the live outage check (quickstart).
5. Measure and record: pipe capacity and bytes per event inside the container (confirms R3).

Exit: tests green, live check shows no exit, no restart, no gap, no replay.
Commit message: `feat(ingestion): retry the current line through a database outage`.

### Phase 3 — Freshness SLI view and healthcheck (US3, P3)

Goal: FR-016 to FR-023, SC-007, SC-008.

1. Red: view tests on crafted bronze (empty, fresh, stale, mixed, duplicates only, windows); healthcheck
   tests; compose test for the `ingestion` healthcheck and its isolation; ADR addendum test; schema
   init and write-guard updates; `feed_control` selection test on a fake `/proc` tree.
2. Implement `006_ops.sql`, `health.py`, `feed_control.py`; add the healthcheck and the setting to the
   `ingestion` service and `.env.example`; add the ADR-0001 addendum line.
3. Green: tests, Andon run, then the live feed-stop check (quickstart).
4. Measure and record: start-to-first-healthy time (confirms the 20 s start period) and the view cost on
   1 million rows (decides whether the `arrival_ts` index stays in the evolution list).

Exit: tests green; live check shows `unhealthy` within 15 s + 5 s + probe duration after the feed stops
and `healthy` again after resume.
Commit message: `feat(ops): expose ingestion freshness and add an ingestion healthcheck`.

### Phase 4 — Documentation and drill rerun (FR-024 to FR-027, SC-009 to SC-011)

1. Red: `test_ops_docs.py` section checks for the post-mortem, runbook, SLI/SLO proposal, branch protection
   and drill table; add the `scripts` mount.
2. Write `docs/ops/*` and `scripts/drill/run_drill.sh`.
3. Run the drill on a fresh volume (quickstart Phase 4), fill `docs/ops/drill-rerun.md` with the real
   numbers, and update the SLO proposal with measured stale times.
4. Andon run; SC-011 check (`git diff` of ADR-0001 adds one content line and nothing else).
5. Human walk-through of the runbook (SC-010), recorded in `verification.md`.

Exit: all docs and the before/after table present; Andon green.
Commit message: `docs(ops): post-mortem, runbook, SLI/SLO proposal and drill rerun`.

## Risks

| # | Risk | Effect | Mitigation |
|---|---|---|---|
| 1 | `retries: 1` flaps on a one-probe database blip | a 5 s `unhealthy` flash | nothing restarts on health, the 15 s threshold already filters; written in compose comments and the runbook |
| 2 | The retry window is exhausted (database down more than 120 s) | exit 1, restart policy restarts the pipe, the seeded day replays as duplicates | known limit in the spec; the replay shows as duplicates (not rejections) and as a stale `unhealthy` signal; simulator resume is first on the evolution list |
| 3 | F3 (ingestion crash) still replays from the start | stale for about as long as the process had run; lag reported, not fixed | declared in SC-009 ("reported"); SLO proposal says so |
| 4 | A lost acknowledgement can duplicate one `bronze.rejections` row per outage | one extra row at most per outage | accepted and documented (R3); bronze events are never duplicated |
| 5 | Existing database volumes lack schema `ops` | healthcheck reports `unhealthy: check failed` | runbook and quickstart give the idempotent `psql -f` and the `down -v` options (R14) |
| 6 | `docker compose` on `ubuntu-latest`, action major versions and job timeouts are assumptions | first run could fail for environment reasons | `docker compose version` guard step; confirm majors when writing the file; timeouts adjusted after the first runs; all recorded in `verification.md` |
| 7 | The default simulated day lasts 720 s of wall time, then ingestion goes stale and restarts into a replay | `unhealthy` in a long-running demo, which is correct for a finite feed | spec edge case; the drill sets a long `SIM_DURATION_S`; runbook explains it |
| 8 | SC-011 "exactly one added line" versus the blank separator line of the 002 precedent | a strict reader counts two added lines | follow the 002 precedent; verification reports the numstat and states the blank line |
| 9 | `view` scans `bronze.events` for the 60 s counts | cost grows with table size | measured in Phase 3; the healthcheck does not use the counts; index kept as evolution unless the measurement asks for it |
| 10 | A hung connect could stall the loop | window overrun | 3 s connect timeout per attempt; window measured on a monotonic clock |
| 11 | A non-retryable database error (for example `53100` disk full) exits the process | restart loop | intended loud failure; not hidden by retry (R2) |
| 12 | The rerun on the real repo stack could delete the developer's volume or collide on ports | data loss on a dev machine | own Compose project name `pulsoflota-drill`, port guard in the script (research "Gate decisions") |

## Open questions

1. **Resolved (data owner, 2026-11-20).** The original 2026-11-18 drill is available in `.drill-input/`
   (git-ignored, local only, never committed). The rerun reuses its faults (F1 api 30 s, F2 db 30 s,
   F3 kill of ingestion), observation windows (45 / 30 / 25 / 30 / 90 / 90 s) and metric columns, with
   one sample every 2 s. Repo versions: `scripts/drill/run_drill.sh` (English, real repo stack under its
   own Compose project name) and `docs/ops/drill-baseline/` (baseline metrics as the "before" data).
   Details: research.md "Gate decisions".
2. **Resolved (data owner, 2026-11-20).** `.github/workflows/` gets no CODEOWNERS entry for now; the
   decision is taken with the team in issue #5. `.github/CODEOWNERS` stays untouched.

No open question remains. Defaults chosen in the plan (retry numbers, health timing, SLO starting point) are
stated with reasons in research.md and can be changed there without changing the structure.

## Complexity Tracking

No Constitution Check violations. Nothing to justify.

## Readiness for `/speckit.tasks`

Ready. All `NEEDS CLARIFICATION` items are resolved (the two open questions were answered on 2026-11-20
and recorded in research.md "Gate decisions"). Tasks should follow the four phases in order, each task list
beginning with its red tests, and each phase ending with the Andon run.
