# Research: Decision Model (Simulation-Based MPC)

**Feature**: `specs/006-decision-mpc` | **Date**: 2026-11-22 | Phase 0 output of `/speckit.plan`

Every number below was taken from the repository, the reference data, the data contract v0.3, the prototype, or a throwaway script (not committed, marked "scratch"). Nothing is invented. A value that is a declared assumption says whose and where it is stored. No `NEEDS CLARIFICATION` is left here. The three questions of the first draft were decided by the data owner on 2026-11-22 (`plan.md`, "Decisions of the data owner").

## R1. Where each input of FR-003 is read, and why the read is consistent (FR-001)

The model runs inside `run_cycle`, after `build_snapshot` and `build_instruction_status`, before COMMIT. The cycle is REPEATABLE READ and every read below is either (a) a table rebuilt in this same transaction, or (b) bronze filtered by `id <= M` and `event_ts <= as_of`, where `M` and `as_of` are the cycle's own. So the model sees exactly the world the snapshot was built from, and a second run on the same `(as_of, M)` reads the same rows.

| Input (FR-003) | Source | Why this source |
|---|---|---|
| Bus position, next stop, `bus_state`, `data_quality` | `gold.decision_inputs.doc.buses` of this snapshot | It is the snapshot (FR-001). Same objects as `corridor_now`. |
| Bus occupancy | `silver.bus_current_state.occupancy` (new column, phase 2) | `decision_inputs.buses` has no occupancy. `bus_position.payload.occupancy` exists in bronze; silver takes it from the same newest in-range position row that supplies `distance_along_m`, so both agree. |
| Bus at a stop (dwelling) and when it arrived | bronze `stop_arrival` with no `silver.stop_visits` row (the `_OPEN` query of `pipeline/holds.py`, bounded by `event_ts` ≥ `as_of` − 10 min) | The remaining dwell of a bus at a stop is `arrival + dwell(boarded, alighted) − as_of`, with `boarded` and `alighted` from that arrival's payload. |
| M1 per segment, per local hour | `gold.m1_baseline` (all 24 bands, rebuilt this cycle) | The snapshot doc holds only the current hour's forecast. A 1,800 s window can cross the hour (17:00 to 18:00 is the demo window), so each projected step reads its own local hour band (`timebands.local_hour_band`). |
| Metro train arrivals at Prado | `config.ref_train_arrival` (new, 511 rows, loaded from `data/reference/train_arrivals.csv` by `pipeline/reference.py`) | The simulator reads the same file. 40 trains per hour at 17:00 and 18:00 (scratch count). |
| M2 | `gold.m2_baseline` (bands covering the window) | Gives the expected riders per 15-minute band at P-883. Per-train batch = M2 band / trains in that band, delivered at train time + mean walk 120 s (the simulator draws walk uniformly in 60 to 180 s). |
| Rider arrival rate at the other stops | bronze `rider_arrival` in `(as_of − 30 min, as_of]` per stop (index `bronze_events_type_ts_idx`), else the reference rate | Spec: observed over the last 30 minutes, reference as fallback. |
| Current queue per stop | `silver.stop_queue` (new table, rebuilt each cycle) | FR-004. See R3. |
| Next terminal departure | `max(departure_ts)` at P-883 in `silver.stop_visits` (and an open visit at P-883) + `config.corridor_settings.headway_planned_s` (600) | FR-003 literally. Following slots add one planned headway each. |
| Free reserves, drivers | `decision_inputs.doc.resources` | Snapshot. |
| Enabled stops | `decision_inputs.doc.enabled_stops` | A hold or adjustment targets only an enabled stop. |
| Breakdown end | `silver.incidents.end_ts` for a `bus_breakdown` active at `as_of` | A broken bus is projected as stopped until `end_ts`. |
| Parameters | `config.decision_model` (one row) | FR-010: never constants in code. |

Silver is rebuilt by DELETE and INSERT in the same transaction (002 R2), so the new `silver.stop_queue` and the `occupancy` column are part of the same consistent read.

## R2. Alighting share per stop (spec Assumptions: not invented)

There is no origin-destination data in `data/reference/` (checked `SOURCES.md`: only the Metro hourly shape, the daily volume, congestion, stops, segments and trains). The only source is the simulator's destination model, which the projector must match to be consistent with the world it predicts:

- Train riders (boarding at stop index 0): `dest = randint(1, last)` (`engine.py`, step 1).
- Street riders boarding at stop `i`: `dest = randint(i + 1, last)` (`engine.py`, step 2).
- A rider alights at the first stop equal to the destination; riders whose destination is passed have already left.

Take stop indices `0..last` (`last` = 17). A rider on board when the bus reaches stop `i` boarded at some stop `j < i` and has `dest ≥ i`. Whatever `j` is, its destination is uniform on `j+1..last`, so given `dest ≥ i` it is uniform on `i..last`. The alighting share at stop `i` is therefore exactly:

`alight_share(i) = 1 / (last − i + 1)`, and `1` at `i = last`.

**Finding (data owner's HTML prototype).** The prototype alights a share of `1/(LAST − i)` of the occupancy at stop `i`. The simulator's destination model implies `1/(LAST − i + 1)`: a rider on board at stop `i` has a destination uniform on `i..LAST`, which is `LAST − i + 1` equally likely stops. The plan adopts `1/(LAST − i + 1)`. The prototype's formula alights everyone one stop early (at `i = LAST − 1` it gives 1 where the simulator's model gives 1/2); it is a known difference, not a precedent, and the simulator-based check below measures which is right.

**Deviation from the prototype**, stated: the prototype uses `occ / max(1, LAST − i)`, which alights everyone one stop early (at `i = LAST − 1` it gives 1 where the model gives 1/2). The plan uses the exact value and records the prototype's as a known error, not a precedent. The share is a function of the stop index and `last` only, so no stored table is needed.

Verification (phase 1, no database): run the engine for one simulated hour (seeds 42 and 43), group `stop_arrival` payloads by stop and compare `Σ alighted / Σ occupancy_in` with the formula. The test reports the largest absolute difference and asserts it is within a tolerance fixed after the first run and recorded in `verification.md`; the simulator's randomness is the source of the gap (SC-010 reports it too). If a stop has fewer than 30 boarded riders in the sample, the comparison for that stop is skipped, not forced.

## R3. Queue per stop (FR-004), traceable to bronze

`silver.stop_queue(stop_id, queue_riders, basis_ts, basis_bronze_id, as_of_ts)`:

`queue(stop) = rejected of the newest stop_arrival at the stop (any bus) + count of rider_arrival at the stop with event_ts > that arrival's event_ts`.

Why this is exact for the simulator: in a step, riders are released (step 3) before buses act (step 4), boarding happens at arrival, and `stop_arrival.rejected` is the queue left after boarding. A rider with `event_ts` after the arrival second was released later, so is still queued. A rider with `event_ts` at or before it was released before or in that step, so is already counted in `rejected` or boarded. `rejected` equals `len(queue)` after `board_fifo`. The same arrival second is used for both, so there is no double count.

Bound: both sides look back at most 30 minutes (`event_ts > as_of − 30 min`, the same window as the rates). A stop with no arrival in the window has `queue = count of rider_arrival in the window` and `basis_ts` NULL. This underestimates a stop nobody served for 30 minutes (a source outage longer than that). That is a declared limit. The bound keeps the query on the existing `(event_type, event_ts)` index and constant in cost as the run grows (R9).

The row carries `basis_bronze_id` (the largest bronze id used), which gives the traceability FR-004 asks for.

## R4. How the seed is retired without moving the story-004 golden hash (SC-009, H-15)

Today the simulator's poller learns what a `rec_id` means from the seed file (`SeedHold`), and `build_orders` in `pipeline/holds.py` does the same from `config.seed_recommendation`. After this story both read `gold.recommendation`:

- **Pipeline (`build_orders`)**: `SELECT rec_id::text, doc FROM gold.recommendation` replaces `_SEEDS`; `type = 'hold'` filter, first `decision` per `rec_id` by bronze id, unchanged. `expires_ts` is the row's. `observe()` in `rules/holds.py` is untouched, so every 004 rule (cap 90 s, tolerance ±15 s, strict-after-decision matching, conflict, breakdown) keeps its tests.
- **Simulator**: `HoldPoller.poll_once` fetches decisions with the existing shared query, then looks the `rec_id`s up in `gold.recommendation` (`SELECT rec_id, doc, params`) with the same read-only session and 2 s timeouts. `HoldBoard.apply_decision` takes the action from that row instead of `_seeds`. A decision whose row is not found yet is kept and retried on the next poll (the row is written in a cycle that commits before the console can list it, so this is a tolerance, not an expected path). The database-down behavior is unchanged: log once, keep known orders, never block the stream.
- **Hash**: the engine is not changed in phase 2 at all. With nothing approved, the board is empty and `dwell_end` returns `natural_end`; the existing `test_simulator_golden_hash` and the 004 "empty bronze is byte-identical" test run unchanged in every phase. Phases 3b and 3c add hooks to the engine guarded by "an order exists"; the same tests prove they are inert.
- **Removal list** (SC-009 "0 reads"): `src/data/seeds/` (file and loader), `pipeline/seeds.py`, `config.seed_recommendation` (`DROP TABLE IF EXISTS` in `009`, and the section removed from `007`), the `load_seeds` calls in `refresh/run.py` and `pipeline/compute.py`, `get_seed_recommendations_path`, `SEED_RECOMMENDATIONS_PATH` in `.env.example` and its entry in `tests/unit/test_env_example.py`, `SeedError` handling in `simulator/main.py`, tests `test_seeds.py` and the seed fixture file. A test greps the tree for `seed_recommendation`, `recommendations.json` and `SEED_RECOMMENDATIONS_PATH` and fails if any remains outside `specs/` and `docs/`.
- **Tests that used seed rec ids** (`test_hold_board`, `test_hold_poller`, `test_hold_loop`, `test_instruction_status`, `test_stop_ewt_gold`, `test_schema_init`): a small builder in `src/data/tests/fixtures/` inserts a validated `gold.recommendation` row for a given hold. The scenario values stay identical, so the expected numbers in `verification.md` of 004 keep their meaning.

`DROP TABLE` on `config.seed_recommendation` removes demo data only. No bronze row is touched.

## R5. Executing `slow_down` and `reserve_dispatch` in the simulator (FR-023, FR-026), separable

Both orders arrive through the same poller as holds and live in a new module `scenarios/actions.py` (one `ActionBoard` next to `HoldBoard`). Cutting item 4 means leaving that module and its two engine hooks out; phases 1, 2 and 3a do not depend on it.

**`slow_down`** (phase 3b). Order: `bus_id`, `from_s` (the decision's simulated second), `until_s = from_s + duration_s` (300 s), `share = action.speed_reduction_pct / 100` (10 or 20 today), read from the recommendation `doc` that the poller already fetches, not from a side column (gate decision 2). Engine hook: in the driving step, `b.drive_t += STEP_S × factor`, where `factor = 1 − share` while `from_s < t ≤ until_s` and the bus is driving, else 1.0. The reported `speed_kmh` is scaled by the same factor. Because the engine advances along a precomputed time profile, a lower factor stretches the trip by exactly `share/(1 − share)` of the covered time, which is what the projector models (segment time ÷ (1 − share)). No random draw is consumed, so streams without an order are bit-identical (the hook is `if factor != 1.0`). The prototype multiplies speed by `(1 − p)`; same effect.

**`reserve_dispatch`** (phase 3c). Order: reserve `bus_id`, `from_s`, `start_s = from_s + 120` (readiness, `config.decision_model.reserve_ready_s`; the simulator reads it from the order row's `params`, because the simulator never reads `config` tables; `params` keeps only `ready_s` and carries nothing for `slow_down`). Engine hook: when `t ≥ start_s` and the reserve is not yet in `buses`, append a `Bus(bus_id, start_at=t)` and call `start_trip` (one profile draw from the single seeded `rng`, at a step fixed by the order, so the run stays deterministic given the same orders). After its last stop the reserve goes to a terminal phase `off` with no further events (its trip is not re-dispatched, as the layover stands in for a return leg only for the five base buses). The reserve emits `bus_position`, `stop_arrival` and `stop_departure` like any bus. `config.fleet_roster` already lists B-106 and B-107; `decision_inputs.buses` already allows their ids.

**`adjust_departure` and `skip_stop`** (FR-024): `apply_decision` returns no order and increments `ignored_not_executed[type]`; one JSON log line per `rec_id` (`not_executed_in_this_story`). Nothing else changes.

**Determinism of approved runs.** An approved run is deterministic given the same decisions in bronze at poll time, as in story 004: tests insert decisions before the run (forced mode); live runs depend on poll timing exactly as holds already do (declared in 004).

## R6. The two schema bumps (FR-029)

Both are additive. Details in `contracts/recommendation-1.1.0.md` and `contracts/command-event-1.1.0.md`.

**Recommendation 1.0.0 → 1.1.0** (phase 2):

1. `title`: `Recommendation (v1.1.0)`. The generated class becomes `RecommendationV110` (the generator names it from the title). The only importer is the seed loader, which is deleted; `pipeline/recommend.py` and the tests use the new name.
2. `schema_version` enum: `["1.0.0", "1.1.0"]`. This keeps all 18 existing fixtures valid (SC-013). The model writes `1.1.0`.
3. `action.type` enum gains `slow_down` and `skip_stop`.
4. The `duration_s` rule is a chain of `if/then/else`: `hold` 0 to 90, `adjust_departure` −600 to 600, **`slow_down` 1 to 1800** (new), else null (`reserve_dispatch`, and **`skip_stop`** new). The cap of 1800 is the scoring window; the value used is 300.
5. **`action.speed_reduction_pct`** (decision 2): optional number `0 < x <= 50`, required when `type = slow_down` and forbidden otherwise, through a separate `allOf` conditional like the one on `duration_s`. Range reasoning and exact text are in `contracts/recommendation-1.1.0.md`. The schema does not enumerate 10 and 20 because `config.decision_model.slow_shares` is a parameter (FR-010); the model only writes values taken from it.
6. `case`, `lineage` and every other property are unchanged (`lineage` is closed, which drives R10).

Fixtures: two new directories (`c1_slow_down`, `c2_skip_stop`), because the fixture file stem must equal the schema name. The test that asserts "18 fixtures" is updated to 22 once both bumps exist (20 after phase 2).

**Command event 1.0.0 → 1.1.0** (phase 4):

1. Envelope `schema_version` enum `["1.0.0", "1.1.0"]`. A 1.0.0 `decision` without `reason` therefore stays valid.
2. `decision` payload gains optional `reason`: string, `minLength 1`, `maxLength 200`. It is not added to `required`.
3. Nothing else changes (`incident_report` and `confirmation` untouched).

Fixtures: `c1_discard_reason/command_event.json` (1.1.0, with reason) and `c1_discard_legacy/command_event.json` (1.0.0, no reason). There is no generated model for `command_event` today (the `READ_SCHEMAS` list in the Makefile does not include it), so none is added; the contract test and the `test_bronze_builders` validator cover it. The Builder `command_decision` gains an optional `reason` argument (test fixture code).

`reason` is never logged (A09: it is free text) and never used in a computation: it is copied with `NULLIF(btrim(payload->>'reason'), '')` into `gold.decision_log`.

## R7. `rec_id`, lifecycle, expiry and rest (FR-014, FR-021, FR-030, SC-001, SC-007)

**Key.** `key = (action.type, bus_id, stop_id, duration_s, speed_reduction_pct)`, all read from the `doc` action. Including the intensity means a dispatcher approving "hold B-103 60 s at P-888" can never see the row change to 90 s under him. If the best intensity flips, that is a new proposal with a new `rec_id`, and the old one stays until it expires (the spec edge case).

**`rec_id`.** `uuid` shaped from `sha256("rec|{key}|{first_snapshot_id}|{model_version}")`, version-4 bits, the same technique as `rules/snapshot_id.py`. It is a pure function of the snapshot where the key was first recommended, so a rerun gives identical ids (SC-001) and a still-recommended proposal keeps its id (FR-014).

**Per cycle**, in this order, all derived from the previous table rows and this cycle's facts:

1. *Status derivation for every existing row* (always, even when the snapshot is stale or the model is off): first `decision` per `rec_id` by bronze id (the shared `hold_orders.sql` query, with `reason` added in phase 4) gives `applied` or `discarded`. Else `expired` if `as_of > expires_ts` or the bus has passed the stop; else `proposed`. "Passed the stop" means a row in `silver.stop_visits` for `(bus_id, stop_id)` with `arrival_ts ≥ proposed_ts`. For `reserve_dispatch` (stop P-883) it means the reserve has been seen leaving P-883. The decision wins over expiry.
2. *Candidates and scores*, only if the snapshot is fresh (≤ 15 s of `clock_timestamp() − snapshot_commits.committed_at`, FR-017) and not disabled.
3. *Match*: a current top-3 key that equals the key of a row still `proposed` and not stale keeps that row's `rec_id`, `proposed_ts`, `expires_ts`; its `ewt_saving_s`, `reason`, `rank`, `lineage.snapshot_id` and `data_quality` are refreshed.
4. *New*: a top-3 key with no live row, and not resting, gets a new `rec_id`, `proposed_ts = as_of`, `expires_ts = as_of + 120 s` (config `proposal_ttl_s`).
5. *Stale*: a `proposed` row whose key is not in this cycle's top 3 is flagged `stale = true`, its `doc` numbers are frozen, and it stays until it expires (decision 2 of the data owner, 2026-11-22: DECIDED, the proposal keeps its last rank, frozen numbers and `stale = true` until it expires).
6. *Rest*: a key is resting while `as_of < close_ts + 300 s` (config `rest_s`), where `close_ts = min(expires_ts, passed_ts)` for an expired row and, per the data owner's decision 3 (DECIDED, 2026-11-22), the decision's event time for a decided row, applied or discarded. The model skips resting keys when it fills the top 3. Everything in `close_ts` comes from facts in bronze and silver, so it is deterministic.

**Clock.** `as_of` is the cycle's reference time. With `REFRESH_CLOCK=data` (the `.env.example` default) it is simulated time, so `expires_ts` is in the same clock as the simulator's order window (`until_s = expires_ts − start`). With `REFRESH_CLOCK=wall` and a simulated stream the hold order's window would be off; that is the existing 004 limitation and the plan does not change it.

**Idempotency (SC-007).** Rows are written with `INSERT … ON CONFLICT (rec_id) DO UPDATE` of derived columns only; `proposed_ts`, `first_snapshot_id`, `key` and `rec_id` are never updated. The same bronze and the same cycle sequence give the same rows. Re-ingesting a duplicate batch is dropped by bronze idempotency (`source + event_id`), so `M` does not change.

**Not deleted.** The table keeps expired and decided rows for the run (a few per hour; at most 3 new proposals per 2 minutes), because `gold.instruction_status`, the shift log and the effect measure need the `rec_id` after the proposal closes. "Rebuilt each cycle in the cycle transaction" (FR-020) is met in the sense that every column except the four immutable ones is recomputed each cycle. A retention rule is out of scope.

## R8. `gold.decision_log` and Q11 (FR-033, phase 4)

Rebuilt each cycle by DELETE and INSERT in the cycle transaction from `gold.recommendation`, the first `decision` per `rec_id` and `gold.instruction_status` (data contract H2 and Q11). Columns exactly as H2: `rec_id` (PK), `case`, `action` (the doc's `action` object), `proposed_ts`, `expires_ts`, `outcome` (same derived status as the table, so the two cannot disagree: it reads the row's `status`), `decided_ts`, `user_id`, `reason`, `instruction_status`, `effect_result`, `rules_version`, `max_bronze_id`.

- `decided_ts`, `user_id`, `reason` come from the first decision's payload (`ts`, `user_id`, `reason`). `decided_ts` is the payload's `ts` (the dispatcher's click, schema: "UTC timestamp of the dispatcher click"); the simulated-time estimate of the decision (`decided_at_sim`) is used only for the rest rule and the hold order window, not exposed.
- `instruction_status` is `gold.instruction_status.status` (a left join: NULL while pending or for a non-hold).
- `effect_result` is NULL until the story-004 effect table exists (spec FR-033). The column is created now so Q11 is stable.
- Q11 is run as written in the contract (`WHERE proposed_ts >= … AND proposed_ts < … ORDER BY proposed_ts DESC`). An index on `proposed_ts` supports it.
- SC-015 cases are tests: discard with reason, 1.0.0 discard without reason (`reason IS NULL`), apply on a hold with `instruction_status` after the visit, no decision then `expired` after 2 minutes, rebuild idempotence.

**Observed check and tolerance (phase 1, T003/T013).** Seeds 42 and 43 pooled, 3,600 s, stops with at least 30 riders on board in the sample (the sample size is `Σ occupancy_in`, the denominator of the share, not riders boarded at that stop; 6 of 18 stops are skipped at scale 1). Results (`largest |observed − formula|`):

| Run | Stops compared | Formula `1/(last − i + 1)` | Prototype `1/(LAST − i)` | Tolerance (observed + margin) |
|---|---|---|---|---|
| scale 1.0 (the spec's check) | 12 | 0.0385 | 0.0500 | 0.06 (margin 0.0215) |
| scale 10 (same seeds, `demand_scale` argument, test only) | 17 | 0.0551 | 0.5263 | 0.10 (margin 0.0449) |

Margin: the runs are seeded and deterministic, so the margin does not absorb run-to-run noise; it absorbs an engine edit that changes the random sequence without changing the destination model. It is set near one binomial standard deviation of a stop at the smallest admitted sample, sqrt(0.25 / 100) = 0.05 at scale 10, and about half of that at scale 1 where the observed value is smaller. At scale 1 the sample is too small to separate the two formulas (0.0385 against 0.05), so the test that fails for the prototype's formula uses scale 10 (0.5263 against a tolerance of 0.10). Both numbers are in `verification.md`.

## R9. Cycle time (SC-011)

**Candidate count per cycle** (from the catalog conditions, FR-008). Per follower of a bunched pair: hold at its next stop 30/60/90 s (3) + slow down 10 % and 20 % (2) = 5. Per bus with a gap ahead: skip stops (1). When trouble exists (bunching, gap, breakdown or a queue above 20): adjust departure ±60 ±120 (4) + reserve (1 per free reserve candidate, taking the first free reserve). With one bunched follower (C1): 5 + 4 + 1 = 10, plus the baseline = **11 projections**. Maximum with 5 buses: 4 bunched followers (20) + 4 adjust + 1 reserve = 25 (the brief says about 30 with gap skips) plus the baseline = **26 to 31**. Hour boundary does not multiply the count.

**Cost of one projection.** Events: each bus passes at most 18 stops; on the corridor at demo time about 9 remaining stops for 5 buses plus 2 to 3 waiting buses starting at P-883 inside the window (a full trip takes about 1,370 to 1,430 s: 1,169 s drive at hour 17 plus 17 dwells of about 12 s, scratch computation from `segments.csv` and `congestion_factor.csv`), so about 80 events and at most 126. Scratch benchmark of the bare event loop (heap, queue update, boarding, dwell, 7 buses, 81 events, Python 3.12): **0.065 ms per projection**. The real projector adds dataclasses, hourly lookups, action hooks and the queue-integral bookkeeping. Allowance 30×: **about 2 ms per projection**.

| Part | Typical C1 | Worst |
|---|---|---|
| Projections (11 / 31) × ~2 ms | ~22 ms | ~62 ms |
| Input reads (6 to 8 small indexed queries: open visits, rates, queue, last departure, rows) | ~15 ms | ~25 ms |
| Writes (≤ 10 `gold.recommendation` upserts, 1 evaluation replace, doc validation) | ~5 ms | ~10 ms |
| **Added per cycle** | **~40 ms** | **~100 ms** |

These are estimates to be replaced by measurement in each phase. Against the current figures: demo cycle p95 about 100 ms (005) becomes about 140 ms typical and at most about 200 ms; far below the 5 s interval (about 40× margin at the worst case). The 4-hour stress cycle (about 1.55 s median, 1.6 s worst, issue #21) grows by the same roughly constant 40 to 100 ms, which is **+3 % to +6 %**, to about 1.60 to 1.70 s. The 1.5 s budget of 005 for the 4-hour figure is already exceeded by H-8 (linear growth of the silver rebuild); this story adds to that and says so. It does not make the 5 s interval risky. Why constant: every new query is bounded by `event_ts > as_of − 30 min` on the existing index, and `silver.stop_queue` has 18 rows; nothing scans all of bronze.

**Measurement** (each phase from phase 2):

1. The `refresh_cycle` log line gains `model_ms` (time of the model step only, `time.monotonic` around the call), so the model's own time is reported separately from the cycle's.
2. `MPC_ENABLED=off` (env, default on) skips candidate generation and the status/log steps, to A/B the same stream.
3. Run the 005 scratch recipe (C1 seed 42, 2,700 s, 108 cycles) with the model on and off on a dedicated compose project (`docker compose -p pf006`), and the 4-hour run (15,388 events) near the end of phase 2. Report median, p95 and max of `duration_ms` and of `model_ms`. Pass: max `duration_ms` < 5,000 and no skipped cycle attributable to the model; target p95 ≤ 250 ms at demo length (the 005 budget). The result is recorded in `verification.md` with the difference to the 005 numbers.
4. The existing loop already skips a tick that falls inside a long cycle (FR-039 of 002), which is the spec's "cycle longer than 5 s is skipped, not queued" edge case; a test covers the log line.

## R10. Where the model's parameters and explanation are recorded (FR-010, FR-031)

`lineage` in the recommendation schema is closed (`model_version`, `rule_version`, `snapshot_id`) and FR-029 forbids widening it. So:

- `doc.lineage = {model_version: "1.0.0", rule_version: RULES_VERSION, snapshot_id}`.
- `gold.recommendation.lineage_detail` (JSONB, side column): `params` (every value read from `config.decision_model` for this cycle: threshold, scoring window, reserve cost, ready delay, slow duration, ttl, rest), `inputs` (the projector input, compact JSON, hashed for SC-001), `base_score_s`, `riders`, `candidates_evaluated`, and from phase 6 `trend_ratios` per segment. It is written at first publication and refreshed with the numbers.
- `gold.mpc_evaluation` (one row per candidate of the latest cycle, replaced each cycle, with `snapshot_id`): the evidence for SC-003 and SC-004 ("evaluated in every cycle even when not recommended") and for the explanation. A test collects it after each `run_cycle` during a replay.

Storing `inputs` makes the counterfactual report (phase 5) possible without a historical database: it re-projects from the stored input with the pure projector.

## R11. Projector design, scoring definition and units (FR-005, FR-006, FR-011)

**Dynamics** (expected values, no randomness):

- Time is on the simulator's 5 s grid: arrival at a stop is `ceil` to the grid of `departure_from_previous + segment_time`; departure is `ceil(arrival + dwell)`. Dwell `= max(10, 10 + 3·boarded + 2·alighted)` (the simulator's `dwell_s`), `boarded = min(queue, 40 − occupancy_after_alighting)`, `alighted = occupancy × alight_share(i)` (R2). Capacity 40 (`model.CAPACITY`, read from the reference data's single definition by the rule module as a parameter, default 40).
- Segment time = M1 of that segment and the local hour of the step, times the road-trend ratio (phase 6; 1.0 before). A slow-down divides the segment time by `1 − share` while active. A hold adds stop time `max(natural, hold_s)` at that stop.
- A bus is a heap event; ties break by bus order (leader first, then id), so results are reproducible. Buses do not block each other (the simulator has no overtaking constraint); they interact only through the shared queue at each stop.
- Estimated or `sources_down` buses are projected from their last known state with no action (FR-007). A broken bus waits until its incident `end_ts`.
- The projection ends for a bus at the last stop (edge case); an action with no stop left in the window is not a candidate.

**Queues.** `q_i(t)` = initial queue + cumulative arrivals − boarded. Street stops use a piecewise-constant rate per local hour; Prado uses train batches (R1). Cumulative arrivals have closed form, so no 5 s stepping is needed.

**Score** (FR-011), all in passenger-seconds over the window `[as_of, as_of + 1,800]`:

1. **Waiting** `W = Σ_i ∫ q_i(t) dt` = queue-seconds. This is the numerator of the stop-based EWT of story 005: with no one left behind, `∫q dt = λ Σh²/2`, and `Σh²/(2Σh)` is the mean wait that `rules/stop_metrics.py` uses. A unit test links the two on a crafted input (same departures give the same mean wait). Riders left behind stay in `q`, so they are counted through their extra waiting, with no separate term (Clarifications). Riders still queued at the end of the window are counted up to its end; this truncation is why the window is 1,800 s and not 600 s (the prototype's lesson).
2. **Onboard delay** `O = Σ occupancy × (extra seconds the action imposes)`: a hold's surplus dwell over the natural dwell, and a slow-down's extra segment time, each times the bus's occupancy at that moment. "Do nothing" has `O = 0` by definition; natural delays are not counted because they are the same in both worlds.
3. **Reserve cost** `C = reserve_cost_s` (900) per dispatch.

`saving = (score(do nothing) − score(action)) / riders`, with `riders = initial queues + expected arrivals in the window` (the prototype's definition). That value is `ewt_saving_s` and is compared with the 15 s threshold. It is a per-rider figure, which matches the reason text "saves 33 s per rider" and the contract's "reduction in EWT".

**Determinism** (SC-001): iteration orders are sorted (buses, stops, candidates), floats only from the same operations in the same order, no `set` iteration, no `dict` order dependence beyond insertion of sorted keys, no clock. Money-like exactness is not needed; values are rounded to 0.1 s when written.

## R12. Candidate rules and tie-breaks (FR-008, FR-009, SC-005)

- *Follower of a bunched pair*: a bus with `bus_state = 'bunched'` in the snapshot (headway ahead < 300 s, existing rule). Hold at its next enabled stop ahead (30, 60, 90 s) and slow down (10 %, 20 %, 300 s).
- *Gap ahead*: `bus_state = 'gap'`. Skip stops with an empty queue for the next 4 stops (the prototype's reach); the target is the bus behind the gap.
- *Trouble*: any bunched, gap or broken-down bus, or any queue above `0.5 × 40 = 20`. Candidates: `adjust_departure` of the next terminal departure (±60, ±120) and `reserve_dispatch` (first free reserve in id order, only if a driver is free).
- `case`: `C1` for a bunched trigger, `C2` for a gap, `C5` for a breakdown. If both bunching and a breakdown hold, the action's own trigger decides (a hold or slow down is `C1`; a reserve is `C5` if a breakdown is active, else `C1` or `C2` by which condition holds, bunching first).
- Nothing targets a bus that is `estimated` or in `sources_down`; nothing is a candidate against an `estimated` bus ahead (D1, as in the prototype).
- Best intensity per `(type, bus, stop)` is kept; then the list is sorted by saving descending, ties by catalog order (FR-008), then bus id. Top 3 of those at or above the threshold. `conflicts_with`: any two rows on the same bus, or a hold and a slow down on the same follower, list each other's `rec_id`.
- `normal` run: no bunched, gap, broken bus and no queue above 20 means zero candidates (SC-005). Nothing is evaluated, so "delay the departure 60 s" cannot appear.

## R13. Arrival rates: numbers and fallbacks

Reference volume `daily_riders_dir1 = 633.92` (`demand_volume.csv`). Simulator split: 80 % train riders at Prado, 20 % street riders over `n_street = last − 1 = 16` stops (declared assumption of the data owner in `SOURCES.md`; stored in `config.decision_model.train_share`, owner: data owner, source: SOURCES.md). Hourly shape at 17 h is 0.104833, at 18 h 0.075124.

- Prado at 17:00: `633.92 × 0.8 × 0.104833 = 53.2` riders per hour, 40 trains per hour, so about **1.33 riders per train**. 
- A street stop at 17:00: `633.92 × 0.2 × 0.104833 / 16 = 0.83` riders per hour, so about **0.42 riders per stop per 1,800 s**.

The queues are small: a few riders. The queue "above 20" trigger will not fire at the reference demand (the simulator's `demand_scale` argument, exposed by `SIM_DEMAND_SCALE`, can raise it for a demo; see below). All results are per rider, so small totals do not break the 15 s threshold, but the expected savings are small too (risk 3 in `plan.md`).

**Demo demand (gate decision 3).** `engine.run` already accepts `demand_scale` (default `1.0`, applied to both Prado trains and street riders, `engine.py`). `simulator/main.py` calls `run(args.seed, args.duration)` and `scenario_events(...)` without it, so today it cannot be set from the environment. Phase 2 adds `SIM_DEMAND_SCALE` (env, default `1.0` = the real reference demand; accepted range 0.1 to 10; a value outside the range or not a number stops the simulator before the first event, like an invalid scenario file), passes it to `engine.run(demand_scale=...)` (through `scenario_events`), and documents it in `.env.example` and `tests/unit/test_env_example.py`. Reasons for 0.1 to 10: the capacity tests already drive 25 (overload, a test-only value), the prototype uses 3, and below 0.1 the stream has almost no riders. Consequences:

- It is a demo setting, not a model change. The model reads only bronze, silver and `config`; a static test fails if `rules/`, `pipeline/` or `config` code mentions `SIM_DEMAND_SCALE` or `demand_scale`. The extra riders reach the model only as observed arrivals and queues, which is the real path.
- With the default `1.0` the value passed is the one `run` already used, so the stream and the golden hash do not move (tested with the variable unset and set to `1.0`).
- The demo runs C1 with `SIM_DEMAND_SCALE=3`, the same as the data owner's prototype. The scale is stated wherever a demo result is shown.
- Live check in phase 2: C1 in forced mode (fixed time and seed) at scale 3 yields at least one evaluated candidate in `gold.mpc_evaluation` per bunching cycle (every cycle whose snapshot has a `bunched` bus). Whether a candidate is recommended is reported, not required, and no parameter is tuned to make it so. The same run at scale 1 is reported next to it.

Observed rate at a street stop: `count in the last 30 minutes / 1800`. With so few events this is noisy, so the observed value is used only when the stop's 30-minute count is at least `config.corridor_settings.min_sample_count` (5); otherwise the reference rate. For a projected hour other than the current one, the rate is scaled by `shape(h)/shape(h_now)` from the reference. At Prado the observed rate is not used: the batches come from the GTFS schedule and M2 (which is itself observed or reference by its own `min_sample_count` rule).

## R14. Safety rules (FR-015 to FR-019, SC-006)

All are checks in the pure `rules/mpc.py` and a final guard in `pipeline/recommend.py`, so a bug in candidate generation cannot publish an unsafe row:

- Hold candidates are `{30, 60, 90}`; the guard drops any hold above `MAX_HOLD_S` (the constant of `rules/holds.py`, reused) and logs it.
- Targets are filtered with `data_quality = 'live'` and not in `source_status.sources_down`.
- `fresh = (clock_timestamp() − snapshot_commits.committed_at) ≤ 15 s`, with 15 a config value `freshness_max_s` (ADR-0006). If not fresh: no new rows; existing rows still get their derived status (the edge case).
- `horizon_s` is written as the constant 600 (ADR-0007), independent of the scoring window; a test asserts it on every row of every scenario run.
- The model has only `INSERT/UPDATE` on `gold.*` tables; it never touches bronze (the static test `test_no_bronze_writes` is extended to the new modules).

## R15. Road trend (FR-031, phase 6, outside the committed scope: built only if time is left after phase 5)

Per segment `s`, over traversals in `silver.segment_traversals` whose departure is within the last 15 minutes: `ratio_s = Σ observed travel_s / Σ M1(s, local hour of departure)`, bounded to `[0.7, 1.5]`, and `1.0` when fewer than 3 traversals qualify. The spec says "from `silver.stop_visits`, excluding traversals that touch an `estimated` departure". `segment_traversals` is itself derived from the stop visits and already carries `travelled_while_estimated` and `broken_down`; but a traversal's *departure* flag `estimated_at_departure` lives in `silver.stop_visits` (added in 005). So the SQL joins each traversal to the visits at its two ends (by bus, trip and the segment's stops from `config.ref_stops`) and excludes it if either end has `estimated_at_departure`, or if `travelled_while_estimated` or `broken_down` is set. This is the one place where the plan reads `segment_traversals`; the join keys are `(bus_id, trip_id, segment_id)` (its primary key) and `stop_visits (bus_id, trip_id, stop_id)`.

Config keys in `config.decision_model` (phase 6 section of `009`): `trend_window_s = 900`, `trend_min_samples = 3`, `trend_ratio_min = 0.7`, `trend_ratio_max = 1.5`. The ratios actually used are saved in `lineage_detail.trend_ratios` (17 numbers) with each recommendation and in `gold.mpc_evaluation` (one `trend` entry per cycle), so a number can be explained. Exact pure function in `rules/trend.py` (no database), SQL only gathers the sums. M1 itself is not changed. In a normal run the ratio is near 1 because M1 is the median of the same simulator's traversals (SC-014 checks the range and that SC-005 still holds).

## R16. Test strategy and oracles

Tests first, in this order per phase (details in `quickstart.md`):

- **Phase 1 (pure)**: crafted one-bus, two-bus-with-queue, full-bus, zero-queue snapshots with hand-computed departures within 1 s (SC-002); hour-boundary crafted case; dwell rule; alighting share vs simulator (R2); wait score = EWT numerator on a crafted case; determinism (same input twice, byte-identical serialization); parameters read from the params object, never constants; a source test that fails on a float literal 90, 900, 300, 120 or 15 outside `mpc_params.py` defaults.
- **Phase 2**: `SIM_DEMAND_SCALE` (unset and `1.0` give the same golden hash; 0.05, 11 and `abc` stop the simulator; the model code never references the variable; C1 forced mode at scale 3 has at least one evaluated candidate per bunching cycle); `speed_reduction_pct` contract cases and `RecommendationV110`; candidacy per catalog condition; top-3 and threshold; `rec_id` stability and rest; status lifecycle with scripted `decision` rows; stale snapshot; estimated and `sources_down` targets; normal run no rec; C1 and C5 forced-mode runs through `run_cycle` loops collecting `gold.mpc_evaluation`; schema validation of every row with `RecommendationV110`; seed absence grep; golden hashes.
- **Phase 3**: hold within ±15 s; slow-down speeds (the simulator reads `speed_reduction_pct` from the recommendation `doc`); reserve emits events after 120 s; not-executed counter; no-order hash identical.
- **Phase 4**: SC-015 cases and Q11.
- **Phase 5**: report reproducible from two seeded runs.
- **Phase 6** (optional): SC-014 cases.

Coverage: new pure modules aim near 100 % (they protect the metric); total stays above 80 %.

## R17. Projection record: matching, `affected_by_decision`, volume and cost (FR-035, FR-036, SC-016; phase 2b)

Decided by the implementer from the amended spec (data owner, 2026-11-22). The data owner can overrule each point; each is one line of the view.

**What is stored.** The "do nothing" projection that the model already computes as the baseline of every candidate. Until now it was computed only when a candidate existed (`evaluate_candidates`), so a cycle with no candidate had no baseline. Phase 2b projects the baseline in every fresh cycle with the model on, and passes it to `evaluate_candidates`, so a cycle with candidates does not project it twice. The stored rows are the baseline's departures inside the 1,800 s window (`lead_s ≤ 1800`, the projector already drops later ones). Rows come from the pure function `projection_record(inputs, projection)`; nothing is invented or recomputed in SQL.

**No row before the first report (found by the first live run).** With the data clock the first cycles run before any event is in bronze, at the wall-clock time, and every roster bus is a placeholder with a terminal slot. Those rows were paired with the first departure of the feed two days later (errors of 196,000 s; 38 rows of 5,552). The record is therefore written only when `silver.bus_current_state` has at least one row (some bus has reported). The view is not bounded in time: a real error of any size, such as a breakdown, must stay visible.

**Matching rule for the real departure.** For a row `(snapshot, bus, stop)` the real departure is the `departure_ts` of the first `silver.stop_visits` row of that bus at that stop with `departure_ts ≥ as_of_ts`, ordered by `departure_ts`. Reasons:

- `≥ as_of_ts` (not `> as_of_ts`) keeps a bus that is dwelling at the stop at `as_of_ts` (arrival before, departure after), which the projector projects with its remaining dwell. T048a used the same rule.
- The key is `(bus, stop)` and not `(bus, trip, stop)`: the projector has no trip id, and a bus normally does one trip in the window. The "first at or after" rule picks the current trip's visit because the next trip of the same bus is at least one full trip later (about 1,400 s of driving plus the layover, longer than the remaining lead of any row near the window end in the C1 runs). The edge where a short trip would be mispaired is not guarded; it would show as a large error in a high bucket and is noted as a limitation.
- If that first visit is flagged `estimated_at_departure`, `actual_departure_ts` and the error are NULL. The alternative (skip it and take the next visit) was rejected: it could pair the row with the bus's next trip and invent a huge error. The spec says estimated departures are excluded from the comparison; NULL excludes the row without risking a false pairing.
- No visit yet: NULL, never 0 (FR-036). The row is kept, so the denominator "projected" and the numerator "compared" are both readable.

**`affected_by_decision`.** True when an applied recommendation on the same bus was decided between `as_of_ts` and the real departure. Implemented on `gold.recommendation`: `status = 'applied'`, `doc.action.bus_id = bus_id`, `close_ts > as_of_ts` and (no real departure yet, or `close_ts ≤` the first departure). `close_ts` is the decision's event time for an applied row (data-model M5). Notes: (1) it uses the time of the first departure found even when that visit is estimated, so the flag does not depend on the NULL error; (2) only the targeted bus is flagged. A hold on bus A also changes the queues that bus B finds, and a reserve changes everyone's queue; those effects on other buses are not flagged (the baseline is shared state), and the aggregate may show a small bias after an approved action. This is the narrowest reading of FR-036 and is stated, not hidden; the phase 5 report measures the action's own effect. (3) A discarded recommendation changes nothing and is not flagged.

**Buckets.** `0-5 min` is `lead_s < 300`, `5-10 min` is `300 ≤ lead_s < 600`, `10-30 min` is `lead_s ≥ 600` (up to 1,800). SC-016 asks for the first two; the third is reported as the user story's view.

**Aggregate.** Count of compared departures (non-NULL error), mean absolute error, median absolute error, worst absolute error, per bucket, excluding `affected_by_decision`. The median uses `percentile_cont(0.5)` on the absolute error. The mean signed error is added as a bias column because T048a found a constant +20 s lag; it is extra, not required. An empty bucket returns `n = 0` and NULL statistics.

**Row volume per cycle.** T048a (C1 seed 42, scale 3): 8,319 projected departures over 160 cycles, about **52 rows per cycle**, with a range of about 20 (early, few buses) to about 90 (7 buses with 10 stops left each). Bounded by buses × stops in the window: at most 7 × 18 = 126. Per run at the real 5 s refresh interval: 45 minutes = 540 cycles, about **28,000 rows**; 4 hours = 2,880 cycles, about **150,000 rows**. A row is about 130 bytes of data plus the primary key and one secondary index, so roughly 250 bytes: about **7 MB for 45 minutes and 40 MB for 4 hours**. Retention is not designed here (like `gold.snapshots`): the table grows with the snapshots. The measured figures replace these estimates in `verification.md`. The `refresh` live recipe at pace 1 runs 108 cycles per 2,700 s, so its table is about 5,600 rows.

**Cycle-time cost.** The baseline projection is about 2 ms (R9); it already ran in every cycle with candidates, so the new cost is the baseline in the cycles without candidates (about 2 ms), building about 50 rows (negligible) and one `INSERT ... SELECT FROM unnest(...)` of about 50 rows (about 1 to 3 ms with the primary-key and secondary-index maintenance). Estimate: **+3 to +6 ms per cycle**, against the added median of 4.9 ms and maximum of 10.4 ms of phase 2 (target: added median ≤ 60 ms, added maximum ≤ 150 ms). The view costs nothing per cycle: it is read on demand, one indexed lookup per row (`silver_stop_visits_stop_dep_idx`), about 50 lookups per cycle read.

**Determinism.** `snapshot_id` is a function of `(as_of, rules_version, max_bronze_id)`, so the same bronze and rules give the same snapshot and the same projection; `ON CONFLICT DO NOTHING` makes a repeated cycle a no-op. `RULES_VERSION` moves to `1.7.0` because the gold output gains a table, so a snapshot of 1.7.0 has a different id from one of 1.6.0 on the same data (the rule of 005).

**Effect on phase 5.** The projection error no longer needs a report of its own: `gold.v_projection_accuracy` has it for every run. Phase 5 reports only the actual effect of the approved action (and may quote the view).

## Alternatives considered (summary)

| Decision | Chosen | Rejected and why |
|---|---|---|
| Projection loop | Event-driven with 5 s grid rounding | Fixed 5 s stepper like the prototype: about 360 steps × 25 stops per projection, 10 to 30× slower, and queue state per step; the event form is exact on the grid and hand-computable |
| Wait score | Queue-seconds (numerator of the stop EWT) | Per-stop EWT from projected departures only: ignores riders left behind and truncation at the window end |
| Alighting | `1/(last − i + 1)` from the simulator's destination model | Prototype's `1/(LAST − i)` (biased); bronze-history estimate (noisy with 40 to 600 riders per hour) |
| Recommendation state | Persist rows, derive status each cycle | Recompute everything from scratch each cycle: `rec_id` stability and `proposed_ts` need memory of past cycles |
| Slow-down intensity | Optional `action.speed_reduction_pct` in the 1.1.0 bump (data owner's decision) | Side column `params` + `reason` text: the console could not show it as data and the simulator would read a field outside the contract |
| Demo demand | `SIM_DEMAND_SCALE` passed to the simulator only | Tuning model parameters or letting the model read the scale: would change the model for a demo and hide the real-demand result |
| Seed switch | Poller joins `gold.recommendation` | Keep a seed file for the simulator only: violates "no code path may read the seed" (FR-025) |
| Cycle placement | Inside `run_cycle` | A separate process: loses the consistent read (FR-001) and the same-cycle publication |
