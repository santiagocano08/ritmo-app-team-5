# Quickstart: validating the decision model

**Feature**: `specs/006-decision-mpc` | Validation and run guide. It has no implementation code. Contracts: [contracts/](contracts/README.md). Objects: [data-model.md](data-model.md). Decisions: [research.md](research.md).

## Prerequisites

- Worktree `~/Documents/ritmo-006-mpc`, branch `feature/006-decision-mpc`, stacked on `feature/005-data-fixes-metrics`.
- Python via `uv` (as in the Makefile), Docker with `docker compose`.
- A copy of `.env.example` with a password set. For the live checks use a **dedicated compose project** and its own env file, never the default stack:

```bash
cp .env.example /tmp/pf006.env
# edit /tmp/pf006.env: POSTGRES_PASSWORD (any local value), POSTGRES_PORT=55432, API_PORT=58000,
# DATABASE_URL pointing at db:5432 inside the project, REFRESH_CLOCK=data, SIM_HOLDS=on
export PF="docker compose -p pf006 --env-file /tmp/pf006.env"
```

A new project has an empty volume, so `009_decision_mpc.sql` runs by itself. On an existing volume apply it by hand (one section per phase, all idempotent):

```bash
$PF exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/009_decision_mpc.sql
```

Committed scope: phases 1, 2, 3a, 3b, 3c, 4, 5 (6.10 h). Phase 6 is optional. Cut order on overrun: phase 5, phase 4, then 3b and 3c; never 1, 2 or 3a (plan.md).

## Gate after every phase (must be green before the phase is committed)

```bash
uv run pytest -q                       # host suite (coverage threshold from pyproject)
$PF --profile tools build tests && $PF --profile tools run --rm tests      # CI-ready command, coverage > 80 %
make generate-read && git diff --stat  # empty on a second run (phase 2 onward)
```

Expected: 0 failures, coverage above 80 %, no change in `git diff` after regeneration. The simulator golden-hash tests (`test_simulator_golden_hash`, the 004 "empty bronze is byte-identical" test) pass unchanged in every phase.

## Phase 1: projection and scoring (no database)

```bash
uv run pytest src/data/tests/unit -k "projector or mpc_score or alight" -q
```

Expected, each a failing test before the code exists:

| Check | Expected |
|---|---|
| Crafted snapshots (one bus; two buses with a queue; a full bus; zero queue) | projected stop departures equal the hand-computed values within 1 s (SC-002) |
| Hour-boundary case crossing 18:00 | each step uses its own local-hour M1 and rate |
| Dwell | `10 + 3·boarded + 2·alighted`, 5 s grid |
| Alighting vs simulator (seeds 42, 43, 1 simulated hour, no database) | largest difference reported and within the recorded tolerance (research R2) |
| Wait score vs stop EWT | same departures give the same mean wait as `rules/stop_metrics.py` on a crafted case (R11) |
| Determinism | two runs give byte-identical canonical JSON of projections, scores and ranking (SC-001) |
| Parameters | changing a value in the params object changes the result; no literal 90, 900, 300, 120, 15 outside `mpc_params.py` |

## Phase 2: recommendations, status, seed retirement

```bash
uv run pytest src/data/tests -k "recommend or mpc or hold or instruction or seed or contract" -q
```

Expected:

| Check | Expected |
|---|---|
| Contract: 18 old fixtures + 2 new validate against 1.1.0; invalid variants fail, including `slow_down` without `speed_reduction_pct`, `slow_down` with 0, -5 or 51, and any other type carrying the field | pass; fixture count 20 |
| `speed_reduction_pct` of published rows | every `slow_down` row has a value in `{10, 20}` (`slow_shares` × 100) and validates against the JSON Schema |
| `SIM_DEMAND_SCALE` | unset and `1.0` give the same golden hash; `0.05`, `11` and `abc` stop the simulator before the first event; `rules/`, `pipeline/` and config code never mention it or `demand_scale` |
| Normal snapshot | 0 candidates, 0 rows (SC-005) |
| C1 snapshot | hold, slow down and reserve all in `gold.mpc_evaluation`; published rows ≤ 3, ranked, with a plain-text reason, validating with `RecommendationV110` (SC-003) |
| C5 snapshot with a free reserve | `reserve_dispatch` evaluated every cycle; recommended only if the saving after the reserve cost is ≥ 15 s per rider (SC-004) |
| D1 | 0 rows target the `estimated` bus; 0 on a `sources_down` bus |
| Stale snapshot (crafted age 20 s) | no new row; existing rows keep their derived status (SC-006) |
| Lifecycle with scripted decisions | `apply` gives `applied`, `discard` gives `discarded`, none gives `expired` after 120 s or when the bus passes the stop; the same key rests 300 s; nothing `applied` without a `decision` in bronze (SC-007) |
| Rerun of the same bronze | identical rows and `rec_id`s |
| Seed grep | 0 hits for `seed_recommendation`, `recommendations.json`, `SEED_RECOMMENDATIONS_PATH` outside `specs/` and `docs/` (SC-009) |

Live check (dedicated project, C1, 2,700 s, seed 42):

```bash
$PF up -d db && $PF up -d --build refresh
SIM_SEED=42 SIM_DURATION_S=2700 SIM_SCENARIO_FILE=src/data/tests/fixtures/scenarios/c1_bunching.json $PF up -d --build ingestion
$PF exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT rank, status, doc->'action'->>'type' AS action, doc->'action'->>'bus_id' AS bus, doc->>'ewt_saving_s' AS saving, doc->>'reason' AS reason FROM gold.recommendation ORDER BY proposed_ts, rank"
```

Expected: at least the evaluated candidates in `gold.mpc_evaluation` during bunching; rows (if any) with the saving reported as the model yields it; no row on an `estimated` bus. Whether a hold is recommended in C1 is not a pass or fail item (SC-003). Record the actual numbers in `verification.md`.

Live check at the demo demand (same project, same seed, forced mode; the only change is `SIM_DEMAND_SCALE=3`, as in the data owner's prototype):

```bash
$PF down -v && $PF up -d db && $PF up -d --build refresh
SIM_DEMAND_SCALE=3 SIM_SEED=42 SIM_DURATION_S=2700 SIM_SCENARIO_FILE=src/data/tests/fixtures/scenarios/c1_bunching.json $PF up -d --build ingestion
$PF exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c \
  "SELECT count(*) AS candidates, count(DISTINCT snapshot_id) AS cycles FROM gold.mpc_evaluation"   # while the bunching lasts; the table holds the latest cycle only, so the test collects it after every run_cycle
```

Pass: at least one evaluated candidate in every cycle whose snapshot has a `bunched` bus (the integration test collects `gold.mpc_evaluation` after each `run_cycle` of the replay and asserts this). Report: whether any candidate reached the 15 s threshold and was recommended, with its saving. Do not tune any parameter. Run the scale 1 case first for the real-demand number; both go in `verification.md` with the scale used.

## Phase 3: execution

```bash
uv run pytest src/data/tests -k "hold_loop or slow_down or reserve or not_executed or golden" -q
```

3a (holds, never cut): scripted approval of a model hold in C1 forced mode; the dwell is within ±15 s of the recommended time; `gold.instruction_status` reads it from `gold.recommendation` (SC-008). Live: insert a `decision` row for a published hold `rec_id` (as the backend would) and watch `gold.instruction_status` become `executed` after the bus leaves the stop.

3b (slow down, cut third): the follower's `speed_kmh` is lowered by `action.speed_reduction_pct` (read from the recommendation, 10 and 20 tested) for 300 s of simulated time and its next arrivals are later by about `share/(1 − share)` of the covered driving time.

3c (reserve, cut third): after the 120 s readiness the reserve appears in the stream and in `corridor_now`; `adjust_departure` and `skip_stop` approvals change nothing and are counted.

## Phase 4: reason and shift log (cut second)

```bash
uv run pytest src/data/tests -k "decision_log or command_event or reason" -q
```

Expected (SC-015): discard with "Driver not available" gives `outcome = 'discarded'`, that `reason`, `decided_ts`, `user_id`; a 1.0.0 discard gives `reason` NULL; an `apply` on a hold gives `instruction_status` after the visit; no decision gives `expired` after 2 minutes; the same bronze gives the same rows; Q11 runs as written in the contract.

## Phase 5: counterfactual report (cut first)

```bash
uv run python -m src.data.validation.counterfactual --scenario c1_bunching --seed 42 --out /tmp/pf006-report.md
```

Runs the scenario twice on the same seed (without and with the model's top executable action approved by a scripted decision), re-projects from the stored `lineage_detail.inputs`, and writes, per action: projected passing times with and without, actual passing times, the error in seconds, and the effect on the mean journey time (wait + ride) of the cohort arriving in the 600 s after the decision (the same riders in both runs). The post-005 reference (C1 seed 42, 90 s hold, stop EWT P-888..P-900, 16 minutes: +25.8 s to +10.6 s, 15.2 s saving) is printed next to it as context only. Pass: the report exists and a second run gives the same file (SC-010).

## Phase 6: road trend (optional, outside the committed scope; only if time is left after phase 5)

```bash
uv run pytest src/data/tests -k "trend" -q
```

Expected (SC-014): observed 1.3 × M1 projects 1.3 × M1; 2.0 × clamps to 1.5; 0.5 × to 0.7; 2 traversals give ratio 1; a traversal touching an `estimated` departure is not counted; in a normal run every ratio is within [0.7, 1.5] and no recommendation appears.

## Cycle time (every phase from 2)

```bash
# A: model on, B: MPC_ENABLED=off, same seed and scenario; 108 cycles of 5 s (2,700 s)
$PF logs refresh | python -c "import sys,json,statistics as s; d=[json.loads(l) for l in sys.stdin if l.startswith('{') and '\"refresh_cycle\"' in l]; x=sorted(r['duration_ms'] for r in d); m=sorted(r.get('model_ms',0) for r in d); print('n',len(x),'median',s.median(x),'p95',x[int(len(x)*.95)-1],'max',x[-1],'| model median',s.median(m),'max',m[-1])"
```

Report median, p95 and max of `duration_ms` and of `model_ms` for A and B, and the 4-hour stress run near the end of phase 2. Pass (SC-011): max `duration_ms` below 5,000 and no cycle skipped because of the model; planning targets: added median ≤ 60 ms, added max ≤ 150 ms, p95 at demo length ≤ 250 ms. Compare with 005's figures (demo p95 about 100 ms; 4-hour median about 1.55 s, max 1.6 s; issue #21) and state the difference.

## Independence check (SC-012)

```bash
$PF stop api            # the backend and console are not needed
$PF ps                  # ingestion and refresh keep running
```

Expected: bronze keeps growing and `gold.recommendation` keeps being updated. A static test shows no network client import and no LLM call on the model path.

## Cleanup

```bash
$PF down -v        # removes only the pf006 project and its volume
```
