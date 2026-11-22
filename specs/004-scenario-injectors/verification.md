# Verification — 004 scenario injectors, hold loop and effect table

## Phase 1 — Injectors and incident view (US1)

- Start: 2026-11-21T14:05:26Z (UTC)
- Branch: `feature/004-scenario-injectors`
- Checklist gate: not re-asked; the data owner approved implementation on 2026-11-21 (checklist files untouched).

### Baseline (T001)

Command: `docker compose --profile tools build tests && docker compose --profile tools run --rm tests`

Result: **559 passed, 7 skipped, 0 failed, coverage 94.91 %**, 119.86 s.
Note: the 003 figure quoted in tasks.md (434 passed, 4 skipped, 91.97 %) is out of date; this run is the reference for "never lower".

### Golden hash (T002)

`src/data/tests/unit/test_simulator_golden_hash.py` written and run **green on the untouched engine** (before any edit to `engine.py` or `main.py`):
`uv run --frozen --extra dev pytest src/data/tests/unit/test_simulator_golden_hash.py --no-cov -q` → 3 passed.
Seed 42: `51a5e9b3…39e1` (3,851 lines, 1,439,431 bytes); seed 7: `6bd20707…0132`. Also confirmed with the CLI piped to `sha256sum`.

### Red confirmation (T013)

Each new test was run before any implementation. Failure reasons (all the expected ones, no syntax errors):

| Test file | Failure before the code |
|---|---|
| `test_scenario_config.py`, `test_scenario_injectors.py`, `test_scenario_channel.py`, `test_scenario_truth.py`, `test_scenarios_gold.py` | `ModuleNotFoundError: src.data.simulator.scenarios` |
| `test_silver_incident_null_duration.py` | `psycopg.errors.NotNullViolation: null value in column "end_ts" of relation "incidents"` (the pre-existing 002 failure) |
| `test_incident_gold.py`, `test_baselines.py` (via `gold_conn`) | `UndefinedTable: relation "gold.incident" does not exist` |
| `test_rules_version.py` | `assert '1.0.0' == '1.1.0'` |
| `test_schema_init.py` | `gold.incident missing` |
| `test_generated_read_models.py` | `No module named 'src.pulsoflota.models.read.incident'` |
| `tests/unit/test_env_example.py` (new tests) | `ImportError: get_sim_scenario_file` |
| `test_no_truth_reads.py` | green by design (3 passed); `test_no_bronze_writes.py` green on the existing files (14 passed) |
| `test_simulator_golden_hash.py` | stays green (3 passed) |

Existing acceptance test edited: `test_baselines.py` lines 92 and 159 now read `src.data.rules.RULES_VERSION` instead of the literal `"1.0.0"`; the assertion is otherwise the same (only the pinned version changed).
Fixture edit needed beyond the task list: `gold_support.clear_all` deletes `gold.incident` before `gold.snapshots` (foreign key).

### Implementation notes and rework

- T004 went green with the `COALESCE(..., 'infinity')` in `silver_incidents.sql`; `silver_support.incidents()` now selects an explicit column list (`open_ended` flag, `end_ts` NULL for infinity).
- Rework 1 (found by the first host-suite run): two existing 002 tests broke because of the new table and the version bump and were not in the T012 list: `test_decision_inputs.py` pinned `"1.0.0"` (now reads `RULES_VERSION`, same assertion) and `test_rebuild.py` drops `gold.snapshots` (now drops `gold.incident_current` and `gold.incident` first and replays `007_scenarios.sql`; the incident rows of the last snapshot are also compared). No assertion was weakened.
- Rework 2: first version of `pipeline/incidents.py` passed the `active` column into the strict `IncidentV100` model (`extra="forbid"`) and every cycle failed; `active` is now excluded from the doc.
- Rework 3 (live check): `.dockerignore` excludes `src/data/tests/`, so the fixtures are not in the `ingestion` image. The first live attempt failed fast (`scenario file rejected: cannot read scenario file`, exit non-zero before any event, as designed). The live checks mount the fixture directory read-only through an override file outside the repo (`/tmp/verify-override.yml`, `-f docker-compose.yml -f ...`).

### Offline hand checks (T023)

- `python -m src.data.simulator.main --seed 42/7 --duration 3600` with no file and with `empty.json`: `51a5e9b3…` and `6bd20707…`, both unchanged.
- `phase1_live.json`, seed 42, run twice: same stream hash (`16701d91…`) and byte-identical truth files.
- Invalid file (unknown bus): exit 2, 0 bytes on stdout.
- Truth file deleted before `python -m src.data.pipeline.compute --from … --to … --step 5` (scratch database, ingestion through `src.data.ingestion.run`):
  - C1: 22:30:00Z snapshot `n_bunched` 1, B-103 `bunched` headway 171.4 s behind B-102; truth `follower_gap_s` 185.
  - C5 (B-102): `bus_breakdown` incident `duration_s` 240, `until` null while active; B-102 `broken_down`, `headway_ahead_s` null, B-103 `gap` 1,213 s, `buses_in_service` 2 (three buses on the corridor, one excluded).
  - D1 silence: B-101 in `sources_down` since 22:04:05Z, no incident, no bunched or gap.
  - D1 duplicates: `duplicate_event` 20 rows, 0 other rejections.

### Live check C2 (T024), project `pulsoflota-verify`, db on port 55432

`SIM_SCENARIO_FILE=/scenarios/c2_gap.json`, seed 42, 2,100 s at `SIM_PACE_S=0.5`, `REFRESH_INTERVAL_S=1`, `REFRESH_CLOCK=data`. 2,221 events accepted, 0 rejected.
- 33 snapshots with `n_gaps >= 1`; first at 22:27:30Z: B-103 `gap`, `headway_ahead_s` 1,650.
- 0 snapshots where `n_gaps` differs from the count of `gap` buses; 0 snapshots with a gap bus at or below 900 s.
- Truth line in `docker compose logs ingestion`: `c2-b103`, bus B-103, fired, effective 22:05:00Z.
- Finding for the data owner: the truth names the same bus, but its `effective_ts` is the step where the delay was applied (22:05:00Z, delayed start 22:26:40Z). The gap first shows in gold at 22:27:30Z, so "within one 5 s cycle" holds for the bus and kind, not for C1 and C2 times. For C5 (since = effective_ts, bus `broken_down` in the first snapshot) and D1 silence (estimated 121 to 125 s after the last report) it holds and is tested.

### Live check Phase 1 (T025 step 3), project `pulsoflota-verify`

`SIM_SCENARIO_FILE=/scenarios/phase1_live.json`, seed 42, 3,000 s, same pace settings. 3,127 events accepted, 0 rejected, 10 duplicates.
- C1: first snapshot with a `bunched` follower 22:22:05Z.
- C5: `gold.incident_current` row B-104 `bus_breakdown`, since 22:40:00Z, until 22:44:00Z; 24 snapshots with it active (22:40:00Z to 22:43:50Z) and B-104 `broken_down` in the same 24.
- D1(a): B-101 in `sources_down` in 18 snapshots (22:06:15Z to 22:09:05Z); 0 snapshots with a bunched or gap alert in that period.
- D1(b): `duplicate_event` rows in `bronze.rejections` (10 in the first pass; the compose service restarts the finished simulator, which then re-ingests the same events as duplicates, 320 when read).
- Truth lines (4) in the container log: d1-silence-b101 22:04:10Z, d1-dup 22:08:20Z, c1-b102 22:12:05Z (`follower_gap_s` 185, `target_reached` true), c5-b104 22:40:00Z.
- Cleanup: `docker compose -p pulsoflota-verify down -v`; the default project (db, ingestion, api, refresh) was left running and untouched.

### Whole suite (T025 steps 1 and 2)

| Run | Command | Result |
|---|---|---|
| Baseline (T001) | Andon | 559 passed, 7 skipped, 0 failed, 94.91 % |
| First host run | `uv run pytest` | 690 passed, 3 skipped, **2 failed** (rework 1), 95.75 % |
| Host, after rework | `uv run pytest` (14:2x–14:3x, 298 s) | **692 passed, 3 skipped, 0 failed, 95.75 %** |
| Andon | `docker compose --profile tools build tests && docker compose --profile tools run --rm tests` | **688 passed, 7 skipped, 0 failed, 95.75 %**, 142 s |

Golden hashes green in both. Coverage of the new modules: `scenarios/channel.py`, `config.py`, `truth.py`, `pipeline/incidents.py`, `engine.py` 100 %; `injectors.py` 95 % (lines 45–48, C2 layover branch); `main.py` 88 %.

### Untouched check (T025 step 4)

`git status --short` and `git diff --stat` show no change to `contracts/`, `docs/adr/`, `002_bronze.sql`, `ingestion/bronze.py`, `ingestion/validate.py`, `.github/`, `Dockerfile`, `pyproject.toml`, `uv.lock`, `.kiro/`, `.specify/`. Init scripts 001 to 006 unchanged; `007_scenarios.sql` is new. Files outside the allowed list: `src/data/tests/integration/test_decision_inputs.py`, `test_rebuild.py`, `test_schema_init.py`, `src/data/tests/fixtures/gold_support.py` (see rework 1; reported, not hidden).

- End: 2026-11-21T14:45:05Z (UTC). Start: 2026-11-21T14:05:26Z. About 40 minutes elapsed.
- Not committed or pushed (left to the data owner).

## Phase 1 gate decision: scenario truth time and "detection time" (data owner, 2026-11-21)

The hidden truth records the **injection** time for C1 and C2 (code unchanged). SC-006 in `spec.md` and the T024 note in `tasks.md` now compare **bus and kind** only. The time from injection to the first gold snapshot that shows the effect is a separate measure, the "detection time". Phase 1 live figure for C2: injected 22:05:00Z (truth), first snapshot with the gap 22:27:30Z; this is reported as detection time, not as a pass condition. Research R2 line 151 and the T011 sentence still say "within one cycle"; they were not in the requested edit and are flagged for the data owner.

## Phase 2 — Hold loop (US2)

- Start: 2026-11-21T16:41:59Z (UTC). End: 2026-11-21T17:02Z (UTC).
- Branch: `feature/004-scenario-injectors`. Checklist gate not re-asked (data owner approval 2026-11-21); checklist files untouched.

### Red confirmation (T037)

Run before any Phase 2 code. All failures are the expected ones; no syntax errors.

| Test file | Failure before the code |
|---|---|
| `test_hold_rules.py` | `ImportError: cannot import name 'holds' from 'src.data.rules'` |
| `test_hold_compliance.py`, `test_hold_board.py`, `test_scenario_injectors.py` (hold cases), `test_hold_poller.py` | `ModuleNotFoundError: src.data.simulator.scenarios.holds` |
| `test_instruction_status.py`, `test_hold_loop.py` | `ModuleNotFoundError: src.data.pipeline.seeds` |
| `test_seeds.py` | `ImportError: cannot import name 'seeds' from 'src.data'` |
| `test_simulator_golden_hash.py` (new holds case), `test_loop_isolation.py` (offline) | `SystemExit: 2` (argparse: `--holds` does not exist) |
| `test_schema_init.py` | `config.seed_recommendation missing` |
| `test_generated_read_models.py` | `No module named 'src.pulsoflota.models.read.recommendation'` |
| `test_env_example.py` (new tests) | `ImportError: cannot import name 'get_seed_recommendations_path'` |
| `test_no_bronze_writes.py` | green by design (14 passed); it scans the simulator and passes on the new files |
| Phase 1 tests, golden hashes (`--holds` absent) | stay green |

### Implementation notes and decisions

- `rules/holds.py` is the one definition of the cap (90 s), the tolerance (15 s), visit matching and observation. Both sides apply the same order rules. A conflict is "two orders whose first matching visit is the same visit": the earlier bronze id runs, the later one is `not_executed` at the arrival time (the engine cancels the loser the same way).
- The compliance draw reads the first **8 bytes** of the SHA-256 digest as an integer and divides by 2**64. The task text says `[:8]` of the digest, which as 8 hex characters would give values below 2**-32 and make the probability meaningless.
- Pending needs the open arrivals: `silver.stop_visits` only has finished visits, so `pipeline/holds.py` also reads bronze arrivals that have no visit row yet (SELECT only). Without it an order whose bus is still at the stop after `expires_ts` would be reported `not_executed` and then flip.
- `gold.instruction_status` is rebuilt every cycle (not only when a snapshot is created), by DELETE + INSERT in the cycle transaction. The table has a CHECK that `ts_by_status` holds exactly one key equal to `status`.
- Seeds: `src/data/seeds/recommendations.json` (demo hold of 90 s, B-103 at P-887, expires 22:35:00Z, `ewt_saving_s` 55, horizon 300 s). `refresh` and `compute` load it with `pipeline/seeds.py` at start.
- Beyond the task text: `SEED_RECOMMENDATIONS_PATH` is also passed to the `refresh` service in `docker-compose.yml` (default empty), so the simulator and the pipeline cannot read different files. Added a `TruthSink.add_record` for hold records and `gold_support.clear_all` clears `gold.instruction_status`.
- The CODEOWNERS paths touched in this phase: `src/data/rules/holds.py` (new), `src/data/rules/sql/hold_orders.sql` (new). `rules/__init__.py` and `silver_incidents.sql` are not touched again.

### Offline hand checks (T044)

Scratch database, simulator CLI with `--holds on`, seed fixture, `SIM_HOLD_NONCOMPLIANCE` forced:
- Empty bronze, 3,600 s: seed 42 `51a5e9b3…` and seed 7 `6bd20707…`, both equal to the baselines.
- A `discard` decision: stream identical to the no-holds stream (zero holds).
- An `apply` decision for the 90 s seed on B-103: arrival 22:27:30Z, departure 22:29:00Z with `SIM_HOLD_NONCOMPLIANCE=0`; departure 22:27:40Z (natural 10 s dwell) with `=1`.

### Whole suite (T045 steps 1 and 2), one at a time

| Run | Command | Result |
|---|---|---|
| Phase 1 end | host and Andon | 692 passed, 3 skipped (host); 688 passed, 7 skipped (Andon); 95.75 % |
| Host | `uv run pytest` (16:51 to 16:56Z, 337 s) | **809 passed, 4 skipped, 0 failed, 96.40 %** |
| Andon | `docker compose --profile tools build tests && docker compose --profile tools run --rm tests` (16:57Z, 161 s run) | **805 passed, 8 skipped, 0 failed, 96.40 %** |

Skips: the `-m live` tests, which skip themselves unless `-m live` is passed; the container run has 4 more skips than the host run, which I did not itemize. Golden hashes green in both runs (base-case test T002 stayed green with and without `--holds on`). Coverage of the new code: `rules/holds.py` **100 %**, `pipeline/holds.py` 100 %, `simulator/scenarios/holds.py` 99 % (lines 236-237, the closing-error guard), `seeds/__init__.py` 93 %, `simulator/main.py` 95 %, `engine.py` 100 %.

Wall-clock sampling (SC-008): the batch of N = 200 `rec_id` values with seed 42 and probability 0.10 gives a reproducible non-compliant count, equal to the truth-record count; the expected 20 is reported by the test comment, not asserted.

### Live check (T045 step 3), project `pulsoflota-verify`, db on port 55432

Commands (each names the project on its own line): `COMPOSE_PROJECT_NAME=pulsoflota-verify docker compose down -v`; `POSTGRES_PORT=55432 API_PORT=58000 SIM_HOLDS=on SIM_PACE_S=0.5 SIM_DURATION_S=3600 COMPOSE_PROJECT_NAME=pulsoflota-verify docker compose up -d --build db ingestion`; `COMPOSE_PROJECT_NAME=pulsoflota-verify … uv run pytest src/data/tests/integration/test_loop_isolation.py -m live -q --no-cov -s`; `COMPOSE_PROJECT_NAME=pulsoflota-verify docker compose down -v`.
Result: **1 passed** in 12.5 s. `api` and `refresh` were not running (the test stopped them with `-p pulsoflota-verify` and confirmed), the ingestion service ran with the poller on (`SIM_HOLDS=on`), and `bronze.events` grew by more than 5 rows over 12 s. No `hold_poll_failed` line. The default project (db, ingestion, api, refresh) was running before and after and was not touched.

### Untouched check (T045 step 4)

`git status --short` shows no change to `contracts/`, `docs/adr/`, `002_bronze.sql`, `ingestion/bronze.py`, `ingestion/validate.py`, `.github/`, `Dockerfile`, `pyproject.toml`, `uv.lock`, `.kiro/`, `.specify/`. Init scripts 001 to 006 unchanged; `007_scenarios.sql` has the Phase 2 section appended. Existing 002/003 tests edited: `test_schema_init.py` (table lists), `tests/unit/test_generated_read_models.py` (NAMES), `tests/unit/test_env_example.py` (new tests only), `test_simulator_golden_hash.py` and `test_scenario_injectors.py` (new tests only), `gold_support.py` (one table added to `clear_all`); no assertion was weakened. Outside the written allowed list: `docker-compose.yml` refresh env (see decisions), reported.

- Not committed or pushed (left to the data owner).
