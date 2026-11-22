# Tasks: Data Fixes and Boarding-Probability Metrics

**Input**: Design documents from `/specs/005-data-fixes-metrics/`

**Prerequisites**: plan.md (approved with "Decisions at the human gate"), spec.md (approved, amended to the post-US1 oracles in `026190c`), research.md (R1–R14), data-model.md (E1–E10), contracts/ (README, gold-stop-metrics, guards, reference-congestion), quickstart.md. External oracle: `~/Documents/contexto/mock-005/resultados-post-us1.md` (and `mock_calculos.py`).

**Tests**: ON (project default; the spec and the constitution do not opt out, and FR-001 requires a failing test before every behavior change). Nothing in the spec or constitution says "no tests".

**Organization**: the four phases of the plan, in this order: (1) US1 + US2 → (2) US3 → (3) US4 → (4) US5 + US6. There are no separate Setup or Foundational phases: no new service, dependency or contract file is added (plan, Constraints), so nothing blocks the stories except the phase order. Each phase ends with a verification task and can be committed on its own. A final Polish phase closes `verification.md`.

## Format: `- [ ] T### [P?] [US?] Description with file paths (FR/SC ids)`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task).
- **[US1..US6]**: user story of `spec.md`. Verification and Polish tasks carry no story label.
- **✂**: on the cut list (see the end). Phase 4 is cut as a whole, never half-built.
- Paths are relative to the repository root. Agents never commit or push; the human commits each phase.
- **Red rule**: every implementation task names the test task it turns green. A test task is done only when it has been run and seen to **fail for the stated reason** (no import or syntax error). Exceptions are marked "green by design".
- **Commands** (run one at a time, never together):
  - *Host suite* = `uv run pytest -m "not slow and not live" -p no:cacheprovider` (the full suite with the 80 % gate; add `--no-cov` only for fast loops).
  - *Andon* = `docker compose --profile tools build tests && docker compose --profile tools run --rm tests` (CI-ready, unchanged, coverage ≥ 80 %).
- **Verify project**: every live check that starts, stops or resets a compose stack uses a dedicated project and the project name is **on the same command line**: `COMPOSE_PROJECT_NAME=pulsoflota-verify docker compose ...` or `docker compose -p pulsoflota-verify ...`. Never `export` in one call and run a bare `docker compose down -v` in another (it would delete the default `db_data` volume). Never touch the default stack. Cleanup: `COMPOSE_PROJECT_NAME=pulsoflota-verify docker compose down -v`.
- **Live-check recipe** (used by every phase; each phase adds its own queries): `COMPOSE_PROJECT_NAME=pulsoflota-verify docker compose down -v`, then start `db`, `ingestion`, `refresh` under the same prefix with `SIM_SEED=42 SIM_DURATION_S=2700 SIM_PACE_S=<fast>`, `SIM_SCENARIO_FILE=src/data/tests/fixtures/scenarios/c1_bunching.json`, `REFRESH_CLOCK=data`, and query with `COMPOSE_PROJECT_NAME=pulsoflota-verify docker compose exec -T db psql ...`. Phases 2 and 3 apply `008_data_fixes_metrics.sql` to the new volume through `docker-entrypoint-initdb.d` (a fresh `down -v` volume gets it); the by-hand apply command in `quickstart.md` is only for existing volumes and is not used here.
- **Cycle-time measurement** (every phase): on a throwaway database as in `quickstart.md` "Scratch measurement recipe" (ingest the C1 seed 42 stream at 2,700 s, `run_cycle(conn, as_of, notify=False)` every 25 s), plus the `duration_ms` of the `refresh_cycle` log lines of the live check. Required: **cycle p95 ≤ 250 ms at demo length**. Record median, p95 and max in `verification.md` (baseline: 48 / 68 / 81 ms, research R12).
- **Untouched check** (shared by every verification task): `git status --short` and `git diff --stat feature/004-scenario-injectors` show **no** change to `contracts/` (JSON Schemas), `docs/adr/` or any ADR text, `docs/data-contract.md`, `src/data/db/init/001`–`007` and every bronze table definition (`002_bronze.sql`), `.github/` (including `.github/CODEOWNERS`), `Dockerfile`, `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `.env.example`, `src/pulsoflota/config.py`, and the simulator engine (`src/data/simulator/**`), whose output changes **only** through the regenerated `data/reference/congestion_factor.csv`. `src/data/ingestion/validate.py` may change **only** for the US5 range check, in Phase 4. Each verification task lists its own allowed-file list; any other changed file is reported, not accepted (FR-003, FR-053, SC-014).
- **Rules version**: `RULES_VERSION` in `src/data/rules/__init__.py` is bumped **once per phase**: 1.1.0 → 1.2.0 (P1) → 1.3.0 (P2) → 1.4.0 (P3) → 1.5.0 (P4). `src/data/tests/unit/test_rules_version.py` is updated in the same phase, red first. `rules/` and `contracts/`-adjacent changes need the data owner's CODEOWNERS review (reported, not self-approved).
- **Oracle policy** (plan decision 2): the only oracles are the post-US1 numbers in `plan.md` and `resultados-post-us1.md`. No frozen pre-005 reference, no `reference_pre005/`, no substitution helper. Oracle code is an independent recomputation from the raw simulator events, never from the tables under test.
- **No code in this file.** Task lines say what to write and where; the code is written during implementation.

---

## Phase 1: Reference Hour and Terminal Headway (US1 + US2, P1) 🎯 MVP

**Time**: 1.25 h.

**Goal**: the SIMM factor describes the right local hour, and a bus leaving the terminal gets the headway measured from the leader's departure (FR-010 to FR-013, FR-020 to FR-022, SC-001 to SC-004).

**Independent Test**: the 24 committed factors equal the raw SIMM file grouped by `UTC hour − 5` and the old file rotated by 5 rows; golden hashes equal the new values; on C1 seed 42 the terminal headways are 615 / 595 / 605 s (300–900 s) at 22:20:40Z, 22:30:35Z, 22:40:40Z.

### Baseline and tests first (US1 + US2)

- [ ] T001 Record the baseline in `specs/005-data-fixes-metrics/verification.md` (create it with a "Baseline" section): suite result and coverage figure of the Host suite and of the Andon command on head `8351274`-based `feature/005-data-fixes-metrics`; the two old golden hashes (seed 42 `51a5e9b3…39e1`, 3,851 lines, 1,439,431 B; seed 7 `6bd20707…0132`); the old CSV value `17 h = 0.5011`; `RULES_VERSION = 1.1.0`. Run the Cycle-time measurement once on the unchanged code (baseline for later comparison). (FR-012, SC-002, SC-014)
- [ ] T002 [P] [US1] Add the CI-safe committed-CSV test to `src/data/tests/unit/test_reference_build.py`: `data/reference/congestion_factor.csv` has 24 rows (hours 0–23), `17 h = 0.4816`, slowest hour = 18 (0.4575), highest speed factor at 03 h (0.5656). Must **fail** on the current file (17 h = 0.5011). Runs in CI without `data/raw/`. (FR-010, FR-011, SC-001)
- [ ] T003 [US1] Add the build test to `src/data/tests/unit/test_reference_build.py` (same file as T002, so not parallel): the 24 factors produced by `build_congestion_factor` from `data/raw/plata/simm_corredor_c6008.csv` equal an independent recomputation (group raw rows by `UTC hour − 5`, `round(mean(VELOCIDAD) / free_flow_kmh, 4)`), maximum difference 0; the hours-with-no-data fallback (overall mean with a warning) is still exercised on a small synthetic file; skips without `data/raw/` like the existing build tests. Must fail on the unfixed build (shifted by 5). (FR-010, SC-001)
- [ ] T004 [P] [US2] Add `pass_time` / `headway_s` unit tests to `src/data/tests/unit/test_headway.py`: leader waiting at 0 m for N s then leaving → `pass_time(..., distance_m=0, origin_m=0, departure_ts=D)` returns `D`, never a waiting sample; follower at 0 m gets `follower_ts − D`; leader that has not left (no `departure_ts`, no sample past the origin) → `None` and `headway_s` returns "no evidence" with no exception and no negative value; no `departure_ts` but samples past the origin → the **last** sample at or below `origin_m`; `distance_m > origin_m` behaves exactly as before; existing `BusObs` built without `departure_ts` still work. Must fail on the unfixed code (US2.5, FR-022). (FR-020, FR-021, FR-022, SC-003)
- [ ] T005 [US2] Write `src/data/tests/integration/test_terminal_headway.py` (throwaway database, C1 seed 42, current reference): cycles at 22:20:40Z, 22:30:35Z and 22:40:40Z give the headway of the bus leaving the terminal of 615 / 595 / 605 s to the nearest second (between 300 s and 900 s), no `gap` caused by the terminal wait, and the snapshot EWT is not 211, 467 or 731 s (that value check is only a "not equal" here; stop-based EWT arrives in Phase 2). Must fail on the unfixed code (1,240 / 1,835 / 2,440 s) once T009 has regenerated the CSV; before T009 it is also red for the CSV reason, note which. (FR-020, FR-022, SC-003, SC-004)
- [ ] T006 [P] [US1] Update the pinned values in `src/data/tests/unit/test_simulator_golden_hash.py` to the new golden hashes: seed 42 `8bae0e5229b2e547fac181f0f87176809d71be7a80600a4b066832b6274690bc` (3,831 lines, 1,433,630 B, also in `test_seed_42_shape`); seed 7 `27a8206e4bcf896b54f847521ae80d65db9db260c2ba1431422e04b244d4df7e` (3,844 lines, 1,437,557 B). These are the plan's dry-run values; T011 re-measures them from the committed CSV and the test must agree. Fails now (old stream). (FR-012, SC-002)
- [ ] T007 [P] Update `src/data/tests/unit/test_rules_version.py` to expect `1.2.0` (value read from `src.data.rules.RULES_VERSION` where the file already does so; the pinned literal moves). Must fail. (plan R13)

### Implementation (US1, then US2)

- [ ] T008 [US1] Change `src/data/reference/build.py` so `build_congestion_factor` parses `FECHAHORA` as UTC and takes the hour through `timebands.local_hour_band` (one `LOCAL_OFFSET`, no second copy of UTC−5); unparsable rows are skipped as before; the no-data-hour fallback stays; then change the sentence in `src/data/reference/sources.py` that generates `SOURCES.md` (now: `FECHAHORA` is UTC and is converted to local hour, UTC−5). Do not edit `SOURCES.md` by hand. Turns T003 green. (FR-010, FR-011, FR-013)
- [ ] T009 [US1] Regenerate with `python -m src.data.reference.build` (needs `data/raw/`): rewrites `data/reference/congestion_factor.csv` and `data/reference/SOURCES.md`. Check `git diff --stat data/reference/` shows **only those two files**; any other changed reference file is a defect (the old code rebuilt all seven byte-identical). Turns T002 green. (FR-011, SC-001)
- [ ] T010 [US1] One-off comparison (result recorded in `verification.md`, nothing committed): `git show HEAD:data/reference/congestion_factor.csv` against the new file, new `h` = old `(h + 5) mod 24`, maximum difference 0 at 4 decimals; record the 24 new factors and the three anchors (17 h 0.5011 → 0.4816, slowest hour 23 h → 18 h, highest factor 08 h → 03 h). Do not keep a frozen copy of the old file. (SC-001)
- [ ] T011 [US1] Re-measure the golden hashes from the committed CSV (simulator CLI, seeds 42 and 7, 3,600 s, no scenario, no holds) and confirm they equal T006; record **old and new** hashes, line counts and byte counts in `verification.md`. If they differ from the plan's dry run, stop and report (the CSV is not the expected rotation). Turns T006 green. (FR-012, SC-002)
- [ ] T012 [US1] Run the Host suite once and record the list of tests that fail only because of the regenerated stream. Expected **18**: the 9 golden-hash tests in `test_simulator_golden_hash.py` (already re-pinned by T006, so they should now pass) and the **9 time-pinned tests** below. Any other failure is a finding to report, not to patch silently. (plan R1)
- [ ] T013 [P] [US1] Re-pin to the new stream the 5 time-pinned tests in `src/data/tests/unit/test_scenario_injectors.py`: `test_c1_waits_for_the_first_arrival_at_or_after_start_s` (pinned arrival 725 s), `test_decision_must_precede_the_arrival_strictly`, `test_hold_extends_the_total_dwell_to_the_requested_seconds`, `test_hold_keeps_reporting_with_doors_open_and_the_bus_does_not_move`, `test_second_order_for_the_same_visit_is_a_conflict_and_never_runs`. Read the new seconds from the regenerated stream (B-103 arrives at P-887 22:27:45Z and leaves 22:29:15Z after a 90 s hold, as the mock prints); change only the pinned constants, not the assertions. (plan R1, FR-012)
- [ ] T014 [P] [US1] Re-pin the 3 time-pinned tests in `src/data/tests/integration/test_hold_loop.py`: `test_forced_compliance_gives_executed`, `test_same_decision_delivered_twice_runs_once`, `test_two_orders_for_the_same_visit_run_the_first_only`; constants only. (plan R1)
- [ ] T015 [P] [US1] Re-pin the 1 time-pinned test in `src/data/tests/integration/test_hold_poller.py`: `test_pre_written_decision_is_on_the_board_before_the_first_event`; constants only. (plan R1)
- [ ] T016 [US2] Implement the origin pass time in `src/data/rules/headway.py` (pure): `BusObs.departure_ts: datetime | None = None`; `pass_time(history, distance_m, origin_m=0.0, departure_ts=None)` and `headway_s(..., ahead_departure_ts=None, origin_m=0.0)` as in `data-model.md` E10 and research R3: for `distance_m <= origin_m` return `departure_ts` if given, else the last sample at or below `origin_m`, else `None`; `None` means "no evidence", never an exception or a negative headway. Turns T004 green. (FR-020, FR-021)
- [ ] T017 [US2] In `src/data/pipeline/gold.py`, read the first-stop departures with one query on `silver.stop_visits` joined to `silver.bus_current_state` on `position_trip_id`, for the first stop of `config.ref_stops` (`stop_seq = 1`) and take `origin_m` from the same table (no literal 0 or `P-883` in code); pass `departure_ts` and `origin_m` through `compute_headways` into `BusObs`. Parameterized SQL only. Turns T005 green. (FR-020, FR-021, FR-022, SC-003, SC-004)
- [ ] T018 Bump `RULES_VERSION` to `1.2.0` in `src/data/rules/__init__.py` (CODEOWNERS review applies); turns T007 green. (plan R13)

### Phase 1 verification and exit gate

- [ ] T019 Verify Phase 1, one command at a time, results written into `verification.md`: (1) Host suite → 0 failed, coverage ≥ 80 %, golden hashes green, passed count not below the T001 baseline plus the new tests; (2) then Andon → same; (3) Live check under `pulsoflota-verify` (recipe above, scenario `c1_bunching.json`): `COMPOSE_PROJECT_NAME=pulsoflota-verify docker compose exec -T db psql ...` reads the snapshot nearest 22:20:40Z / 22:30:35Z / 22:40:40Z from `gold.corridor_now` and shows `headway_ahead_s` 300–900 s for the bus leaving the terminal and no `gap` from the terminal wait; finish with `COMPOSE_PROJECT_NAME=pulsoflota-verify docker compose down -v`; (4) Cycle-time measurement (p95 ≤ 250 ms); (5) Untouched check with this phase's allowed list: `data/reference/congestion_factor.csv`, `data/reference/SOURCES.md`, `src/data/reference/{build,sources}.py`, `src/data/rules/{__init__,headway}.py`, `src/data/pipeline/gold.py`, the Phase 1 tests listed above, `specs/005-data-fixes-metrics/**`; `src/data/simulator/**` must show **no** diff. (FR-001, FR-003, FR-010 to FR-013, FR-020 to FR-022, SC-001 to SC-004, SC-014)
- [ ] T020 🛑 **PHASE 1 EXIT GATE — STOP for the data owner's verifier. Phase 2 does not start before this task is closed.** Hand over the regenerated `data/reference/congestion_factor.csv` (working tree). The data owner runs `PYTHONPATH=. uv run python ~/Documents/contexto/mock-005/mock_calculos.py` from the repository root (it overwrites `resultados.md` next to itself) and compares with the table in `quickstart.md`: section 1 every hour ±0.0 % with slowest hour 18 h; section 2 terminal headways 615 / 595 / 605 s at 17:20:40, 17:30:35 and 17:40:40 local; section 3 stop EWT on P-888..P-900, departures 17:28:55–17:44:55 local, **exactly +25.8 s (27 intervals) without the hold and +10.6 s (28 intervals) with it**, hold saving 15.2 s, B-103 at P-887 from 17:27:45 to 17:29:15 local. Paste the verifier's output and the data owner's sign-off into `verification.md`. Any other value: Phase 1 stays open, the CSV is not regenerated as the rule says, and no Phase 2 task starts. (plan Phase 1 exit, SC-001, SC-006 oracle source)

**Checkpoint**: Phase 1 is committable on its own after T020 (`RULES_VERSION` 1.2.0).

---

## Phase 2: Stop-Based EWT (US3, P1)

**Time**: 2.25 h.

**Goal**: EWT is measured at stops from departures: a live trailing-15-minute value in `gold.service_metric` (same columns), per-stop rows per snapshot, and additive per-stop rows for each closed clock-aligned 15-minute local band (FR-030 to FR-036, SC-005 to SC-008).

**Independent Test**: per-stop and corridor values in gold equal an independent recomputation from the raw events exactly; on the current reference, C1 seed 42, P-888..P-900, departures in (22:28:55, 22:44:55]Z: **+25.8 s (27 intervals) without the hold, +10.6 s (28) with the 90 s hold**.

### Tests first (US3)

- [ ] T021 [P] [US3] Write the oracle module `src/data/tests/fixtures/oracle_stop_metrics.py`: an independent recomputation from the raw simulator events (not from `silver`/`gold`): departures per stop, stop headways attributed to the closing departure, `window_sums(lo, hi)` over `(lo, hi]`, trailing-15-minute and per-closed-band sums (`n_headways`, `Σh`, `Σh²`, `Σhp`, `Σhp²`, `n_excluded`), with the planned headway 600 s as an argument. No import from `src/data/rules/stop_metrics.py`. Self-check against the quickstart table (27 / 28 intervals; Σh 13,290 / 14,505; Σh² 8,660,350 / 9,011,425; band 69 + 70 sums 31 headways Σh 16,950 Σh² 12,010,450 without the hold, 32 / 18,165 / 12,361,525 with it). (SC-005, SC-006)
- [ ] T022 [P] [US3] Write `src/data/tests/unit/test_stop_metrics.py` (pure rule, no database): headway attributed to the **closing** departure; one departure means no headway and not computable (no zero, no error); equal-timestamp tie order deterministic; a departure with `estimated_at_departure` excludes both headways that touch it and counts them in `n_excluded` (lost departures leave no row, so are not counted: turn-1 limit); `window_sums` over `(lo, hi]` with the oracle numbers 27 / +25.8 s and 28 / +10.6 s fed from the oracle module; `band_sums` with boundaries 17:14:59 vs 17:15:00 local, closed bands only (`band_end <= as_of`); `add` is additive. Fails: module missing. (FR-030, FR-031, FR-032, FR-035, SC-005, SC-006)
- [ ] T023 [P] [US3] Rewrite `src/data/tests/unit/test_service_metric.py` for the sums-based `service_metric(n, sum_h, sum_h2, planned_s, min_headways)` and `ewt_from_sums`: headways 300 s and 900 s give +75 s; four regular 600 s give 0; below 5 headways `computable = false` with NULL `mean_wait_s`, `scheduled_wait_s`, `ewt_s` and `n_headways` still shown; exactly 5 computable; `Σh = 0` not computable; planned headway is a parameter; values rounded to 3 decimals as before. Fails on the old spatial function. (FR-030, FR-031, FR-035, FR-036)
- [ ] T024 [US3] Update `src/data/tests/unit/test_rules_version.py` to expect `1.3.0`. Fails. (plan R13)
- [ ] T025 [US3] Update the table inventory and lineage parameters in `src/data/tests/integration/test_schema_init.py` for the Phase 2 objects (`config.corridor_settings.min_stop_headways` default 5 with `CHECK (min_stop_headways >= 1)`; `silver.stop_visits.estimated_at_departure boolean NOT NULL DEFAULT false`; index `silver_stop_visits_stop_dep_idx (stop_id, departure_ts)`; tables `gold.service_metric_stop` and `gold.stop_ewt_band` with every column type of data-model E5 and E6, including NOT NULL `rules_version` and `max_bronze_id`). Fails: `008` does not exist. (FR-033, FR-034)
- [ ] T026 [US3] Write `src/data/tests/integration/test_stop_ewt_gold.py` (throwaway database, module scoped, C1 seed 42, 2,700 s, with and without the seeded 90 s hold): (a) live corridor row at 22:44:55Z, all 18 stops: 33 headways +17.6 s without the hold, 35 headways +2.8 s with it; (b) live window on P-888..P-900 from the per-stop rows: 25 headways +21.0 s / 27 headways +1.8 s; (c) the oracle window (22:28:55, 22:44:55]Z read through the pure rule on `silver.stop_visits`: 27 intervals +25.8 s (±0.1) and 28 intervals +10.6 s (±0.1), lower with the hold; (d) band rows equal the oracle grouped by band, 0 differences in `n_headways`, `Σh`, `Σh²`, `Σhp`, `Σhp²`, `n_excluded`; band 69 = 6 / 5 and band 70 = 25 / 27 headways; bands 69 + 70 sums as in T021; band 68 has no row; (e) bunched snapshot (22:30:00Z, B-103 210 s behind B-102): corridor EWT **+116.6 s** with 15 headways, and > 0 at the snapshot where B-103 is 195 s behind (was −202 s); (f) adding or removing a bus with no departure in the window changes the EWT by 0 s; (g) a stop with one departure: row present, `computable = false`, absent from the corridor sums; (h) corridor row not computable below 5 headways, computable at 5; (i) D1 stream `src/data/tests/fixtures/scenarios/d1_silence.json`: headways touching an estimated departure excluded and counted in `n_excluded`; (j) rerun the cycle and rebuild gold twice: rows identical; every row has `rules_version` and `max_bronze_id`; (k) `gold.service_metric` keeps `n_headways`, `mean_wait_s`, `scheduled_wait_s`, `ewt_s`, `computable`, `rules_version`, `max_bronze_id`, one row per snapshot; (l) the read queries Q-S1, Q-S2 and Q-E1 of `contracts/gold-stop-metrics.md` run as written. All fail: tables missing. (FR-030 to FR-036, SC-005 to SC-008)
- [ ] T027 [P] [US3] Update the test helpers and existing tests that list tables or pin the old EWT: `src/data/tests/fixtures/gold_support.py` (`clear_all`: `service_metric_stop` before `snapshots` because of the foreign key, `stop_ewt_band`), `src/data/tests/integration/conftest.py` (gold list gains `service_metric_stop` **before** `snapshots`; silver list unchanged), `src/data/tests/integration/test_scenarios_gold.py` (the two table lists), `src/data/tests/integration/test_gold_contract.py` (`n_headways == 4` and mean 300 s of the old spatial rule become the stop-based values of the same fixture, with the 5-headway minimum respected). Any other test that asserts a spatial EWT is found by running the suite and listed in `verification.md`. (plan R14, FR-033, FR-036)

### Implementation (US3)

- [ ] T028 [US3] Write `src/data/db/init/008_data_fixes_metrics.sql` (idempotent: `ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`) with the Phase 2 objects only: `config.corridor_settings.min_stop_headways int NOT NULL DEFAULT 5 CHECK (min_stop_headways >= 1)`; `silver.stop_visits.estimated_at_departure boolean NOT NULL DEFAULT false` and index `silver_stop_visits_stop_dep_idx ON silver.stop_visits (stop_id, departure_ts)`; `gold.service_metric_stop` (PK `snapshot_id, stop_id`; FK to `gold.snapshots`; `n_headways int ≥ 0`, `sum_headway_s`, `sum_headway_sq_s`, `sum_planned_s`, `sum_planned_sq_s` numeric ≥ 0, `n_excluded int ≥ 0`, `computable boolean`, `rules_version text NOT NULL`, `max_bronze_id bigint NOT NULL`); `gold.stop_ewt_band` (PK `local_date, band, stop_id`; `band smallint 0–95`; same sums; lineage NOT NULL). No change to `001`–`007`. Turns T025 green. (FR-033, FR-034, data-model E2, E3, E5, E6)
- [ ] T029 [US3] Add the estimated-departure flag to `src/data/rules/sql/silver_stop_visits.sql`: `estimated_at_departure` is true when the bus's previous report (any of `bus_position`, `stop_arrival`, `stop_departure`; non-backend; `id <= M`; strictly earlier distinct `event_ts`) is more than `estimated_after_s` (parameter, `ESTIMATED_AFTER_S` = 120, the single value) before `departure_ts`; no earlier report: false. SQL reads only (keeps `test_no_bronze_writes.py` green). (FR-032, data-model E3)
- [ ] T030 [P] [US3] Create `src/data/rules/stop_metrics.py` (pure, no I/O, no wall clock): `Departure`, `StopSums`, `stop_intervals`, `window_sums(departures, lo, hi)` (closing departure in `(lo, hi]`), `band_sums(departures, as_of)` (closed bands only, `timebands.m2_band` and `timebands.local_date`), `add`, exactly as in data-model E10. Turns T022 green. (FR-030, FR-031, FR-032, FR-035)
- [ ] T031 [P] [US3] Rewrite `src/data/rules/service_metric.py` over sums (`service_metric(n, sum_h, sum_h2, planned_s, min_headways)`, `ewt_from_sums`); remove the old spatial EWT function (FR-036; if another rule still imports it, report instead of keeping dead code). Rules constants stay as named arguments, no literal 600 or 5 inline. Turns T023 green. (FR-030, FR-031, FR-035, FR-036)
- [ ] T032 [US3] Create `src/data/pipeline/stop_metrics.py`: read departures from `silver.stop_visits` (parameterized), build per-snapshot per-stop sums over the trailing window `(as_of − 15 min, as_of]` (`timebands.WINDOW`, no new setting), rebuild `gold.stop_ewt_band` for closed bands (delete and re-insert each cycle, same lineage as the cycle), and derive the corridor row by summing the stop sums (never averaging stop EWTs), with the planned headway from `config.corridor_settings.headway_planned_s` and the minimum from `min_stop_headways`. Turns the sums checks of T026 green. (FR-030 to FR-035)
- [ ] T033 [US3] Wire `src/data/pipeline/gold.py` to write `gold.service_metric` (same columns, new definition, one row per snapshot, values rounded to 3 decimals) and `gold.service_metric_stop` (18 rows per snapshot) from T032, and `src/data/pipeline/cycle.py` to call the band rebuild inside the cycle transaction. `snapshot_id` hashing is unchanged apart from the version. Turns T026 and T027 green. (FR-033, FR-034, FR-036, SC-005 to SC-008)
- [ ] T034 [US3] Bump `RULES_VERSION` to `1.3.0` in `src/data/rules/__init__.py`; turns T024 green. (plan R13)

### Phase 2 verification

- [ ] T035 Verify Phase 2, one command at a time, results written into `verification.md`: (1) Host suite → 0 failed, coverage ≥ 80 % (new pure rules near 100 %); (2) then Andon → same; (3) Live check under `pulsoflota-verify` (recipe; `008` comes from the init directory of the fresh volume) with `c1_bunching.json`: `SELECT count(*)` and `SELECT … FROM gold.service_metric_stop WHERE snapshot_id = (newest)` returns 18 rows; `gold.stop_ewt_band` has rows for closed bands only (band 68 absent for P-888..P-900); the newest `gold.service_metric` row has `ewt_s` computable and equal to the oracle at that `as_of`; two consecutive cycles over the same bronze give identical band rows; `docker compose logs refresh` shows no `cycle_failed`; cleanup with the same prefix; (4) Cycle-time measurement: p95 ≤ 250 ms at demo length (new steps budget ≤ 100 ms), and the 4-hour stress figure ≤ 1.5 s recorded; (5) record the oracle table (+25.8 s / 27 and +10.6 s / 28, live and band figures) with the measured values; (6) Untouched check with this phase's allowed list: `src/data/db/init/008_data_fixes_metrics.sql`, `src/data/rules/{__init__,stop_metrics,service_metric}.py`, `src/data/rules/sql/silver_stop_visits.sql`, `src/data/pipeline/{stop_metrics,gold,cycle}.py`, the Phase 2 tests and fixtures listed above, `specs/005-data-fixes-metrics/**`. (FR-001, FR-003, FR-030 to FR-036, SC-005 to SC-008, SC-014)

**Checkpoint**: Phase 2 is committable on its own (`RULES_VERSION` 1.3.0). US3 stands without US4.

---

## Phase 3: P(board ≤ t) (US4, P1)

**Time**: 1.0 h.

**Goal**: additive per-stop, per-band boarding counts (simple method), a view with `closed` and `final`, and documented read queries (FR-040 to FR-045, SC-009 to SC-011).

**Independent Test**: counts equal an independent recomputation from the raw `rider_arrival` and departure events; on C1 seed 42, no hold, cycle at 22:45:00Z, bands 68 / 69 / 70 have 9 / 16 / 21 riders and ≤ 5 / ≤ 10 / ≤ 15 counts of 3 / 9 / 9, 10 / 16 / 16, 9 / 14 / 15 (6 open riders in band 70); 46 riders in all, 37 at P-883.

### Tests first (US4)

- [ ] T036 [P] [US4] Extend `src/data/tests/fixtures/oracle_stop_metrics.py` (T021) with the independent rider oracle: for each `rider_arrival` (deduplicated by `source` + `event_id`) at a stop of `config.ref_stops`, the next departure of any bus from that stop with `a ≤ d ≤ as_of` (wait 0 counts), attributed to the **arrival** band (local), with `n_riders`, `n_board_le_5/10/15` (300 / 600 / 900 s). Must not import `rules/boarding.py`. Self-check against the quickstart Phase 3 table. (FR-040 to FR-042, SC-009)
- [ ] T037 [P] [US4] Write `src/data/tests/unit/test_boarding.py` (pure rule): arrival exactly at a departure counts with wait 0; a rider with no departure counts only in `n_riders` (SC-010); an open rider whose elapsed time is ≤ t stays in `n_riders` only and moves into the columns when a later cycle sees the departure (A-7); a rider whose elapsed time exceeds t with no departure is never counted for that t; the column order invariant `le_5 ≤ le_10 ≤ le_15 ≤ n_riders`; arrival at 17:14:59 local belongs to band 68 even when served in band 69; a rider at a stop outside `config.ref_stops` counts nowhere; `BOARDING_THRESHOLDS_S = (300, 600, 900)` is a named constant in `boarding.py`. Fails: module missing. (FR-040 to FR-042, FR-045, SC-010)
- [ ] T038 [US4] Update `src/data/tests/unit/test_rules_version.py` to expect `1.4.0`, and extend `src/data/tests/integration/test_schema_init.py` and the helpers in `src/data/tests/fixtures/gold_support.py` and `src/data/tests/integration/conftest.py` for `gold.stop_boarding_band` (E7 columns, `CHECK (n_board_le_5 <= n_board_le_10 AND n_board_le_10 <= n_board_le_15 AND n_board_le_15 <= n_riders)`, lineage NOT NULL) and the view `gold.stop_boarding_band_v` (E8). Fails: objects missing. (FR-040, FR-043)
- [ ] T039 [US4] Write `src/data/tests/integration/test_stop_boarding_gold.py` (throwaway database, C1 seed 42 and the base case): (a) counts per stop and band equal the oracle, 0 differences (bands 68 / 69 / 70 = 9 / 16 / 21 riders, ≤ 5: 3 / 10 / 9, ≤ 10: 9 / 16 / 14, ≤ 15: 9 / 16 / 15; 46 riders, 37 at P-883); (b) at least one rider with no departure is in `n_riders` only (SC-010); (c) two gold rebuilds from the same bronze give identical rows (SC-011), each row with `rules_version` and `max_bronze_id`; (d) a duplicated `rider_arrival` (same `source` and `event_id`) through ingestion is counted once; (e) a rider at an unknown stop is counted nowhere; (f) Q-P1 of `contracts/gold-stop-metrics.md` run as written: `P = Σ n_board_le_t / Σ n_riders`, NULL (not 0) when no rider, the `final` filter excludes the open band (at 22:45:00Z only bands 68 and 69 are final; band 70 is `closed = false`); (g) per-stop variant of Q-P1; (h) `gold.stop_ewt_band` and the Phase 2 rows are unchanged by the new step. Fails: table missing. (FR-040 to FR-045, SC-009 to SC-011)

### Implementation (US4)

- [ ] T040 [US4] Append the Phase 3 objects to `src/data/db/init/008_data_fixes_metrics.sql` (same idempotent style): `gold.stop_boarding_band` (PK `local_date, band, stop_id`, `n_riders`, `n_board_le_5`, `n_board_le_10`, `n_board_le_15` with the `CHECK` above, `rules_version text NOT NULL`, `max_bronze_id bigint NOT NULL`) and `CREATE OR REPLACE VIEW gold.stop_boarding_band_v` with `band_start_ts`, `band_end_ts`, `closed` (`band_end_ts <=` newest snapshot `as_of_ts`) and `final` (`band_end_ts + 15 min <=` newest snapshot `as_of_ts`; both false with no snapshot). Turns the schema part of T038 green. (FR-040, FR-043, FR-044, data-model E7, E8)
- [ ] T041 [P] [US4] Create `src/data/rules/boarding.py` (pure): `wait_s(arrival, departures_sorted, as_of)` with `bisect` (departure `≥ arrival` and `≤ as_of`, `None` when there is none), `count_riders(arrivals, departures_by_stop, as_of, band_fn)` returning counts keyed by (`local_date`, `band`, `stop`), `BOARDING_THRESHOLDS_S`. Simple method only: no capacity, no FIFO, no rejections (FR-045). Turns T037 green. (FR-040 to FR-042, FR-045)
- [ ] T042 [US4] Add the boarding step to `src/data/pipeline/stop_metrics.py`: read `rider_arrival` from bronze (insert-only read, deduplicated by `source` + `event_id`, `event_ts <= as_of`) and departures from `silver.stop_visits` (the index of T028 serves the lookup), rebuild `gold.stop_boarding_band` each cycle with the cycle's lineage, including the open band; call it from `src/data/pipeline/cycle.py` inside the cycle transaction. Parameterized SQL. Turns T039 green. (FR-040 to FR-044, SC-009 to SC-011)
- [ ] T043 [US4] Bump `RULES_VERSION` to `1.4.0` in `src/data/rules/__init__.py`; turns T038 green. (plan R13)

### Phase 3 verification

- [ ] T044 Verify Phase 3, one command at a time, results written into `verification.md`: (1) Host suite → 0 failed, coverage ≥ 80 %; (2) then Andon → same; (3) Live check under `pulsoflota-verify` with `c1_bunching.json`: `gold.stop_boarding_band` rows per band and the view's `closed` / `final` flags read through `COMPOSE_PROJECT_NAME=pulsoflota-verify docker compose exec -T db psql ...`; Q-P1 over bands 68–69 returns the oracle probabilities (62.5 % at ≤ 5 min for band 69, 100 % at ≤ 10 min for bands 68 and 69) once the run passes 22:45:00Z; cleanup with the same prefix; (4) Cycle-time measurement: p95 ≤ 250 ms at demo length with all new steps, 4-hour stress figure ≤ 1.5 s; (5) record the US4 oracle table and the band 70 note (open riders in `n_riders`: 42.9 % at ≤ 5 min and 66.7 % at ≤ 10 min versus the mock's 60 % and 93 %, decision 3); (6) Untouched check with this phase's allowed list: `src/data/db/init/008_data_fixes_metrics.sql`, `src/data/rules/{__init__,boarding}.py`, `src/data/pipeline/{stop_metrics,cycle}.py`, the Phase 3 tests and fixtures listed above, `specs/005-data-fixes-metrics/**`. (FR-001, FR-003, FR-040 to FR-045, SC-009 to SC-011, SC-014)

**Checkpoint**: Phase 3 is committable on its own (`RULES_VERSION` 1.4.0).

---

## Phase 4 ✂: Guards (US5 + US6, P2) — cut as a whole if time runs short

**Time**: 1.25 h.

**Goal**: one bad `bus_position` or one future-dated event can no longer blind the dispatcher (FR-050 to FR-053, FR-060 to FR-064, SC-012, SC-013).

**Independent Test**: 99,999 m is rejected through ingestion with `value_out_of_range`; inserted straight into bronze, the cycle still writes a snapshot and the other in-service buses keep their state; a `bus_position` dated 2030-01-01 leaves `as_of_ts` in the simulated day and the other buses `live`.

### Tests first (US5 + US6)

- [ ] T045 [P] ✂ [US5] Write `src/data/tests/unit/test_route_bounds.py` (`FakeConn`, no database): reads `max(distance_along_m)` of `config.ref_stops`; cached after the first non-empty read (a second event does not query again); empty table or `UndefinedTable` → bound unavailable, event accepted, a retry no earlier than 5 s later (injected clock), the log line `route_bound_unavailable` once per outage (fixed vocabulary, no connection data); an `OperationalError` propagates (the retry layer of feature 003 handles it). Fails: module missing. (FR-050, FR-051)
- [ ] T046 ✂ [US5] Write `src/data/tests/integration/test_range_guard.py` (throwaway database): through ingestion, `distance_along_m = 99999` and `5119.5` are rejected with reason `value_out_of_range`, one row in `bronze.rejections` with the original message, nothing in `bronze.events`; `0` and `5119.4` accepted; the same row inserted straight into bronze as the newest report of B-105 at the end of the C1 run gives a cycle that completes and writes a snapshot, B-105 `estimated` and in `sources_down` (`since` = its last report time), no alert from it, the 4 other in-service buses keep their state (SC-012); a later valid position returns B-105 to `live`; a bus with no in-range position has NULL position columns and is absent from `corridor_now.buses`; unreadable bound at ingestion keeps capturing events; `git diff feature/004-scenario-injectors -- contracts docs/adr` is empty (FR-053). On the unfixed code it fails with `ValidationError` in `CorridorNowV100`. (FR-050 to FR-053, SC-012)
- [ ] T047 [P] ✂ [US6] Write `src/data/tests/unit/test_clock_guard.py` (pure, no database): `trusted_clock(latest_by_bus, limit_s)` for 0, 1, 2, 3 and 5 buses (0: no data clock; 1: newest report, nobody untrusted; 2: the bus ahead by more than 120 s is untrusted; 3+: one outlier cannot move `median_low`); exactly 120 s trusted and 121 s untrusted; even number of others uses the lower middle value; all buses within 5 s → `as_of` equals the old `max(event_ts)` (FR-064); two buses far apart; no import of any wall clock or `arrival_ts` (FR-063); `MIN_BUSES_FOR_CLOCK_GUARD = 2` is a named constant in `rules/clock.py`, the limit is `ESTIMATED_AFTER_S` (FR-062). Fails: module missing. (FR-060, FR-062, FR-063, FR-064)
- [ ] T048 ✂ [US6] Write `src/data/tests/integration/test_clock_guard_refresh.py` (throwaway database, C1 stream plus one `bus_position` of B-101 dated 2030-01-01): `resolve_as_of(conn, "data")` stays on or after 2026-11-24T22:00Z and not in 2030; the other buses stay `live` in 100 % of the cycles after the injection; B-101 is `estimated`, in `sources_down`, and no alert or recommendation targets it; a later valid B-101 report returns it to `live` while the 2030 event stays in bronze (latest by arrival, US6.4); one bus alone reporting uses its own latest report (limit documented, US6.5); the simulator at its normal pace has no untrusted bus in any cycle and the golden hashes are unchanged by this phase (US6.6). On the unfixed code `resolve_as_of(conn, "data")` returns 2030-01-01. (FR-060 to FR-064, SC-013)
- [ ] T049 ✂ [US6] Update `src/data/tests/unit/test_refresh_loop.py` (`FakeConn` for the per-bus latest-report query, `resolve_clock` returning `ClockDecision`, the `refresh_cycle` log line gaining `untrusted_buses`, the WARNING `clock_guard` line when the set changes) and `src/data/tests/unit/test_rules_version.py` to expect `1.5.0`. Fails. (FR-061, plan R13)

### Implementation (US5 + US6)

- [ ] T050 ✂ [US5] Create `src/data/ingestion/route_bounds.py`: read `max(distance_along_m)` from `config.ref_stops` on the ingestion connection, cache after the first non-empty read, retry no earlier than 5 s after a failure, fail-open while unreadable, log `route_bound_unavailable` once per outage; no new dependency and no new environment variable. Turns T045 green. (FR-050, FR-051)
- [ ] T051 ✂ [US5] Add the range predicate to `src/data/ingestion/validate.py` (**the only change allowed there**: `bus_position` with `distance_along_m` above the bound → reason `value_out_of_range`; 0 and the bound itself valid) and make `src/data/ingestion/bronze.py` store the rejection (`bronze.rejections`, original message kept) through the existing path; no JSON Schema change. Turns the ingestion part of T046 green. (FR-050, FR-051, FR-053)
- [ ] T052 ✂ [US5] Edit `src/data/rules/sql/silver_position_history.sql` (only `0 <= distance_along_m <= route_end`, `route_end = max(config.ref_stops.distance_along_m)`) and `src/data/rules/sql/silver_bus_current_state.sql` (position columns and waiting test from the newest in-range position; `data_quality = estimated` when the newest report is old, or the newest `bus_position` by `(event_ts, id)` is out of range, or the bus is in the new `untrusted_buses` array parameter, default empty; `last_report_ts` unchanged); `src/data/pipeline/silver.py` gains `rebuild_silver(conn, as_of_ts, max_bronze_id, untrusted_buses=())`. No `try/except` around the snapshot builder. Turns the pipeline part of T046 green. (FR-052, data-model E9)
- [ ] T053 [P] ✂ [US6] Create `src/data/rules/clock.py` (pure): `ClockDecision(as_of, untrusted)`, `trusted_clock(latest_by_bus, limit_s)` with `median_low` of the other buses, `MIN_BUSES_FOR_CLOCK_GUARD = 2`; no wall clock, no `arrival_ts`. Turns T047 green. (FR-060 to FR-064)
- [ ] T054 ✂ [US6] Wire the guard: `src/data/refresh/run.py` `resolve_clock(conn, mode, now_fn)` returns `ClockDecision` (per-bus newest report by arrival, largest bronze `id`, non-backend, the three bus event types), `resolve_as_of` returns only `as_of`, the `refresh_cycle` JSON line gains `untrusted_buses` and the `clock_guard` WARNING is written when the set changes; `src/data/pipeline/cycle.py` `run_cycle(..., untrusted_buses=frozenset())` passes it to `rebuild_silver`; the `compute` CLI passes none; `REFRESH_CLOCK=wall` unchanged. Untrusted buses appear in `sources_down` and classification treats them as `estimated` (no alert, no recommendation target). Turns T048 and T049 green. (FR-060 to FR-064, SC-013)
- [ ] T055 ✂ Bump `RULES_VERSION` to `1.5.0` in `src/data/rules/__init__.py`; run the whole Host suite to catch existing tests that ingest positions above 5,119.4 m (risk in the plan; the five timeline builders peak at 4,320 m) and report each such test instead of weakening the rule. (plan R13, Risks)

### Phase 4 verification

- [ ] T056 ✂ Verify Phase 4, one command at a time, results written into `verification.md`: (1) Host suite → 0 failed, coverage ≥ 80 %; (2) then Andon → same, coverage ≥ 80 % (this is the CI-ready gate for the whole story); (3) Live check under `pulsoflota-verify` with `c1_bunching.json`: inject one `bus_position` with `distance_along_m = 99999` through the ingestion container's stdin path and confirm a row in `bronze.rejections` with `value_out_of_range`; insert the 99999 row straight into bronze with `COMPOSE_PROJECT_NAME=pulsoflota-verify docker compose exec -T db psql ...` and confirm the next `refresh_cycle` log line has `status` ok and a new snapshot; inject a 2030-01-01 `bus_position` of B-101 and confirm `gold.snapshots.as_of_ts` of later snapshots stays in 2026-11-24, B-101 is in `sources_down`, the other buses `live`; cleanup with the same prefix; (4) Cycle-time measurement: p95 ≤ 250 ms at demo length with every step, 4-hour stress ≤ 1.5 s; (5) Untouched check, **final form (SC-014)**: `git diff feature/004-scenario-injectors -- contracts docs/adr` is empty and `git diff --stat feature/004-scenario-injectors` shows no change to `docs/data-contract.md`, `src/data/db/init/001`–`007`, bronze table definitions, `.github/` including `CODEOWNERS`, `src/data/simulator/**`; allowed list for this phase: `src/data/ingestion/{route_bounds,validate,bronze}.py` (`validate.py` for the range check only), `src/data/rules/{__init__,clock}.py`, `src/data/rules/sql/{silver_position_history,silver_bus_current_state}.sql`, `src/data/pipeline/{silver,cycle}.py`, `src/data/refresh/run.py`, the Phase 4 tests listed above, `specs/005-data-fixes-metrics/**`. (FR-001, FR-003, FR-050 to FR-053, FR-060 to FR-064, SC-012 to SC-014)

**Checkpoint**: Phase 4 is committable on its own (`RULES_VERSION` 1.5.0).

---

## Phase 5: Polish — `verification.md`

**Time**: 0.25 h.

- [ ] T057 Close `specs/005-data-fixes-metrics/verification.md` (runs whether or not Phase 4 was cut): the baseline of T001; old and new golden hashes, the 24 factors and the one-off git comparison; the data owner's Phase 1 verifier output and sign-off (T020); the oracle table with the **measured** numbers (stop EWT +25.8 s / 27 and +10.6 s / 28, live and band figures, bunched +116.6 s, terminal headways 615 / 595 / 605 s, US4 counts and the band 70 note); cycle-time table per phase (median / p95 / max at demo length, 4-hour stress) against the 250 ms and 1.5 s budgets; coverage per phase and the final Andon figure; the `RULES_VERSION` history 1.1.0 → 1.5.0 (or → 1.4.0 if Phase 4 was cut); the lost-departure limit (decision 1) and the H-8 note (cycle grows linearly with bronze, about 60,000 rows reach 5 s); SC-001 to SC-014 each marked met or not met with the evidence (SC-012, SC-013 "not built" if cut). End with the **data-contract impact list**, copied from `specs/005-data-fixes-metrics/contracts/README.md` ("Impacts for the data owner's later contract step"), one row per document: `docs/data-contract.md` v0.2 (Q4; §3B H4 and Q12), ADR-0007, ADR-0006 §6, ADR-0003 and `contracts/read/`, ADR-0002 and `contracts/turn1-events/` (`value_out_of_range`), `specs/002-silver-gold-baselines/` (FR-024, SC-007), `specs/004-scenario-injectors/` (Phase 3, R7), `data/reference/SOURCES.md`; with the compatibility summary. State plainly that this story edits none of those documents; the data owner edits `docs/data-contract.md` and the ADRs later. Also list the spec lines that still quote pre-US1 numbers if the data owner has not amended them. (FR-003, FR-012, SC-002, SC-014)

---

## Dependencies & Execution Order

### Phase dependencies (strictly sequential)

- **Phase 1** has no dependency. **T020 (data owner's verifier) blocks Phase 2**; Phase 2 starts only after the sign-off is in `verification.md`.
- **Phase 2** depends on Phase 1 (current reference, `RULES_VERSION` 1.2.0, `silver.stop_visits` first-stop departures).
- **Phase 3** depends on Phase 2 (`silver.stop_visits` index, `008`, the oracle module, `pipeline/stop_metrics.py`).
- **Phase 4** depends on Phase 3 only for the shared files (`cycle.py`, `rules/__init__.py`, the table lists in test helpers); it adds no dependency on US3 or US4 logic. Cut as a whole.
- **Phase 5** depends on every phase that was built.

### Within a phase

- Tests are written and seen failing **before** the code they check (red rule).
- Phase 1 order: T001 → T002–T007 → T008 → T009 → T010 → T011 → T012 → T013–T015 → T016 → T017 → T018 → T019 → T020. T005 can only fail for the right reason after T009 (regenerated CSV); T012 lists the 18 failures that justify T013–T015.
- Phase 2 order: T021–T027 → T028 → T029 → T030, T031 → T032 → T033 → T034 → T035.
- Phase 3 order: T036–T039 → T040 → T041 → T042 → T043 → T044.
- Phase 4 order: T045–T049 → T050 → T051 → T052 → T053 → T054 → T055 → T056.
- Files shared between tasks are never marked [P]: `test_reference_build.py` (T002, T003), `rules/__init__.py` (T018, T034, T043, T055), `008_data_fixes_metrics.sql` (T028, T040), `pipeline/stop_metrics.py` (T032, T042), `pipeline/cycle.py` (T033, T042, T054), `test_rules_version.py` (T007, T024, T038, T049), `oracle_stop_metrics.py` (T021, T036).

### Parallel opportunities

```text
Phase 1 tests:   T002 | T004 | T006 | T007            (T003 after T002, T005 after T004's setup)
Phase 1 re-pins: T013 | T014 | T015                      (three files, constants only)
Phase 2 tests:   T021 | T022 | T023 | T027
Phase 2 rules:   T030 | T031                             (different files, pure)
Phase 3 tests:   T036 | T037
Phase 4 tests:   T045 | T047
Phase 4 rules:   T053 alongside T050–T052                (clock vs ingestion/silver)
```

---

## Implementation Strategy

1. **MVP**: Phases 1–3 (US1 through US4). US1 + US2 change the numbers every later oracle depends on, so they go first and are gated by the data owner's verifier (T020). US3 follows because ADR-0007 compares EWT before and after a hold. US4 reuses the stop departures and the oracle module.
2. Each phase ends green and is committed alone by the human (Conventional Commits, e.g. `fix(reference): convert SIMM FECHAHORA to local hour`, `feat(gold): stop-based EWT`, `feat(gold): P(board ≤ t) counts`, `fix(ingestion): reject positions beyond the route end`).
3. Stop at any checkpoint: the repository is consistent (suite green, `RULES_VERSION` matches the phase, `verification.md` updated).

### Time budget (agent time, matches the plan's ~6 h)

| Phase | Stories | Tasks | Time |
|---|---|---|---|
| 1 | US1 + US2 (gate T020) | T001–T020 (20) | 1.25 h |
| 2 | US3 | T021–T035 (15) | 2.25 h |
| 3 | US4 | T036–T044 (9) | 1.00 h |
| 4 ✂ | US5 + US6 | T045–T056 (12) | 1.25 h |
| 5 | Polish (`verification.md`) | T057 (1) | 0.25 h |
| | **Total** | **57** | **6.0 h** |

The data owner's verifier wait in T020 is not agent time and is not counted.

### Cut list (in this order, if time runs short)

1. **Phase 4 as a whole (US5 + US6, T045–T056, saves 1.25 h)**: either all or none. Without it, SC-012 and SC-013 are reported "not built" in T057, `RULES_VERSION` ends at 1.4.0, and the risk (one bad event blinds the dispatcher) stays open and is written in `verification.md`. Do not leave Phase 4 half-built: a partial guard (for example only the clock) must not be committed.
2. **Never cut**: US1, US2, US3, US4 (Phases 1–3) and the verification tasks of each phase.

---

## Notes

- [P] tasks = different files, no dependency on an unfinished task. Every task names its files and the FR/SC ids it covers.
- Commit after each phase, never before its verification task and (Phase 1) the data owner's gate.
- Agents never commit or push (blocked in their permissions).
- Out of scope, do not build: FIFO P(board ≤ t), per-hour planned headway, history layer H1–H4, cycle performance (H-8), backward position jumps and unknown stop ids (H-6, H-7), a silence-bracket rule for lost departures, any edit to `contracts/`, ADR text or `docs/data-contract.md`.
