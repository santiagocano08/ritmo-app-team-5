# Verification: Decision Model (Simulation-Based MPC)

Built phase by phase. Each phase appends its section.

## Phase 1: projection and scoring core (T001–T014)

**Time**: start 2026-11-22T11:55Z, end 2026-11-22T12:24Z (UTC). Branch `feature/006-decision-mpc`, base commit `4385758`.
**Environment**: dedicated compose project `pf006` (`docker compose -p pf006 --env-file /tmp/pf006.env ...`, Postgres on 55432; port 5432 was held by another project's stack, which was not touched). Stack removed at the end with `docker compose -p pf006 --env-file /tmp/pf006.env down -v`.

### Commands

```text
host:   set -a; . /tmp/pf006.env; set +a; export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}"
        uv run --extra dev pytest -m "not slow and not live" -p no:cacheprovider -q
CI:     docker compose -p pf006 --env-file /tmp/pf006.env --profile tools build tests
        docker compose -p pf006 --env-file /tmp/pf006.env --profile tools run --rm tests
phase:  uv run --extra dev pytest src/data/tests/unit -k "projector or mpc_score or alight or mpc_params" -q
```

### Results

| Run | Baseline (T001) | End of phase 1 |
|---|---|---|
| Host suite | 911 passed, 22 skipped, 5 deselected; coverage 96.84 % (6 min 45 s) | 973 passed, 23 skipped, 5 deselected; coverage 97.25 % (7 min 7 s) |
| CI-ready | 911 passed, 27 skipped; coverage 96.84 % (3 min 16 s) | 973 passed, 28 skipped; coverage 97.25 % (3 min 12 s) |
| Phase subset (`-k projector or mpc_score or alight or mpc_params`) | n/a | 63 passed, 1 skipped (the `rules/mpc.py` literal scan waits for phase 2) |

New modules: `rules/mpc_params.py` 100 %, `rules/projector.py` 99 % (line 296: guard for a zero segment time). Golden-hash tests (`test_simulator_golden_hash.py`) are inside both suites and unchanged. Baseline `git status` was clean at head `4385758`. No `RULES_VERSION` bump (stays `1.5.0`).

Red step: before the code existed, all 7 test modules failed at collection with `ModuleNotFoundError: src.data.rules.projector` (and `mpc_params`), the stated reason. After the projector was written, two tests were red: `test_formula_matches_the_simulator` (placeholder tolerance 0.0, fixed in T013) and `test_changing_one_field_changes_the_projection` (see Rework).

### Hand-computed against projected (all within 1 s; every one matched on the first run)

Corridor: 4 stops 1,000 m apart, 100 s per segment, grid 5 s, bus at 630 m. Values are the departure seconds after `as_of`; derivations are in each test's docstring.

| Case (test) | Hand | Projector |
|---|---|---|
| (a) one bus, empty (`test_projector_crafted`) | stops 1, 2, 3: 50, 160, 270 | 50, 160, 270 |
| (b) leader/follower, queue 6, 0.1/s | L: 45, 155, 280; F: 125, 235, 365 | same |
| (c) full leader, 7 left behind | L: 20, 130, 320; F stop 1: 145 | same |
| (d) zero queue, 20 on board | stop 1: 20 | 20 |
| 17:55 hour boundary (400 s then 800 s segments) | 510, 1320 (17:00: 410, 820, 1230) | same |
| hour-18 rate (0 then 360/h) | 570, 1380 | same |
| hold 60 s at stop 1 | 100, 210, 340; O = 500 | same |
| slow-down 20 % / 10 % / 20 % for 100 s | 185, 340 / 175, 320 / 180, 310; O = 500 / 222.2 / 200 | same |
| reserve dispatch (4 riders at stop 0) | 145, 255, 365, 485; C = 900 | same |
| adjust ±60, −120 (slot 300) | 370, 190 (base 310) | same |
| broken until 300 | 410 | 410 |
| skip stop 1 (empty) | stop 2: 160, stop 3: 280 | same |
| W with four buses, 0.02/s, window 1500 | W = 6300, riders 30, W/riders 210 | same; `stop_metrics` also gives 210 |
| W with a full vs empty leader, window 200 | 1550 vs 990, riders 26 | same |
| saving with a reserve | (7200 − 1380) / 4 = 1455.0 | 1455.0 |

No hand value had to be corrected. One wrong hand line was a typo in a test docstring before the first run (17:00 last departure written as 1240, correct 1230); it was fixed before the code ran, not to make a test pass.

### Alighting share against the simulator (T003, T013)

Seeds 42 and 43 pooled, 3,600 s. Sample size is the riders on board (`Σ occupancy_in`, at least 30), not riders boarded at the stop (see Decisions).

| Run | Stops compared (skipped) | Largest \|diff\| formula | Largest \|diff\| prototype | Tolerance |
|---|---|---|---|---|
| scale 1.0 | 12 (6) | **0.0385** | 0.0500 | **0.06** (margin 0.0215) |
| scale 10 | 17 (1) | **0.0551** | 0.5263 | **0.10** (margin 0.0449) |

The margin is justified in `research.md` R2. At scale 1 the two formulas cannot be told apart, so the check that fails for the prototype formula runs at scale 10.

### Bare projector timing (T014)

7 buses (5 in service, 2 reserves; 18 stops, reference M1 and rates, real train batches), `time.perf_counter`, 30 repetitions. Planned value in research R9: about 2 ms.

| Projections per cycle | Per projection (median / max) | Total per cycle (median) |
|---|---|---|
| 11 | 0.189 ms / 0.202 ms | 2.1 ms |
| 31 | 0.196 ms / 0.198 ms | 6.1 ms |

About 10 times faster than the allowance. The projection has 56 departures for that input. Measured on a laptop, not on the CI image.

### Untouched check

`git status --short` shows only new files: `src/data/rules/mpc_params.py`, `src/data/rules/projector.py`, and the unit tests below. `specs/006-decision-mpc/tasks.md` (task marks), `research.md` (R2 tolerance) and this file changed. No change to ADRs, `docs/data-contract.md`, bronze DDL, `.github/`, `CODEOWNERS`, `.kiro/`, `.specify/`, `src/api/`, the frontend, `contracts/` or any existing file.

### Files

CODEOWNERS paths (`src/data/rules/`): `mpc_params.py`, `projector.py`. Tests (new): `test_mpc_params.py`, `test_alight_share.py`, `test_projector_crafted.py`, `test_projector_hour_boundary.py`, `test_projector_actions.py`, `test_mpc_score.py`, `test_projector_determinism.py`, `test_projector_extras.py` (added for branch coverage and validation), `projector_support.py` (builders). Docs: `tasks.md`, `research.md`, `verification.md`.

### Rework and decisions

- `test_changing_one_field_changes_the_projection` first used `step_s=10`, which gave the same departures as 5 s for that input (all times were multiples of 10). Test input was weak, not the code; changed to a 7 s grid (37 s becomes 42 s).
- The prototype-formula test could not fail at scale 1 (0.05 against 0.0385), so a scale-10 run was added (research R2).
- The wait-versus-EWT link uses the instants at which riders board (bus arrival), as the simulator does, not the departure: a departure adds a dwell that varies with the riders boarded, so headways between departures differ. The numbers agree exactly on boarding instants (210 s).
- Semantics fixed in code where the tasks were silent (documented in the `projector.py` docstring): a slow-down window starts at the departure from the target stop; `adjust_departure` shifts the slot of the named waiting bus and not before 0; a skipped stop records no arrival or departure and keeps the riders on board; a saving with zero riders is 0.0; the last stop's departure is recorded.
- `quality` of a bus takes `sources_down` as well as `live` and `estimated` (M8 lists the first two); FR-007 needs both.
- The simulator golden hash and every existing test are unchanged and green.


## Phase 2: inputs, candidates, top 3, `gold.recommendation`, seed retirement (T015–T049)

**Time**: start 2026-11-22T12:29Z, end 2026-11-22T15:00Z (UTC). Branch `feature/006-decision-mpc`. The data owner committed a spec amendment (`c35d654`, projection record as phase 2b: FR-035, FR-036, SC-016) while this phase was in progress; it adds no Phase 2 task and phase 2b was **not** started.
**Environment**: compose project `pf006` only (`docker compose -p pf006 --env-file /tmp/pf006.env ...`, Postgres on 55432; port 5432 was held by another project's stack, which was not touched). Cleanup at the end: `docker compose -p pf006 --env-file /tmp/pf006.env down -v`.

### Commands

```text
host:    . /tmp/pf006_host.sh   # sets DATABASE_URL to localhost:55432 from the pf006 env file
         uv run --extra dev pytest -m "not slow and not live" -p no:cacheprovider -q
CI:      docker compose -p pf006 --env-file /tmp/pf006.env --profile tools build tests
         docker compose -p pf006 --env-file /tmp/pf006.env --profile tools run --rm tests
         (run with DATABASE_URL unset in the shell: a shell value wins over the env file and pointed the container at localhost)
generate: uv run --extra dev make generate-read   (twice; git diff --stat identical)
slow:    uv run --extra dev pytest -m slow src/data/tests/integration/test_projection_error.py -s     (T048a, by hand)
live:    docker compose -p pf006 --env-file /tmp/pf006_{A,B,C}.env up -d db / up -d --build refresh
         docker compose -p pf006 --env-file /tmp/pf006_A.env run -d --no-deps --rm --name pf006-ingest-A \
            -v "$PWD/src/data/tests/fixtures/scenarios:/scn:ro" ingestion      # SIM_SCENARIO_FILE=/scn/c1_bunching.json
```

The live env files are `/tmp/pf006.env` plus `SIM_SEED=42 SIM_DURATION_S=2700 SIM_PACE_S=1 SIM_SCENARIO_FILE=/scn/c1_bunching.json` (A), `+ MPC_ENABLED=off` (B), `+ SIM_DEMAND_SCALE=3` (C). The scenario file is mounted because the image excludes `src/data/tests/` (`.dockerignore`), so the recipe's relative path does not exist inside the container.

### Results

| Run | End of phase 1 | End of phase 2 (final) |
|---|---|---|
| Host suite | 973 passed, 23 skipped, 5 deselected; 97.25 % | **1135 passed, 22 skipped, 7 deselected; coverage 97.70 %** (2026-11-22T14:36:23Z to 14:46:02Z) |
| CI-ready | 973 passed, 28 skipped; 97.25 % | **1137 passed, 27 skipped; coverage 97.70 %** (14:52:09Z to 14:57:26Z, 5 min 2 s) |
| Slow (T048a, by hand) | n/a | 2 passed (about 50 s) |

The 7 deselected are the 5 of the baseline plus the two scales of the T048a test. New modules: `rules/mpc.py` 100 %, `rules/mpc_params.py` 100 %, `rules/projector.py` 99 %, `pipeline/recommend.py` 99 % (line 78: no row in `config.decision_model`; line 86: a `bool` branch of the parameter reader that no field uses), `pipeline/holds.py` 100 %.

Red step: each test was written and run before its code. The failures seen were the stated ones: contract fixtures and 1.1.0 variants failed until the schema was edited (12 failures of 79); the schema, queue, inputs, lifecycle and scenario tests failed on `UndefinedTable` / `ModuleNotFoundError: pipeline.recommend`; `rules.mpc` tests failed at import; the seed-dependent tests failed at collection (`RecommendationV100` gone with the regenerated model).

### Gate table (T045)

| Check | Result |
|---|---|
| (1) host suite | green, numbers above |
| (2) CI-ready | green, numbers above |
| (3) `make generate-read` twice | second `git diff --stat` identical to the first; the class is `RecommendationV110` |
| (4) golden hash, seed 42, 3,600 s | `SIM_DEMAND_SCALE` unset: `8bae0e5229b2e547fac181f0f87176809d71be7a80600a4b066832b6274690bc`; `=1.0`: the same; 004/005 reference (`test_simulator_golden_hash.py`): the same. Seed 7 stays in its test. Scale 3 gives `58869dfdce250ed153d53b5ab546d9df74063b3d7f11431c58848e1b2f4f0d52` (a demo setting, not a reference). |
| (5) seed grep | `grep -rIn -e seed_recommendation -e recommendations.json -e SEED_RECOMMENDATIONS_PATH . --exclude-dir=specs --exclude-dir=docs --exclude-dir=.git --exclude-dir=.venv --exclude-dir=__pycache__` gives **0 hits** (also 0 in `.kiro/` and `.specify/`) |
| (6) Untouched check | see "Files"; nothing outside the allowed list changed |

### Live check A, default scale (T046), C1 seed 42, 2,700 s, pace 1 s per 5 s step

- `009_decision_mpc.sql` ran by itself on the fresh volume (`config.decision_model` 1 row, `config.ref_train_arrival` 511 rows, no seed table).
- `gold.mpc_evaluation` is filled while the bunching lasts: 21 of 27 samples in which it had rows showed hold, slow down and reserve evaluated (the others: `reserve_dispatch`, `skip_stop` and `adjust_departure` only, outside the bunching window or with the follower at the last stop). No row targets an `estimated` bus (D1 tests, and the live rows below are on live buses). The model reads no `SIM_DEMAND_SCALE` (static test).
- Rows published at the real reference demand (4): `dispatch reserve B-106` saves 23.5 and 42.6 s per rider; `delay the next departure from P-883 (B-105) by 60 s` saves 19.6 and 17.8 s per rider. **Hold and slow down were evaluated in every bunching cycle and never reached the 15 s threshold**: best hold per cycle (replay, see below) median −2.1 s per rider (range −2.6 to −0.7), best slow down −3.0 (−4.7 to −0.5). Reported, not tuned (risk 3, risk 8).
- Independence check (SC-012): the `api` was started, then `docker compose -p pf006 --env-file /tmp/pf006_C.env stop api`; `refresh` and the ingestion container stayed up and healthy, bronze grew 148 → 278 in 25 s, and `gold.recommendation` kept being updated for the rest of the run (5 rows by the end). This check was made on the first run C, before the input fix of the projection-error section; the later runs A and C had the `api` down too (it was never started in them). In `-p pf006` the refresh container turns `unhealthy` after the feed ends (data clock, declared M3 limit).

### Live check B, demo demand (T047), same recipe, `SIM_DEMAND_SCALE=3`

Live: 6 recommendation rows (reserve B-106 19.7, 60.9, 76.4 and 23.2 s per rider; advance the next departure of B-103 and B-104 by 120 s, 18.3 and 19.1 s per rider); hold, slow down, reserve, adjust departure evaluated while the bunching lasted (23 of 30 samples with rows list all of them). Per-cycle table (the live run holds only the latest cycle in `gold.mpc_evaluation`, so the table comes from the forced-mode replay of `test_recommend_scenarios.py`, same seed, scenario and scale; a cycle every 15 simulated seconds). Every bunching cycle had 10 or 11 evaluated candidates and at most 1 recommendation (scale 1: at most 2). `live rows` counts `proposed` and not `stale` rows in that cycle.

Grouped by consecutive cycles with the same figures (scale 3); the complete per-cycle tables for both scales follow.

| cycles (t, s) | n | snapshot ids | candidates | recommended | best action | best saving (s per rider) | best recommended? |
|---|---|---|---|---|---|---|---|
| 1395–1440 | 4 | `368789ff..9c163a1c` | 11 | 0 | reserve_dispatch B-106 | 63.7–65.3 | no (resting) |
| 1455–1575 | 9 | `23dfa721..d93ae8ce` | 11 | 1 | reserve_dispatch B-106 | 55.7–71.0 | yes |
| 1590–1620 | 3 | `83a84211..925b78e0` | 11 | 0 | reserve_dispatch B-106 | 42.9–49.3 | no (resting) |
| 1635–1695 | 5 | `146641a2..fb4df0a5` | 10 | 0 | reserve_dispatch B-106 | 19.6–38.2 | no (resting) |
| 1710–1710 | 1 | `495587f9..495587f9` | 10 | 0 | reserve_dispatch B-106 | 14.6–14.6 | no (below_threshold) |
| 1725–1770 | 4 | `e47952d5..5bce4237` | 10 | 0 | adjust_departure B-104 -60 s | 12.2–13.6 | no (below_threshold) |
| 1785–1785 | 1 | `ace4201a..ace4201a` | 10 | 1 | adjust_departure B-104 -120 s | 21.4–21.4 | yes |
| 1800–1860 | 5 | `386ced9f..0b85eaf0` | 10 | 0 | reserve_dispatch B-106 | 18.8–79.3 | no (resting) |
| 1875–1995 | 9 | `f817be40..b604901b` | 10 | 1 | reserve_dispatch B-106 | 75.4–86.9 | yes |
| 2010–2280 | 19 | `f267d0fb..ffca4f4f` | 10 | 0 | reserve_dispatch B-106 | 28.0–95.9 | no (resting) |
| 2295–2310 | 2 | `5768a849..fac59e9e` | 10 | 1 | reserve_dispatch B-106 | 15.6–20.8 | yes |
| 2325–2385 | 5 | `f3551940..0c7057e9` | 10 | 0 | adjust_departure B-105 -120 s | 8.2–12.8 | no (below_threshold) |
| 2400–2415 | 2 | `35286d01..8aad9d5c` | 10 | 1 | reserve_dispatch B-106 | 21.3–51.7 | yes |
| 2430–2520 | 7 | `014ad930..4daceb20` | 10 | 0 | reserve_dispatch B-106 | 71.4–102.4 | no (resting) |

Best saving by action type over all bunching cycles (s per rider): scale 3: hold median −5.1 (−7.9 to −1.9), slow down −7.3 (−15.5 to −1.5), reserve dispatch median 63.9 (−11.8 to 102.4), adjust departure 2.7 (−21.1 to 21.4), skip stop 0.0. Scale 1: hold −2.1, slow down −3.0, reserve 19.1 (−18.6 to 68.1), adjust departure 15.1 (0.1 to 23.4), skip stop 0.0. Best action of the cycle: reserve dispatch (66 of 76 cycles at scale 3, 43 of 70 at scale 1) or adjust departure. When the best is not recommended it is `resting` (the same key expired less than 300 s earlier, 43 cycles at scale 3) or `below_threshold` (10).

<details><summary>Complete per-cycle tables</summary>

##### `SIM_DEMAND_SCALE=3`: every cycle with a bunched bus (76 of 160 cycles)

| t (s) | snapshot id | candidates | recommended in the cycle | live rows | best candidate (saving s per rider) | best recommended? (reason if not) |
|---|---|---|---|---|---|---|
| 1395 | `368789ff` | 11 | 0 | 0 | reserve_dispatch B-106 (65.3) | no (resting) |
| 1410 | `50d7ecb6` | 11 | 0 | 0 | reserve_dispatch B-106 (63.7) | no (resting) |
| 1425 | `89286697` | 11 | 0 | 0 | reserve_dispatch B-106 (65.3) | no (resting) |
| 1440 | `9c163a1c` | 11 | 0 | 0 | reserve_dispatch B-106 (64.5) | no (resting) |
| 1455 | `23dfa721` | 11 | 1 | 1 | reserve_dispatch B-106 (60.0) | yes |
| 1470 | `9be64337` | 11 | 1 | 1 | reserve_dispatch B-106 (71.0) | yes |
| 1485 | `bafd3c9f` | 11 | 1 | 1 | reserve_dispatch B-106 (69.6) | yes |
| 1500 | `68e91518` | 11 | 1 | 1 | reserve_dispatch B-106 (69.5) | yes |
| 1515 | `b7f03369` | 11 | 1 | 1 | reserve_dispatch B-106 (64.0) | yes |
| 1530 | `b15d8054` | 11 | 1 | 1 | reserve_dispatch B-106 (65.6) | yes |
| 1545 | `c4fd5946` | 11 | 1 | 1 | reserve_dispatch B-106 (60.9) | yes |
| 1560 | `1ee778e9` | 11 | 1 | 1 | reserve_dispatch B-106 (60.8) | yes |
| 1575 | `d93ae8ce` | 11 | 1 | 1 | reserve_dispatch B-106 (55.7) | yes |
| 1590 | `83a84211` | 11 | 0 | 0 | reserve_dispatch B-106 (49.3) | no (resting) |
| 1605 | `9a43da28` | 11 | 0 | 0 | reserve_dispatch B-106 (44.3) | no (resting) |
| 1620 | `925b78e0` | 11 | 0 | 0 | reserve_dispatch B-106 (42.9) | no (resting) |
| 1635 | `146641a2` | 10 | 0 | 0 | reserve_dispatch B-106 (38.2) | no (resting) |
| 1650 | `2c8f21cc` | 10 | 0 | 0 | reserve_dispatch B-106 (35.0) | no (resting) |
| 1665 | `520b7d8d` | 10 | 0 | 0 | reserve_dispatch B-106 (32.7) | no (resting) |
| 1680 | `c6dcee4d` | 10 | 0 | 0 | reserve_dispatch B-106 (26.3) | no (resting) |
| 1695 | `fb4df0a5` | 10 | 0 | 0 | reserve_dispatch B-106 (19.6) | no (resting) |
| 1710 | `495587f9` | 10 | 0 | 0 | reserve_dispatch B-106 (14.6) | no (below_threshold) |
| 1725 | `e47952d5` | 10 | 0 | 0 | adjust_departure B-104 -60 s (12.2) | no (below_threshold) |
| 1740 | `739fb58a` | 10 | 0 | 0 | adjust_departure B-104 -60 s (12.9) | no (below_threshold) |
| 1755 | `edf2c064` | 10 | 0 | 0 | adjust_departure B-104 -60 s (13.6) | no (below_threshold) |
| 1770 | `5bce4237` | 10 | 0 | 0 | adjust_departure B-104 -60 s (13.5) | no (below_threshold) |
| 1785 | `ace4201a` | 10 | 1 | 1 | adjust_departure B-104 -120 s (21.4) | yes |
| 1800 | `386ced9f` | 10 | 0 | 0 | reserve_dispatch B-106 (18.8) | no (resting) |
| 1815 | `360971b9` | 10 | 0 | 0 | reserve_dispatch B-106 (44.1) | no (resting) |
| 1830 | `18e2f1d0` | 10 | 0 | 0 | reserve_dispatch B-106 (50.0) | no (resting) |
| 1845 | `c4caf394` | 10 | 0 | 0 | reserve_dispatch B-106 (79.3) | no (resting) |
| 1860 | `0b85eaf0` | 10 | 0 | 0 | reserve_dispatch B-106 (74.6) | no (resting) |
| 1875 | `f817be40` | 10 | 1 | 1 | reserve_dispatch B-106 (84.5) | yes |
| 1890 | `dc6e3627` | 10 | 1 | 1 | reserve_dispatch B-106 (82.4) | yes |
| 1905 | `318bf669` | 10 | 1 | 1 | reserve_dispatch B-106 (81.1) | yes |
| 1920 | `6c441f62` | 10 | 1 | 1 | reserve_dispatch B-106 (76.7) | yes |
| 1935 | `573e3db5` | 10 | 1 | 1 | reserve_dispatch B-106 (84.7) | yes |
| 1950 | `bd580cfc` | 10 | 1 | 1 | reserve_dispatch B-106 (81.7) | yes |
| 1965 | `d0655146` | 10 | 1 | 1 | reserve_dispatch B-106 (83.7) | yes |
| 1980 | `f0ced4a1` | 10 | 1 | 1 | reserve_dispatch B-106 (86.9) | yes |
| 1995 | `b604901b` | 10 | 1 | 1 | reserve_dispatch B-106 (75.4) | yes |
| 2010 | `f267d0fb` | 10 | 0 | 0 | reserve_dispatch B-106 (95.9) | no (resting) |
| 2025 | `87804b84` | 10 | 0 | 0 | reserve_dispatch B-106 (91.6) | no (resting) |
| 2040 | `d322655f` | 10 | 0 | 0 | reserve_dispatch B-106 (85.8) | no (resting) |
| 2055 | `3e1a0631` | 10 | 0 | 0 | reserve_dispatch B-106 (78.5) | no (resting) |
| 2070 | `dfe18365` | 10 | 0 | 0 | reserve_dispatch B-106 (74.3) | no (resting) |
| 2085 | `c6d707cb` | 10 | 0 | 0 | reserve_dispatch B-106 (80.1) | no (resting) |
| 2100 | `fd380a4e` | 10 | 0 | 0 | reserve_dispatch B-106 (82.8) | no (resting) |
| 2115 | `de1ad71b` | 10 | 0 | 0 | reserve_dispatch B-106 (77.6) | no (resting) |
| 2130 | `675c8222` | 10 | 0 | 0 | reserve_dispatch B-106 (72.5) | no (resting) |
| 2145 | `9bb0ea24` | 10 | 0 | 0 | reserve_dispatch B-106 (72.6) | no (resting) |
| 2160 | `ebd33281` | 10 | 0 | 0 | reserve_dispatch B-106 (67.0) | no (resting) |
| 2175 | `f3df03fa` | 10 | 0 | 0 | reserve_dispatch B-106 (64.9) | no (resting) |
| 2190 | `c2b3d3c2` | 10 | 0 | 0 | reserve_dispatch B-106 (58.9) | no (resting) |
| 2205 | `6e9e60a2` | 10 | 0 | 0 | reserve_dispatch B-106 (52.2) | no (resting) |
| 2220 | `9b5ab521` | 10 | 0 | 0 | reserve_dispatch B-106 (48.2) | no (resting) |
| 2235 | `b8ee4acc` | 10 | 0 | 0 | reserve_dispatch B-106 (43.6) | no (resting) |
| 2250 | `c896c56d` | 10 | 0 | 0 | reserve_dispatch B-106 (40.8) | no (resting) |
| 2265 | `73ca4d20` | 10 | 0 | 0 | reserve_dispatch B-106 (32.9) | no (resting) |
| 2280 | `ffca4f4f` | 10 | 0 | 0 | reserve_dispatch B-106 (28.0) | no (resting) |
| 2295 | `5768a849` | 10 | 1 | 1 | reserve_dispatch B-106 (20.8) | yes |
| 2310 | `fac59e9e` | 10 | 1 | 1 | reserve_dispatch B-106 (15.6) | yes |
| 2325 | `f3551940` | 10 | 0 | 0 | adjust_departure B-105 -120 s (12.8) | no (below_threshold) |
| 2340 | `30a8678c` | 10 | 0 | 0 | adjust_departure B-105 -120 s (12.7) | no (below_threshold) |
| 2355 | `ab0c26e1` | 10 | 0 | 0 | adjust_departure B-105 -120 s (12.7) | no (below_threshold) |
| 2370 | `5a7386ad` | 10 | 0 | 0 | adjust_departure B-105 -120 s (12.4) | no (below_threshold) |
| 2385 | `0c7057e9` | 10 | 0 | 0 | adjust_departure B-105 -120 s (8.2) | no (below_threshold) |
| 2400 | `35286d01` | 10 | 1 | 1 | reserve_dispatch B-106 (21.3) | yes |
| 2415 | `8aad9d5c` | 10 | 1 | 1 | reserve_dispatch B-106 (51.7) | yes |
| 2430 | `014ad930` | 10 | 0 | 0 | reserve_dispatch B-106 (89.7) | no (resting) |
| 2445 | `76470cb6` | 10 | 0 | 0 | reserve_dispatch B-106 (92.8) | no (resting) |
| 2460 | `0d6fb919` | 10 | 0 | 0 | reserve_dispatch B-106 (87.9) | no (resting) |
| 2475 | `623372dd` | 10 | 0 | 0 | reserve_dispatch B-106 (71.4) | no (resting) |
| 2490 | `85afdea7` | 10 | 0 | 0 | reserve_dispatch B-106 (87.8) | no (resting) |
| 2505 | `4cf012dd` | 10 | 0 | 0 | reserve_dispatch B-106 (102.0) | no (resting) |
| 2520 | `4daceb20` | 10 | 0 | 0 | reserve_dispatch B-106 (102.4) | no (resting) |

##### `SIM_DEMAND_SCALE=1.0`: every cycle with a bunched bus (70 of 160 cycles)

| t (s) | snapshot id | candidates | recommended in the cycle | live rows | best candidate (saving s per rider) | best recommended? (reason if not) |
|---|---|---|---|---|---|---|
| 1335 | `1dd26d5d` | 11 | 1 | 1 | reserve_dispatch B-106 (42.1) | yes |
| 1350 | `0774b26c` | 11 | 1 | 1 | reserve_dispatch B-106 (40.0) | yes |
| 1365 | `12c589c0` | 11 | 1 | 1 | reserve_dispatch B-106 (37.9) | yes |
| 1380 | `ea8ffb9e` | 11 | 1 | 1 | reserve_dispatch B-106 (25.0) | yes |
| 1395 | `38fc6afc` | 11 | 1 | 1 | reserve_dispatch B-106 (24.0) | yes |
| 1410 | `0c307807` | 11 | 1 | 1 | reserve_dispatch B-106 (22.4) | yes |
| 1425 | `d121060e` | 11 | 0 | 0 | reserve_dispatch B-106 (19.8) | no (resting) |
| 1440 | `f951a433` | 11 | 0 | 0 | reserve_dispatch B-106 (8.7) | no (below_threshold) |
| 1455 | `72b3cb09` | 11 | 0 | 0 | reserve_dispatch B-106 (7.5) | no (below_threshold) |
| 1470 | `70d2179c` | 11 | 0 | 0 | reserve_dispatch B-106 (21.1) | no (resting) |
| 1485 | `60df3a1a` | 11 | 0 | 0 | reserve_dispatch B-106 (23.7) | no (resting) |
| 1500 | `8824347d` | 11 | 0 | 0 | reserve_dispatch B-106 (21.1) | no (resting) |
| 1515 | `5622f62d` | 11 | 0 | 0 | reserve_dispatch B-106 (18.1) | no (resting) |
| 1530 | `6178c2ae` | 11 | 0 | 0 | reserve_dispatch B-106 (21.3) | no (resting) |
| 1545 | `3b98e71f` | 11 | 0 | 0 | reserve_dispatch B-106 (18.1) | no (resting) |
| 1560 | `a3ce5e67` | 11 | 0 | 0 | reserve_dispatch B-106 (14.9) | no (below_threshold) |
| 1575 | `643fad1c` | 11 | 0 | 0 | reserve_dispatch B-106 (11.6) | no (below_threshold) |
| 1590 | `cb13564f` | 11 | 0 | 0 | reserve_dispatch B-106 (4.3) | no (below_threshold) |
| 1605 | `fabcaf45` | 10 | 0 | 0 | reserve_dispatch B-106 (3.8) | no (below_threshold) |
| 1620 | `6b653721` | 10 | 0 | 0 | adjust_departure B-104 +60 s (1.5) | no (below_threshold) |
| 1635 | `8835f188` | 10 | 0 | 0 | adjust_departure B-104 +60 s (0.1) | no (below_threshold) |
| 1650 | `43025aad` | 10 | 0 | 0 | adjust_departure B-104 +60 s (2.1) | no (below_threshold) |
| 1665 | `c1be5a7a` | 10 | 0 | 0 | adjust_departure B-104 +60 s (0.6) | no (below_threshold) |
| 1680 | `0f2d8d98` | 10 | 0 | 0 | adjust_departure B-104 +60 s (0.7) | no (below_threshold) |
| 1695 | `d172041f` | 10 | 0 | 0 | adjust_departure B-104 +60 s (0.7) | no (below_threshold) |
| 1710 | `e7d86652` | 10 | 0 | 0 | adjust_departure B-104 +60 s (0.7) | no (below_threshold) |
| 1725 | `15f401c9` | 10 | 0 | 0 | adjust_departure B-104 +60 s (0.7) | no (below_threshold) |
| 1740 | `2ec20a3d` | 10 | 0 | 0 | adjust_departure B-104 +60 s (0.8) | no (below_threshold) |
| 1755 | `14491875` | 10 | 0 | 0 | adjust_departure B-104 +60 s (0.8) | no (below_threshold) |
| 1770 | `eeb17288` | 10 | 0 | 0 | adjust_departure B-104 +60 s (0.9) | no (below_threshold) |
| 1785 | `2a135f96` | 10 | 0 | 0 | adjust_departure B-104 +60 s (2.8) | no (below_threshold) |
| 1800 | `d8e2c843` | 10 | 2 | 2 | adjust_departure B-105 +60 s (23.4) | yes |
| 1815 | `3a3cdb7b` | 10 | 2 | 2 | reserve_dispatch B-106 (31.9) | yes |
| 1830 | `66a3009d` | 10 | 2 | 2 | reserve_dispatch B-106 (25.5) | yes |
| 1845 | `ac8b0e6e` | 10 | 2 | 2 | reserve_dispatch B-106 (36.6) | yes |
| 1860 | `6aa293bc` | 10 | 2 | 2 | adjust_departure B-105 +60 s (23.2) | yes |
| 1875 | `dfa9e6b7` | 10 | 2 | 2 | reserve_dispatch B-106 (35.9) | yes |
| 1890 | `3f644b5b` | 10 | 2 | 2 | reserve_dispatch B-106 (34.5) | yes |
| 1905 | `e1452598` | 10 | 2 | 2 | reserve_dispatch B-106 (51.3) | yes |
| 1920 | `0155ef9d` | 10 | 2 | 2 | reserve_dispatch B-106 (49.4) | yes |
| 1935 | `bf9d11eb` | 10 | 0 | 0 | reserve_dispatch B-106 (68.1) | no (resting) |
| 1950 | `480b63fa` | 10 | 0 | 0 | reserve_dispatch B-106 (65.1) | no (resting) |
| 1965 | `fdeb260a` | 10 | 0 | 0 | reserve_dispatch B-106 (60.5) | no (resting) |
| 1980 | `2bd3f869` | 10 | 0 | 0 | reserve_dispatch B-106 (57.4) | no (resting) |
| 1995 | `396a0e8c` | 10 | 0 | 0 | reserve_dispatch B-106 (45.4) | no (resting) |
| 2010 | `89b0c437` | 10 | 0 | 0 | reserve_dispatch B-106 (41.5) | no (resting) |
| 2025 | `4a57132b` | 10 | 0 | 0 | reserve_dispatch B-106 (38.8) | no (resting) |
| 2040 | `5ea96d26` | 10 | 0 | 0 | reserve_dispatch B-106 (40.9) | no (resting) |
| 2055 | `af2528d6` | 10 | 0 | 0 | reserve_dispatch B-106 (30.7) | no (resting) |
| 2070 | `6680ebd1` | 10 | 0 | 0 | reserve_dispatch B-106 (28.0) | no (resting) |
| 2085 | `1d5225e9` | 10 | 0 | 0 | reserve_dispatch B-106 (32.6) | no (resting) |
| 2100 | `9a1dc45a` | 10 | 0 | 0 | reserve_dispatch B-106 (28.7) | no (resting) |
| 2115 | `03c1f96e` | 10 | 0 | 0 | reserve_dispatch B-106 (25.5) | no (resting) |
| 2130 | `70b98754` | 10 | 0 | 0 | reserve_dispatch B-106 (22.1) | no (resting) |
| 2145 | `88f26df1` | 10 | 0 | 0 | reserve_dispatch B-106 (23.9) | no (resting) |
| 2160 | `c1ffa2c0` | 10 | 0 | 0 | reserve_dispatch B-106 (19.5) | no (resting) |
| 2175 | `b1303e41` | 10 | 0 | 0 | reserve_dispatch B-106 (18.4) | no (resting) |
| 2190 | `73041b49` | 10 | 0 | 0 | adjust_departure B-105 +60 s (15.2) | no (resting) |
| 2205 | `2af6ab08` | 10 | 0 | 0 | adjust_departure B-105 +60 s (17.7) | no (resting) |
| 2220 | `9a373508` | 10 | 1 | 1 | adjust_departure B-105 +60 s (17.7) | yes |
| 2235 | `317049fa` | 10 | 1 | 1 | adjust_departure B-105 +60 s (17.7) | yes |
| 2250 | `4adc1eeb` | 10 | 1 | 1 | adjust_departure B-105 +60 s (17.4) | yes |
| 2265 | `458b8734` | 10 | 1 | 1 | adjust_departure B-105 +60 s (18.1) | yes |
| 2280 | `70501c97` | 10 | 1 | 1 | adjust_departure B-105 +60 s (18.1) | yes |
| 2295 | `514b347a` | 10 | 1 | 1 | adjust_departure B-105 +60 s (18.2) | yes |
| 2310 | `68ecd6e3` | 10 | 1 | 1 | adjust_departure B-105 +60 s (17.8) | yes |
| 2325 | `5a0676e4` | 10 | 1 | 1 | adjust_departure B-105 +60 s (17.8) | yes |
| 2340 | `52201305` | 10 | 1 | 1 | adjust_departure B-105 +60 s (17.8) | yes |
| 2355 | `0338f7a4` | 10 | 0 | 0 | adjust_departure B-105 +60 s (18.3) | no (resting) |
| 2370 | `408b5a5e` | 10 | 0 | 0 | adjust_departure B-105 +60 s (16.4) | no (resting) |

</details>

### Projection error (T048a), C1 seed 42, 2,700 s, a cycle every 15 s from 300 s (160 cycles)

The departures the projector gives for "do nothing" in each cycle (`load_inputs` + `project`) against the first real departure from that stop at or after the cycle's reference time (`silver.stop_visits` after the run). Error = real − projected (the sign of FR-036), so positive means the bus left later than projected. Nothing was tuned. Test: `src/data/tests/integration/test_projection_error.py` (marked `slow`, no production code).

| Scale / horizon | compared departures | mean abs error (s) | median abs error (s) | worst abs error (s) | mean signed error (s) |
|---|---|---|---|---|---|
| scale 3, next 300 s | 1284 | 37.8 | 15.0 | 400.0 | +21.7 |
| scale 3, next 600 s | 2453 | 57.1 | 30.0 | 400.0 | +25.3 |
| scale 1.0 (default), next 300 s | 1283 | 36.9 | 15.0 | 400.0 | +15.9 |
| scale 1.0 (default), next 600 s | 2478 | 53.6 | 30.0 | 400.0 | +17.4 |

Projected departures: 8319 per run at scale 3; 5751 had a real departure in the run (the rest are after its end). The 300 s rows are the departures projected up to 300 s ahead, the 600 s rows up to 600 s ahead (so they include the 300 s ones).

By look-ahead, scale 3, all departures up to 600 s:

| Look-ahead (s) | n | mean abs (s) | median abs (s) | worst abs (s) | mean signed (s) |
|---|---|---|---|---|---|
| 0-150 | 646 | 31.3 | 5.0 | 400.0 | +24.7 |
| 150-300 | 614 | 44.2 | 25.0 | 385.0 | +19.4 |
| 300-450 | 592 | 69.4 | 40.0 | 390.0 | +24.5 |
| 450-600 | 601 | 85.9 | 55.0 | 400.0 | +32.7 |

By what is being projected, scale 3, up to 600 s:

| Departure of | n | mean abs (s) | median abs (s) | worst abs (s) |
|---|---|---|---|---|
| a bus that is at the stop now (dwell only) | 119 | 47.6 | 0.0 | 400.0 |
| the next stop of a bus on the corridor | 390 | 34.1 | 10.0 | 390.0 |
| the stop after the next | 358 | 40.3 | 15.0 | 380.0 |
| two stops after the next | 337 | 49.3 | 25.0 | 360.0 |
| three or more stops after the next | 993 | 57.7 | 35.0 | 370.0 |
| a bus not on the corridor (terminal slot estimate) | 256 | 127.7 | 80.0 | 400.0 |

**Main source.** (1) Travel-time noise of the simulator: the error grows with the look-ahead from 31 s (0–150 s) to 86 s (450–600 s) mean, and from the next stop (34 s) to three or more stops ahead (58 s); the simulator draws each segment time from a lognormal with σ = 0.20 around M1 and the model projects the expected value. (2) A constant lag of about +20 s (the real bus is later): M1 is the median of that noise, which is about 2 % under its mean, and the dwell is computed from the expected queue. (3) The worst error, 400 s, is exactly the 400 s stall that the C1 scenario injects at P-884 (`extra_s` 400), which nothing in bronze announces; the "bus at the stop now" median is 0 s because the dwell is known, and its mean is the stall. (4) Buses that are not on the corridor yet have the largest group error (mean 128 s at scale 3): their departure is the model's slot estimate (last departure at the terminal plus the planned headway, one slot per waiting bus), while the simulator re-dispatches on its own 3,000 s cycle.

**What this check found and was fixed before the numbers above** (kept separate so the first measurement is not lost): the first run gave mean absolute errors of 356 s (300 s horizon) and 323 s (600 s) at scale 3. Cause: `load_inputs` treated a bus waiting at the terminal for its scheduled departure (silver `waiting`, position 0, reporting) as a bus that leaves now, so it projected B-103 to B-105 as departing within seconds and took them out of the terminal slots. Fix: such a bus is `waiting` with a terminal slot (those waiting at the terminal take the first slots, then the buses back from their trip, both by id), and `adjust_departure` targets the waiting bus with the earliest slot. A test covers it (`test_buses_waiting_at_the_terminal_leave_first_...`). The first live run A (before the fix) and the first replay tables were repeated; the numbers in this section are from after the fix. Parameters were not touched.

### Cycle time (T048)

Live runs, C1 seed 42, 2,700 s, pace 1 (refresh every 5 s of wall time; the `refresh_cycle` log lines, cycles with data). "Model on" is run A (after the fix), "model off" is run B (`MPC_ENABLED=off`: no candidates, status still derived).

| Run | cycles | `duration_ms` median / p95 / max | `model_ms` median / p95 / max | skipped / errors |
|---|---|---|---|---|
| A, model on (first run, before the input fix) | 127 | 80 / 190 / 202 | 5.4 / 11.1 / 12.5 | 0 / 0 |
| **A, model on (final code)** | 112 | **89.5 / 186 / 233** | **5.75 / 11.1 / 11.7** | 0 / 0 |
| B, model off | 118 | 83 / 179 / 206 | 0.8 / 0.9 / 1.3 | 0 / 0 |
| C, model on, scale 3 | 112 | 90.5 / 187 / 269 | 8.9 / 11.2 / 17.3 | 0 / 0 |

Model's added time, final code: model step A minus B **median +4.9 ms, max +10.4 ms**; the whole cycle (A minus B) median +6.5 ms, p95 +7 ms, max +27 ms (the cycle figures are within the noise of two live runs on a laptop: a `psql` sampler ran every 10 s in both). Targets: added median ≤ 60 ms (**4.9 ms**), added max ≤ 150 ms (**10.4 ms**), demo p95 ≤ 250 ms (**186 ms**). SC-011: max `duration_ms` 233 (269 at scale 3) < 5,000, no cycle skipped because of the model.

Against 005 (demo p95 about 100 ms): the p95 here is 186 ms with the model **off** too (179 ms), so the rise is not the model. It comes from the phase 2 silver additions (`silver.stop_queue` is rebuilt every cycle), the sampler and the host; the model's own step is 5.75 ms median.

4-hour stress (14,400 simulated seconds of C1, **15,396 bronze events**, ingested once; 40 cycles over the last 10 minutes at distinct reference times, on two clones of the same data, one with the model on and one off; `/tmp/stress.py`, not committed):

| Pass | model | `duration_ms` median / p95 / max | `model_ms` median / p95 / max |
|---|---|---|---|
| off first, on second (clean pass) | off | 660 / 686 / 713 | 2.0 / 2.4 / 2.9 |
| | **on** | **674 / 705 / 718** | **13.2 / 16.5 / 17.8** |
| on first, off second (a live-run sampler was still running) | on | 676 / 712 / 729 | 13.1 / 16.6 / 21.5 |
| | off | 668 / 1,609 / 1,715 | 1.9 / 2.2 / 3.0 |

The model adds about 11 ms to a 4-hour cycle (+14 ms median on the clean pass, **+2.1 %**), inside the planned +3 % to +6 % (R9, issue #21). The 1.6 s of the 005 note was not reproduced: this method gives about 0.67 s for the same event count, so the absolute numbers are not comparable, only the added time is. The off-pass outliers of the second pass (1.6 s) coincided with the end of a live-run sampler and were not repeated in the clean pass; they are reported, not explained.

### Untouched check

`git diff --stat feature/005-data-fixes-metrics` and `git status --short`: no change to `docs/adr/`, `docs/data-contract.md`, bronze DDL (`002_bronze.sql`), `.github/`, `.kiro/`, `.specify/`, `src/api/`, the frontend or `CODEOWNERS`. Under `contracts/` only `read/recommendation.schema.json`, `read/README.md` and the two new fixture directories. No existing fixture changed.

### Files

CODEOWNERS paths (`/contracts/`, `/src/data/rules/`; for the data owner's review): `contracts/read/recommendation.schema.json`, `contracts/read/README.md`, `contracts/read/fixtures/c1_slow_down/recommendation.json`, `contracts/read/fixtures/c2_skip_stop/recommendation.json`, `src/data/rules/mpc.py` (new), `src/data/rules/__init__.py` (`RULES_VERSION` 1.6.0), `src/data/rules/sql/silver_stop_queue.sql`, `mpc_inputs_rates.sql`, `mpc_inputs_open_visits.sql`, `mpc_inputs_last_departure.sql` (new), `silver_bus_current_state.sql` (occupancy). To report to the data owner (not CODEOWNERS): `.env.example` and `docker-compose.yml` (T044).

Other source: `src/data/db/init/009_decision_mpc.sql` (new), `007_scenarios.sql` (seed section removed), `pipeline/recommend.py` (new), `pipeline/cycle.py`, `pipeline/silver.py`, `pipeline/reference.py`, `pipeline/holds.py`, `pipeline/compute.py`, `refresh/run.py`, `simulator/main.py`, `simulator/scenarios/__init__.py`, `simulator/scenarios/holds.py`, `pulsoflota/config.py`, generated `pulsoflota/models/read/recommendation.py`. Deleted: `src/data/seeds/` (2 files), `pipeline/seeds.py`, `tests/integration/test_seeds.py`, `tests/fixtures/scenarios/seed_recommendations.json`.

Tests (new): `contract/test_recommendation_110.py`, `integration/test_decision_model_schema.py`, `test_stop_queue.py`, `test_mpc_inputs.py`, `test_recommend_scenarios.py`, `test_recommend_lifecycle.py`, `test_projection_error.py` (slow), `unit/test_mpc_candidates.py`, `test_mpc_ranking.py`, `test_mpc_lifecycle.py`, `test_mpc_safety.py`, `test_seed_retired.py`, `test_simulator_demand_scale.py`; fixtures `rec_support.py`, `mpc_runs.py`, `projector_support.facts`. Tests edited: `contract/test_read_fixtures.py` (20 fixtures), `integration/test_hold_loop.py`, `test_hold_poller.py`, `test_instruction_status.py`, `test_stop_ewt_gold.py`, `test_schema_init.py`, `test_silver.py`, `test_rebuild.py`, `test_range_guard.py`, `unit/test_hold_board.py`, `test_hold_compliance.py`, `test_scenario_injectors.py`, `test_rules_version.py`, `test_compose_ingestion.py`, `test_compose_refresh.py`, `fixtures/gold_support.py`, and `tests/unit/test_env_example.py`.

### Rework and decisions made here

Rework (in order):
- First host run: 7 failures and 1 error. `test_rebuild.py` recreates silver from `004` and `008` only, so it lacked `silver.stop_queue` (helper now also applies `009`; same for the "drop silver and gold" test). `test_range_guard.py::test_no_contract_or_adr_changed` is a 005 guard that compares `contracts/` with story 004; 006 is allowed by FR-029 to change exactly the recommendation schema, its README and two fixture directories, so the guard now excludes exactly those paths (every other contract file and every ADR still must match). This narrows a 005 test to what the spec authorises; flagged for the data owner.
- `rules/mpc.py::derive_all`: a row first expired because the bus passed its stop flipped back to `proposed` in the next cycle (the passing is only looked up for rows still proposed). Found by `test_immutable_columns_never_change_...`; expired is now sticky without a decision.
- First CI-ready run: `test_seed_retired` needs `git`, absent in the image; it now walks the mounted tree when there is no git. Second CI attempt used a `DATABASE_URL` leaked from my shell (compose gives the shell precedence over the env file); rerun with it unset.
- Hand values corrected (code was right): the train batches at 17:00 are not all hour-17 batches (trains of 16:58 and 16:59 still have riders walking and are sized with hour 16); the 004 instruction-status test hard-coded `rules_version` 1.5.0.
- The input bug of the previous section (found by T048a).

Decisions (each in the code docstrings):
- `DROP TABLE config.seed_recommendation` (T033) is written as a catalog loop that drops every `seed_*` table of `config`, so that no file names the retired table and the tree grep (SC-009) is a literal 0.
- `case` of reserve and adjust departure: C5 with a breakdown, else C1 with bunching, else C2 (a gap or a queue above the trigger, which has no case of its own).
- `reason_not` has one extra value, `weaker_intensity` (a candidate beaten by another intensity of the same type, bus and stop); M6 lists four.
- `gold.recommendation."case"` is updated with the doc when it changes (M5 lists it as immutable), so the column and `doc.case` cannot differ.
- A stale proposal that returns to the top 3 keeps its `rec_id` and stops being stale (one row per key).
- A hold, slow down or skip stop targets the bus's next stop, never the stop it is dwelling at (the 004 executor matches only visits that begin after the decision).
- Rows that did not change are not written again; only a changed row or a new one is upserted (lineage then names the last cycle that changed it). `gold.mpc_evaluation` is emptied when the model is off or the snapshot is too old.
- Applied orders already in force (a hold approved but not yet executed) are not part of the projection input.
- Terminal slots: one planned headway after the last departure at P-883 (or an open visit there), one per waiting bus.
- T015 puts the invalid-variant cases in a new `contract/test_recommendation_110.py` (the named `test_contract_examples.py` validates the turn-1 event schemas, not the read schemas).
- The live runs pass the scenario file by a read-only mount; the image cannot see `src/data/tests/`.

### Open items for the data owner

- `.env.example` and `docker-compose.yml` changed (T044): `SIM_DEMAND_SCALE` to `ingestion`, `MPC_ENABLED` to `refresh`, `SEED_RECOMMENDATIONS_PATH` removed.
- No `RULES_VERSION` bump in phase 1; phase 2 bumps to 1.6.0.
- `test_range_guard.py` (a 005 guard) now excludes the four 006 contract paths.
- At the real reference demand hold and slow down never reach the 15 s threshold in C1; the recommendations are reserve dispatch and a delayed terminal departure. This is the model's result as measured.
- Phase 2b (projection record, FR-035, FR-036, SC-016) is not started.


## Phase 2b: projection record (T049a–T049m; FR-035, FR-036, SC-016)

**Time**: start 2026-11-22T15:05Z, end 2026-11-22T16:40Z (UTC). About 1.6 h of wall time against 0.6 h planned: the four live runs (C twice, A, B) take about 10 minutes each at pace 1, and the two suites take 11 and 6 minutes. Branch `feature/006-decision-mpc`; nothing committed. Phase 3 not started. The "Phase 2b is not started" line of the Phase 2 open items above is historical.
**Environment**: compose project `pf006` only (`-p pf006 --env-file /tmp/pf006*.env`, Postgres on 55432, the default stack on 5432 untouched). `down -v` of `pf006` at the end.

### Commands

```text
tests first: uv run --extra dev pytest src/data/tests/unit/test_projection_record.py src/data/tests/integration/test_projection_{schema,accuracy_view,accuracy_query,record}.py --no-cov -q
slow (SC-016, forced mode): uv run --extra dev pytest -m slow src/data/tests/integration/test_projection_error.py -s     (15:28Z to 15:30Z, 2 passed in 96 s)
host suite:  . /tmp/pf006_host.sh; uv run --extra dev pytest -m "not slow and not live" -p no:cacheprovider -q
CI-ready:    docker compose -p pf006 --env-file /tmp/pf006.env --profile tools build tests
             docker compose -p pf006 --env-file /tmp/pf006.env --profile tools run --rm tests      (DATABASE_URL unset in the shell)
generate:    uv run --extra dev make generate-read   (twice; the second `git diff --stat` equals the first; no file under src/pulsoflota changed)
live:        docker compose -p pf006 --env-file /tmp/pf006_{A,B,C}.env up -d db / up -d --build refresh /
             run -d --no-deps --rm --name pf006-ingest-X -v "$PWD/src/data/tests/fixtures/scenarios:/scn:ro" ingestion
             (A: scale 1, model on; B: MPC_ENABLED=off; C: SIM_DEMAND_SCALE=3; all C1 seed 42, 2,700 s, pace 1)
stress:      PYTHONPATH=. uv run --extra dev python /tmp/stress2b.py   (4-hour C1, 15,396 events; not committed)
```

### Results

| Run | Result |
|---|---|
| Red step | `test_projection_record.py` (unit and integration): `ImportError: projection_record`; the schema tests: `UndefinedTable`; the view and query tests: fixture error `relation gold.mpc_projection does not exist`; `test_rules_version`: `1.6.0 != 1.7.0`. The test added after the first live run (no row before any bus has reported) failed with `assert 36 == 0` before the guard. |
| Host suite (16:18:03Z to 16:28:47Z) | **1162 passed, 22 skipped, 7 deselected; coverage 97.72 %** (phase 2: 1135 passed, 97.70 %). `rules/mpc.py` 100 %, `rules/projector.py` 99 % (line 313, as before), `pipeline/recommend.py` 99 % (lines 88 and 96, as before). |
| CI-ready (16:28:54Z to 16:35:11Z) | **1164 passed, 27 skipped; coverage 97.72 %** (phase 2: 1137 passed, 97.70 %). |
| Golden hash, seed 42, 3,600 s | unchanged: `8bae0e5229b2e547fac181f0f87176809d71be7a80600a4b066832b6274690bc` (unset and `SIM_DEMAND_SCALE=1.0`; the constant of `test_simulator_golden_hash.py`, green in both suites). The record touches no simulator file. |
| `make generate-read` twice | second `git diff --stat` identical to the first; `RecommendationV110` and every generated model unchanged. |
| `RULES_VERSION` | `1.7.0` (new gold table and view); `test_rules_version.py` updated, red first. |

New tests: 27 (unit 5, integration 22: schema 4, view 5, query 3, record 10). Rewritten: `test_projection_error.py` (slow).

### SC-016: forced mode, C1 seed 42, 2,700 s, a cycle every 15 s from 300 s (160 cycles), read from `gold.v_projection_accuracy`

Aggregate query of `contracts/projection-accuracy.md`, run unchanged. Error = real − projected, so positive means the bus left later than projected; the statistics are on the absolute error. `affected_by_decision` rows: 0 (a replay has no decision). Nothing tuned.

| Scale | Lead bucket | Compared departures | MAE (s) | Median (s) | Worst (s) | Mean signed (s) |
|---|---|---|---|---|---|---|
| 3 | 0–5 min | 1,260 | 37.6 | 15.0 | 400 | +22.2 |
| 3 | 5–10 min | 1,175 | 77.0 | 45.0 | 400 | +27.9 |
| 3 | 10–30 min | 3,316 | 114.4 | 75.0 | 435 | +33.4 |
| 1.0 | 0–5 min | 1,269 | 37.0 | 15.0 | 400 | +16.2 |
| 1.0 | 5–10 min | 1,198 | 70.6 | 45.0 | 370 | +18.3 |
| 1.0 | 10–30 min | 3,262 | 106.9 | 90.0 | 330 | −7.0 |

Rows: 8,319 at scale 3 (160 cycles; 8,337 at scale 1), all with a real departure or a NULL error: 5,751 compared at scale 3, 2,568 without a real departure yet (the run ended first). `error_s` is NULL exactly when `actual_departure_ts` is NULL (0 mismatches). Two replays of the same bronze give the same SHA-256 of the ordered rows (scale 3: `2d9ce59e8da63a155ec10e07777232a395a7db89b3d5a0c4869ed8797950e49c`, asserted by the test).

**Comparison with T048a** (the one-off script, same run). T048a: scale 3, up to 300 s: 1,284 departures, MAE 37.8, median 15.0, worst 400; up to 600 s: 2,453, MAE 57.1, median 30.0, worst 400. The view's two buckets up to 600 s together: 2,435 departures, MAE 56.6 (weighted, 1,260 × 37.6 + 1,175 × 77.0), worst 400. Scale 1: T048a 2,478 and 53.6 against the view's 2,467 and 53.3. The same projected rows (8,319 and the same 5,751 matched at scale 3). The small differences: T048a put a departure at exactly 300 s and 600 s in the lower bucket (`≤`), the view puts them in the next (`<`), and T048a took the next visit when the first one was estimated, where the view gives NULL (18 and 11 fewer compared departures). The new 10–30 min bucket is not in T048a: it has the largest error (MAE 114 s at scale 3), consistent with the look-ahead trend T048a found (31 s at 0–150 s to 86 s at 450–600 s). The T048a table above stays as recorded.

### Live check under `-p pf006` (C1 seed 42, 2,700 s, pace 1, `SIM_DEMAND_SCALE=3`, run C, final code)

The live run reads the view from the database the `refresh` container filled (`REFRESH_CLOCK=data`, a cycle every 5 s of wall time).

| Quantity | Run C (scale 3) | Run A (scale 1) | Run B (model off) |
|---|---|---|---|
| Snapshots / cycles with rows | 109 / 109 | 110 / 109 | 110 / 0 |
| Rows total | 5,516 | 5,550 | 0 |
| Rows per cycle min / median / max | 35 / 52 / 57 | 35 / 52 / 57 | |
| Table size with indexes | 1,335,296 bytes (1.3 MB, 242 bytes per row) | | |
| Compared / `affected_by_decision` | 3,938 / 0 | | |

SC-016 table from the live run (aggregate query on the live database):

| Scale | Lead bucket | Compared | MAE (s) | Median (s) | Worst (s) | Mean signed (s) |
|---|---|---|---|---|---|---|
| 3 (C) | 0–5 min | 785 | 36.8 | 15.0 | 390 | +21.2 |
| 3 (C) | 5–10 min | 767 | 76.1 | 40.0 | 405 | +30.8 |
| 3 (C) | 10–30 min | 2,386 | 126.3 | 80.0 | 430 | +57.9 |
| 1 (A) | 0–5 min | 798 | 36.3 | 15.0 | 400 | +15.8 |
| 1 (A) | 5–10 min | 779 | 69.9 | 45.0 | 370 | +21.1 |
| 1 (A) | 10–30 min | 2,340 | 114.2 | 95.0 | 365 | +13.8 |

The live and forced-mode tables agree (0–5 min about 37 s, 5–10 min about 70 to 77 s, medians 15 and 40 to 45 s). **Rerun identical**: not possible between two live runs, because the data clock takes `as_of` from the cycle's wall time against the feed, so two live runs have different `as_of` and `max_bronze_id` and therefore different snapshot ids. The strict rerun check is the forced-mode replay: `test_the_same_bronze_gives_identical_rows` (1,200 s at scale 3) and the slow test above (2,700 s, both scales) compare the ordered rows including the snapshot id, and are equal. No live decision was made, so `affected_by_decision` is exercised by the crafted tests only.

**Finding of the first live run** (kept, not hidden): the first live run C, before the guard, gave `worst_abs_error_s` of 196,175 s and a MAE of 784 s in the 0–5 min bucket. The first cycles ran before any event was in bronze, at the wall-clock time (2026-11-22), and every roster bus was a placeholder with a terminal slot; the view paired those 38 rows with the first departure of the feed two days later. Fix: the record is written only when `silver.bus_current_state` has a row (some bus has reported); a test covers it (`test_a_cycle_with_no_bus_report_stores_nothing`, red with `36 == 0` first); the view is not bounded in time, so a real large error stays visible. The numbers above are from after the fix (run C repeated). Parameters were not touched.

### Volume (research R17 estimates against measured)

| | Estimate (R17) | Measured |
|---|---|---|
| Rows per cycle | about 52 (T048a) | 35 / 52 / 57 (min / median / max), live; 44 / 53 / 57, replay at scale 3; 52 on the 4-hour data |
| Bytes per row | about 250 | 242 (1,335,296 B for 5,516 rows, with the primary key and the secondary index) |
| 108-cycle live run (45 minutes at pace 1) | about 5,600 rows | 5,516 and 5,550 rows, 1.3 MB |
| 45 minutes at the real 5 s interval (540 cycles) | about 28,000 rows, 7 MB | 540 × 52 = about 28,100 rows, about 6.8 MB |
| 4 hours at 5 s (2,880 cycles) | about 150,000 rows, 40 MB | 2,880 × 52 = about 150,000 rows, about 36 MB |

The last two rows are the measured row size and median times the cycle count (not a run). The table has no retention rule, like `gold.snapshots`.

### Cycle time (SC-011), live runs of 110 cycles (C1 seed 42, 2,700 s, pace 1; one cycle per distinct snapshot)

| Run | `duration_ms` median / p95 / max | `model_ms` median / p95 / max |
|---|---|---|
| A, model on, scale 1 (phase 2b) | 85.0 / 197 / 302 | 8.1 / 13.7 / 27.3 |
| B, model off | 85.0 / 182 / 190 | 0.8 / 1.3 / 14.3 |
| C, model on, scale 3 | 93 / 187 / 193 | 9.8 / 12.2 / 15.1 |
| (phase 2, for comparison) A / B / C | 89.5 / 186 / 233; 83 / 179 / 206; 90.5 / 187 / 269 | 5.75 / 11.1 / 11.7; 0.8 / 0.9 / 1.3; 8.9 / 11.2 / 17.3 |

**Model's added time (A − B, model step): median +7.3 ms, max +13.0 ms** (max of A's 27.3 ms is one outlier cycle; B's 14.3 ms max too). Phase 2 was +4.9 ms median and +10.4 ms max, so phase 2b adds about 2.4 ms at the median (the baseline projection in cycles with no candidate, about 50 rows and one insert). Targets: added median ≤ 60 ms, added max ≤ 150 ms, demo p95 ≤ 250 ms: met (**demo p95 197 ms** with the model on, 182 ms with it off). SC-011: max `duration_ms` 302 < 5,000, no cycle skipped. The A and B cycle figures differ by less than the noise of two laptop runs (A's max of 302 ms is one cycle; p95 differs by 15 ms; medians are equal).

4-hour stress (14,400 simulated seconds, **15,396 events**, 40 cycles over the last 10 minutes on clones of the same data; the passes alternate; "norecord" is the final code with `projection_record` patched to return no row, so it still projects the baseline):

| Pass | `duration_ms` median / p95 / max | `model_ms` median / p95 / max | Rows |
|---|---|---|---|
| model off (1st) | 664 / 681 / 682 | 2.0 / 2.7 / 2.9 | 0 |
| model on, final (1st) | 684 / 711 / 736 | 16.9 / 22.3 / 23.8 | 2,077 |
| norecord (1st) | 682 / 1,658 / 1,737 | 14.2 / 17.2 / 24.2 | 0 |
| model on, final (2nd) | 688 / 1,635 / 1,721 | 16.4 / 20.6 / 22.6 | 2,077 |
| norecord (2nd) | 685 / 1,640 / 1,669 | 15.3 / 19.0 / 23.6 | 0 |
| model off (2nd) | 670 / 1,622 / 1,624 | 1.9 / 2.8 / 3.4 | 0 |

The model adds about **+14.9 ms** to a 4-hour cycle's median (16.9 against 2.0 in the first pair; +20 ms of the cycle median, +3 %, inside the planned +3 % to +6 %). The record and its insert cost **+1.7 to +2.7 ms** of that (16.9 and 16.4 against 14.2 and 15.3). The p95 and maximum of 1.6 s in the later passes appear in the model-off pass too (the last row), so they are not the model; the same outliers were seen in phase 2's second pass and are reported, not explained. Added cost of phase 2b: about +2 ms (live: +2.4 ms).

### Untouched check

`git status --short` and `git diff --stat feature/005-data-fixes-metrics` for `docs/`, `.github/`, `.kiro/`, `.specify/`, `src/api/`, `CODEOWNERS` and `contracts/turn1-events`: no change. `contracts/` has no change in this phase (the two schema files and fixtures changed in phase 2 only). `docs/data-contract.md` and `docs/adr/` untouched. No change in `.env.example`, `docker-compose.yml` or the simulator.

### Files changed in phase 2b

CODEOWNERS paths (for the data owner's review): `src/data/rules/projector.py` (`projection_record`), `src/data/rules/mpc.py` (optional `base` argument of `evaluate_candidates`), `src/data/rules/__init__.py` (`RULES_VERSION` 1.7.0). Under `contracts/`: nothing.
Other source: `src/data/db/init/009_decision_mpc.sql` (Phase 2b section: `gold.mpc_projection`, `gold.v_projection_accuracy`), `src/data/pipeline/recommend.py` (baseline projected every fresh cycle, one `INSERT … SELECT FROM unnest … ON CONFLICT DO NOTHING`).
Tests: new `unit/test_projection_record.py`, `integration/test_projection_schema.py`, `test_projection_accuracy_view.py`, `test_projection_accuracy_query.py`, `test_projection_record.py`; rewritten `integration/test_projection_error.py` (slow, reads the view); edited `unit/test_rules_version.py`, `fixtures/gold_support.py` (`clear_all` empties `gold.mpc_projection` first), and the cleanup lists of `integration/test_incident_gold.py`, `test_scenarios_gold.py`, `test_stop_boarding_gold.py`, `test_stop_ewt_gold.py`, `test_rebuild.py`.
Documents: `specs/006-decision-mpc/tasks.md` (Phase 2b, phase 5 reduced, hours and checkpoints, `RULES_VERSION` plan), `plan.md`, `data-model.md` (M10, M11), `research.md` (R17), `quickstart.md`, `contracts/projection-accuracy.md` (new), `contracts/README.md`, `verification.md`.

### Rework and decisions made here

Rework:
- First full host run: 8 failures, all one cause: `gold.mpc_projection` has a foreign key to `gold.snapshots` and a view on `silver.stop_visits`, so five older tests that delete the gold tables or drop the silver and gold tables (`test_incident_gold`, `test_scenarios_gold`, `test_stop_boarding_gold`, `test_stop_ewt_gold`, `test_rebuild`) failed on cleanup. Their cleanup lists now name the new table (and the view) first. No assertion changed.
- Test buses in the view test (`B-3`…) are outside the recommendation contract's bus enum; the crafted recommendation rows are inserted without model validation (`validate=False`, as the old seed rows allowed).
- The finding of the first live run (above): guard and test added.

Decisions (details in research R17; each is one line of the view or one condition in `recommend.py`, and the data owner can overrule):
- Real departure = first `silver.stop_visits` departure of the bus at the stop with `departure_ts ≥ as_of_ts`. If that visit is an estimated departure, the error is NULL (the next visit is not used, to avoid a pairing with the next trip).
- `affected_by_decision`: only an applied recommendation on the same bus, decided after `as_of_ts` and not after the real departure (via `gold.recommendation.close_ts`). Effects of an action on other buses' baselines are not flagged.
- No row is stored before any bus has reported, when the model is off or when the snapshot is older than 15 s.
- The projection is written for every bus the baseline gives a departure inside 1,800 s, including waiting buses with a terminal slot (their error is the largest, as T048a found) and `estimated` buses.
- `RULES_VERSION` 1.7.0 (phase 4 and 6 move to 1.8.0 and 1.9.0 in the task list).
- Phase 5 reduced from 0.60 h to 0.35 h; committed scope 6.45 h.
- Phase 2 exit gate T049 is left unchecked in `tasks.md` (it is the data owner's confirmation); the data owner committed phase 2 and asked for 2b, which I took as the go-ahead.
