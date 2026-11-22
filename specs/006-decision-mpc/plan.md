# Implementation Plan: Decision Model (Simulation-Based MPC)

**Branch**: `feature/006-decision-mpc` (the setup script reports `006-decision-mpc`), stacked on `feature/005-data-fixes-metrics` (head `8c1a0b7`, PR #22 not merged) | **Date**: 2026-11-22 | **Spec**: [spec.md](spec.md) (approved by the data owner, including the amendments of 2026-11-22, commit `bada3fa`)

**Input**: `specs/006-decision-mpc/spec.md`, read in full. Also read: `specs/002`, `004`, `005` (plan, research, data-model, verification), the code under `src/data/`, `contracts/read/`, and, from `origin/docs/data-contract-005`, `docs/data-contract.md` v0.3 (§4.5, §4.6, H2, Q7, Q11, Q13) and the ADR-0006 and ADR-0007 amendments of 2026-11-22. The data owner's prototype (`~/Documents/contexto/simulacion-despacho.html`) and the brief (`datos/modelo-decision-mpc.md`) are references, not code to copy.

**Notes on the run**: `setup-plan.sh` was not executable (run with `bash`). `.specify/extensions.yml` does not exist, so no before-plan or after-plan hooks apply. The constitution is v1.2.0 and the active turn is turn 1 (`docs/turns-ritmo.md` v0.1.2).

## Summary

The decision model is data analytics. Every refresh cycle, inside the cycle transaction (REPEATABLE READ, same `M` as silver and gold), a pure, deterministic projector simulates the next 1,800 s of every bus and rider from the snapshot, once without action and once per candidate action. The score of a world is total passenger time (queue-seconds waiting + onboard delay + reserve cost). Candidates exist only when their catalog condition holds. The top 3 whose saving is at least 15 s per rider are written to a new table, `gold.recommendation` (one row per `rec_id`, `doc` shaped as `recommendation.schema.json` 1.1.0). Status is derived from `decision` events and expiry. The seed (file, table, loader, env var) is removed; the hold executor, `gold.instruction_status` and the simulator poller read `gold.recommendation`. The simulator also executes approved `slow_down` and `reserve_dispatch`. **Phase 2b (data owner, 2026-11-22)** also stores the model's "do nothing" projection every cycle in the append-only `gold.mpc_projection` and compares it with what really happened in the view `gold.v_projection_accuracy` (FR-035, FR-036, SC-016), so the model is measured continuously. A shift log (`gold.decision_log`) and a report of the approved action's effect are separable later phases inside the committed scope; the road-trend correction (FR-031) is outside the committed scope and is built only if time is left after phase 5 (gate decision 1).

**Approach** (details in [research.md](research.md)):

- **Event-driven projector, not a 5 s stepper.** Buses are events on a heap; queues are cumulative-arrival functions. Stop times are rounded up to the simulator's 5 s grid so crafted tests are hand-computable. A kernel of this shape runs in 0.065 ms per projection in a scratch benchmark (81 events). With a 30× allowance for the real code, 11 to 30 projections cost about 20 to 60 ms per cycle.
- **No new service, no new dependency, no randomness, no network** (Principle III). One new init script `src/data/db/init/009_decision_mpc.sql` (sections per phase). New pure rules in `src/data/rules/`; orchestration in `src/data/pipeline/`.
- **Contract files**: only the two additive bumps of FR-029 (the recommendation bump also carries `action.speed_reduction_pct`, gate decision 2). No ADR text, no `docs/data-contract.md`.
- **Same cycle, same snapshot** (FR-001): the model runs inside `run_cycle`, after `build_snapshot`, `build_instruction_status` and before COMMIT. It never opens its own transaction and never reads outside `id <= M` and `event_ts <= as_of`.

## Technical Context

**Language/Version**: Python 3.12+ (existing). No new package.

**Primary Dependencies**: psycopg 3, Pydantic V2 and the generated models (existing). `datamodel-codegen` regenerates `recommendation.py` (existing `make generate-read`).

**Storage**: PostgreSQL only. New: `gold.recommendation`, `gold.mpc_evaluation`, `silver.stop_queue`, `config.decision_model`, `config.ref_train_arrival` (phase 2); `gold.mpc_projection` and the view `gold.v_projection_accuracy` (phase 2b); `gold.decision_log` (phase 4); trend columns in `config.decision_model` (phase 6, optional). Dropped: `config.seed_recommendation`. Bronze stays insert-only.

**Testing**: pytest. Pure rules tested without a database. Integration tests use the existing `conn` fixture. Host suite plus the CI-ready command `docker compose --profile tools build tests && docker compose --profile tools run --rm tests` (coverage gate 80 %).

**Target Platform**: Linux containers (`docker compose`), as today. No new service.

**Project Type**: data pipeline (disciplined lane), with a simulator change.

**Performance Goals**: SC-011: the model's added time per cycle fits in the 5 s refresh interval at its maximum. Planning target: added median ≤ 60 ms, added maximum ≤ 150 ms at demo length (see Cycle time in research.md R9).

**Constraints**: deterministic, the model never reads the simulator's demand scale (`SIM_DEMAND_SCALE` is a demo setting of the simulator only), no LLM, no external call on the model path; hold ≤ 90 s; nothing on `estimated` or `sources_down` buses; no recommendation on a snapshot older than 15 s; `horizon_s = 600`; simulator never blocks on the database.

**Scale/Scope**: one corridor, direction 1, 5 buses plus 2 reserves, 18 stops, 17 segments.

**Unknowns**: none. The three open questions of the first draft were decided by the data owner on 2026-11-22 (section "Decisions of the data owner" at the end).

## Constitution Check

Gate source: `.specify/memory/constitution.md` v1.2.0 and `docs/turns-ritmo.md` v0.1.2 (turn 1 active).

| Gate | Result | How the plan satisfies it |
|---|---|---|
| I. Risk-first order | PASS | Level 1 risk here is data integrity. Phase order puts determinism, safety rules and the human gate first; the optional value items (trend, report, log) come last and are the first to cut; the trend is already outside the committed scope. No adaptive-lane feature is added. |
| II. Contract-first and data ownership | PASS | The two schema bumps and their fixtures and contract tests are tasks that precede the code that emits them. Every new table has an owner (data, `src/data/pipeline/`), a schema validated at the boundary (generated Pydantic model for `doc`) and lineage columns (`rules_version`, `max_bronze_id`, `first_snapshot_id`). The model's `doc` is validated with `RecommendationV110` before insert. |
| III. Isolated ingestion, deterministic real time | PASS | The model runs in the `refresh` container, off the capture path. Ingestion and the simulator keep running if refresh or the backend stops. No LLM, no network call, no randomness. A cycle longer than the interval is skipped by the existing loop (FR-039 of 002). The simulator keeps reading `gold.recommendation` with a read-only session and a 2 s timeout, as in story 004. |
| IV. Human gate | PASS | The model writes only `proposed` rows. `applied` is derived only from a backend `decision` event; the simulator acts only on an `apply` decision. A test (SC-007) proves no row reaches `applied` without a `decision` in bronze. The static test `test_no_bronze_writes` stays green (the model writes gold only). |
| V. Test-first and gates | PASS | Each phase starts with failing tests. Coverage stays above 80 %. Gate 1 in turn 1 is schema validation: both schemas are checked with the existing contract tests. Gate 2: unit and integration suites. Gate 4: dispatcher approval, kept (the model never writes a decision). |

**Turn-1 scope check** (`docs/turns-ritmo.md` §3): PostgreSQL only, no Redis, no PostGIS, position as distance in meters, 5 s step, 5 + 2 buses. Hold, reserve dispatch, slow down are within the "hold, adjust departure and reserve dispatch, always with dispatcher approval" scope of RF-2.3; `slow_down` and `skip_stop` are new action types added by the data owner's decision of 2026-11-21. Deferred norms (RBAC, JWT, mTLS, HMAC, SAST/SCA, Redis, 1,000 events/s) are not designed here and are not reported as findings. Evolution notes: execution of `adjust_departure` and `skip_stop`, both directions, short turns, live traffic feeds, the recommendation effect table (story 004 phase 3).

**Post-design re-check (after Phase 1 artifacts)**: PASS, same result. Two points to watch in review, not violations: (1) the `decision` event's `reason` is free text and is copied, never computed on, and never logged in the structured cycle log (privacy rule of the security steering, A09); (2) the closed `lineage` object of the recommendation schema cannot carry the model parameters, so they are stored in a side column of `gold.recommendation` (R10 in research.md).

**Update of 2026-11-22 (data owner's gate decisions)**: the Constitution Check result does not change. (a) `action.speed_reduction_pct` extends the FR-029 list of schema changes by one optional field; the data owner decided it, and it satisfies Principle II because it is defined, fixtured and contract-tested before the code that emits it. (b) `SIM_DEMAND_SCALE` touches only the simulator and the `.env.example`; the model never reads it, so Principle III (deterministic real time) and the golden hash are unaffected. (c) Dropping phase 6 from the committed scope leaves the Level 1 items (Principle I) untouched.

**Complexity Tracking**: no unjustified violation. Nothing to track.

## Deadline and budget

Data owner, binding: demo on 2026-11-24; about 6 hours of agent work. **Gate decision 1 (2026-11-22): budget approved with the first cut applied.** The road trend (FR-031, phase 6) is out of the committed scope and stays as the last, optional phase: it is built only if time is left after phase 5. Times include tests-first, the phase gate (host suite, CI-ready command, coverage), the live check under a dedicated compose project and the cycle-time measurement. Phase order is the reverse of the cut order (FR-034).

**Committed scope = phases 1, 2, 2b, 3a, 3b, 3c, 4, 5.** Phases 1, 2, 2b and 3a are never cut. Phase 2b was added by the data owner on 2026-11-22 (spec commit `c35d654`), after the table below was first approved.

| Phase | Content | Status | Hours | Cumulative |
|---|---|---|---|---|
| 1 | US1: projector, scoring, parameters, determinism (pure Python) | committed, never cut | 1.25 | 1.25 |
| 2 | US2: inputs, candidates, top 3, `gold.recommendation`, derived status, expiry and rest, schema 1.1.0 (recommendation, with `action.speed_reduction_pct`), seed retirement, hold executor and `instruction_status` on `gold.recommendation`, safety rules, `SIM_DEMAND_SCALE` and its live check (+0.15 h) | committed, never cut | 2.15 | 3.40 |
| 2b | US2 extension (added 2026-11-22): projection record `gold.mpc_projection` (append-only, every cycle) and view `gold.v_projection_accuracy`, aggregate query for SC-016, `RULES_VERSION` 1.7.0 (FR-035, FR-036, SC-016) | committed, never cut | 0.60 | 4.00 |
| 3a | US3 holds: scripted-approval end-to-end check on the new source (SC-008, SC-009) | committed, never cut | 0.25 | 4.25 |
| 3b | US3 `slow_down` execution, reading `speed_reduction_pct` from the recommendation (separable task group) | committed, cut third | 0.50 | 4.75 |
| 3c | US3 `reserve_dispatch` execution (separable task group) | committed, cut third | 0.75 | 5.50 |
| 4 | FR-032 and FR-033: `command_event` 1.1.0 `reason`, `gold.decision_log` (`RULES_VERSION` 1.8.0) | committed, cut second | 0.60 | 6.10 |
| 5 | US4: effect of the approved action (reduced from 0.60 h: the projection error now comes from `gold.v_projection_accuracy`) | committed, cut first | 0.35 | **6.45** |
| **cut line** | | | | |
| 6 | FR-031: road trend (`RULES_VERSION` 1.9.0, or 1.8.0 if phase 4 is cut) | **optional**, only if time is left after phase 5 | 0.40 | 6.85 |

**Hours and the cut line.** The committed scope was 5.95 h in the gate decision, then 6.10 h with `SIM_DEMAND_SCALE`, and is now **6.45 h**: phase 2b adds 0.60 h and phase 5 gives back 0.25 h (it no longer re-projects or reports the projection error). The 6.10 h came from: phase 2 grows by 0.15 h for `SIM_DEMAND_SCALE` (a small task plus its live check, gate decision 3). The `speed_reduction_pct` field (gate decision 2) adds a few minutes to the schema, fixtures and tests of phase 2 and removes the side-column read from 3b, so it is absorbed in the existing 2.15 h and 0.50 h. Before phase 2b the committed scope was 0.10 h above the 6 h target (now 0.45 h); this is inside the ±25 % uncertainty of phase 2 but it is stated, not hidden (see "What no longer fits" in the report of this update and risk 7).

**Overrun rule (binding).** If phase 2 or phase 3 (3a to 3c) overruns its estimate by more than 0.5 h, cut in this order: first phase 5, then phase 4, and only then touch 3b and 3c. Phases 1, 2 and 3a are never cut. Phase 6 is not part of this order: it is never started while any committed phase is late.

Checkpoints for the data owner:

1. After phase 3a (4.25 h): the never-cut core is done. Committed remaining about 2.20 h.
2. After phase 3c (5.50 h): measure the overrun of phases 2 and 3. More than 0.5 h: cut phase 5, then phase 4.
3. After phase 5 (6.45 h): only if hours remain, start phase 6.

Each phase ends with a check that can be run (quickstart.md): phase 1 the pure test group; phase 2 the integration group, 2b the projection record check (rows per cycle, rerun identical, SC-016 table), the live C1 check at the default scale and at `SIM_DEMAND_SCALE=3`, and the cycle-time measurement; 3a the scripted approval; 3b the speed-ratio test; 3c the reserve-appears test; 4 the SC-015 cases and Q11; 5 the report command run twice; 6 the SC-014 cases. Each phase can be committed on its own. The data owner commits (agents never commit).

## Project Structure

### Documentation (this feature)

```text
specs/006-decision-mpc/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    ├── README.md
    ├── recommendation-1.1.0.md
    ├── command-event-1.1.0.md
    ├── gold-recommendation.md
    └── execution.md
```

`tasks.md` is not created here (`/speckit.tasks`).

### Source code (files to be touched)

`[CO]` marks a CODEOWNERS path (`/contracts/`, `/src/data/rules/`, `/docs/adr/`): the data owner must review it. Nothing under `src/api/`, `.kiro/`, `.specify/`, `.github/`, `CODEOWNERS` or the constitution is touched. No ADR and no `docs/data-contract.md`.

```text
contracts/read/                                              [CO]
├── recommendation.schema.json          # 1.0.0 -> 1.1.0 (phase 2): new action types, optional action.speed_reduction_pct
├── command_event.schema.json           # 1.0.0 -> 1.1.0 (phase 4)
├── README.md                           # version notes
└── fixtures/                           # new dirs only; no existing fixture changes
    ├── c1_slow_down/recommendation.json            (phase 2, carries speed_reduction_pct)
    ├── c2_skip_stop/recommendation.json            (phase 2)
    ├── c1_discard_reason/command_event.json        (phase 4)
    └── c1_discard_legacy/command_event.json        (phase 4, a 1.0.0 decision without reason)

src/data/rules/                                              [CO]
├── __init__.py                         # RULES_VERSION 1.5.0 -> 1.6.0 (phase 2) -> 1.7.0 (phase 2b); bump again if a later phase changes gold output (phase 4: 1.8.0)
├── mpc_params.py                       # new, phase 1: parameter dataclass and defaults
├── projector.py                        # new, phase 1: pure projection and score; phase 2b: `projection_record` (pure rows of the baseline)
├── mpc.py                              # new, phases 1-2: candidates, ranking, rec keys, rec_id, status derivation, rest rule
├── trend.py                            # new, phase 6 (optional, outside the committed scope)
└── sql/
    ├── silver_stop_queue.sql           # new, phase 2
    ├── silver_bus_current_state.sql    # phase 2: add occupancy
    ├── mpc_inputs_*.sql                # new, phase 2: rates, open visits, last terminal departure
    ├── hold_orders.sql                 # unchanged (still the shared decision query)
    ├── decision_log.sql                # new, phase 4
    └── trend_ratio.sql                 # new, phase 6 (optional)

src/data/pipeline/
├── recommend.py                        # new, phase 2: load inputs, run model, write gold.recommendation and gold.mpc_evaluation; phase 2b: project the baseline every cycle and append gold.mpc_projection
├── cycle.py                            # phase 2: call recommend step; phase 4: call decision_log step
├── holds.py                            # phase 2: orders from gold.recommendation instead of config.seed_recommendation
├── decision_log.py                     # new, phase 4
├── reference.py                        # phase 2: load config.ref_train_arrival
├── silver.py                           # phase 2: add silver.stop_queue to the build order
├── seeds.py                            # DELETED, phase 2
└── compute.py                          # phase 2: remove load_seeds

src/data/refresh/run.py                 # phase 2: remove load_seeds; log model_ms
src/data/seeds/                         # DELETED, phase 2 (recommendations.json and loader)
src/data/validation/counterfactual.py   # new, phase 5 (effect of the approved action)
src/data/db/init/009_decision_mpc.sql   # new, sections per phase; DROP TABLE IF EXISTS config.seed_recommendation
src/data/db/init/007_scenarios.sql      # edit: remove the seed table section (phase 2)

src/data/simulator/
├── scenarios/holds.py                  # phase 2: poller reads gold.recommendation; no seed loader
├── scenarios/actions.py                # new, phases 3b/3c: slow_down (reads action.speed_reduction_pct from the doc) and reserve orders (separable)
├── engine.py                           # phases 3b/3c: small hooks, inert without orders; `run` already has `demand_scale` (unchanged by SIM_DEMAND_SCALE)
├── scenarios/ (scenario_events wrapper)  # phase 2: forward `demand_scale` to `engine.run`
└── main.py                             # phase 2: read SIM_DEMAND_SCALE (default 1.0, range 0.1-10, invalid stops before the first event) and pass it to `engine.run(demand_scale=...)`; no seeds; phase 3: pass the board

src/pulsoflota/config.py                # remove get_seed_recommendations_path (phase 2)
src/pulsoflota/models/read/recommendation.py   # regenerated (RecommendationV110), phase 2
.env.example                            # remove SEED_RECOMMENDATIONS_PATH; add MPC_ENABLED and SIM_DEMAND_SCALE (phase 2)
Makefile                                # none (generate-read already covers recommendation)

src/data/tests/                         # unit, integration, contract tests per phase (see quickstart.md)
tests/unit/test_env_example.py          # phase 2: env var list (adds MPC_ENABLED, SIM_DEMAND_SCALE)
```

**Structure Decision**: keep the existing layered layout (pure rules in `rules/`, orchestration in `pipeline/`, simulator in `simulator/`). The projector and the model rules are pure so they can be tested without a database (FR-028). Execution of `slow_down` and `reserve_dispatch` lives in one new module (`scenarios/actions.py`) plus two inert hooks in the engine, so cutting item 4 means not merging that module and the hooks.

## Risks

1. **Phase 2 is large** (inputs from four sources, rec lifecycle, seed retirement, `SIM_DEMAND_SCALE`). Mitigation: pure rules first, SQL inputs second, seed retirement last in the phase, each with a test that fails first. An overrun above 0.5 h triggers the cut rule in "Deadline and budget".
2. **Simulator golden hash** must not move (SC-009). The engine changes are guarded (`if board is not None and order`); `SIM_DEMAND_SCALE` defaults to `1.0`, which is the value `engine.run` already uses, so the default stream is byte-identical. The existing golden tests run in every phase, and a new test runs `main` logic with the variable unset and with `1.0` and compares hashes.
3. **Real-demand risk: the model may find no saving in C1.** At the reference demand the model's expected saving is small and may stay under 15 s per rider (SC-003): about 53 train riders per hour at Prado and 0.83 riders per hour at a street stop at 17:00 (research R13). The data owner's prototype showed +33 s with its own, higher demand. **Mitigation (gate decision 3):** the simulator exposes `SIM_DEMAND_SCALE` (default `1.0` = the real reference demand; safe range 0.1 to 10), passed to `engine.run(demand_scale=...)` from `simulator/main.py` and documented in `.env.example`. The demo runs C1 with `SIM_DEMAND_SCALE=3`, the same as the HTML prototype. It is a demo setting, not a model change: the model never reads it, a static test fails if any module under `rules/` or `pipeline/` references it, and the model's inputs (observed queues and rates in bronze) are the only way the extra demand reaches it. The result is reported as the model yields it; parameters are not tuned. The plan states in the demo notes that the demo ran at scale 3.
4. **Hour-boundary scoring** (17:00 to 18:00 is the demo window): both hours are read for each projected step; tested with crafted input crossing 18:00.
5. **Existing volumes** do not re-run init scripts: `009_decision_mpc.sql` is applied by hand (quickstart.md), as for 007 and 008.
6. **4-hour stress cycle** is already at 1.55 s (issue #21); the model adds a roughly constant amount (R9). Reported, not hidden.
7. **Committed scope is 6.45 h, 0.45 h above the 6 h target** after adding `SIM_DEMAND_SCALE` (+0.15 h, to 6.10 h) and phase 2b (+0.60 h) and reducing phase 5 (−0.25 h). No slack. The overrun rule protects phases 1, 2 and 3a; phase 6 is not started unless every committed phase is done.
8. **A demo scale hides the real-demand result.** A run at scale 3 can show a recommendation that does not appear at scale 1. Mitigation: `verification.md` records both runs (default scale and scale 3) and the demo states which scale it used.

## Decisions of the data owner (human gate, 2026-11-22)

All three open questions of the first draft are **DECIDED**. No `[NEEDS CLARIFICATION]` remains.

1. **DECIDED: slow-down intensity is a field in the contract.** `recommendation.schema.json` 1.1.0 adds an optional `action.speed_reduction_pct`, required when `action.type = 'slow_down'` and absent otherwise, enforced by the schema conditional like `duration_s`. The simulator (phase 3b) reads it from the recommendation `doc`, not from a side column. Exact change in [contracts/recommendation-1.1.0.md](contracts/recommendation-1.1.0.md).
2. **DECIDED: rank of a stale proposal.** A stale proposal keeps its last rank, its frozen numbers and `stale = true` until it expires. SC-003 ("at most 3 per cycle") counts only the current top 3.
3. **DECIDED: rest after a decision.** The 5-minute rest also starts at a decision (applied or discarded), at the decision's event time, not only at expiry.

Also decided on the same date: gate decision 1 (budget and cut line, section "Deadline and budget") and gate decision 3 (`SIM_DEMAND_SCALE`, risk 3, phase 2).
