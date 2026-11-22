# Feature Specification: Decision Model (Simulation-Based MPC)

**Feature Branch**: `feature/006-decision-mpc` (created from `feature/004-scenario-injectors`, head `8351274`; stacked on story 005, which is specified in parallel on `feature/005-data-fixes-metrics` and is not merged)

**Created**: 2026-11-21

**Status**: Draft

**Traces to**: PRD US-02 (RF-2.1 to RF-2.3: recommendations, human approval), console screen US-05 (recommendations, ADR-0003), the hold loop of story 004, and the freshness rule of ADR-0006. Turn-1 risk "data integrity" (Disciplined lane): a recommendation is only as good as the snapshot and the rules behind it, so every recommendation must be reproducible and traceable.

**Input**: User description: "Data story. Build the decision model as data analytics: a deterministic, explainable, simulation-based model predictive control (MPC). Every refresh cycle (5 s) it projects every bus and rider from the latest gold snapshot over a 1,800 s scoring window (the decision horizon reported in recommendations stays 600 s), evaluates a catalog of five candidate actions, scores them by total passenger time within safety rules, and recommends the top 3. Recommendations are published in `gold.recommendation`. The simulator executes reserve dispatch, slow down and hold. The seed file is retired."

**Decision of record**: on 2026-11-21 the data owner decided that decision analysis and the decision model are data analytics, not backend. The data team builds them and merges them on the data owner's approval. The backend only reads active recommendations and writes the dispatcher's `decision` command event.

**Ground truth (binding, not re-decided here)**:

- `.specify/memory/constitution.md` v1.2.0 and `docs/turns-ritmo.md`. Principle III: no LLM or external service on the real-time path. Principle IV: every action needs the dispatcher's approval.
- ADR-0001 to ADR-0004 on this branch. ADR-0005 to ADR-0007 and `docs/data-contract.md` are **not on this branch**: they live on branch `docs/data-contract` (ADR-0005 is not present there either). This spec relies on ADR-0006 (freshness rule, 15 s; recommendation door), ADR-0007 (`horizon_s = 600`) and `docs/data-contract.md` Q7, Q13 and §4.5 as read from that branch.
- `specs/001` to `specs/004` and the code in `src/data/` (rules, pipeline, simulator, `scenarios/holds.py`), `contracts/read/`, `config.corridor_settings` (planned headway 600 s).

## Dependencies

- **Story 005 (`005-data-fixes-metrics`, in parallel)** provides: the stop-based EWT, P(board ≤ t), the terminal false-gap fix, the SIMM local-hour fix, and the robustness of the clock and positions. The model scores waiting with the stop-based EWT and reads the local-hour M1 times, so **the plan and the implementation of this story start only after 005 is merged**. This spec may be reviewed before that.
- **Contract and document impacts (listed here, not edited by this story).** The data owner updates them in a separate step:
  1. `contracts/read/recommendation.schema.json` 1.0.0 → 1.1.0: add `slow_down` and `skip_stop` to `action.type`, with their `duration_s` rules.
  2. ADR-0003 boundary: the decision engine moves from the backend to data.
  3. ADR-0006 item 4: the backend no longer sends recommendations, so the `recommendation` command event type is not needed and data publishes `gold.recommendation` itself.
  4. `docs/data-contract.md` Q7 (the seed is retired), Q13 and §4.5 (the producer is data, not the backend).

## Clarifications

### Session 2026-11-21

Answers from the data owner, and changes taken from the data owner's HTML prototype (run on 2026-11-21 in scenarios C1, C5 and normal, with approvals and a counterfactual "shadow world").

- Q: Reserve readiness delay between approval and the reserve leaving P-883? → A: **120 s**. Declared assumption, stored in `config`.
- Q: Slow-down duration N? → A: **5 minutes (300 s)** for both intensities (−10 % and −20 %). Stored in `config`.
- Q: Weights of the score? → A: **Riders left behind have no separate weight.** They count through their extra waiting until the next bus, because the queue keeps growing in the projection. **Reserve cost: 900 s of passenger time per dispatch**, configurable.
- Prototype change, projection window: **1,800 s for scoring; `horizon_s` stays 600** (the decision horizon reported in recommendations and used by ADR-0007). With a 600 s projection, "delay the next terminal departure 60 s" scored a 154 s saving per rider in normal operation because its cost fell beyond the horizon; its real effect against the counterfactual was zero.
- Prototype change, candidacy: each action is a candidate only when its catalog condition holds (FR-008). Without this, "dispatch a reserve" always wins, because adding a bus always reduces waiting.
- Prototype change, expiry: a proposal expires at **2 minutes** (MVP-3 of the team's mock-ups) **or** when the bus has passed the stop, whichever comes first. After it expires, the same action on the same bus is not proposed again for 5 minutes.
- Prototype change, counterfactual effect: measured as the mean journey time (wait + ride) of the same cohort of riders (those arriving in the 600 s after the decision) in both runs, not as accumulated waiting alone, which cancels against ride time.
- Prototype change, time of day: the projection reads M1 travel times and arrival rates for the local hour of each projected step, because a 30-minute projection can cross an hour boundary (peak 17:00–18:00).
- Reference result (prototype, scenario C1): holding the bunched follower B-103 scored −3 to +1.4 s per rider; dispatching a reserve scored +33 s. This matches the 2026-11-21 review: a 90 s hold does not fix a 400 s delay. A hold is therefore not required to be recommended in C1 (SC-003).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Projection and Scoring Core (Priority: P1)

As the data owner, I want a deterministic projection of the next 1,800 s of every bus and rider, and a score of total passenger time for any candidate action, so that every recommendation rests on a number I can reproduce.

**Why this priority**: Everything else (catalog, recommendations, execution) is a modification of the projection plus a score. If the projection cannot be trusted against the simulator, no recommendation can be.

**Independent Test**: Build the projection from a crafted snapshot and compare it with a hand-computed expectation (tests first). Then replay a forced-mode run twice and compare projected stop-departure times with the actual ones; the projection error is reported in seconds.

**Acceptance Scenarios**:

1. **Given** a snapshot with known positions, occupancies, queues and M1 times, **When** the model projects 1,800 s, **Then** it yields the projected departure time of every bus at every stop, equal to the hand-computed values under the dynamics of FR-004 to FR-006.
2. **Given** the same snapshot twice, **When** the model runs twice, **Then** the projections and scores are identical.
3. **Given** a bus that boards riders, **When** it dwells at a stop, **Then** the queue at that stop is empty after the bus leaves (up to the free capacity) and dwell follows `10 + 3·boarded + 2·alighted`.
4. **Given** a candidate action, **When** it is applied to the projection, **Then** the score is the sum of waiting at stops (which includes the extra wait of riders left behind), onboard delay and a cost for reserve use, and "do nothing" is scored on the same basis.

---

### User Story 2 - Top-3 Recommendations in `gold.recommendation` (Priority: P2)

As a dispatcher, I want every refresh cycle to show up to 3 explained recommendations ranked by how much passenger time they save, so that I can approve the one that fits.

**Why this priority**: This is the product of the model. It replaces the seed, and it feeds the console and the human gate.

**Independent Test**: Run scenario C1 (bunching) in forced mode and read `gold.recommendation`: there is at least one `proposed` row, ranked, with a plain-text reason and a projected `ewt_saving_s` above the threshold, validating against the recommendation schema.

**Acceptance Scenarios**:

1. **Given** a C1 bunching snapshot, **When** a cycle runs, **Then** hold, slow down and reserve dispatch are all evaluated, and the best one whose projected improvement over "do nothing" is at least the configured threshold is published, with a plain-text reason such as "dispatch reserve B-106 saves 33 s per rider". A hold is recommended only if it passes the threshold; it is not required to.
2. **Given** a C5 breakdown snapshot with free reserves, **When** a cycle runs, **Then** a `reserve_dispatch` recommendation is among the candidates evaluated, and it is recommended only if its improvement exceeds the threshold after the reserve cost.
3. **Given** a normal snapshot (no bunching, gap, breakdown or queue above 20 riders), **When** a cycle runs, **Then** no action is a candidate and no recommendation is proposed.
4. **Given** the dispatcher applies or discards a recommendation (a `decision` event), **When** the next cycle runs, **Then** its status in `gold.recommendation` is `applied` or `discarded`; with no decision it is `expired` 2 minutes after creation or when the bus has passed the stop, whichever comes first.
5. **Given** the snapshot is older than 15 s of wall time, a bus is `estimated`, or a bus is in `sources_down`, **When** a cycle runs, **Then** no recommendation is created that targets that bus (and none at all for a stale snapshot).

---

### User Story 3 - Simulator Executes Reserve Dispatch, Slow Down and Hold from the Model (Priority: P3)

As the data owner, I want the simulator to carry out approved reserve dispatches, slow downs and holds read from `gold.recommendation`, so that I can compare what the model projected with what really happened.

**Why this priority**: Execution closes the loop and enables the counterfactual validation. It needs the recommendations from P2 and the story-004 hold loop.

**Independent Test**: In forced mode, approve the model's recommendation with a scripted `decision` and run the same scenario with and without it; the actual change in stop passing times and stop EWT is compared with the projection.

**Acceptance Scenarios**:

1. **Given** an approved `hold` recommendation, **When** the bus reaches the stop, **Then** the simulator holds it for the recommended time (no more than 90 s) and `gold.instruction_status` reports it from `gold.recommendation`, not from the seed.
2. **Given** an approved `reserve_dispatch`, **When** the 120 s readiness delay has passed, **Then** the reserve bus enters service at the terminal and appears in the event stream and in `corridor_now`.
3. **Given** an approved `slow_down`, **When** the following bus travels, **Then** its segment speeds are reduced by the recommended share for 300 s.
4. **Given** an approved `adjust_departure` or `skip_stop`, **When** the simulator reads it, **Then** it is ignored and counted as "not executed in this story" (Evolution). Nothing breaks and the bus is unchanged.

---

### User Story 4 - Counterfactual Validation Report (Priority: P4)

As the data owner, I want to compare the projection with the actual run with and without the action, so that I can trust (or distrust) the model with numbers.

**Why this priority**: The model is only useful if its error is known. It does not block P1 to P3, but it is the evidence for the data owner's approval to merge.

**Independent Test**: Run scenario C1 twice with the same seed (with and without the model's top action approved), compute the projection error and the actual effect, and write the report.

**Acceptance Scenarios**:

1. **Given** a forced-mode run and the same run with an approved action, **When** the report is produced, **Then** it states, per action: the projected passing times with and without the action, the actual ones, the error in seconds at the stop passing times, and the effect on the mean journey time (wait + ride) of the cohort of riders arriving in the 600 s after the decision, the same cohort in both runs.
2. **Given** the 2026-11-21 reference measurement (scenario C1 with the seeded 90 s hold: real EWT effect of +3.3 s / +36.3 s, stop EWT from about 40.6 s to about 23.6 s downstream), **When** the report is produced, **Then** the reference is shown next to the new numbers as context. It is not a pass or fail target.

---

### Edge Cases

- **No bus qualifies** (all `estimated` or in `sources_down`): the model proposes nothing and says why in the logs, not as a recommendation (case D1 is information only).
- **Snapshot older than 15 s of wall time**: no recommendation is created. Existing ones keep their derived status and expire on their own `expires_ts`.
- **A recommendation is still valid when the next cycle runs** (the situation has not changed): it keeps its `rec_id`, so a dispatcher's decision is never orphaned by a refresh. A situation that changed produces a new `rec_id`, and the old one expires.
- **Two recommendations that cannot both be applied** (same bus, or hold and slow down on the same follower): each lists the other in `conflicts_with`.
- **No free reserve or no free driver**: `reserve_dispatch` is not a candidate.
- **A hold longer than 90 s**: never generated. A decision that arrives for one is refused by the executor as in story 004.
- **Queue data missing for a stop** (no riders observed yet): the reference arrival rate is used; if neither exists the stop has an empty queue and the reason is logged.
- **Bus bunched at a terminal or close to the end of the corridor**: the projection ends at the last stop; actions with no stop left before the end of the horizon are not candidates.
- **Cycle runs longer than 5 s**: the next cycle is skipped, not queued, and the overrun is logged. Recommendations from the last completed cycle stay valid until they expire.
- **The dispatcher approves a recommendation after the situation has changed**: the executor applies it as recommended; the model does not cancel approved orders. The effect shows in the validation report.
- **Same snapshot, rerun**: identical recommendations, identical `rec_id`s and identical order.
- **Backend is stopped**: the model keeps publishing recommendations (data is independent of the backend, Principle III); nothing is applied without a `decision`.

## Requirements *(mandatory)*

### Functional Requirements

**Cycle and inputs**

- **FR-001**: Every refresh cycle (5 s) the model MUST work on the latest gold snapshot (`gold.decision_inputs`) plus the silver state, in one consistent read, and publish its result in the same cycle.
- **FR-002**: The model MUST be deterministic: the same snapshot, silver state, reference data and configuration give the same projections, scores, ranking and `rec_id`s. It MUST use no randomness, no LLM and no synchronous call to anything outside the database (Principle III).
- **FR-003**: The projector MUST use, from the snapshot: position, next stop and occupancy of each bus; M1 travel time per segment and the rider arrival rate, each read for the **local** hour of every projected step (not only the hour at the start, because the 1,800 s window can cross an hour boundary); Metro train arrivals at Prado (GTFS reference) plus M2; the rider arrival rate at the other stops (observed over the last 30 minutes, or the reference when there are no observations); the current queue per stop; the next terminal departure (last departure plus the planned headway from `config.corridor_settings`); and the free reserves.
- **FR-004**: The current queue per stop (new input) MUST be computed by data as riders arrived minus riders boarded since the last departure from that stop, and MUST be traceable to bronze events.

**Projection**

- **FR-005**: The projector MUST simulate the next **1,800 s** (scoring window, configurable) of every bus. The decision horizon reported in recommendations stays `horizon_s = 600` (ADR-0007). Each bus is simulated with expected values only: it travels each segment at the M1 speed; at each stop `boarded = min(queue, 40 − occupancy)`, `alighted = occupancy × alighting share of that stop`, `dwell = 10 + 3·boarded + 2·alighted`, consistent with the simulator's dwell rule (`src/data/simulator/model.py`; capacity 40).
- **FR-006**: Queues MUST grow with their arrival rate and empty when a bus boards. The output MUST be the projected departure time of every bus at every stop within the scoring window.
- **FR-007**: Buses that are `estimated` or in `sources_down` MUST still be projected as obstacles for the buses behind them (their last known state, no action), but MUST NOT be the target of any action.

**Action catalog**

- **FR-008**: The model MUST evaluate this catalog, in this order of preference when scores tie, each as a modification of the projection. "Do nothing" MUST always be the baseline.

  | # | Action | Candidate only when | Recommendation type | Executed by the simulator in this story |
  |---|---|---|---|---|
  | 1 | Dispatch a reserve bus (B-106 or B-107 from P-883) | There is bunching, a gap, a breakdown, or a queue above half a bus (20 riders) | `reserve_dispatch` | **Yes (new)** |
  | 2 | Slow down the following bus (−10 % or −20 % for 300 s) | The bus is the follower of a bunched pair | `slow_down` (new) | **Yes (new)** |
  | 3 | Hold at the next stop (30, 60 or 90 s, maximum 90) | The bus is the follower of a bunched pair | `hold` | Yes (exists in 004; its source moves from the seed to the model) |
  | 4 | Advance or delay the next terminal departure (±60 or ±120 s) | There is bunching, a gap, a breakdown, or a queue above 20 riders | `adjust_departure` | No (recommended only; execution is Evolution) |
  | 5 | Skip stops with an empty queue | The bus has a gap ahead | `skip_stop` (new) | No (recommended only; execution is Evolution) |

- **FR-009**: "Candidate only when" is a filter on which actions are evaluated, not the decision. It exists because otherwise "dispatch a reserve" always wins, since adding a bus always reduces waiting. The choice between candidates MUST come only from the score (FR-010 to FR-012). No fixed rule or decision tree picks the action.
- **FR-010**: The reserve readiness delay (**120 s**), the slow-down duration (**300 s**, both intensities) and the reserve cost (**900 s** of passenger time per dispatch) are parameters. The model MUST read them from `config`, never from constants in the code, and MUST record the values used in the recommendation's lineage.

**Scoring and recommendation**

- **FR-011**: The score of an action MUST be the total passenger time over the 1,800 s scoring window: the sum of (a) waiting at stops, using the stop-based EWT from story 005 applied to the projected departures; (b) onboard delay (occupancy × extra seconds); (c) a cost for using a reserve (default 900 s of passenger time per dispatch, configurable). Riders left behind have no separate term: they count through their extra waiting until the next bus, because the queue keeps growing in the projection.
- **FR-012**: The model MUST recommend an action only if its improvement over "do nothing" is at least a configurable threshold, which defaults to **15 s per rider**. It MUST rank the qualifying actions by total passenger time saved and publish at most the **top 3** (`rank` 1 to 3).
- **FR-013**: Each recommendation MUST carry the projected `ewt_saving_s`, a plain-text `reason` that names the action, the bus, the stop and the saving per rider (for example "hold B-103 60 s at P-888 saves 22 s per rider"), `horizon_s = 600`, `data_quality`, `expires_ts`, `conflicts_with`, and `lineage` (model version, rule version, snapshot id).
- **FR-014**: Recommendations MUST keep a stable `rec_id` while the same action on the same bus and stop remains valid across cycles (see Edge Cases), and MUST be reproducible from the snapshot id.

**Safety rules (constraints, never the decision logic)**

- **FR-015**: A hold MUST NOT exceed 90 s.
- **FR-016**: The model MUST NEVER recommend an action on a bus that is `estimated` or in `sources_down` (case D1, story 004).
- **FR-017**: The model MUST NOT create any recommendation when the snapshot is older than 15 s of wall time (ADR-0006 freshness rule; age counted from `gold.snapshot_commits.committed_at`).
- **FR-018**: `horizon_s` MUST be 600 (ADR-0007), independent of the 1,800 s scoring window.
- **FR-019**: Every recommendation MUST be a suggestion. Nothing reaches `applied` without a dispatcher `decision` (Principle IV). The model never writes a `decision` and the simulator never acts on a `proposed` row.

**Output and status**

- **FR-020**: The model MUST publish `gold.recommendation`: one row per `rec_id`, `doc` equal to the recommendation schema (v1.1.0 once updated, v1.0.0 until then for the types that exist), rebuilt each cycle in the cycle transaction, with lineage (rules version, snapshot id, bronze range).
- **FR-021**: The `status` in `doc` MUST be derived by data from facts: `proposed` (no decision, now ≤ `expires_ts`), `applied` or `discarded` (the first `decision` for that `rec_id` by bronze order), `expired` (now > `expires_ts` or the bus has passed the stop, no decision), as in `docs/data-contract.md` §4.5. The producer is now data, not the backend; the backend never writes a status.
- **FR-022**: `case` MUST follow the situation that triggered the action: `C1` for bunching, `C2` for a gap, `C5` for a breakdown. No new case value is added.
- **FR-030**: A proposal MUST expire **2 minutes** after it is created (`expires_ts`) or when the bus has passed the stop, whichever comes first. After it expires, the same action on the same bus MUST NOT be proposed again for 5 minutes. Both values are configuration.

**Simulator execution and retirement of the seed**

- **FR-023**: The simulator MUST execute approved `reserve_dispatch`, `slow_down` and `hold` recommendations, reading them from `gold.recommendation` with a read-only session as the story-004 poller does. It MUST NOT write to bronze other than the events a simulated bus emits, and MUST NOT block the event stream if the database is unavailable (story 004, SC-011).
- **FR-024**: The simulator MUST accept `adjust_departure` and `skip_stop` without executing them, and count them as "not executed in this story".
- **FR-025**: `src/data/seeds/recommendations.json` and `config.seed_recommendation` MUST be retired. The hold executor and `gold.instruction_status` MUST read `gold.recommendation` instead (finding H-15). No code path may still read the seed.
- **FR-026**: Reserve dispatch execution MUST emit the reserve bus's events like any bus, and MUST keep all story-001 and story-004 behavior when no reserve is dispatched (the output hash with no recommendation approved is unchanged).

**Validation and quality**

- **FR-027**: A counterfactual validation MUST compare, in the deterministic simulator, the projection with the actual run with and without each executable action, and MUST report the projection error in seconds at the stop passing times. The actual effect of an action MUST be measured as the mean journey time (wait + ride) of the same cohort of riders (those arriving in the 600 s after the decision) in both runs, not as accumulated waiting alone, which cancels against ride time.
- **FR-028**: Tests MUST be written first. Quality rules and the safety rules MUST have tests that run without a database where possible; total coverage MUST stay above 80 %.
- **FR-029**: No contract file under `contracts/`, no ADR and no `docs/data-contract.md` line changes in this story; the impacts are listed in Dependencies for the data owner.

**Out of scope (Evolution)**

- Executing actions 4 (`adjust_departure`) and 5 (`skip_stop`) in the simulator; short turns; both directions.
- Learning a decision tree from the MPC history; reinforcement learning.
- The recommendation effect table (story 004 phase 3, rule ADR-0007) and the reports (§3B of the data contract).

### Key Entities *(include if feature involves data)*

- **Snapshot input**: the latest `gold.decision_inputs` document and the silver state it was built from. Read only.
- **Stop queue**: for each stop, riders arrived minus riders boarded since the last departure. New derived input, owned by data and traceable to bronze.
- **Projection**: the expected departure time of every bus at every stop over the next 1,800 s, with and without a candidate action. In memory, rebuilt each cycle.
- **Candidate action**: one entry of the catalog applied to one bus and stop, with its intensity (for example 60 s, −20 %). Carries its score and its improvement over "do nothing".
- **Recommendation** (`gold.recommendation`): the published suggestion, one per `rec_id`, shaped as `recommendation.schema.json`. Status derived from `decision` events and `expires_ts`.
- **Decision event**: the dispatcher's `apply` or `discard`, written by the backend to bronze. Read by data; never written by data.
- **Model configuration**: threshold (15 s per rider), decision horizon (600 s), scoring window (1,800 s), reserve readiness delay (120 s), slow-down duration (300 s), reserve cost (900 s), proposal expiry (2 min) and repeat suppression (5 min), intensities. Lives in `config`.
- **Validation report**: per action, projected versus actual passing times and the error in seconds.

## Success Criteria *(mandatory)*

### Measurable Outcomes

Each criterion is checked by running the code. Where a number is a reference only, it is marked as such.

- **SC-001**: Determinism. Two runs of the model on the same snapshot give byte-identical projections, scores, ranking and recommendation rows. Two full forced-mode runs with the same seed give the same `gold.recommendation` content.
- **SC-002**: Projection exactness on crafted input. For crafted snapshots (one bus; two buses with a queue; a full bus; a stop with zero queue), the projected stop departures equal the hand-computed values from FR-005 and FR-006 within 1 s.
- **SC-003**: Scenario C1 (bunching) in forced mode: in every cycle with bunching, hold, slow down and reserve dispatch are all evaluated, and the best one whose projected improvement is at least the threshold is published, ranked, with a plain-text reason; the row validates against the recommendation schema. At most 3 are published per cycle. The criterion does not require a hold to be recommended. Reference only (prototype, C1): holding the bunched follower B-103 scored −3 to +1.4 s per rider and dispatching a reserve scored +33 s.
- **SC-004**: Scenario C5 (breakdown) in forced mode: `reserve_dispatch` is evaluated as a candidate in every cycle while a reserve and a driver are free, and is recommended only when its improvement after the reserve cost is at least the threshold. The result (recommended or not, and its saving) is reported as the model yields it, not tuned.
- **SC-005**: A normal run (no scenario): no recommendation is published in any cycle, and in particular "delay the next terminal departure 60 s" and "dispatch a reserve" are not candidates and never score a saving. In the D1 scenario: 0 recommendations target the `estimated` bus.
- **SC-006**: Safety. Over all runs of SC-003 to SC-005 and a crafted stale snapshot: 0 holds above 90 s, 0 recommendations on `estimated` or `sources_down` buses, 0 recommendations when the snapshot is older than 15 s of wall time, and 100 % of rows with `horizon_s = 600`.
- **SC-007**: Status lifecycle. A scripted `apply` moves a row to `applied`, a `discard` to `discarded`, and no decision after `expires_ts` (2 minutes) or after the bus passes the stop to `expired`, and the same action on the same bus is not proposed again for 5 minutes; nothing is `applied` without a `decision` event in bronze (Principle IV). Re-ingesting the same bronze batch leaves `gold.recommendation` unchanged.
- **SC-008**: Execution. In C1 forced mode with a scripted approval, a `hold` recommendation is executed by the simulator within ±15 s of the recommended time and `gold.instruction_status` reads it from `gold.recommendation`. An approved `reserve_dispatch` makes the reserve bus emit events after the 120 s readiness delay. An approved `slow_down` lowers the follower's segment speeds by the recommended share for 300 s. `adjust_departure` and `skip_stop` run no change and are counted.
- **SC-009**: Seed retired. A search of the code, tests and database init finds 0 reads of `config.seed_recommendation` or `recommendations.json`. With no recommendation approved, the simulator output hash equals that of story 004 for the same seed.
- **SC-010**: Counterfactual validation. For scenario C1 (and C5 if a reserve is recommended), the validation report is produced from two runs with the same seed, with and without the action, and states, for each action, the projection error in seconds at the stop passing times and the effect on the mean journey time (wait + ride) of the same cohort of riders arriving in the 600 s after the decision. The 2026-11-21 measurement (hold of 90 s: real EWT effect of +3.3 s and +36.3 s; stop EWT about 40.6 s to about 23.6 s downstream) is shown as a reference. Success is that the report exists and is reproducible; the error values are reported, not constrained.
- **SC-011**: Cycle time. On a C1 run with the 5 bus base fleet and 2 reserves, the model's added time per cycle, measured over the whole run, is within the 5 s refresh interval at its maximum (not only on average), so no cycle is skipped because of the model. The measured maximum and the 95th percentile are reported.
- **SC-012**: Independence. With the backend and the console stopped, the model still publishes recommendations and bronze keeps growing (Principle III). No code on the model path calls an LLM or an external service.
- **SC-013**: Total coverage stays above 80 % with the CI-ready command green; no file under `contracts/`, no ADR and no `docs/data-contract.md` changes (FR-029). The plan and implementation start only after story 005 is merged.

## Assumptions

- **Story 005 is merged first.** The stop-based EWT, P(board ≤ t), the terminal false-gap fix, the local-hour fix and the clock and position robustness are inputs of this model. If 005 is not merged, this spec can be reviewed but not planned or built.
- **Scope**: one corridor (C6-008), direction 1, base fleet of 5 buses plus 2 reserves, 5 s refresh, as in turn 1. Both directions and short turns are Evolution.
- **Projection is expected values**: no randomness. The simulator's own randomness (travel-time noise, rider draws) is the source of the projection error that SC-010 reports.
- **Alighting share per stop**: derived from the reference data and the simulator's destination model; the plan states the source. If none exists, it is derived from the bronze history, never invented.
- **Rider arrival rates**: observed over the last 30 minutes, with the reference demand as fallback, as in the brief.
- **Recommendation expiry**: a recommendation expires 2 minutes after creation (MVP-3 of the team's mock-ups) or when the bus has passed the stop, whichever is first. After expiry the same action on the same bus is not proposed for 5 minutes (FR-030). The plan records the rule as part of the rules version.
- **Case mapping** (FR-022) keeps the `case` enum unchanged (`C1`, `C2`, `C5`, `D1`).
- **Stability of ranking**: ties are broken by the catalog order of FR-008, then by bus id, so ranking is deterministic.
- **Ownership**: the data owner approves the merge; the backend owner is told through the contract impacts listed in Dependencies.
- **Model parameters are declared, not hidden**: every number that is not in the repository or the data owner's brief is a configuration value with its source and owner recorded. The data owner declared on 2026-11-21: reserve readiness delay 120 s, slow-down duration 300 s, reserve cost 900 s of passenger time per dispatch (see Clarifications).
