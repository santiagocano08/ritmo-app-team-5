# Implementation Plan: Scenario Injectors, Hold Loop and Effect Table

**Branch**: `feature/004-scenario-injectors` (stacked on `feature/003-ops-ci-reliability`, PR #9 → `feature/002-silver-gold-baselines` → `feature/001-base-simulator`; none merged) | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md) (approved, commit `d7d674f`, Clarifications included: Q1 = A, Q2 = C, Q3 = B)

**Input**: Feature specification from `/specs/004-scenario-injectors/spec.md`

**Note**: `setup-plan.sh` was not executable (permission denied), so it was run with `bash`. It reported
the branch as `004-scenario-injectors`; the git branch is `feature/004-scenario-injectors`.
`.specify/extensions.yml` does not exist, so no before-plan or after-plan hooks apply.

## Summary

Make the demo scenarios happen on demand and close the hold loop, in data only. (1) The simulator
accepts a JSON scenario file (env or CLI) with four injector families: C1 bunching (a long dwell of
one bus at one stop), C2 gap (a late departure from P-883), C5 breakdown (the bus stops and an
`incident_report` is emitted) and D1 (silence of one bus, duplicate events) as a **channel layer**
between the world and the output. Each fired injector appends one record to a **hidden truth** sink
that no pipeline code reads. (2) The simulator polls `bronze.events` **read-only** from a daemon thread
for backend `decision` rows, maps `rec_id` to a **seeded recommendation**, and makes the target bus dwell
(total dwell = requested hold, at most 90 s) unless a seeded draw says the driver does not comply
(default 10 %). Data observes the real dwell in silver and marks the instruction `executed` (within
±15 s) or `not_executed` in a read-only gold table. (3) Data adds the `incident` gold object and the
`recommendation_effect` gold object, rebuilt each cycle from the stored snapshots and bronze, with the
result rule of ADR-0003 gate decision 6. (4) One command runs the ~8 minute demo timeline on a
dedicated compose project.

**Approach** (from [research.md](research.md)): no new service, no new dependency, no change under
`contracts/` or in any ADR. Everything new in the simulator is gated by "a scenario or a hold board is
present", so with nothing configured the engine runs the same code and the output keeps the baseline
hashes measured at planning time (seed 42, 3600 s: `51a5e9b3…39e1`; seed 7: `6bd20707…0132`). New data
objects reuse the 002 pattern (JSONB doc validated by a model generated from the read schema, lineage
columns, deterministic rebuild in the cycle transaction). Four phases, each ending green and
committable on its own: injectors plus incident view, hold loop, effect table, demo script.

## Technical Context

**Language/Version**: Python 3.12+ (unchanged).

**Primary Dependencies**: unchanged. `psycopg` 3 (poller, pipeline), Pydantic V2 (scenario file
validation and generated read models), stdlib `threading`, `hashlib`, `json`. `jsonschema` (dev extra)
for schema checks in tests. No `pyproject.toml` or `uv.lock` change (research R13). `datamodel-code-generator`
(dev extra, already used) generates three more read models: `incident`, `recommendation`,
`recommendation_effect`.

**Storage**: PostgreSQL 16 only. One new init script `007_scenarios.sql`: `config.effect_settings`
(one row), `config.seed_recommendation`, `gold.incident`, `gold.instruction_status`,
`gold.recommendation_effect`. Bronze stays insert-only and untouched. The scenario truth is a JSON-lines
file or stderr, outside the database (research R2).

**Testing**: pytest + pytest-cov, tests first, throwaway database per module (002 R10). Pure unit tests
for the config validator, injectors, channel layer, truth sink, hold rules, compliance draw and effect
rule; integration tests for the gold objects and the poller against a real database; one live check
(`-m live`, host only, own compose project) for the demo. Gate 2: coverage above 80 % through the
unchanged CI-ready command. Baseline at planning (003 `verification.md`): 434 passed, 4 skipped, coverage 91.97 %.

**Target Platform**: Linux containers via `docker-compose` (existing `db`, `ingestion`, `api`,
`refresh`, `tests`).

**Project Type**: data story inside the existing single Python project: simulator extension, three
pipeline steps, one init script, one script folder for the demo.

**Performance Goals**: measured, not assumed. The three new cycle steps read a few rows (decisions,
incidents, two snapshots per hold); the cycle time is measured before and after Phase 3 against the
002 figure and must stay inside the 5 s refresh interval (research R12). The poller issues one query
per `SIM_HOLD_POLL_S` (1 s default). No throughput SLO (turn 3).

**Constraints**: PostgreSQL only; no new service (a thread in the existing `ingestion` container's
simulator process is the only new runtime piece); bronze insert-only; no change to `contracts/` or to
any ADR line; no new event type or field; no wall clock or unseeded randomness inside injectors; the
poller never blocks the event stream; config via env with safe defaults and no scenario enabled by
default; no secrets in code, tests or logs; ingestion isolation (Principle III) asserted by tests.

**Scale/Scope**: 1 corridor, 5 + 2 buses, 3,851 events and 1,439,431 bytes per simulated hour (seed 42,
measured); about 2.57 buses on the corridor at any time (research R1); a demo run of about 2,700
simulated seconds (about 2,900 events at the measured 3,851 per hour); at most a few dozen scenario records and a handful of holds.

## Key decisions (numbers and where they are justified)

| Decision | Value | Research |
|---|---|---|
| Scenario input | one JSON file, `SIM_SCENARIO_FILE` or `--scenario-file`; Pydantic V2 discriminated union on `type`; `extra="forbid"`; nothing enabled when unset | R1 |
| Base unchanged | hooks default to `None`; golden hashes pinned in a test before any engine edit: seed 42 / 3600 s = `51a5e9b3063667320a6e66cab6293f84197822378783724dd664b6f6865d39e1` (3,851 lines, 1,439,431 B), seed 7 = `6bd20707…b0132` | R1 |
| C1 | extra dwell of one bus at one stop, `300 < extra_s ≤ 600` (more than half of the 600 s plan, so the follower falls below 300 s) | R1 |
| C2 | late departure from P-883, `300 < delay_s ≤ 600`, gap above 900 s | R1 |
| C5 | bus halts while `driving`, `0 < duration_s ≤ 300` (the base minimum headway is 300 s, so the follower cannot reach the stopped bus); `incident_report` with `duration_min = duration_s / 60` | R1 |
| D1 | channel layer after envelope creation: silence of one bus (any positive duration; demo 300 s), duplicates (`count` 1 to 1,000) | R3 |
| Truth | JSON lines to `SIM_TRUTH_PATH` or stderr; written when an injector fires; never read by `src/data/{rules,pipeline,refresh,ingestion}`, guarded by a static test | R2 |
| Hold intake | daemon thread, `SIM_HOLD_POLL_S` = 1 s wall (5 simulated seconds at pace 1), read-only session, 2 s connect and statement timeouts, in-memory board; DB down means no new holds, never a blocked stream | R4 |
| Order identity | `rec_id` → seeded recommendation (`config.seed_recommendation` for data, the same JSON file for the simulator); order valid for arrivals strictly after `decided_at_sim` and up to `expires_ts` | R4, R5 |
| Compliance | `SHA-256("{seed}\|hold\|{rec_id}")` mapped to [0, 1); non-compliant when below `SIM_HOLD_NONCOMPLIANCE` (default 0.10); main RNG untouched | R4 |
| Hold semantics | total dwell: departure no earlier than arrival + D, D ≤ 90 s; a natural dwell longer than D is kept | R4 |
| Executed | `executed` when the observed dwell is within ±15 s of D, else `not_executed`; constants in `rules/holds.py` | R5 |
| Incident object | `gold.incident`, one row per incident per snapshot, `duration_s = duration_min × 60`, `until` null while active | R6 |
| Effect object | rebuilt each cycle from stored snapshots: before = last snapshot at or before the hold start, after = first snapshot at or after start + `horizon_s`; EWT observed = corridor `service_metric.ewt_s` clamped at 0; threshold 30 s in `config.effect_settings` | R7 |
| Rules version | `RULES_VERSION` 1.0.0 → 1.1.0 (new derivations; old objects unchanged); snapshot ids re-key | R8 |
| Demo | `scripts/demo/run_demo.sh`: project `pulsoflota-demo`, seed 42, `SIM_PACE_S=0.9` (2,700 simulated s = 486 s ≈ 8.1 min), stand-in approval script keyed to simulated time | R9 |

## Constitution Check

*GATE: evaluated before Phase 0; re-checked after Phase 1 design (below).*

Constitution v1.1.0; turn 1 active (`docs/turns-ritmo.md` §3). The five Core Principles apply; other
norms only as adopted in §3.2.

| Principle | Status | Evidence |
|---|---|---|
| **I. Risk-First Order** | PASS | Disciplined lane, turn-1 Level 1 risk (data integrity): scenarios and the effect measurement are what lets the team show that duplicated, missing or injected data does not contaminate the metric. Nothing from the adaptive lane (no endpoint, no frontend, no decision engine). C3, C4, stochastic mode and reserve dispatch stay out. |
| **II. Contract-First & Data Ownership** | PASS | Interfaces are written before code in [contracts/](contracts/README.md): scenario file, truth record, hold command door and seed shape, gold read access. Every object has an owner ([data-model.md](data-model.md)). `incident` and `recommendation_effect` rows are built through models generated from the existing read schemas; the instruction status is a typed table whose `status` and `ts_by_status` are checked against `instruction.schema.json`. Nothing under `contracts/` and no ADR line changes. |
| **III. Isolated Ingestion & Deterministic Real Time** | PASS | The poller is a thread inside the existing simulator process; it reads, never writes, and a failure only stops new holds. Ingestion depends on `db` only, as before. Injectors use no wall clock and no unseeded randomness. No LLM and no third party on the path. A test stops `api`, `refresh` and the poller and shows bronze still growing. |
| **IV. Unbreakable Human Gate** | PASS (enforced from the data side) | A hold order exists only for a bronze `decision` with `action = "apply"` from `source = "backend"`. `discard`, no decision, unknown `rec_id`, expired window: the world is unchanged (tested). Data reports `executed` / `not_executed` and never writes a decision or a confirmation. The demo stand-in script only plays the backend's role of writing the `decision` row after a person chooses to run it (open question 1). |
| **V. Test-First & Automated Gates** | PASS | Each phase starts with failing tests ([quickstart.md](quickstart.md)). The golden-hash test is written and run green before the first engine edit. Coverage stays above 80 % through the unchanged CI-ready command; pure rules aim at near 100 % (CODEOWNERS review applies to `src/data/rules/`). |

**Turn-1 adopted norms (§3.2)**: RNF-3.2.1 / 3.2.2 (compose, ingestion isolated): PASS, no service
added. RNF-3.3.1 (boundary validation of 100 % of packets): injected events pass the same envelope
validation as any other (SC-002); backend `decision` rows are written directly to bronze by the backend,
as the 002 builders already do (`insert_backend_commands`), because the ingestion boundary lists only the
six turn-1 event types. RF-2.3 (approval before action): PASS. Gate 1 (schema validation only): PASS,
scenario file, seed file and gold objects are schema-validated. Gate 2: PASS. Gate 4: the explicit
approval step is exercised by the demo. Security baseline: parameterized SQL only, no secrets in the
repository or in logs, JSON log lines without stack traces.

**Deferred norms (Evolution, not blocking)**: Redis, PostGIS, 1,000 events/s, SAST/SCA, RBAC, HMAC,
secret manager, route diversion (US-03). Story-level evolution: C3 and C4, stochastic mode, reserve
dispatch, adjust-departure and short-turn, the real recommendation door, the decision engine, any
endpoint or frontend, direction 2 (spec FR-032, research R11).

**Post-design re-check**: the design adds no deferred norm as a requirement and weakens no principle.
Points checked explicitly:

1. `config` gains two tables (`effect_settings`, `seed_recommendation`). The ADR-0001 addendum allows
   "settings and reference data only"; the seed table is declared demo and test reference data, to be
   removed when the recommendation door exists. No ADR line changes.
2. `RULES_VERSION` moves to 1.1.0. This changes snapshot ids (they hash the version) but no existing
   gold content. One existing test pins `"1.0.0"` and is updated in the same commit. Changes under
   `src/data/rules/` need the data owner's review (CODEOWNERS).
3. The truth sink is a file or stderr, outside every schema the pipeline reads, which meets the FR-010
   guarantee without a new store.
4. The instruction status published by data has no `inst_id` or `text`, which the backend owns. It is
   keyed by `rec_id` (open question 3).

**No violations; Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/004-scenario-injectors/
├── spec.md                          # approved
├── plan.md                          # this file
├── research.md                      # Phase 0 output (R1–R14)
├── data-model.md                    # Phase 1 output
├── quickstart.md                    # Phase 1 output (per-phase validation, demo run)
├── contracts/                       # Phase 1 output (feature-local interface notes)
│   ├── README.md                    # index + new environment variables
│   ├── scenario-config.md           # scenario file, truth record, CLI
│   ├── hold-loop.md                 # command door, seed shape, order rules
│   └── gold-read-access.md          # incident, instruction_status, recommendation_effect
├── checklists/requirements.md       # exists
├── tasks.md                         # /speckit.tasks (not created here)
└── verification.md                  # written during implementation (evidence per phase)
```

### Source code and repository files (to be touched)

New:

```text
src/data/simulator/scenarios/__init__.py
src/data/simulator/scenarios/config.py        # Phase 1: Pydantic models, loader, validation
src/data/simulator/scenarios/injectors.py     # Phase 1: C1, C2, C5 world hooks; Phase 2: hold application
src/data/simulator/scenarios/channel.py       # Phase 1: D1 silence and duplicates
src/data/simulator/scenarios/truth.py         # Phase 1: truth sink (file or stderr)
src/data/simulator/scenarios/holds.py         # Phase 2: HoldBoard, Order, poller thread, compliance draw
src/data/simulator/scenarios/demo.json        # Phase 4: the demo timeline (scenario file)
src/data/seeds/recommendations.json           # Phase 2: demo seed recommendations (recommendation schema)
src/data/rules/holds.py                       # Phase 2: constants, visit matching, observation rule (pure)
src/data/rules/effect.py                      # Phase 3: result rule (pure)
src/data/rules/sql/hold_orders.sql            # Phase 2: decisions with decided_at_sim (shared by simulator and pipeline)
src/data/pipeline/incidents.py                # Phase 1: gold.incident per snapshot
src/data/pipeline/holds.py                    # Phase 2: gold.instruction_status
src/data/pipeline/effects.py                  # Phase 3: gold.recommendation_effect
src/data/pipeline/seeds.py                    # Phase 2: load seed file into config.seed_recommendation
src/data/db/init/007_scenarios.sql            # Phase 1 (incident), Phase 2, Phase 3 sections
src/pulsoflota/models/read/incident.py                 # generated, Phase 1
src/pulsoflota/models/read/recommendation.py           # generated, Phase 2
src/pulsoflota/models/read/recommendation_effect.py    # generated, Phase 3
scripts/demo/run_demo.sh                      # Phase 4
scripts/demo/approve_hold.py                  # Phase 4 (stand-in for the backend, piped into the container)
scripts/demo/README.md                        # Phase 4
specs/004-scenario-injectors/verification.md  # evidence
```

New tests (all red first):

```text
src/data/tests/unit/test_simulator_golden_hash.py       # Phase 1, written and green BEFORE the engine edit
src/data/tests/unit/test_scenario_config.py             # Phase 1
src/data/tests/unit/test_scenario_injectors.py          # Phase 1 (C1, C2, C5) and Phase 2 (holds in the engine)
src/data/tests/unit/test_scenario_channel.py            # Phase 1 (D1)
src/data/tests/unit/test_scenario_truth.py              # Phase 1
src/data/tests/unit/test_no_truth_reads.py              # Phase 1 (static guard)
src/data/tests/unit/test_hold_rules.py                  # Phase 2
src/data/tests/unit/test_hold_compliance.py             # Phase 2
src/data/tests/unit/test_hold_board.py                  # Phase 2 (poller behavior with a fake connection)
src/data/tests/unit/test_effect_rule.py                 # Phase 3
src/data/tests/integration/test_scenarios_gold.py       # Phase 1 (C1, C2, C5, D1 against fixtures and truth)
src/data/tests/integration/test_incident_gold.py        # Phase 1
src/data/tests/integration/test_hold_poller.py          # Phase 2 (real database, read-only session)
src/data/tests/integration/test_instruction_status.py   # Phase 2
src/data/tests/integration/test_hold_loop.py            # Phase 2 (simulator + crafted decisions + pipeline)
src/data/tests/integration/test_recommendation_effect.py # Phase 3
src/data/tests/integration/test_loop_isolation.py       # Phase 2 (Principle III)
src/data/tests/integration/test_demo_scenario.py        # Phase 4 (offline replay of demo.json at pace 0, tolerance on times)
src/data/tests/integration/test_demo_live.py            # Phase 4 (-m live, host only)
src/data/tests/fixtures/scenarios/*.json                # scenario files and seed recommendations for tests
tests/unit/test_demo_script.py                          # Phase 4 (structure of the script, no secrets)
```

Modified:

```text
src/data/simulator/engine.py                  # optional `hooks` and `holds` arguments; guarded calls only
src/data/simulator/main.py                    # --scenario-file, --truth-path, --holds; env defaults
src/data/rules/__init__.py                    # RULES_VERSION = "1.1.0"
src/data/pipeline/cycle.py                    # three steps after build_snapshot, same transaction
src/data/refresh/run.py                       # load seeds next to load_reference
src/data/pipeline/compute.py                  # load seeds next to load_reference
src/pulsoflota/config.py                      # getters for the new variables
docker-compose.yml                            # ingestion: new env vars (defaults leave everything off)
.env.example                                  # new variables with defaults
Makefile                                      # READ_SCHEMAS gains the three schemas
.gitignore                                    # demo-out/
src/data/tests/unit/test_rules_version.py     # expects 1.1.0
tests/unit/test_generated_read_models.py      # NAMES gains the three modules
tests/unit/test_env_example.py                # new variables
src/data/tests/unit/test_no_bronze_writes.py  # scan list unchanged; new files fall under the existing folders
src/data/db/init/ tests (schema init)         # new tables expected
```

Not touched: `contracts/`, `docs/adr/`, `src/data/ingestion/`, `Dockerfile`, `pyproject.toml`,
`uv.lock`, `.github/`, `src/data/rules/sql/silver_*.sql` and the existing gold SQL.

**Structure Decision**: keep the existing layout. The simulator extension lives in a sub-package
`src/data/simulator/scenarios/` so `engine.py` and `model.py` change as little as possible. Pure
rules go to `src/data/rules/` (CODEOWNERS), orchestration to `src/data/pipeline/`, DDL to
`src/data/db/init/`. Tests mirror 002 and 003 (`src/data/tests/unit`, `integration`, `fixtures`). The
`tests` service already mounts `scripts/`, `contracts/`, `data/` and `specs/`, so no compose mount is
added.

## Phases

Each phase: tests first (they must fail for the stated reason), implementation, the Andon check (the
CI-ready command) green, then the human commits. Phase *n+1* needs Phase *n* but each ends in a state
that can be committed and demonstrated alone. Time estimates are for the agent and sum to the 4–5 hour
budget (research R14).

### Phase 1 — Injectors and incident view (US1, P1) — about 1 h 45 min

Goal: FR-001 to FR-011, FR-021, FR-027, FR-028 (part), SC-001 to SC-006.

1. **Golden hash first**: add `test_simulator_golden_hash.py` with the two baseline hashes; run it
   green on the untouched engine.
2. Tests red: scenario file validation (each invalid case of AC10), injector behavior with a fake step
   loop and with `run()` (C1, C2, C5 effects at the expected steps), channel layer (silence, duplicates),
   truth sink, static guard that no pipeline code reads the truth, incident gold, shape tests against the
   fixtures `c1_bunching`, `c2_gap`, `c5_breakdown`, `d1_source_outage` (counts and states, not byte equality).
3. Implement `scenarios/{config,injectors,channel,truth}.py`, the guarded hooks in `engine.py`, the CLI
   and env wiring in `main.py`, `config.py` getters, `007_scenarios.sql` (incident table),
   `pipeline/incidents.py`, the cycle step, the generated `incident` model, `RULES_VERSION` 1.1.0.
4. Green: golden hashes unchanged, 002 and 003 acceptance tests unchanged, new tests green, coverage
   above 80 %.

Commit point: scenarios on demand plus the incident object. The hold loop and the effect table are not needed.

### Phase 2 — Hold loop (US2, P2) — about 1 h 30 min

Goal: FR-012 to FR-020, FR-028, SC-007, SC-008, SC-011, SC-012.

1. Tests red: hold rules (matching, ±15 s, cap 90, conflict, breakdown, expiry), compliance draw
   (reproducible, share near 10 % over the batch size chosen in R4), board and poller with a fake
   connection (DB down, unknown `rec_id`, duplicate decision, `discard`), engine holds (total dwell,
   non-compliance, no order = baseline hash), instruction status in the database, loop isolation.
2. Implement `rules/holds.py`, `rules/sql/hold_orders.sql`, `scenarios/holds.py`, hold application in
   `injectors.py`/`engine.py`, `pipeline/seeds.py`, `pipeline/holds.py`, the cycle step, the seed file,
   the generated `recommendation` model, the `007` sections for `config.seed_recommendation` and
   `gold.instruction_status`.
3. Green: baseline hashes unchanged with `--holds` on and an empty bronze; crafted decisions give
   `executed` and `not_executed` as specified; stopping the poller, `api` and `refresh` leaves bronze growing.

Commit point: approved holds execute and are observed. The effect table is not needed.

### Phase 3 — Recommendation effect table (US3, P3) — about 45 min

Goal: FR-022 to FR-027, SC-009, SC-012 (effect rows).

1. Tests red: the result rule at its boundaries (29 s, 30 s, the `c1_bunching` fixture values, no
   improvement, `no_data`), the pipeline step with crafted snapshots (window open, window closed, not
   executed, missing snapshot, same bronze recomputed), schema validation of every row.
2. Implement `rules/effect.py`, `pipeline/effects.py`, the cycle step, the generated
   `recommendation_effect` model, the `007` sections for `config.effect_settings` and
   `gold.recommendation_effect`.
3. Green: all rows validate against `recommendation_effect.schema.json`; reruns leave rows unchanged;
   cycle time measured and recorded.

Commit point: effect rows. Demo script not needed.

### Phase 4 — Demo script (US1 to US3 together, SC-010) — about 1 h

1. Dry runs fix the timeline numbers (research R9 lists the base times measured at planning and the
   candidate timeline). Tests red: structure of the script (own compose project, ports, no secrets, no
   `down -v` outside its own project), the demo scenario file validates, an offline replay test of the
   demo scenario file at pace 0 asserts the gold states at the chosen simulated times with tolerance.
2. Implement `demo.json`, `scripts/demo/run_demo.sh`, `approve_hold.py`, `README.md`, the live test.
3. Green: one live run on project `pulsoflota-demo` of about 8 minutes shows D1, C1 with its hold and
   effect row, C5 with the active incident, and the close; evidence in `verification.md`. The effect
   `result` is recorded as the rule yields it (SC-010).

If time runs short, cut in this order: the live test (keep the offline replay), the C2 live check
(keep the unit and integration tests), the README wording. Never cut the golden hash, the human-gate
tests or the isolation test.

## Risks (summary; detail in research)

1. **Few buses on the corridor.** A trip lasts about 1,540 s and buses start 600 s apart, so 2 or 3
   buses are on the corridor at a time (measured, seed 42). The fixture number "4 of 5 in service" cannot
   occur; tests assert the semantics (broken-down bus excluded) and the demo C5 shows the breakdown and
   incident only (R1, R9).
2. **Injection changes the RNG stream.** After the first world injection, later events differ from the
   base case. Same configuration still gives the same bytes. Demo times are fixed by dry run (R9).
3. **Effect result may not be `worked`.** A hold moves a headway by at most 90 s; the rule compares the
   seeded 55 s expected saving with the observed corridor EWT. The result is reported as it comes (R7).
4. **Total-dwell semantics misread natural dwell.** A natural dwell within ±15 s of D counts as
   `executed` even when the driver did not comply. The demo stop has a natural dwell near 10–15 s (R5).
5. **Live race of the poller.** A decision approved within one poll interval before the bus arrives can
   miss the bus (5 simulated seconds at pace 1). It can only turn an applicable order into
   `not_executed`, never the reverse (R4).
6. **Existing volumes lack `007`.** Init scripts run on a fresh volume only (003 R14); the demo uses a
   fresh project volume and the runbook gets one line (R8).
7. **A dispatcher incident with `duration_min = null` breaks the silver rebuild** (`end_ts` is NOT NULL).
   Pre-existing from 002; this story's scripted incidents always carry a duration. Recorded, not fixed (R6).
8. **CODEOWNERS.** `src/data/rules/` changes (new files and the version bump) need the data owner's review.

## Open questions

1. **[NEEDS CLARIFICATION] Who approves the demo hold on 2026-11-24?** The plan uses a stand-in script
   that writes the `decision` row at a fixed simulated time (reproducible). If the real backend and
   console are ready, the same data path is used with no change; only the script step is skipped. Confirm
   which one the demo uses.
2. **[NEEDS CLARIFICATION] "Headway after at the target stop" (FR-023).** After the horizon (600 s) the
   held bus has left the stop, so the plan measures the held bus's `headway_ahead_s` in the first snapshot at
   or after start + `horizon_s`, and "before" in the last snapshot at or before the hold start (the bus is
   at the stop). It also clamps `ewt_observed_s` at 0 because the schema minimum is 0 and the corridor EWT can
   be negative. The data owner should confirm both readings.
3. **[NEEDS CLARIFICATION] Instruction status without `inst_id` and `text`.** Data publishes
   `gold.instruction_status` keyed by `rec_id` (`bus_id`, `status`, `ts_by_status`); the backend owns
   `inst_id` and `text`. The backend owner should confirm that joining by `rec_id` is acceptable.

## Complexity Tracking

Empty: no Constitution Check violation. The three new `config`/`gold` table groups, the poller thread and
the demo script are each required by a spec item (FR-018, FR-017, SC-010) and none adds a service.
