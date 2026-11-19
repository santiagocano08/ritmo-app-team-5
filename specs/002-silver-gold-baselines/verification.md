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
