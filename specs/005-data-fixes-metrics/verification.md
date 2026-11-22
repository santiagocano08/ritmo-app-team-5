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
