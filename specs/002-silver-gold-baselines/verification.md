# Verification — 002-silver-gold-baselines

Evidence per phase. Times are UTC. Branch `feature/002-silver-gold-baselines` (base commit `122afc4`).
Nothing is committed; the human reviews and commits.

## Phase 0 — Foundations (T001–T024, T075)

| | |
|---|---|
| Start | 2026-11-19 11:51:25Z |
| End (full-suite run green) | 2026-11-19 12:01:32Z |
| Elapsed | about 10 min of agent time |
| Tasks | T001–T024 and T075, all marked `[x]` in `tasks.md` |

### Phase 0 findings (T005)

Command (after the T004 fix, image rebuilt):
`docker compose --profile tools run --build --rm tests`

Result: 96 passed, 3 failed, 3 skipped. **No 001 simulator test failed because of the new spacing**:
`test_simulator_travel_time.py` (2), `test_simulator_capacity.py` (5) and `test_simulator_determinism.py` (6)
all passed unchanged. So T006 had nothing to update: no 001 test was edited and no assertion carries
`# R14: new spacing`. The 3 failures were the new `tests/unit/test_env_example.py` tests: the `tests`
service did not mount `docker-compose.yml` or `.env.example` (see Rework). The 3 skipped tests are the
isolation tests that need the docker CLI and only run from the host.

### R14 numbers (T007)

Commands: `uv run pytest tests/unit/test_simulator_base_headway.py` plus the 001 unit and contract suites
(all green), then a recount with `run(seed, 7200)` and `run(42, 3600)`.

| Check | Before the fix (T001 failure output) | After the fix |
|---|---|---|
| P-883 gaps, seed 42, 2 h | median 300 s, minimum 10 s | 12 arrivals, median 600 s, minimum 600 s, maximum 600 s |
| P-883 gaps, seed 7, 2 h | median 320 s, minimum 15 s | 12 arrivals, median 600 s, minimum 600 s, maximum 600 s |
| Events in the 1-hour seed-42 run | 3,986 | **3,851** |

### Commands and results (T024)

| Command | Result |
|---|---|
| `make generate-read` run twice, outputs compared | identical (the directory is new and untracked, so `git diff --exit-code` alone proves nothing; a copy was compared with `diff -r`) |
| `tests/unit/test_simulator_base_headway.py` | 6 passed |
| `tests/unit/test_simulator_travel_time.py`, `..._capacity.py`, `..._determinism.py` (001, unchanged) | 2, 5, 6 passed |
| `tests/contract/test_read_fixtures.py` | 33 passed (18 fixtures, 8 read schemas, notify schema, T075 consistency check on 5 `corridor_now` fixtures) |
| `tests/unit/test_env_example.py` | 5 passed |
| `tests/unit/test_generated_read_models.py` | 6 passed |
| `tests/unit/test_rules_version.py` | 5 passed |
| `tests/integration/test_schema_init.py` | 17 passed |
| `tests/integration/test_db_fixture.py` | 5 passed |
| `tests/integration/test_bronze_builders.py` | 18 passed |
| `git diff --stat contracts/` | one file: `contracts/read/fixtures/c1_bunching/corridor_now.json`, 1 insertion, 1 deletion (`headway_ahead_s` 752 → 960) |
| `grep -n config docs/adr/0001-...md` / `git diff --numstat docs/adr` | addendum on line 121; 2 lines added (the addendum and one blank separator line), 0 removed |

### Whole suite (Andon check, end of phase)

| Command | Result |
|---|---|
| `docker compose --profile tools run --rm tests` (the CI-ready command) | exit 0; **183 passed, 0 failed, 3 skipped**; coverage 90.27 % (gate 80 %) |
| `uv run pytest -q` on the host (includes the 3 docker-CLI tests) | **186 passed, 0 failed**; coverage 90.27 % |
| Baseline before Phase 0 (host) | 91 passed |

Throwaway databases: none left on the server after the runs (`pg_database` lists only `postgres`,
`pulsoflota`, `template0`, `template1`).

### Rework (tests that failed for an unexpected reason and were fixed)

| # | Test | Cause | Fix |
|---|---|---|---|
| 1 | `test_planned_headway_setting_changes_start_spacing` | My test ran 1,500 s, so only 3 arrivals (2 gaps) existed for a 3-gap assertion | Duration 2,400 s. Test bug, not a product bug. |
| 2 | `test_env_example.py` (3 tests), in the container only | The `tests` service did not mount `docker-compose.yml` and `.env.example` | Added the read-only mounts (see below). |
| 3 | `test_generated_read_models.py::test_normal_fixture_round_trips` | My helper picked the first class in the generated module, not the top-level `<Title>V100` model | Helper selects the `V100` class. Test bug. |
| 4 | `test_rules_version.py::test_slow_and_live_markers_registered`, in the container only | The probe file was written under `tests/`, which is a read-only mount | The probe is written to `tmp_path`. Found by the end-of-phase full run (Andon): it stopped there, was fixed, and the whole suite was rerun green. |

Rework count: 4 (2 and 4 only show up inside the container; 1 and 3 are test-authoring mistakes).

### Decisions taken during the phase

- `tests` service mounts, beyond the `./db` that T015 names: `./specs`, `./docs/adr`, `./docker-compose.yml`,
  `./.env.example` (all read-only). T002, T008 and T016 read those files and they are not in the image.
- The image bakes `src/`, so `docker compose --profile tools run --rm tests` needs the image built from the
  current tree. Run `docker compose --profile tools build tests` first (or add `--build`). A CI job should do the same.
- No `decision_inputs` fixture exists in `contracts/read/fixtures/` (18 fixtures, none for it). T009's
  round trip for `decision_inputs` therefore uses a sample built from the `normal` `corridor_now` plus the
  extra fields. Phase 3 tests exercise the real object.
- The `src.ingestion` boundary accepts only the six turn-1 event types, so backend `decision` and
  `confirmation` rows cannot go through `ingest`. The builders validate them against
  `command_event.schema.json` and insert them directly, as the backend writer does. Backend
  `incident_report` rows do pass the boundary.
- Bus speed in the crafted timelines is 1.2 m/s so that buses started up to ~3,300 s apart fit on the
  5,119.4 m corridor; headway classes are unambiguous, headway values are not compared (SC-002).
- The live compose stack was not recreated. The new init scripts only apply on a fresh volume
  (`docker compose down -v && docker compose up -d --build`); tests use throwaway databases.

---

## Phase 1 — Silver current state (US1), T025–T033

| Item | Value |
|---|---|
| Start | 2026-11-19T12:53:55Z |
| End | 2026-11-19T13:02:22Z (whole-suite run finished 13:00:59Z) |
| Branch | `feature/002-silver-gold-baselines`, on top of `777b59e` |

Note: the Docker daemon was stopped at the start of the phase, so the stack was not up as announced. I started Docker Desktop; the `db`, `api` and `ingestion` containers came back healthy on their own before any test ran.

### Test-first evidence

Before `src/pipeline/silver.py` and the SQL files existed, the three integration files failed at collection with `ModuleNotFoundError: No module named 'src.pipeline.silver'`. `test_no_bronze_writes.py::test_silver_sql_files_are_part_of_the_scan` failed because the silver SQL files were absent (12 of its 13 tests passed, as they exercise the detector). After the implementation: 77 passed.

### Commands and results

| Command | Result |
|---|---|
| `uv run pytest tests/unit/test_no_bronze_writes.py tests/integration/test_silver.py tests/integration/test_silver_visits_traversals.py tests/integration/test_rebuild.py --no-cov -q` (host) | **77 passed, 0 failed** (13 + 26 + 31 + 7) |
| `docker compose --profile tools build tests` then `docker compose --profile tools run --rm tests` (CI-ready command, Andon check, whole suite) | exit 0; **260 passed, 0 failed, 3 skipped**; coverage 90.60 % (gate 80 %) |
| `uv run pytest -q` (host, whole suite, includes the 3 docker-CLI tests) | **263 passed, 0 failed**; coverage 90.60 % |

Per-file counts (host): `test_no_bronze_writes.py` 13, `test_silver.py` 26 (incl. the 5 parametrized Estimated ages), `test_silver_visits_traversals.py` 31, `test_rebuild.py` 7; the four files sum to 77.

The whole suite (001 + 002, unit + integration + contract) is green, so the line was not stopped. Before the phase: 183 passed + 3 skipped in the container. After: 260 passed + 3 skipped (+77).

Throwaway databases: none left on the server (`pg_database`: `postgres`, `pulsoflota`, `template0`, `template1`).

### Rework (tests that failed for an unexpected reason and were fixed)

| # | Test | Cause | Fix |
|---|---|---|---|
| 1 | `test_silver.py::test_reserve_bus_is_reserve_when_off_corridor_and_in_service_when_dispatched` | I used bus id `B-109`, which the 001 boundary rejects (not a valid bus id) | Used `B-101` with a finished trip for the `off_corridor` case. Test bug. |
| 2 | `test_silver_visits_traversals.py::test_incident_rows_use_event_id_and_the_half_open_interval` | I used `reported_by="dispatcher-01"`; the contract enum is `dispatcher` or `script` | Value changed to `dispatcher`. Test bug. |
| 3 | `test_rebuild.py::test_rebuild_source_does_not_use_truncate` | Plain substring `truncate` also matched the word in the docstring of `silver.py` | Check changed to a regex for a `TRUNCATE <schema>.<table>` statement. Test bug. |

Rework count: 3, all test-authoring mistakes. No product rule or threshold was changed to make a test pass.

### Decisions taken during the phase

- The 120 s threshold is `ESTIMATED_AFTER_S` in `src/rules/__init__.py` and reaches the SQL only as the `estimated_after_s` parameter. It is a rule constant, not an environment setting, so `.env.example` has no new entry.
- SQL parameters use psycopg named placeholders (`%(as_of_ts)s`, `%(max_bronze_id)s`, `%(estimated_after_s)s`) instead of the `$name` style in the task text.
- `rebuild_silver(conn, as_of_ts, max_bronze_id)` does not commit; the caller (the cycle, in Phase 2) owns the transaction. A test checks that a failing rebuild leaves the previous silver after rollback.
- `silver.bus_current_state` and `segment_traversals` read `silver.incidents`, so the build order is position_history, incidents, bus_current_state, stop_visits, segment_traversals.
- Segment id = `stop_seq` of the departure stop (segment *k* = seq *k* → *k+1*, as in data-model S5). The `segment_id` column of `stops.csv` is not used.
- Test support only: `tests/integration/conftest.py` (function-scoped `silver_conn`, clears bronze and silver in the throwaway database only) and `tests/fixtures/silver_support.py`.
- No change under `contracts/`, `docs/adr/`, `db/init/`, the simulator, the ingestion code, `.kiro/`, `.specify/` or the checklists. No new setting, so `.env.example` is unchanged.

## Phase 2 — Gold console views (US2), T034–T050

| Item | Value |
|---|---|
| Start | 2026-11-19T13:10Z (08:10 local, UTC−5) |
| Interrupted run 1 | model timeout, 08:10–12:06 local = 13:10–17:06Z on 2026-11-19. Tests, rules and the CLI of T034–T049 were written in this run (files dated 08:12–08:15 local). |
| Interrupted run 2 | network error, 21:04–23:09 local on 2026-11-19 = 02:04–04:09Z on 2026-11-20. `tests/fixtures/gold_support.py` and the transaction-contract rework come from this run. |
| Closing run | 2026-11-20, about 12:15Z to 12:30Z: waiting-bus fix, whole-suite runs, live check, bookkeeping. |
| Branch | `feature/002-silver-gold-baselines`, nothing committed |

The times of the two interrupted runs are the ones reported by the data owner. I read them as local time (UTC−5) because the file modification times of the code written in those runs match.

### Commands and results (T050)

| Command | Result |
|---|---|
| `pytest tests/integration/test_waiting_buses.py` before the fix | 3 failed, 1 passed (the 4th passes trivially before the fix). |
| Same file after the fix, plus `test_real_run_acceptance.py` | 5 passed in 6.8 s. |
| `test_real_run_acceptance.py` with the waiting rule disabled (temporary edit, reverted) | failed: `n_bunched == 3`. The test catches the defect. |
| `pytest -q` (host, whole suite, `DATABASE_URL` pointing at `localhost`) | **335 passed, 0 failed**, coverage 92.23 % (2 min 36 s). 330 before the fix + 5 new. |
| `docker compose --profile tools build tests`, then `docker compose --profile tools run --rm tests` | build exit 0; **332 passed, 3 skipped, 0 failed**, coverage 92.23 % (68.8 s). 327 + 3 skipped before the fix + 5 new. |
| `docker compose down -v && docker compose up -d --build`; health loop of at most 120 s | `db` and `api` healthy and `ingestion` up about 18 s after the build. |
| `docker compose exec -T ingestion python -m src.pipeline.compute --as-of 2026-11-24T22:10:00Z` (bronze held events up to 22:09:57Z) | printed `snapshot_id 1d9fe96f-980d-4c17-a49a-76fba7d5ed13`, `max_bronze_id 645`, status `live`. |
| `SELECT doc FROM gold.corridor_now WHERE snapshot_id = '1d9fe96f-…'` | one bus: B-101, `leader`, 2,640.5 m, prev P-888, next P-889, `live`, `headway_ahead_s` null; summary `buses_in_service 1`, `n_bunched 0`, `n_gaps 0`. `source_status`: `live`, `sources_down []`. |
| `silver.bus_current_state` at that snapshot | B-101 `on_corridor` true; B-102..B-105 `waiting` true, `off_corridor`. |

At minute 10 the only bus on the corridor is B-101: B-102 is at P-883 and has not departed yet (its scheduled start is 600 s), which is the correct reading after the fix. Before it, the same data gave 3 `bunched` buses.

### Acceptance on a real run (seed 42, 3,600 s)

`test_real_run_acceptance.py` ingests the whole simulator run through `src.ingestion.bronze.ingest` into a throwaway database and runs `run_cycle` at minutes 5, 10, …, 60 (12 snapshots). Result: `n_bunched == 0` and `n_gaps == 0` in every snapshot, and **11 non-null headways, minimum 485.7 s, maximum 700.0 s** (all inside 300–900 s). Runtime about 4–5 s, so the test is not marked `slow`.

### Rework

| # | What | Cause | Fix |
|---|---|---|---|
| 1 | Transaction contract of the cycle | `run_cycle` must own its transaction (REPEATABLE READ). Tests and `gold_support.cycle` held an open read transaction. | `cycle` in `gold_support.py` ends the test's own transaction first; `run_cycle` rejects a non-idle or autocommit connection. |
| 2 | `c2_gap` builder | The reference time (`as_of`) fell before B-105 started at 3,584 s, so B-105 never reported. | `as_of` moved to 3,600 s (comment in the builder). Test data bug. |
| 3 | Waiting buses (found by the independent verifier) | The simulator reports `bus_position` at 0 m for buses waiting at P-883. Silver and gold treated them as on the corridor: 3 `bunched` buses at minute 10 and false gaps of 900–3,000 s. The crafted builders never include waiting buses. | New rule, decided 2026-11-20 by the data owner (R7): on the corridor only from `stop_departure` at P-883 to `stop_arrival` at P-900. New `waiting` column; `on_corridor` excludes waiting buses; `sources_down` still includes silent waiting buses. Tests first: `test_waiting_buses.py`, `test_real_run_acceptance.py`. |

### Decisions taken in the closing run

- **Waiting definition.** A bus is waiting when its current trip is not finished, has no `stop_departure` at P-883, and the latest position of that trip is at the first stop (0 m), or the trip has no position yet and has a `stop_arrival` at P-883. The extra condition on position keeps the crafted builders valid: `Builder.drive` emits positions from 0 m without a `stop_departure`, and a bus that has moved past 0 m is on the corridor. The real simulator always emits the departure. No builder was changed.
- **New column.** `silver.bus_current_state.waiting` (`db/init/004_silver.sql`, `CREATE TABLE` plus `ADD COLUMN IF NOT EXISTS`). It is needed so a silent waiting bus stays in `sources_down` while a bus that finished its trip does not. `data-model.md` S3 has one new row; research R7 has the new paragraph. Nothing else in spec or plan changed. Phase 1 said `db/init/` was untouched; this is the first change there after T018.
- **Status of a waiting bus** is `off_corridor` (or `reserve` for a roster reserve bus), the existing values, so the CHECK constraint is unchanged.
- `sources_down` is now built from every state row that is on the corridor or waiting, so a bus on the corridor that has stop events but no position also appears there when Estimated.
- No change under `contracts/`, `docs/adr/` or the simulator. No thresholds added: the planned headway and the 120 s rule still come from config and `ESTIMATED_AFTER_S`.

## Phase 3 — M1/M2 baselines and decision inputs (US3), T051–T063 and T076

| Item | Value |
|---|---|
| Start | 2026-11-20T12:36Z |
| End | 2026-11-20T12:58Z (about 22 min, one uninterrupted run) |
| Branch | `feature/002-silver-gold-baselines`, nothing committed |

### Commands and results

| Command | Result |
|---|---|
| `pytest tests/unit/test_timebands.py` before `src/rules/timebands.py` existed | collection error (`ImportError`), the expected failure |
| `pytest tests/integration/test_baselines.py test_decision_inputs.py test_rebuild.py::<T057>` before the implementation | 9 + 17 failed (`KeyError` on missing baseline rows, `NoneType` for the missing `decision_inputs` row) |
| Same files after the implementation, plus `test_timebands.py`, `test_timebands_sql.py`, whole `test_rebuild.py` | **63 passed**, 0 failed |
| `uv run pytest tests -q -m "not slow"` (host, whole suite 001 + 002, unit + integration + contract) | **391 passed**, 1 deselected, 0 failed, coverage 92.54 % (178 s) |
| `uv run pytest tests/integration/test_replay_60min.py -m slow` (720 snapshots, `REPLAY_STEP_S = 5`, full density) | **1 passed** (47 s). 720 `source_status`, 720 `corridor_now`, 720 `decision_inputs` objects validate against their schemas; `buses` and `summary` equal `corridor_now` in all 720. |
| `docker compose --profile tools build tests`, then `docker compose --profile tools run --rm tests` (the CI-ready command) | build exit 0; **389 passed, 3 skipped, 0 failed**, coverage 92.54 % (117 s). 389 + 3 = 392 = 391 + the slow test. The 3 skips are the same ones as in Phase 2. |
| Coverage of the new rule code | `src/rules/timebands.py` 100 %, `src/pipeline/gold.py` 100 %, `src/pipeline/cycle.py` 96 % |

No cut item was taken: CUT-2 (replay density) and CUT-3 (R12 edge cases) are both implemented in full.

### Rework

Three test-authoring mistakes, no rule or threshold changed to get green.

| # | What | Cause | Fix |
|---|---|---|---|
| 1 | `test_decision_inputs.py` failed at collection with `NameError: pytest` | my import edit did not match the text | added the import |
| 2 | M1 observed tests got 2 samples instead of 5 or 6 | test data: traversals spaced 1,000 s apart ran past 23:00Z, so most fell into local hour 18, not 17 | spacing 300 s from t = 0 (all in hour 17) |
| 3 | `test_decision_inputs.py` incident test: ingest rejected an event | test data: `segment_accident` is not an `incident_type` of the contract (`bus_breakdown`, `stop_closed`, `other`) | used `stop_closed` at `P-885` |

### Decisions taken during the phase

- **Baselines replaced every cycle** (`DELETE` + `INSERT` in the cycle's transaction, before the snapshot is built), also for a no-op recompute. At the same `(as_of_ts, M)` the values are identical; a replay at an older time overwrites them with that time's values, as G5/G6 say ("replaced each cycle").
- **M2 rider count** counts every `rider_arrival` at the M2 stop up to `as_of_ts` and `M`, with no source filter (FR-030 says "rider_arrival events"; only the simulator emits them). R12's "simulator running" test does exclude `backend` bus positions.
- **`reserve_free`** = roster reserve buses that are not on the corridor in silver (the G3 wording; FR-033 says "not on an active trip"). A reserve bus that is waiting at P-883 or has finished its trip is free.
- **`active_incidents`** = silver incidents with `start_ts <= as_of_ts < end_ts`, ordered by `inc_id`; `duration_min = 0` is therefore never active (R7). `enabled_stops` ordered by `stop_id`.
- **`decision_inputs`** is built from the `model_dump` of the same `corridor_now` object, so `buses` and `summary` cannot differ.
- **Test support**: new `config_reset` fixture in `tests/integration/conftest.py` restores the seeded `config` tables after tests that change them (the module database is shared). The new T057 test was appended to `tests/integration/test_rebuild.py`.
- No new setting, so `.env.example` is unchanged. No change under `contracts/`, `docs/adr/`, `db/init/`, the simulator, ingestion, `.kiro/`, `.specify/`, checklists, or the silver/gold console rules.
