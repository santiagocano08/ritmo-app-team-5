# Feature Specification: CI Gate, Ingestion Resilience and Freshness Signal

**Feature Branch**: `feature/003-ops-ci-reliability` (stacked on `refactor/src-data-layout`, which is stacked on `feature/002-silver-gold-baselines`; none merged yet)

**Created**: 2026-11-18

**Status**: Draft

**Traces to**: Turn-1 risk "data integrity" (Disciplined lane), Principle III (isolated ingestion keeps capturing), Principle V (automated gates, constitution Gate 2: coverage > 80 %), RNF-3.3.1. DevOps/SRE review of the course (Unit 3: CI as the Andon, small batches, observability, resilience, blameless post-mortem). Owner: data team.

**Input**: User description: "Small operations story that closes three gaps found by the 2026-11-18 incident drill on story 001: (1) a minimal CI workflow that blocks merges on a red build; (2) ingestion that survives a database outage without exiting, replaying or losing events, and that does not count duplicates as rejections; (3) an ingestion freshness SLI exposed as a read-only view plus a healthcheck that turns ingestion unhealthy when data stops arriving. Deliver also a blameless post-mortem, a runbook and a before/after rerun of the drill."

**Ground truth (binding, not re-decided here)**: `.specify/memory/constitution.md` v1.1.0 and `docs/turns-ritmo.md` (turn 1: Gate 1 schema validation, Gate 2 tests and coverage, Gate 4 human approval; SAST/SCA and observability stacks are deferred); ADR-0001 (insert-only bronze, `(source, event_id)` dedup, PostgreSQL only, schemas `bronze`/`silver`/`gold`/`config`); ADR-0002 (event contract and rejection reasons); ADR-0003 (read contract); `specs/001-base-simulator/` and `specs/002-silver-gold-baselines/` (compose services, the `refresh` freshness healthcheck, the CI-ready test command, `.env.example` conventions).

## Drill Evidence (baseline)

Incident drill on a copy of story 001 on 2026-11-18, faults injected with `docker compose stop/kill`. These numbers are the "before" column of the final acceptance.

| Fault | Duration | Observed behavior |
|-------|----------|-------------------|
| F1: API down | 31 s | Ingestion unaffected (good). |
| F2: database down | 31 s | The ingestion process dies (no reconnect). Compose restarts the whole `simulator \| ingestion` pipe, the simulator replays the day from the start with the same seed, 0 new events arrive, final lag 125 s. |
| F3: ingestion crash | n/a | Same restart-and-replay behavior, final lag 204 s. |
| End of drill | n/a | 971 duplicates counted as rejections (a false 65 % rejection rate). Bronze intact (525 of 525 rows, nothing corrupted). **No alert fired at any point.** |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CI as the Andon (Priority: P1)

A team member opens a pull request. Within minutes the repository itself reports whether the change keeps the test suite above the coverage gate, keeps the read-contract fixtures valid, and still builds the stack. If any check is red, the merge is blocked, so a broken change stops the line instead of reaching `main`.

**Why this priority**: it is the cheapest control and it protects every later story, including the other two in this feature. Principle V forbids skipping the gates, and today nothing enforces them automatically.

**Independent Test**: open a pull request with a harmless change and observe all jobs green. Push a commit that makes one test fail on purpose and observe the failing job red and the merge blocked. Revert it and observe green again.

**Acceptance Scenarios**:

1. **Given** a pull request or a push to `main`, **When** the workflow runs, **Then** it executes the existing CI-ready test command unchanged (`docker compose --profile tools build tests && docker compose --profile tools run --rm tests`) with the 80 % coverage gate, and the job fails if any test fails or coverage is below 80 %.
2. **Given** the same trigger, **When** the workflow runs, **Then** a separate job validates every read-contract fixture against its JSON Schema and fails if any fixture is invalid or any fixture has no schema.
3. **Given** the same trigger, **When** the workflow runs, **Then** a separate job checks that `docker compose build` succeeds for all services and fails otherwise.
4. **Given** a pull request with a deliberately failing test, **When** the workflow runs, **Then** the test job is red and the pull request shows as not mergeable once branch protection is configured as documented.
5. **Given** a fresh clone and no repository secrets, **When** the workflow runs, **Then** it succeeds using only the committed `.env.example` values.
6. **Given** the workflow file, **When** the DevOps owner later adds lint or security jobs (ruff, bandit, pip-audit), **Then** they can be added as new independent jobs without editing or removing the three jobs of this story.

---

### User Story 2 - Ingestion Survives a Database Outage (Priority: P2)

When the database becomes unreachable, ingestion keeps its place in the input stream and waits, instead of dying and being restarted from the beginning. When the database returns, ingestion continues from the exact line where it stopped: the simulator is not restarted, no event is lost and none is replayed. Duplicates that do reach ingestion are tallied as duplicates, not as rejections, so the rejection rate reflects real data problems only.

**Why this priority**: it fixes the integrity and availability failures of drills F2 and F3 (Principle III, turn-1 data-integrity risk) and removes the false 65 % rejection rate. It depends on nothing else in this story, but CI (P1) should guard it.

**Independent Test**: on a live stack, record the highest bronze sequence, stop `db` for about 30 s, start it again, and compare. Bronze keeps growing after recovery, the simulator process was not restarted, and there is no gap and no restart-from-zero in the event sequence.

**Acceptance Scenarios**:

1. **Given** a live stack ingesting, **When** the database is stopped for about 30 s and started again, **Then** the ingestion process does not exit, the simulator is not restarted, and after recovery new events keep being added to bronze.
2. **Given** the outage in scenario 1, **When** bronze is compared before and after, **Then** the event sequence has no gap and no event is inserted twice (the line being processed when the database failed is retried, not skipped).
3. **Given** the database is unreachable, **When** ingestion retries, **Then** each retry produces exactly one structured JSON log line, and the wait between retries grows (bounded exponential backoff) up to a maximum wait.
4. **Given** the retry limits are set through environment variables, **When** they are unset, **Then** safe defaults apply, and a default total retry window covers at least the 31 s outage of the drill.
5. **Given** the database stays down longer than the total retry window, **When** the window is exhausted, **Then** ingestion exits with a non-zero status and a final structured error line (it fails loudly, it does not hang forever).
6. **Given** the simulator emits an event whose `(source, event_id)` is already in bronze, **When** ingestion processes it, **Then** it is counted as a duplicate, is not counted as a rejection, and bronze is unchanged.
7. **Given** a mix of invalid events and duplicates, **When** the rejection count and rate are read, **Then** they include only events rejected for contract reasons and exclude duplicates, and the duplicates are reported on their own.

---

### User Story 3 - Ingestion Freshness SLI and Alert Signal (Priority: P3)

The on-call person (and any later alerting) needs to know, without reading logs, whether ingestion is currently landing data. A read-only view reports how fresh bronze is, how many events per minute are arriving, and the real rejection rate. A healthcheck on the ingestion service turns it `unhealthy` when data stops arriving, in the same way the `refresh` service already does for gold.

**Why this priority**: it closes the "no alert fired at any point" gap, but it is only useful once ingestion survives outages (P2) and CI protects it (P1).

**Independent Test**: on a live stack, read the view and confirm freshness is below the threshold. Stop the simulator feed and watch the ingestion service turn `unhealthy`. Resume the feed and watch it recover.

**Acceptance Scenarios**:

1. **Given** a live stack, **When** the ingestion health view is queried, **Then** it returns seconds since the last bronze insert (below 15 s), events per minute, and the real rejection rate over a recent window.
2. **Given** the view and the healthcheck, **When** the feed stops (the simulator is stopped), **Then** the ingestion service becomes `unhealthy` within the freshness threshold plus one healthcheck interval.
3. **Given** the service is `unhealthy` because the feed stopped, **When** the feed resumes, **Then** the service becomes `healthy` again without manual intervention beyond restoring the feed.
4. **Given** the threshold is set through its environment variable, **When** it is unset, **Then** the default of 15 s applies.
5. **Given** the database is unreachable, **When** the healthcheck runs, **Then** it reports `unhealthy` and prints no connection details (same rule as the `refresh` healthcheck).
6. **Given** bronze holds no rows yet, **When** the healthcheck runs after its start grace period, **Then** it reports `unhealthy` (no data is not healthy).
7. **Given** the view, **When** it is inspected, **Then** it is read-only: it contains no derived data stored outside the view and writes nothing to bronze, silver or gold.

---

### Documentation and Acceptance Deliverables

These are required outputs of the story, verified by existence and content checks plus the final drill rerun.

1. **Blameless post-mortem** of the 2026-11-18 drill under `docs/ops/`: what happened, impact, root causes, contributing factors and actions (actions = this story). No individual is blamed.
2. **Runbook** "ingestion or refresh unhealthy" under `docs/ops/`: how to see the state, how to check freshness, how to recover, and when to escalate.
3. **SLI definition, proposed SLO target and error budget** as text in the report (a proposal; the constitutional amendment is a separate PR).
4. **Drill rerun** on the fixed code: same faults F1, F2, F3 as the baseline, with a before/after table of the numbers in the Drill Evidence section. This is the final acceptance step.

### Edge Cases

- **Database comes back during a backoff wait**: the next retry succeeds; the wait is never longer than the configured maximum wait.
- **Database fails in the middle of a line**: the same line is retried. Dedup on `(source, event_id)` makes a retry safe, so a line that was in fact committed before the failure is counted as a duplicate, not lost or double-inserted.
- **Database down while the input stream keeps producing**: the simulator blocks on the full pipe and waits. No event is dropped. Wall-clock pacing of the simulator stalls during the outage; this is accepted.
- **Retry window exhausted**: ingestion exits non-zero (US2 scenario 5). The existing restart policy then restarts the pipe, which replays the seeded day as duplicates. This is a known limit; simulator resume is out of scope.
- **Simulator reaches the end of its configured duration**: the feed ends, freshness grows past the threshold and ingestion turns `unhealthy`. This is correct for a live feed and expected for a finite demo run.
- **Empty bronze**: freshness is not a number; the view reports it as unknown and the healthcheck is `unhealthy` after the start grace period.
- **Window with zero events**: events per minute is 0; the rejection rate is reported as not computable, not as 0 % or 100 %.
- **Window with only duplicates**: the real rejection rate is not computable (denominator excludes duplicates), duplicates are reported separately.
- **Workflow on a fork or a pull request without secrets**: it still runs, because it needs none.
- **Workflow runner without a cached image**: the first run is slower; the result is the same.
- **Branch protection not configured**: the checks still report red, but the merge is not blocked. The runbook states that enabling protection is a manual step by a repository admin.

## Clarifications

### Session 2026-11-20

- Q: Where are duplicates recorded (FR-013)? → A: Option A (answered by the data owner). Duplicates stay in `bronze.rejections` with reason `duplicate_event`, as ADR-0001 and ADR-0002 define today; no ADR change and no contract change. They are excluded from the rejection count and the rejection rate everywhere (logs, summary and the `ops` health view) and are reported on their own as a separate "duplicates" figure.

## Requirements *(mandatory)*

### Functional Requirements

**CI as the Andon (P1)**

- **FR-001**: A GitHub Actions workflow MUST run on every pull request and on every push to `main`.
- **FR-002**: A test job MUST run the existing CI-ready command unchanged: `docker compose --profile tools build tests && docker compose --profile tools run --rm tests`. The coverage gate (80 %, constitution Gate 2) comes from that command and MUST NOT be duplicated or lowered in the workflow.
- **FR-003**: A contract job MUST validate every fixture under `contracts/read/fixtures/` against its JSON Schema (draft 2020-12 with format checks) and MUST fail if a fixture is invalid or has no matching schema.
- **FR-004**: A build job MUST check that `docker compose build` succeeds for every service of `docker-compose.yml`.
- **FR-005**: Each job MUST fail the workflow run when its check fails, and a run MUST be green only when all three jobs pass.
- **FR-006**: The workflow MUST need no repository secrets. The test stack MUST use the committed `.env.example` values.
- **FR-007**: The workflow MUST be structured as independent jobs so that additional jobs (lint, security scanning) can be added later without changing these three.
- **FR-008**: The repository MUST document how a repository admin sets branch protection so that the three jobs are required checks to merge into `main`. Setting it is a manual admin step and is not part of this change.

**Ingestion survives a database outage (P2)**

- **FR-009**: When the database is unreachable (at start, or at any point while running), the ingestion process MUST NOT exit. It MUST retry the same input line until the line is stored or the retry window is exhausted.
- **FR-010**: Retries MUST use exponential backoff with a bounded maximum wait per attempt and a bounded total retry window. The initial wait, the maximum wait and the total window MUST be configurable through environment variables with safe defaults. The default total window MUST cover at least the 31 s outage of the drill. The exact default values are fixed in the plan and documented in `.env.example`.
- **FR-011**: Each retry MUST emit exactly one structured JSON log line with a UTC timestamp, the attempt number, the wait before the next attempt and a generic reason. It MUST NOT include connection strings, credentials or the content of the event.
- **FR-012**: When the window is exhausted, ingestion MUST exit non-zero after one final structured error line. When the database returns within the window, ingestion MUST resume from the retried line with no skipped and no repeated line, and the simulator process MUST NOT be restarted.
- **FR-013**: A duplicate (same `source` and `event_id` already in bronze) MUST NOT be counted as a rejection. It MUST be recorded in `bronze.rejections` with reason `duplicate_event` (as ADR-0001 and ADR-0002 define today) and MUST be counted separately from contract rejections. No new table is created, and neither the ADRs nor the event contract change for this.
- **FR-014**: The rejection count and rejection rate reported by ingestion (logs, summary and the health view) MUST exclude every row of `bronze.rejections` whose reason is `duplicate_event`. The duplicates count MUST be reported on its own as a separate "duplicates" figure in the same places.
- **FR-015**: Bronze MUST stay insert-only. This story MUST NOT update or delete bronze rows and MUST NOT change the event contract.

**Ingestion freshness SLI and alert signal (P3)**

- **FR-016**: A read-only view in a new schema `ops` MUST report, from the database clock: (a) seconds since the last bronze insert, (b) events per minute inserted into bronze over the last 60 s, and (c) the real rejection rate over the last 60 s, defined as contract rejections ÷ (accepted events + contract rejections), excluding duplicates; and (d) the number of duplicates (rejections with reason `duplicate_event`) over the last 60 s, reported on its own. The 60 s window matches the constitution's "rejection above 5 % within 1 min" alert condition.
- **FR-017**: The view MUST report "not computable" (not 0 and not a made-up value) when its inputs are empty: unknown freshness with an empty bronze, unknown rejection rate with an empty denominator.
- **FR-018**: The view MUST only read. It MUST NOT write, create derived storage, or change bronze, silver or gold.
- **FR-019**: The new schema `ops` MUST be recorded with a one-line addendum to ADR-0001 in the same style as the `config` addendum. No other line of the ADR changes.
- **FR-020**: The `ingestion` service MUST have a healthcheck that reports `healthy` when seconds since the last bronze insert is at most the freshness threshold, and `unhealthy` otherwise. The threshold MUST be configurable through an environment variable and default to 15 s.
- **FR-021**: The healthcheck MUST report `unhealthy` when the database is unreachable or any check fails, MUST print no connection details, and MUST follow the pattern of the `refresh` healthcheck (exit 0 healthy, exit 1 unhealthy).
- **FR-022**: The service MUST turn `unhealthy` within the freshness threshold plus one healthcheck interval after the feed stops, and MUST return to `healthy` without manual action once inserts resume. The healthcheck interval, retries and start grace period are set so that this holds and are documented in `docker-compose.yml`.
- **FR-023**: The ingestion healthcheck MUST NOT make ingestion depend on the API, the console or `refresh`. Ingestion keeps its isolation (Principle III).

**Documentation and acceptance**

- **FR-024**: A blameless post-mortem MUST be added under `docs/ops/` with these sections: summary, timeline, impact (with the drill numbers), root causes, what went well, actions (each action mapped to a user story of this feature) and lessons.
- **FR-025**: A runbook for "ingestion or refresh unhealthy" MUST be added under `docs/ops/`. It MUST cover how to see the service state, how to read the freshness view, the recovery steps for a database outage, a stopped feed, a crashing ingestion and a stalled `refresh`, and when to escalate.
- **FR-026**: The report MUST define the SLI precisely and MUST propose an SLO target and an error budget as text, marked as a proposal.
- **FR-027**: The drill MUST be rerun after the fix with the same faults as the baseline and a before/after table MUST be recorded in the repository documentation.

**Test-first**

- **FR-028**: For every requirement above that changes behavior, a failing test or a failing check MUST exist before the implementation is written. New tests count toward the 80 % coverage gate and MUST NOT lower it.

### Key Entities *(include if feature involves data)*

- **CI workflow run**: one execution per pull request or push to `main`, made of three independent jobs (tests with coverage gate, contract fixtures, compose build). Result: green or red.
- **Retry attempt**: one failed attempt to store an input line, with its attempt number, wait and generic reason, emitted as one structured log line. Not stored in the database.
- **Duplicate tally**: count of events discarded because `(source, event_id)` already exists, kept apart from the rejection count. Stored as rows of `bronze.rejections` with reason `duplicate_event` (no new table); counted separately from contract rejections.
- **Ingestion health view (`ops`)**: read-only, computed on read: seconds since last bronze insert, events per minute, real rejection rate over 60 s, duplicates over 60 s. Owner: data.
- **Ingestion freshness SLI**: the proportion of time ingestion is fresh, defined below. A document concept, not a stored object.
- **Drill report**: before/after table of the baseline numbers, post-mortem and runbook under `docs/ops/`.

#### Freshness SLI (definition for the report)

- **Measurement**: at every healthcheck probe, the service is *fresh* if seconds since the last bronze insert is at most the threshold (15 s by default) and *stale* otherwise. The probe interval is the one documented in the compose file.
- **SLI**: fresh probes ÷ total probes, over a rolling window, counted only while a live feed is expected.
- **Proposed SLO and error budget** (proposal for the report, not an adopted norm; to be reviewed by the team and, if adopted, added to the constitution through a separate amendment PR): an SLO target and its error budget in minutes per window are proposed in the report, derived from the measured drill rerun, not from numbers invented in advance.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A pull request with a harmless change shows all three jobs green. A pull request with one deliberately failing test shows the test job red, and with branch protection configured as documented the merge is blocked. After reverting the failing test, the run is green again.
- **SC-002**: The test job reproduces the local CI-ready command result: same test count and coverage above 80 %. Lowering coverage below 80 % on a throwaway branch turns the job red.
- **SC-003**: An invalid fixture or a fixture without a schema, added on a throwaway branch, turns the contract job red. The 18 current fixtures pass.
- **SC-004**: On a live stack, stopping `db` for about 30 s and starting it again gives: zero ingestion process exits, zero simulator restarts, bronze row count increasing again after recovery, no gap and no restart-from-zero in the event sequence, and zero duplicates attributable to a replay from the start.
- **SC-005**: During the same outage, the log contains one structured JSON line per retry and none of them contains a credential or a connection string.
- **SC-006**: After the drill, the rejection count excludes duplicates: a stream with N invalid events and M duplicates reports N rejections and M duplicates, and a real rejection rate of N ÷ (accepted + N). The M duplicates remain stored in `bronze.rejections` with reason `duplicate_event` and are excluded from N in logs, summary and the `ops` health view.
- **SC-007**: On a live stack, the health view reports freshness below 15 s, a positive events-per-minute value and a computable rejection rate.
- **SC-008**: Stopping the simulator feed turns the `ingestion` service `unhealthy` within 15 s plus one healthcheck interval, measured by timestamped `docker compose ps` or `docker inspect` readings. Resuming the feed returns it to `healthy` within one healthcheck interval plus the time of the first insert.
- **SC-009**: The drill rerun table shows, against the baseline: ingestion does not die on F2 and F3, the lag after F2 returns to below the 15 s freshness threshold (baseline 125 s), the F3 lag is reported (baseline 204 s), the false rejection rate drops from 65 % to the real rate of the run, and at least one `unhealthy` transition is observed where the baseline had no alert. The rerun records the actual numbers, and any value that does not improve is reported as such.
- **SC-010**: The post-mortem, the runbook and the SLI/SLO text exist under `docs/ops/` and contain every section named in FR-024 to FR-026. A person who has not seen the drill can follow the runbook to see freshness and recover a stopped feed on a live stack.
- **SC-011**: The full test suite stays green with coverage above 80 % after the change, and the `git diff` of ADR-0001 is exactly one added line.

## Assumptions

- The repository is hosted on GitHub and the team can run GitHub Actions on it. Setting branch protection requires a repository admin and is done by hand after the workflow exists.
- The simulator and ingestion keep running as one `simulator | ingestion` pipe in one service, as in story 001. Backpressure through the pipe holds events while ingestion waits, so no event is dropped during an outage.
- "Event sequence has no gap" is checked on the bronze ids and on the simulator's deterministic event order for a fixed seed; the plan defines the exact check.
- A dedup on `(source, event_id)` makes retrying a line safe even if it was committed just before the failure.
- Default retry values and the healthcheck interval, retries and start grace period are chosen in the plan. They must satisfy FR-010 and FR-022 and be written in `.env.example` and `docker-compose.yml`.
- The 60 s window of the view is aligned with the constitution's alert condition (rejection above 5 % within 1 min). Raising an alert on it is out of scope; this story only exposes the signal.
- The ingestion healthcheck reads the database, so a database outage also shows as `unhealthy` ingestion. That is accepted: the runbook distinguishes the two by checking `db` first.
- The `refresh` healthcheck from story 002 is not changed. The runbook covers it for diagnosis only.
- Only the numbers given in the drill baseline and the 15 s and 60 s values above are fixed. Other numbers (retry defaults, SLO target) are decided in the plan or proposed in the report from measurements.
- Out of scope (Evolution): simulator resuming mid-day, a persistent buffer or broker, OpenTelemetry and metrics dashboards, Dependabot and secret scanning configuration, deploy or CD to a server, lint and security CI jobs (ruff, bandit, pip-audit; owned by the DevOps owner), scenario injectors C1/C2/C5/D1 (next story), and any backend or frontend change.
