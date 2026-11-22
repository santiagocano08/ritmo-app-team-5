# Verification: 005 data fixes and metrics

Branch `feature/005-data-fixes-metrics`, based on `9f03695`. Agent: implement-code. Nothing committed.

## Phase 1 (US1 + US2), T001 to T019

Start 2026-11-22T03:35Z (UTC, approx.; first command of the session). End 2026-11-22T04:30Z.
Phase 1 exit gate (T020) is **open**: it belongs to the data owner's verifier.

## Baseline (T001)

Run on `git archive HEAD` exported to `/tmp/base005` (the working tree was not touched), with `data/raw/` copied in.

| Item | Value |
|---|---|
| Host suite, command `uv run --extra dev pytest -m "not slow and not live" -p no:cacheprovider -q` | 804 passed, 4 skipped, 5 deselected, 0 failed; coverage 96.40 % (04:00:47Z to 04:05:36Z) |
| Andon baseline on unchanged code | **not run separately**: `docker compose` in a copy of the repo would address the default project. The Andon run after the changes is below |
| Old golden hashes | seed 42 `51a5e9b3…39e1` (3,851 lines, 1,439,431 B); seed 7 `6bd20707…0132` |
| Old CSV | `17 h = 0.5011` |
| `RULES_VERSION` | `1.1.0` |
| Cycle time, C1 seed 42, 2,700 s, 108 cycles, 2,877 events | median 47.7 ms, p95 67.0 ms, max 69.8 ms (R12: 48 / 68 / 81) |

## Regenerated CSV (T009, T010)

`python -m src.data.reference.build`; `git diff --stat data/reference/` shows only `congestion_factor.csv` and `SOURCES.md`.

Comparison with `git show HEAD:data/reference/congestion_factor.csv`: new `h` = old `(h + 5) mod 24`, **maximum difference 0.0** over the 24 hours.

New factors by local hour 0..23: 0.5194, 0.5360, 0.5498, 0.5656, 0.5400, 0.5226, 0.5261, 0.5184, 0.5200, 0.5223, 0.5119, 0.5102, 0.5011, 0.4941, 0.4878, 0.4856, 0.4794, 0.4816, 0.4575, 0.4675, 0.4883, 0.4985, 0.4991, 0.5023.

| Anchor | Old | New |
|---|---|---|
| 17 h | 0.5011 | 0.4816 |
| Slowest hour | 23 h | 18 h (0.4575) |
| Highest factor | 08 h | 03 h (0.5656) |

## Golden hashes (T011)

Simulator CLI, 3,600 s, no scenario, no holds.

| Seed | Old | New | Lines | Bytes |
|---|---|---|---|---|
| 42 | `51a5e9b3063667320a6e66cab6293f84197822378783724dd664b6f6865d39e1` | `8bae0e5229b2e547fac181f0f87176809d71be7a80600a4b066832b6274690bc` | 3,851 → 3,831 | 1,439,431 → 1,433,630 |
| 7 | `6bd20707cf9aaccc852b6f8431e1129b759321b69f5cd06e5697c1638e0ab132` | `27a8206e4bcf896b54f847521ae80d65db9db260c2ba1431422e04b244d4df7e` | n/a → 3,844 | n/a → 1,437,557 |

Both equal the plan's dry-run values and the values pinned by T006.

## The 18 tests moved by US1 (T012)

Host suite run after regenerating the CSV (T006 already re-pinned): **19 failed**. Nine were the time-pinned tests below (the expected set). The other 10 were my own red tests for later tasks (6 headway unit tests, `test_rules_version`, 3 terminal-headway cases), so the set matched. The 9 golden-hash tests passed after T006 (their new values come from T011).

Re-pinned values (constants only, assertions untouched):

| Test | Old | New |
|---|---|---|
| golden hash, seed 42 and 7 (6 hash tests + `test_seed_42_shape`) | see table above | see table above |
| `test_c1_waits_for_the_first_arrival_at_or_after_start_s` | arrival 725 s | 715 s |
| `test_hold_extends_the_total_dwell_to_the_requested_seconds` | arrival 1650, departure 1740 | 1665, 1755 |
| `test_hold_keeps_reporting_with_doors_open_and_the_bus_does_not_move` | window `1650 < t < 1740` | `1665 < t < 1755` (still 17 reports) |
| `test_decision_must_precede_the_arrival_strictly` | decision 1650 / 1649, dwell (1650, 1740) | 1665 / 1664, (1665, 1755) |
| `test_second_order_for_the_same_visit_is_a_conflict_and_never_runs` | (1650, 1740) | (1665, 1755) |
| `test_forced_compliance_gives_executed` | 22:27:30Z to 22:29:00Z | 22:27:45Z to 22:29:15Z |
| `test_same_decision_delivered_twice_runs_once` | 22:29:00Z | 22:29:15Z |
| `test_two_orders_for_the_same_visit_run_the_first_only` | 22:29:00Z | 22:29:15Z |
| `test_pre_written_decision_is_on_the_board_before_the_first_event` | 22:27:30Z to 22:29:00Z | 22:27:45Z to 22:29:15Z |

The golden-hash row counts as 9 tests (T012 text: "the 9 golden-hash tests" and "9 time-pinned tests"). New values come from the regenerated stream (B-103 arrives at P-887 22:27:45Z, leaves 22:29:15Z after the 90 s hold, as the mock prints).

Rework: `src/data/tests/integration/test_instruction_status.py::test_lineage_columns_and_table_shape` pinned `rules_version == "1.1.0"`. It failed in the first full run after the T018 bump and is not in the task list. I changed that one literal to `1.2.0` (same kind of change as T007).

## Final runs (T019)

| # | Command | Result | Time (UTC) |
|---|---|---|---|
| 1 | `uv run --extra dev pytest -m "not slow and not live" -p no:cacheprovider` (DATABASE_URL to localhost) | **820 passed, 0 failed, 0 skipped**, 5 deselected; coverage 96.44 % (gate 80 %); `rules/headway.py` 100 % | 04:11:48Z to 04:17:38Z |
| 2 | `docker compose --profile tools build tests && docker compose --profile tools run --rm tests` | **817 passed, 8 skipped, 0 failed**; coverage 96.44 % | 04:17:43Z to 04:21:30Z |

An earlier host run (04:05Z) had 1 failed / 819 passed: the `1.1.0` literal above. Passed count 820 is above the baseline 804 plus the new tests.
The 8 skipped in the container are the tests that need `data/raw/` or the host (not mounted); in the baseline copy 4 skipped.

## Live check (T019 step 3)

Project `pulsoflota-verify` (every command had `-p pulsoflota-verify` on the same line); db host port 5433; services `db`, `ingestion`, `refresh` only. `SIM_SEED=42 SIM_DURATION_S=2700 SIM_PACE_S=0.15 REFRESH_CLOCK=data REFRESH_INTERVAL_S=1`, scenario `c1_bunching.json`. The fixture is not in the image (`.dockerignore`), so it was mounted read-only at `/scn` through a throwaway override file `/tmp/verify-override.yml` (outside the repo, `-f docker-compose.yml -f /tmp/verify-override.yml`). The first attempt ran with a path that does not exist in the image (0 events) and a too-fast pace (3 snapshots); both were rerun.

Result: 2,881 bronze events, 84 snapshots, 0 `cycle_failed`. Terminal headways from `gold.corridor_now` at the first snapshot at or after each instant:

| Instant | Snapshot | Bus | Distance | `headway_ahead_s` | State |
|---|---|---|---|---|---|
| 22:20:40Z | 22:20:55Z | B-103 | 176.0 m | 611.2 | regular |
| 22:30:35Z | 22:30:40Z | B-104 | 42.3 m | 596.4 | regular |
| 22:40:40Z | 22:41:00Z | B-105 | 138.8 m | 608.6 | regular |

All inside 300 to 900 s, no `gap` from the terminal wait. (Snapshots are about 15 to 30 s apart in data time, so these are a few seconds after the instant; the exact 615 / 595 / 605 s are asserted by `test_terminal_headway.py` at the exact `as_of`.) Cleanup: `docker compose -p pulsoflota-verify down -v`; the default stack was not touched.

## Terminal headways (T005, exact `as_of`)

`test_terminal_headway.py`, throwaway database, C1 seed 42: 615 / 595 / 605 s (tolerance 1 s) at 1,240 / 1,835 / 2,440 s. Before the fix (stale CSV and old rule) the test was red for both reasons (the third case got 595.9 s with the old CSV).

## Cycle time (T019 step 4)

Scratch recipe (throwaway database, C1 seed 42, 2,700 s, `run_cycle(conn, as_of, notify=False)` every 25 s, 108 cycles, 2,881 events). Script `/tmp/cycletime.py` (not in the repo).

| Run | Median | p95 | Max |
|---|---|---|---|
| Baseline (T001) | 47.7 ms | 67.0 ms | 69.8 ms |
| After Phase 1, run 1 | 48.7 ms | 67.1 ms | 79.7 ms |
| After Phase 1, run 2 | 48.6 ms | 67.8 ms | 70.2 ms |
| Live `refresh_cycle` `duration_ms` (99 cycles, while ingesting, host under load) | 97 ms | 155 ms | 173 ms |

Required p95 ≤ 250 ms: met in both.

## Untouched check (T019 step 5)

`git diff --stat feature/004-scenario-injectors` on `contracts/`, `docs/adr/`, `docs/data-contract.md`, `src/data/db/init/`, `.github/`, `Dockerfile`, `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `.env.example`, `src/pulsoflota/config.py`, `src/data/simulator/`, `src/data/ingestion/`: **empty**.

Changed files:
- `data/reference/congestion_factor.csv`, `data/reference/SOURCES.md` (CODEOWNERS path)
- `src/data/reference/build.py`, `src/data/reference/sources.py`
- `src/data/rules/__init__.py`, `src/data/rules/headway.py` (CODEOWNERS path)
- `src/data/pipeline/gold.py`
- tests: `unit/test_reference_build.py`, `unit/test_headway.py`, `unit/test_rules_version.py`, `unit/test_simulator_golden_hash.py`, `unit/test_scenario_injectors.py`, `integration/test_terminal_headway.py` (new), `integration/test_hold_loop.py`, `integration/test_hold_poller.py`, `integration/test_instruction_status.py`
- `specs/005-data-fixes-metrics/tasks.md` (marks), `specs/005-data-fixes-metrics/verification.md`

## T020

Open. Hand-over: the regenerated `data/reference/congestion_factor.csv` in the working tree.

## T020 — Phase 1 exit gate (data owner's verifier, 2026-11-21 23:30)

The independent mock (`mock_calculos.py`, run from a copy so its results file is not overwritten) was re-run on the Phase 1 working tree with the regenerated `data/reference/congestion_factor.csv`: **+25.8 s (27 intervals) without the hold, +10.6 s (28 intervals) with it**, hold saving 15.2 s, hold at P-887 17:27:45–17:29:15 local, slowest local hour 18 h. The whole report is identical to the post-US1 oracle file. Targeted tests (headway, reference build, golden hash, terminal headway, rules version): 57 passed. Gate passed; Phase 2 may start.

## Phase 2 (US3: stop-based EWT), T021 to T035

Start 2026-11-22T04:29Z. End 2026-11-22T05:12Z (UTC). Agent: implement-code. Nothing committed. Phase 3 not started.
`.specify/extensions.yml` does not exist, so no hooks applied.

### Oracle results (all exact; none changed to fit the code)

Independent oracle `src/data/tests/fixtures/oracle_stop_metrics.py` (raw simulator events, no import of the rules). Self-check before any code existed, then reproduced by gold:

| Check | Plan value | Measured |
|---|---|---|
| 16-minute window (22:28:55, 22:44:55]Z, P-888..P-900, no hold | 27 intervals, +25.8 s (S h 13,290, S h2 8,660,350) | 27, +25.82 s, 13,290, 8,660,350 |
| same window, 90 s hold of B-103 at P-887 | 28 intervals, +10.6 s | 28, +10.6 s (hold saving 15.2 s) |
| Live 15-minute value at 22:44:55Z, all 18 stops, no hold / hold | 33 / +17.6 s, 35 / +2.8 s | 33 / +17.596 s, 35 / +2.8 s |
| Live value, P-888..P-900 from the per-stop rows | 25 / +21.0 s, 27 / +1.8 s | 25 / +21.0 s, 27 / +1.8 s |
| Band 69, no hold / hold (P-888..P-900) | 6 / 5 intervals | 6 (S h 4,770, S h2 4,190,600) / 5 |
| Band 70, no hold / hold | 25 / 27 intervals | 25 (12,180; 7,819,850) / 27 |
| Bands 69 + 70 sums, no hold | 31, 16,950, 12,010,450 | 31, 16,950, 12,010,450 |
| Bands 69 + 70 sums, hold | 32, 18,165, 12,361,525 | 32, 18,165, 12,361,525 |
| Band 68 on P-888..P-900 | no row | no row (the 18-stop table has 1 band-68 row, on another stop) |
| Bunched snapshot 22:30:00Z, no hold | 15 headways, +116.6 s | 15, +116.636 s |
| Gold band rows vs oracle grouped by band, all stops, hold and no hold | 0 differences | 0 differences (n, S h, S h2, S hp, S hp2, n_excluded) |

Band sums are the sums of the stop sums over the closing departures; the corridor row is the sum of the 18 stop rows (checked: 33 = 33 on the live stack).

Plan figure that does not occur: "B-103 195 s behind". On this stream B-103 stays bunched at 204 to 230 s (1,340 s to 2,080 s) and the stop EWT is +80 to +129 s over the whole stretch; `test_bunched_snapshot_has_positive_stop_ewt` asserts it for every such snapshot (38 snapshots checked). Not an oracle value; the plan's own oracles above are unchanged.

### Minimum sample (`min_stop_headways = 5`)

Corridor row of `gold.service_metric`: `computable = n >= 5 and S h > 0`. Below it `mean_wait_s`, `scheduled_wait_s` and `ewt_s` are NULL and `n_headways` keeps the count. Checked every 100 s over the 2,700 s run against the oracle (both branches occur: n in 1..4 not computable; n >= 5 computable); exactly 5 and exactly 4 in `test_service_metric.py`. A stop with fewer than two usable departures gets a row with `n_headways = 0`, `computable = false` and zero sums (never 0 as a value); it adds nothing to the corridor sums.

### Test runs (one at a time)

| # | Command | Result | Time (UTC) |
|---|---|---|---|
| 1 | `uv run --extra dev pytest -m "not slow and not live" -p no:cacheprovider -q` (host, DATABASE_URL to localhost) | first full run 9 failed / 852 passed (see Rework); after the fixes **862 passed, 0 failed, 0 skipped**, 5 deselected; coverage **96.66 %** (gate 80 %); `rules/stop_metrics.py` 100 %, `rules/service_metric.py` 100 %, `pipeline/stop_metrics.py` 100 % | 04:48:55Z to 04:55:51Z |
| 2 | `docker compose --profile tools build tests && docker compose --profile tools run --rm tests` | run as `docker compose -p pulsoflota-verify --profile tools ...` with `POSTGRES_PORT=5433 API_PORT=8001` (the default project has a running stack on 5432/8000; the rule is to never touch it). **859 passed, 8 skipped, 0 failed**; coverage **96.66 %**. Same 8 container-only skips as Phase 1. The fresh volume applied `008` through the init directory | 04:56:08Z to 05:00:33Z |

Passed count 862 vs 820 at the end of Phase 1: +42 new tests.

### Live check (project `pulsoflota-verify`, ports 5433 / 8001, fixture mounted through `/tmp/verify-override.yml`)

`SIM_SEED=42 SIM_DURATION_S=2700 SIM_PACE_S=0.15 SIM_SCENARIO_FILE=/scn/c1_bunching.json REFRESH_CLOCK=data`, fresh volume (`008` from `docker-entrypoint-initdb.d`):

| Check | Result |
|---|---|
| bronze events / snapshots | 2,881 / 84, last snapshot 22:44:55Z |
| `gold.service_metric_stop` rows of the newest snapshot | 18 |
| newest `gold.service_metric` row | 33 headways, ewt 17.596 s, computable (= oracle +17.6 s) |
| sum of the 18 stop rows vs corridor row | 33 = 33 |
| `gold.stop_ewt_band` | band 68: 1 row; band 69: 10 rows, 15 headways; band 70 absent (closes at 22:45:00Z, last snapshot 22:44:55Z); band 68 on P-888..P-900: 0 rows |
| two consecutive cycles over the same bronze (second run, 3 s apart) | identical band table: md5 `d4a1bbbe7b9c213e8e7a20da60035abf`, 11 rows both times |
| `cycle_failed` in the refresh log | 0 (both runs) |
| cleanup | `docker compose -p pulsoflota-verify --profile tools down -v`; default stack untouched and still running |

The first attempt at the md5 comparison had a quoting error in my psql command and I removed the stack before fixing it, so the live check was run a second time with a shorter pace (47 snapshots) for the md5 comparison. No product impact.

### Cycle time (scratch recipe: throwaway database, C1 seed 42, 2,700 s, 108 cycles, 2,881 events; `/tmp/cycletime.py`, not in the repo)

| Run | Median | p95 | Max |
|---|---|---|---|
| Baseline (T001, before the story) | 47.7 ms | 67.0 ms | 69.8 ms |
| After Phase 1 | 48.6 ms | 67.8 ms | 70.2 ms |
| After Phase 2, run 1 | 61.8 ms | 88.5 ms | 99.8 ms |
| After Phase 2, run 2 | 60.7 ms | 88.7 ms | 96.8 ms |
| Live `refresh_cycle` `duration_ms` (130 cycles, host also ingesting) | 144 ms | 165 ms | 180 ms |
| 4 simulated hours, 15,388 events, 15 cycles near the end (`/tmp/stress4h.py`) | 1,428 ms | | 1,475 ms |

Required: p95 <= 250 ms at demo length (met, 88.7 ms; the new steps add about 13 ms at the median, inside the 100 ms budget) and the 4-hour figure <= 1.5 s (met, but with 25 ms of margin; baseline was 1.27 to 1.31 s). The H-8 linear growth stays as recorded in the plan.

### Rework and findings

1. First full host run: 9 failed. Seven of them (`test_rebuild.py`) recreate silver from `004` alone, so the new `silver.stop_visits.estimated_at_departure` column was missing, and replay of the dropped gold tables did not include the new ones. `test_incident_gold.py` deleted `gold.snapshots` before the new child table. `test_waiting_buses.py` pinned the old spatial `n_headways == 1`. All fixed in the tests (listed below). No rule or oracle was relaxed.
2. `test_instruction_status.py` pinned `rules_version == "1.2.0"` (same kind of literal as `test_rules_version.py`); changed to `1.3.0`.
3. `test_waiting_buses.py::test_gold_ignores_waiting_buses_for_ahead_summary_and_metric`: that timeline has stop departures without arrivals, so no `silver.stop_visits` row exists. Under the stop-based definition the metric is `0 headways, NULL, not computable` and all stop rows are zero. The assertion now says that (it also asserts the per-stop rows). The intent (waiting buses add nothing) is kept. Flagged for the data owner.
4. `test_gold_contract.py::test_service_metric_is_stored_with_the_cycle` pinned the old spatial `n_headways == 4`. `bb.normal()` has positions only and no stop events, so the fixture alone gives 0 headways. I added crafted stop visits (three buses, three stops, 600 s apart; expected 6 headways, mean 300 s, EWT 0) and a second test for "positions only: not computable".
5. D1 silence fixture (`d1_silence.json`): the departure that follows the silence is preceded by a report within 120 s, so it is not flagged; the lost departures simply leave no row (the R4 limit). The exclusion path is therefore covered by a crafted stream (`test_estimated_departure_excludes_both_headways_and_counts_them`: B-102 last reported at 200 s and departs at 400 s) and by the pure unit tests, not by D1. The D1 stream is still compared with the oracle (band rows equal).
6. `conftest.py` needed no change (it uses `clear_all`, which now deletes the two new tables before `snapshots`).

### Untouched check

`git diff --stat feature/004-scenario-injectors` on `contracts/`, `docs/adr/`, `docs/data-contract.md`, `src/data/db/init/001`-`007`, `.github/`, `Dockerfile`, `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `.env.example`, `src/pulsoflota/config.py`, `src/data/simulator/`, `src/data/ingestion/`, `.kiro/`, `.specify/`: **empty**. `git status` shows no change outside the list below.

### Files changed in Phase 2 (CODEOWNERS paths marked)

Created: `src/data/db/init/008_data_fixes_metrics.sql` (CODEOWNERS: db), `src/data/rules/stop_metrics.py` (CODEOWNERS: rules), `src/data/pipeline/stop_metrics.py`, `src/data/tests/fixtures/oracle_stop_metrics.py`, `src/data/tests/unit/test_stop_metrics.py`, `src/data/tests/integration/test_stop_ewt_gold.py`.

Modified: `src/data/rules/__init__.py` (RULES_VERSION 1.3.0, CODEOWNERS: rules), `src/data/rules/service_metric.py` (CODEOWNERS: rules), `src/data/rules/sql/silver_stop_visits.sql` (CODEOWNERS: silver SQL), `src/data/pipeline/gold.py`, `src/data/pipeline/cycle.py`; tests `unit/test_service_metric.py`, `unit/test_rules_version.py`, `integration/test_schema_init.py`, `integration/test_gold_contract.py`, `integration/test_idempotency.py`, `integration/test_scenarios_gold.py`, `integration/test_incident_gold.py`, `integration/test_rebuild.py`, `integration/test_waiting_buses.py`, `integration/test_instruction_status.py`, `fixtures/gold_support.py`; `specs/005-data-fixes-metrics/tasks.md` (marks), `specs/005-data-fixes-metrics/verification.md`.

## Phase 3 (US4: P(board <= t)), T036 to T044

Start 2026-11-22T05:09Z. End 2026-11-22T05:33Z (UTC). Agent: implement-code. Nothing committed. Phase 4 not started.
`.specify/extensions.yml` does not exist, so no hooks applied.

### Oracle results (all exact; none changed to fit the code)

Independent oracle `riders()` / `riders_by_band()` in `src/data/tests/fixtures/oracle_stop_metrics.py` (raw simulator events; no import of `rules/boarding.py`, silver or gold). Self-check passed **before** any implementation existed, then gold reproduced it with 0 differences per (band, stop):

| Band (local) | n_riders | <= 5 min | <= 10 min | <= 15 min | Plan | Oracle | Gold |
|---|---|---|---|---|---|---|---|
| 68 (17:00-17:15) | 9 | 3 | 9 | 9 | 9 / 3 / 9 / 9 | same | same |
| 69 (17:15-17:30) | 16 | 10 | 16 | 16 | 16 / 10 / 16 / 16 | same | same |
| 70 (17:30-17:45) | 21 | 9 | 14 | 15 | 21 / 9 / 14 / 15 | same | same |

46 riders in all, 37 at P-883 (plan: 46 and 37). Band 70 has 6 riders not in `n_board_le_15` (open, still in `n_riders`; the test checks that all 6 are in band 70 and have no departure at or before `as_of`).
Q-P1 at 22:45:00Z: bands 68 + 69 final: 25 riders, 52.0 % at <= 5 min (13/25), 100 % at <= 10 and <= 15 min. Band 69 alone: 62.5 % at <= 5 min, 100 % at <= 10 min. Band 68 alone: 33.3 % and 100 %. Band 70 (provisional, all riders in the denominator): 42.9 % at <= 5 min, 66.7 % at <= 10 min (decision 3; the mock's 60 % and 93 % leave the 6 open riders out).

### Read query (Q-P1, as written in `contracts/gold-stop-metrics.md`)

Run by `test_stop_boarding_gold.py` with parameters `day`, `from_band`, `to_band`, over `gold.stop_boarding_band_v ... AND final`: NULL (not 0) when no rider (bands 10-11 and the open band 70), per-stop variant equals the oracle.

### Test runs (one at a time)

| # | Command | Result | Time (UTC) |
|---|---|---|---|
| 1 | `uv run --extra dev pytest -m "not slow and not live" -p no:cacheprovider -q` (host, `DATABASE_URL` to localhost) | **887 passed, 0 failed**, 5 deselected; coverage **96.75 %** (gate 80 %); `rules/boarding.py` 100 %, `pipeline/stop_metrics.py` 100 % | 05:14:21Z to 05:21:45Z |
| 2 | `docker compose --profile tools build tests && docker compose --profile tools run --rm tests` | run as `POSTGRES_PORT=5433 API_PORT=8001 docker compose -p pulsoflota-verify --profile tools ...` (the default project has a running stack on 5432/8000 and is never touched). **884 passed, 8 skipped, 0 failed**; coverage **96.75 %**. Same 8 container-only skips as before | 05:21:52Z to 05:26:23Z |

Passed count 887 vs 862 at the end of Phase 2: +25 new tests.

### Live check (project `pulsoflota-verify`, ports 5433 / 8001, fixture mounted through `/tmp/verify-override.yml`)

`SIM_SEED=42 SIM_DURATION_S=2700 SIM_PACE_S=0.05 SIM_SCENARIO_FILE=/scn/c1_bunching.json REFRESH_CLOCK=data`, fresh volume (`008` through the init directory):

| Check | Result |
|---|---|
| bronze events / newest snapshot | 2,881 / 22:44:55Z (the stream ends at 22:44:55Z, so the run itself never passes 22:45:00Z) |
| view at 22:44:55Z | band 68 closed + final (9 / 3 / 9 / 9); band 69 closed, not final (16 / 10 / 16 / 16); band 70 open (21 / 9 / 14 / 15) |
| one extra cycle at 22:45:00Z through `run_cycle` inside the refresh container (verify project only) | band 68 closed + final; band 69 closed + final; band 70 closed, not final; same counts |
| Q-P1 over bands 68-69 | 25 riders, 52.0 % / 100 % / 100 % |
| `cycle_failed` in the refresh log | 0 |
| cleanup | `docker compose -p pulsoflota-verify --profile tools down -v`; default stack untouched and still running |

### Cycle time (scratch recipe, throwaway database, C1 seed 42, 2,700 s, 108 cycles, 2,881 events)

| Run | Median | p95 | Max |
|---|---|---|---|
| Baseline (T001) | 47.7 ms | 67.0 ms | 69.8 ms |
| After Phase 2 | 60.7 ms | 88.7 ms | 96.8 ms |
| After Phase 3, run 1 | 65.1 ms | 93.9 ms | 187.2 ms (one outlier) |
| After Phase 3, run 2 | 65.8 ms | 96.4 ms | 107.3 ms |
| Live `refresh_cycle` `duration_ms` (18 cycles) | 152 ms | 159 ms | 160 ms |
| 4 simulated hours, 15,388 events, 15 cycles near the end, three runs | median 1,442 / 1,439 / 1,435 ms | | max 1,519 / 1,543 / 1,507 ms |

p95 <= 250 ms at demo length: met (about 94-96 ms; the boarding step adds about 5 ms at the median). **4-hour figure <= 1.5 s: the median meets it (about 1.44 s); the worst cycle of each run is 1.51 to 1.54 s, slightly over.** Phase 2 recorded median 1,428 / max 1,475 ms. The linear growth is the known H-8 finding; the boarding step adds about 15 ms. Flagged for the data owner; no code was changed to hide it.

### Rework and findings

1. Red first, seen for the expected reason: `test_boarding.py` (`boarding` module missing), the schema and gold tests (table and view missing; `clear_all` failed on the missing table), `test_rules_version` (1.3.0 vs 1.4.0).
2. Four test mistakes of mine, fixed in the tests (no rule or oracle touched): the threshold test used one stop for riders who all see the same next departure (now one stop per case); a CHECK case in `test_schema_init` was actually valid (3, 4, 5 of 5 riders); the builder's `rider_arrival` already appends to `events`, so I had added the event twice.
3. `test_instruction_status.py` pinned `rules_version == "1.3.0"`; changed to `1.4.0` (same kind of literal as `test_rules_version.py`).
4. Lists of gold tables in `gold_support.clear_all`, `test_incident_gold`, `test_scenarios_gold`, `test_idempotency`, `test_rebuild`, `test_schema_init` gained `stop_boarding_band` (and the view is dropped before the table in the rebuild test).
5. The first live attempt ran the refresh image built in Phase 2 (no `boarding.py`); the table stayed empty. I rebuilt `ingestion` and `refresh` under the verify project (`docker compose -p pulsoflota-verify ... build ingestion refresh`) and repeated the check. No product impact.
6. **Decision on the wording of T039 (f).** The task says band 70 "is `closed = false`" at 22:45:00Z. Data-model E8 defines `closed` as `band_end_ts <= newest as_of_ts`, and band 70 ends at 22:45:00Z, so it is `closed = true`, `final = false` at 22:45:00Z and `closed = false` at 22:44:55Z. I followed E8 (same rule as `stop_ewt_band`, where band 70 appears at 22:45:00Z) and tested both instants. The `final` result (only 68 and 69) is as the plan says.

### Untouched check

`git diff --stat feature/004-scenario-injectors` on `contracts/`, `docs/adr/`, `docs/data-contract.md`, `src/data/db/init/001`-`007`, `.github/`, `Dockerfile`, `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `.env.example`, `src/pulsoflota/config.py`, `src/data/simulator/`, `src/data/ingestion/`, `.kiro/`, `.specify/`: **empty**. `git status` shows only the files below.

### Files changed in Phase 3 (CODEOWNERS paths marked)

Created: `src/data/rules/boarding.py` (CODEOWNERS: rules), `src/data/tests/unit/test_boarding.py`, `src/data/tests/integration/test_stop_boarding_gold.py`.

Modified: `src/data/db/init/008_data_fixes_metrics.sql` (CODEOWNERS: db; adds `gold.stop_boarding_band` and `gold.stop_boarding_band_v`), `src/data/rules/__init__.py` (RULES_VERSION 1.4.0, CODEOWNERS: rules), `src/data/pipeline/stop_metrics.py`, `src/data/pipeline/cycle.py`; tests `fixtures/oracle_stop_metrics.py`, `fixtures/gold_support.py`, `unit/test_rules_version.py`, `integration/test_schema_init.py`, `test_idempotency.py`, `test_incident_gold.py`, `test_scenarios_gold.py`, `test_rebuild.py`, `test_instruction_status.py`; `specs/005-data-fixes-metrics/tasks.md` (marks), `specs/005-data-fixes-metrics/verification.md`.

## Phase 4 (US5 + US6: position range guard and clock guard), T045 to T056

Start 2026-11-22T05:35Z. End 2026-11-22T06:05Z (UTC). Agent: implement-code. Nothing committed.
`.specify/extensions.yml` does not exist, so no hooks applied. Checklists: approved by the data owner (2026-11-21), not edited.
`docs/turns-ritmo.md` lists "impossible position" as deferred for turn 1. The approved spec and tasks.md (US5) call for it, so
it was built as specified; the data owner may want to record it as pulled forward.

### Red first

Seen failing for the stated reason before any implementation:

| Test file | Red reason |
|---|---|
| `unit/test_route_bounds.py`, `unit/test_clock_guard.py` | module missing (`ModuleNotFoundError` / `ImportError`) |
| `unit/test_refresh_loop.py` (new and changed cases), `unit/test_rules_version.py` | `resolve_clock` missing, `untrusted_buses` missing in the log line, `guard_state` unknown, `1.4.0 != 1.5.0` |
| `integration/test_clock_guard_refresh.py` | `refresh.resolve_clock` missing |
| `integration/test_range_guard.py` | after the ingestion module existed, I put the two unfixed silver SQL files back for one run: `CycleError` (cause `ValidationError` in `CorridorNowV100`, as research R10 measured). The fixed SQL was restored from a copy and is what the suite ran |

### Guard results (all exact; no oracle changed)

| Check | Plan | Measured |
|---|---|---|
| 99,999 m and 5,119.5 m through ingestion | rejected, `value_out_of_range`, original message kept, nothing in `bronze.events` | same (1 row in `bronze.rejections` each, 0 in events) |
| 0 m and 5,119.4 m through ingestion | accepted | accepted |
| Unreadable bound (fake bound that returns None) | event accepted | accepted, stored in bronze |
| 99,999 m inserted straight into bronze as the newest report of B-105 (C1 seed 42, as_of 22:44:15Z) | cycle completes, snapshot written, B-105 `estimated`, in `sources_down` with `since` = its last report time, no alert | same. B-105 keeps its last valid distance, `bus_state = regular`, no `gold.incident` row mentions it |
| Other buses (SC-012) | keep their state | the silver rows of B-101..B-104 are identical before and after the insert (all columns); the corridor buses of gold keep state, quality and distance |
| Later valid position of B-105 | back to `live` | `live`, distance 4,300.0 |
| Bus with no in-range position | NULL position columns, absent from `corridor_now.buses`, in `sources_down` | same |
| C1 seed 42 positions outside 0 to 5,119.4 m | 0 | 0 of 2,700 (min 0.0, max 5,119.4) |
| 2030-01-01 `bus_position` of B-101 (injected at 1,300 s while B-101 is on the corridor) | `as_of` stays in the simulated day, other buses `live` in every later cycle | first cycle after the injection: `as_of` in 2026-11-24, `untrusted = {B-101}`, B-101 `estimated` and in `sources_down`, no alert; every later cycle (every 25 events): the other buses `live`, 0 snapshots in 2027 or later |
| Later valid B-101 report | `live` again, 2030 event stays in bronze | clock decision has no untrusted bus; 1 bronze row dated 2030 |
| 0 buses | wall clock | wall clock (`ClockDecision(now, {})`) |
| 1 bus alone (its only report is dated 2030) | its own newest report, nobody untrusted (limit documented) | `as_of` = 2030-01-01, nobody untrusted |
| 2 buses (one dated 2030) | guard applies | the 2030 bus is untrusted, clock = the other |
| No bad event (C1, 1,200 s) | nobody excluded, `as_of` = old `max(event_ts)` | identical to the old query |
| Simulator at normal pace, C1 full run, a cycle every 25 events | no untrusted bus in any cycle | none in more than 50 cycles |

Notes on two plan figures that do not match this stream (not oracle values, reported):

1. SC-012 says "the 4 other in-service buses". On C1 seed 42 at most 3 buses are on the corridor at once (probe every 100 s,
   1,200 to 2,700 s), so the test checks the 4 other buses of the fleet in `silver.bus_current_state` (unchanged) and the other
   corridor buses in gold. B-105 is on the corridor at 22:44:15Z with 1 other bus (B-104).
2. B-101 finishes its trip at about 1,550 s, so the future-event test injects at 1,300 s; at 2,200 s B-101 is not on the corridor
   and cannot be in `sources_down` (that list is for buses on the corridor or waiting).
3. A leading bus that is `estimated` stays `leader`; only `bunched` and `gap` are forced to `regular` (`classify.py`, unchanged).
   The tests accept `regular` or `leader` and check there is no alert.

### Test runs (one at a time)

| # | Command | Result | Time (UTC) |
|---|---|---|---|
| 1 | `uv run --extra dev pytest -m "not slow and not live" -p no:cacheprovider -q` (host, `DATABASE_URL` to localhost) | **933 passed, 0 failed, 0 skipped**, 5 deselected, 1 warning; coverage **96.84 %** (gate 80 %); `rules/clock.py` 100 %, `ingestion/route_bounds.py` 98 %, `ingestion/validate.py` 96 %, `ingestion/bronze.py` 98 %, `refresh/run.py` 85 % (loop `main()` is not unit tested) | 05:42:57Z to 05:51:19Z |
| 2 | `docker compose --profile tools build tests && docker compose --profile tools run --rm tests`, run as `POSTGRES_PORT=5433 API_PORT=8001 docker compose -p pulsoflota-verify --profile tools ...` (the default project has a running stack on 5432/8000, never touched) | **929 passed, 9 skipped, 0 failed**; coverage **96.84 %**. The 9 skips are the 8 container-only ones plus the new `git diff` check (no git in the image) | 05:51:25Z to 05:56:33Z |

Passed count 933 vs 887 at the end of Phase 3: +46 new tests.

T055: running the whole host suite after the version bump found **no** existing test that ingests a position above 5,119.4 m.
The only test touched by the bump is the literal `rules_version == "1.4.0"` in `integration/test_instruction_status.py`,
changed to `1.5.0` (same kind of change as `test_rules_version.py`, not in the task list).

### Live check (project `pulsoflota-verify`, ports 5433 / 8001, fixture mounted through `/tmp/verify-override.yml`)

`SIM_SEED=42 SIM_DURATION_S=2700 SIM_PACE_S=0.5 SIM_SCENARIO_FILE=/scn/c1_bunching.json REFRESH_CLOCK=data REFRESH_INTERVAL_S=1`, fresh volume.

| Step | Result |
|---|---|
| 99,999 m `bus_position` of B-105 through the ingestion container's stdin (`docker compose -p pulsoflota-verify run --rm -T --no-deps ingestion python -m src.data.ingestion.run`) | `{'accepted': 0, 'rejected': 1, 'by_reason': {'value_out_of_range': 1}}`; 1 row in `bronze.rejections` (`value_out_of_range`, event type `bus_position`, distance 99999.0); 0 events above 5,119.4 m in bronze |
| ingestion container paused, 99,999 m row for B-101 inserted straight into bronze with psql (id 681, `event_ts` = newest) | next `refresh_cycle`: `status = estimated` (a snapshot, not an error), `max_bronze_id` 681; `sources_down` = `[{"bus_id": "B-101", "since": "2026-11-24T22:10:55Z"}]`; B-101 `estimated` at its last valid distance 2,784.5 m, B-102 `live`; 0 `cycle_failed` |
| 2030-01-01 `bus_position` of B-101 through the ingestion container | next cycle: `as_of_ts` 2026-11-24T22:10:55Z, `untrusted_buses: ["B-101"]`, B-101 in `sources_down`, B-102 `live` |
| ingestion resumed | log: WARNING `{"event": "clock_guard", "untrusted_buses": ["B-101"]}` once, then `{"event": "clock_guard", "untrusted_buses": []}` once (after B-101's next real report); last snapshot 22:14:15Z, **0 snapshots after 2027-01-01**; the 2030 row is still in bronze |
| `cycle_failed` in the refresh log | 0 (checked after the 99,999 m insert and again at the end) |
| cleanup | `docker compose -p pulsoflota-verify ... down -v`; default stack untouched and still running |

Rework (live check): my first straight-insert statement failed (`event_id` is a uuid column, I passed text); the second stream position was
already past B-101's bad row, so I paused the ingestion container and inserted again to catch the cycle. No product impact.

### Cycle time (scratch recipe: throwaway database, C1 seed 42, 2,700 s, 108 cycles, 2,881 events)

| Run | Median | p95 | Max |
|---|---|---|---|
| Baseline (T001) | 47.7 ms | 67.0 ms | 69.8 ms |
| After Phase 3, run 1 / run 2 | 65.1 / 65.8 ms | 93.9 / 96.4 ms | 187.2 / 107.3 ms |
| After Phase 4, run 1 | 66.2 ms | 100.3 ms | 120.2 ms |
| After Phase 4, run 2 | 67.5 ms | 98.0 ms | 109.8 ms |
| Live `refresh_cycle` `duration_ms` (about 90 cycles, host also ingesting, pace 0.5) | about 35 to 75 ms | | |
| 4 simulated hours, 15,388 events, 15 cycles near the end, Phase 4 code, four runs | median 656 (an odd run), 1,547, 1,549, 1,547 / 1,556 ms | | max 1,610 / 1,629 / 1,613 / 1,616 / 1,598 ms |
| Same stress run with the Phase 3 versions of the two silver SQL files put back, two runs | median 1,430 / 1,442 ms | | max 1,537 / 1,484 ms |

**Phase 4 makes the cycle slower.** At demo length the median is +1 to +2 ms and p95 +4 ms (still far below 250 ms). At 4 hours the
median goes from about 1.44 s to about 1.55 s (+7 %), and the worst cycle from 1.51 to 1.54 s to 1.60 to 1.63 s. The A/B above
(Phase 3 SQL versus Phase 4 SQL on the same code and machine) isolates the cause to `silver_bus_current_state.sql` and
`silver_position_history.sql`: the extra `positions` CTE casts every `bus_position` payload once more and a second
`DISTINCT ON` finds the newest position. **The 4-hour figure of 1.5 s is now exceeded by the median as well as by the worst
cycle.** I did not change the SQL to hide it. A possible fix is to compute the range flag once in `silver.position_history`
(already filtered) and join it instead of casting in `bus_current_state`; it is outside tasks.md, so left to the data owner. The first
run of the stress series reported median 656 ms; I have no explanation and treated it as an outlier (the other five runs agree).

### Untouched check (final form, SC-014)

`git diff --stat feature/004-scenario-injectors` on `contracts/`, `docs/adr/`, `docs/data-contract.md`, `src/data/db/init/001`-`007`,
`.github/`, `Dockerfile`, `pyproject.toml`, `uv.lock`, `docker-compose.yml`, `.env.example`, `src/pulsoflota/config.py`,
`src/data/simulator/`, `.kiro/`, `.specify/`: **empty**. `test_no_contract_or_adr_changed` also asserts it for `contracts` and
`docs/adr`. `src/data/ingestion/validate.py` changed only for the range check (new optional `route_end_m` argument and one
predicate). No new environment variable, dependency or config key (`MIN_BUSES_FOR_CLOCK_GUARD` is a named constant; the 120 s is
`ESTIMATED_AFTER_S`).

### Files changed in Phase 4 (CODEOWNERS paths marked)

Created: `src/data/ingestion/route_bounds.py`, `src/data/rules/clock.py` (CODEOWNERS: rules), `src/data/tests/unit/test_route_bounds.py`,
`src/data/tests/unit/test_clock_guard.py`, `src/data/tests/integration/test_range_guard.py`, `src/data/tests/integration/test_clock_guard_refresh.py`.

Modified: `src/data/ingestion/validate.py`, `src/data/ingestion/bronze.py`, `src/data/rules/__init__.py` (RULES_VERSION 1.5.0, CODEOWNERS: rules),
`src/data/rules/sql/silver_position_history.sql` and `src/data/rules/sql/silver_bus_current_state.sql` (CODEOWNERS: silver SQL),
`src/data/pipeline/silver.py`, `src/data/pipeline/cycle.py`, `src/data/refresh/run.py`; tests `unit/test_refresh_loop.py`, `unit/test_rules_version.py`,
`integration/test_instruction_status.py`; `specs/005-data-fixes-metrics/tasks.md` (marks), `specs/005-data-fixes-metrics/verification.md`.

## Phase 5 (Polish): closing summary, T057

Nothing is committed. Phases 1 to 3 are committed (`1cc5fb8`, `e8f0eb1`, `e7cca43`); Phase 4 and this file are in the working tree.

### Start of the story and baseline

See "Baseline (T001)" above: 804 passed on the unchanged code, coverage 96.40 %, `RULES_VERSION` 1.1.0, cycle median 47.7 ms.
Golden hashes (old and new), the 24 factors and the one-off git comparison (maximum difference 0.0): see "Regenerated CSV" and
"Golden hashes" above. The data owner's Phase 1 verifier output and sign-off are in "T020" above.

### Oracle table, measured values

| Oracle | Plan | Measured | Phase |
|---|---|---|---|
| Stop EWT, P-888..P-900, (22:28:55, 22:44:55]Z, no hold | +25.8 s, 27 intervals | +25.82 s, 27 | 2 |
| Same, 90 s hold | +10.6 s, 28 intervals | +10.6 s, 28 (saving 15.2 s) | 2 |
| Live value 22:44:55Z, 18 stops, no hold / hold | 33 / +17.6 s, 35 / +2.8 s | 33 / +17.596 s, 35 / +2.8 s | 2 |
| Bands 69 + 70 sums (n, Σh, Σh²), no hold / hold | 31, 16,950, 12,010,450 / 32, 18,165, 12,361,525 | identical | 2 |
| Bunched snapshot 22:30:00Z | +116.6 s, 15 headways | +116.636 s, 15 | 2 |
| Terminal headways 22:20:40Z / 22:30:35Z / 22:40:40Z | 615 / 595 / 605 s | 615 / 595 / 605 s (±1 s) | 1 |
| US4 band 68 / 69 / 70 riders; ≤5, ≤10, ≤15 min | 9 / 16 / 21; 3/9/9, 10/16/16, 9/14/15 | identical; 46 riders, 37 at P-883; band 70 has 6 open riders in `n_riders` only | 3 |
| Position range, C1 seed 42 | 0 of 2,700 outside 0 to 5,119.4 m | 0 of 2,700 | 4 |
| Clock guard | see "Guard results" | all as planned | 4 |

### Cycle time per phase (scratch recipe, median / p95 / max)

| After | Median | p95 | Max | 4 h stress median / max |
|---|---|---|---|---|
| Baseline | 47.7 ms | 67.0 ms | 69.8 ms | 1.27 to 1.31 s (plan) |
| Phase 1 | 48.6 ms | 67.8 ms | 70.2 ms | not measured |
| Phase 2 | 60.7 ms | 88.7 ms | 96.8 ms | 1.428 s / 1.475 s |
| Phase 3 | 65.8 ms | 96.4 ms | 107.3 ms | about 1.44 s / 1.51 to 1.54 s |
| Phase 4 | 67.5 ms | 98.0 ms | 109.8 ms | about 1.55 s / 1.60 to 1.63 s |

Budgets: p95 ≤ 250 ms at demo length is met in every phase. The 4-hour budget of 1.5 s is met only through Phase 2; from Phase 3
the worst cycle is over it, and in Phase 4 the median is too (see "Cycle time" in Phase 4).

### Coverage per phase

| Phase | Host suite | Andon |
|---|---|---|
| Baseline | 804 passed, 96.40 % | not measured on unchanged code |
| 1 | 820 passed, 96.44 % | 817 passed, 8 skipped, 96.44 % |
| 2 | 862 passed, 96.66 % | 859 passed, 8 skipped, 96.66 % |
| 3 | 887 passed, 96.75 % | 884 passed, 8 skipped, 96.75 % |
| 4 (final) | **933 passed, 96.84 %** | **929 passed, 9 skipped, 96.84 %** |

### `RULES_VERSION` history

1.1.0 (start) → 1.2.0 (Phase 1) → 1.3.0 (Phase 2) → 1.4.0 (Phase 3) → 1.5.0 (Phase 4).

### Known limits

- **Lost departures (decision 1).** A departure that was never reported leaves no `silver.stop_visits` row, so it is not counted in
  `n_excluded` and the headway across it is a longer, single interval. Only a departure whose previous report is more than 120 s older is
  flagged and excluded.
- **H-8, linear cycle growth.** The cycle rebuilds silver from all of bronze, so its time grows with bronze: about 60,000 rows reach 5 s.
  At 4 simulated hours (15,388 events) a cycle takes about 1.5 s.
- **Clock guard.** One bus alone uses its own newest report (a bad event from a lone bus hijacks the clock); with a majority of buses
  far in the future there is no trustworthy reference. The guard needs at least 2 buses.
- **Range bound.** Read from `config.ref_stops`, which `refresh`/`compute` load. Until then ingestion accepts every position and logs
  `route_bound_unavailable` once; rows accepted in that window are handled by the silver rule (G2).

### Success criteria

| SC | Result | Evidence |
|---|---|---|
| SC-001 | met | 24 factors equal the independent recomputation, maximum difference 0; 17 h = 0.4816 (was 0.5011) |
| SC-002 | met | new golden hashes seed 42 `8bae0e52…90bc`, seed 7 `27a8206e…df7e`; old ones recorded |
| SC-003 | met | 615 / 595 / 605 s at the three instants, 0 terminal `gap`; live stack 611 / 596 / 609 s at the nearest snapshots |
| SC-004 | met | the EWT at those instants is not 211, 467 or 731 s |
| SC-005 | met | live and band rows equal the oracle, 0 differences, with and without the hold |
| SC-006 | met | +25.8 s (27) and +10.6 s (28), exact |
| SC-007 | met in meaning, number not reproduced | the plan's "195 s behind" snapshot does not exist in this stream (B-103 stays 204 to 230 s behind); EWT is above 0 (+80 to +129 s) in all 38 bunched snapshots; at 22:30:00Z it is +116.6 s |
| SC-008 | met | adding or removing a bus with no departure in the window changes EWT by 0 s |
| SC-009 | met | counts equal the oracle, 0 differences (9 / 16 / 21 riders, 46 in all) |
| SC-010 | met | riders without a departure are only in `n_riders` (6 open riders in band 70) |
| SC-011 | met | two gold rebuilds give identical rows |
| SC-012 | met, with the note on "4 other buses" above | 99,999 m rejected (host tests and live), straight-inserted row gives a snapshot, other buses unchanged |
| SC-013 | met | `as_of` stays in 2026-11-24, 0 snapshots in 2027 or later, other buses `live` in every cycle after the injection |
| SC-014 | met | host 933 passed (96.84 %), Andon 929 passed (96.84 %), `git diff` of `contracts/` and `docs/adr/` against `feature/004-scenario-injectors` empty |

Spec lines that still quote numbers that do not occur: SC-007 ("195 s behind", see above) and SC-012 ("the 4 other in-service buses", at most 3 are on the corridor at once in C1). The spec otherwise carries the post-US1 oracles.

### Data-contract impact list (copied from `contracts/README.md`)

This story edits **none** of these documents. The data owner edits `docs/data-contract.md` and the ADRs later.

| Document | Section | What changes | Number or example |
|---|---|---|---|
| `docs/data-contract.md` v0.2 | Q4 (service KPI) | `gold.service_metric` has the same columns but is now stop-based over a trailing 15-minute window and `computable` needs 5 headways. The example row (`n_headways = 1`, `ewt_s = −27.5`, `computable = true`) is no longer possible | one headway now gives `computable = false` and NULL values |
| `docs/data-contract.md` v0.2 | §3B H4 `report_quality_band` and Q12 | `sum_headway_s`, `sum_headway_sq_s`, `sum_planned_s`, `sum_planned_sq_s`, `n_headways` are sums of stop headways per band, produced by `gold.stop_ewt_band`; `n_riders`, `n_board_le_5/10/15` have a producer in `gold.stop_boarding_band`. H4 is per operator; these tables are per stop (one operator, `OP-01`, today) | band 70, P-888..P-900: 25 headways, Σh 12,180 s (C1 seed 42, no hold) |
| ADR-0007 | Decision: EWT before and after | EWT before and after are stop-based and trailing-window; "EWT before" early in the day can be not computable (`no_data`). The `c1_bunching` numbers in `recommendation_effect` change meaning | same 90 s hold: −15.2 s on the 16-minute window (+25.8 s → +10.6 s) |
| ADR-0006 | §6 history layer | The layer that sums these rows consumes new definitions and two new source tables | none |
| ADR-0003, `contracts/read/` | `service_metric`, gate decision on EWT | No field change. Only the wording of what EWT means may need an update. `distance_along_m` already has `maximum: 5119.4` in `corridor_now` (the cause of US5) | none |
| ADR-0002, `contracts/turn1-events/` | rejection reason `value_out_of_range` | Now also used for a `bus_position` beyond the route end, a bound that comes from reference data, not from the schema | 5,119.4 m |
| `specs/002-silver-gold-baselines/` | FR-024, SC-007, US2 scenario 6 | The spatial EWT (300 s and 900 s give +75 s) is superseded; the same arithmetic now applies to stop headways | none |
| `specs/004-scenario-injectors/` | Phase 3, research R7 | The effect table clamps the corridor EWT at 0. With a stop-based EWT that is often positive and computable only with at least 5 headways; the clamp and the window of "before" and "after" need review before Phase 3 is built | none |
| `data/reference/SOURCES.md` | `congestion_factor.csv` | Regenerated by this story (the `FECHAHORA` is UTC and is converted) | 17 h: 0.5011 → 0.4816 |

Compatibility summary: `gold.service_metric` keeps its columns and types, with different numbers and many more `computable = false`
rows in the first minutes of a run. `corridor_now`, `decision_inputs` and `source_status` keep their schemas; `headway_ahead_s` of a bus
leaving the terminal changes from 1,240 s to 615 s (C1 seed 42, 22:20:40Z), and an unplaceable or untrusted bus is `estimated` and listed
in `sources_down`. Snapshot ids change (the rules version is part of the hash). No JSON Schema, ADR or `docs/data-contract.md` text was edited.
