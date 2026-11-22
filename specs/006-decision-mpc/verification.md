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
