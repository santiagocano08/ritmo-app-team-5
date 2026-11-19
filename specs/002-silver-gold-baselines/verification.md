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
