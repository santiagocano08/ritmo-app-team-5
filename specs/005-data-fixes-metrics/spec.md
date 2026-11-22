# Feature Specification: Data Fixes and Boarding-Probability Metrics

**Feature Branch**: `feature/005-data-fixes-metrics` (stacked on `feature/004-scenario-injectors`, phases 1–2 committed, head `8351274`; not merged yet)

**Created**: 2026-11-21

**Status**: Draft

**Traces to**: PRD quality axis (MVP-5, P(board ≤ t) and EWT), RF-2.1/RF-2.2 inputs of the decision model (story 006). Turn-1 risk "data integrity" (Disciplined lane). Needed for the turn-1 workshop demo (2026-11-24).

**Input**: User description: "Fix the defects found in the 2026-11-21 end-to-end data review (input → ingestion → silver → gold → decision → execution → measurement) that break the demo metric or can take the whole system down with one bad event, and add the boarding probability P(board ≤ t). Six items, approved by the data owner on 2026-11-21, in priority order: H-1 local hour of the SIMM congestion factor, H-10 false gap at the terminal, H-17/H-11 EWT measured at stops, new P(board ≤ t), H-5 impossible position, H-4 future-dated event."

**Ground truth (binding, not re-decided here)**:

- `.specify/memory/constitution.md` v1.2.0 and `docs/turns-ritmo.md` (turn 1: Principles I–V, Gate 1 schema validation only, Gate 2 tests with coverage > 80 %; Redis, PostGIS, SAST/SCA, 1,000 events/s deferred).
- ADR-0001 (bronze insert-only, `(source, event_id)` dedup, lineage = `rules_version` + `max_bronze_id`), ADR-0002 and `contracts/turn1-events/` (event envelope, payloads, rejection reasons), ADR-0003 and `contracts/read/` (read contract 1.0.0).
- ADR-0006 (freshness rule, simulated clock, history layer) and ADR-0007 (recommendation effect rule), and `docs/data-contract.md` v0.2. **These three documents are on branch `docs/data-contract`, not on this branch.** This spec cites them from that branch.
- `specs/001`–`specs/004` (what exists) and the code under `src/data/`.
- Time model: gold time is the simulated clock (`event_ts`, day starts 2026-11-24 22:00Z), never the wall clock (`arrival_ts`). Local time is fixed UTC−5 (`src/data/rules/timebands.py`).

**Review evidence**: all defects below were reproduced on throwaway databases and compared with independent oracles on 2026-11-21 (data owner and Claude). Contract validation, duplicates, silver, the gold arithmetic and the hold execution loop matched the oracles exactly and are **not** touched by this story.

## Clarifications

### Session 2026-11-21

- Q: Which window does the EWT use, a trailing 15-minute window ending at `as_of_ts` or the last closed clock-aligned 15-minute band? → A: Both (data owner). The live headline EWT (the `gold.service_metric` row of each snapshot) uses a trailing 15-minute window ending at `as_of_ts`. In addition, per-stop rows are stored for each closed, clock-aligned 15-minute local band, as additive sums (`n_headways`, `Σh`, `Σh²`, and the planned equivalents). Reports and payment use the band rows, with the same bands as P(board ≤ t) (US4).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Correct Local Hour for the SIMM Congestion Factor (Priority: P1) — finding H-1

The congestion factor that drives simulated and baseline travel times must describe the right hour of the local day. Today the reference build groups SIMM `FECHAHORA` by its UTC hour, while the simulator and baseline M1 read the factor by local hour, so every factor is shifted five hours. The field is truly UTC: in `data/raw/plata/simm_corredor_c6008.csv` the lowest vehicle count (7.2) and the highest speed (20.2 km/h) fall at 08 UTC, which is 03:00 local. At 17:00 local the code uses 0.5011 (really local noon) instead of the 22 UTC value 0.4816.

**Why this priority**: every travel time, every M1 forecast and therefore every projection of the decision model (story 006) inherits the shift. It is also the cheapest fix and changes the simulator output, so it must land first and its new golden hashes must be settled before the other items are measured.

**Independent Test**: rebuild the reference from the raw SIMM file, then compare each of the 24 local-hour factors with an independent recomputation (group the raw rows by `UTC hour − 5`, apply the same normalization). Run the simulator and compare its hashes with the documented new values.

**Acceptance Scenarios**:

1. **Given** the raw SIMM file, **When** the reference build runs, **Then** `congestion_factor.csv` has, for each local hour `h`, the factor of UTC hour `(h + 5) mod 24`, and the value for 17:00 local equals the 22 UTC value (0.4816).
2. **Given** the regenerated CSV, **When** the simulator runs with seeds 42 and 7 for 3,600 s, **Then** the stream hashes equal the new golden hashes recorded in this story, and the old and new hashes are both documented.
3. **Given** the factors are applied by local hour in the simulator and in M1, **When** the build output is read back, **Then** the lowest-traffic hours of the data (03:00 local) carry the highest speed factor.
4. **Given** `data/raw/` is not in git, **When** a team member checks out the branch, **Then** the committed CSV is enough to run all tests, and `data/reference/SOURCES.md` states that SIMM `FECHAHORA` is UTC and is converted to local hour (UTC−5) in the build.

---

### User Story 2 - No False Gap When a Bus Leaves the Terminal (Priority: P1) — finding H-10

A bus must not be reported as `gap` just because the bus ahead waited a long time at the terminal. Before its trip starts, each bus waits at P-883 sending `bus_position` events with `distance_along_m = 0` and the same `trip_id`. When the follower is exactly at 0 m, the headway rule takes the leader's **first** 0 m sample (when it started waiting) instead of when it left. On scenario C1 (seed 42) the headways come out as 1,235 s, 1,835 s and 2,435 s at 22:20:35, 22:30:40 and 22:40:35. Those buses are flagged `gap` and the snapshot EWT jumps to 211, 467 and 731 s.

**Why this priority**: it makes the demo show a false alarm every ten minutes and corrupts the metric the dispatcher watches.

**Independent Test**: build a history where the ahead bus waits at 0 m for several minutes and then departs, place a follower at 0 m, and check the headway equals the follower's position time minus the ahead bus's **departure** time. Then replay C1 seed 42 and read the three snapshots.

**Acceptance Scenarios**:

1. **Given** the bus ahead sat at 0 m for N seconds before leaving, **When** a follower is at 0 m, **Then** the time the ahead bus "passed" the terminal is its departure from the first stop (not any of its waiting samples), and the headway is measured from that time.
2. **Given** scenario C1 with seed 42, **When** the snapshots at 22:20:35, 22:30:40 and 22:40:35 are read, **Then** the headway of the bus leaving the terminal is between 300 s and 900 s (the repo's `bunched` and `gap` thresholds at the 600 s plan) and no bus is `gap` because of the terminal wait.
3. **Given** the same three snapshots, **When** the snapshot EWT is read, **Then** it no longer shows the jumps to 211, 467 and 731 s caused by this defect.
4. **Given** a bus that has never left the terminal and is still waiting, **When** the headway is computed, **Then** it is not used as the "ahead bus passed" evidence for another bus, and no error occurs.
5. **Given** a unit test of the headway rule with a waiting leader at 0 m, **When** the suite runs, **Then** the test exists, was written before the fix, and fails on the unfixed code.

---

### User Story 3 - EWT Measured at Stops (Priority: P1) — findings H-17 and H-11

The service metric must say how long riders wait at stops, which is what the quality payment is based on. Today `rules/service_metric.py` computes EWT from the *spatial* headways between buses on the corridor at one instant. During bunching only the short headway is seen: in C1, B-103 bunched 195 s behind B-102 gives EWT = 97.5 − 300 = **−202 s** ("better than planned"). The value also swings ±200 s whenever a bus enters or leaves the corridor, and headways measured against an `estimated` bus are included.

**Why this priority**: a metric that shows "better than planned" during bunching misleads the dispatcher and breaks Gate 4 (the effect of a hold cannot be judged on it). ADR-0007 compares EWT before and after a hold, so the definition must be right before story 006.

**Definition (standard stop-based EWT)**:

- For each stop, take the headways between consecutive **departures** from that stop (`silver.stop_visits`) inside a window.
- `mean_wait = Σh² / (2 Σh)` and `scheduled_wait = Σhp² / (2 Σhp)`, where the planned headway `hp` comes from `config.corridor_settings` (600 s today).
- `EWT = mean_wait − scheduled_wait`.
- The corridor value combines the stops by summing their `Σh` and `Σh²` (additive), then applies the same formulas.
- A headway that involves a departure made while the bus was `estimated` is excluded.

**Independent Test**: for a seeded scenario, recompute per-stop and corridor EWT directly from the `silver.stop_visits` rows with a separate script (the oracle) and compare with the gold values.

**Acceptance Scenarios**:

1. **Given** C1 seed 42 without the hold, **When** the corridor EWT over stops P-888..P-900 and departures 22:28:55–22:44:55 is read, **Then** it is about +40.6 s (the review reference), and the independent recomputation matches the gold value exactly.
2. **Given** C1 seed 42 with the seeded 90 s hold approved at 22:23:35, **When** the same window is read, **Then** the corridor EWT is about +23.6 s and is lower than the value without the hold.
3. **Given** B-103 is bunched behind B-102 in C1, **When** the EWT is read, **Then** it is positive (never "better than planned" because of bunching).
4. **Given** a bus enters or leaves the corridor between two snapshots and no departure falls in the window, **When** the EWT is read, **Then** it does not swing by the ±200 s seen before; only departures in the window count.
5. **Given** a stop with fewer than two departures in the window, **When** its row is built, **Then** it has no headway, contributes nothing to the corridor sums, and is marked not computable (no zero, no error).
6. **Given** a departure made while the bus was `estimated`, **When** the headways are built, **Then** both headways that touch that departure are excluded, and the exclusion is counted so coverage is visible.
7. **Given** the existing reader of `gold.service_metric`, **When** it selects `n_headways`, `mean_wait_s`, `scheduled_wait_s`, `ewt_s`, `computable`, **Then** the same columns exist with the new definition, and per-stop rows are available in addition.
8. **Given** the same bronze events, **When** the pipeline is rerun or the gold is rebuilt, **Then** the values are identical (idempotent), and each row carries `rules_version` and `max_bronze_id`.

---

### User Story 4 - Boarding Probability P(board ≤ t) (Priority: P1) — new metric, PRD quality axis, MVP-5

The quality screen needs the probability that a rider boards within `t` minutes, for t = 5, 10 and 15. Data stores additive counts per stop and 15-minute local band, so the backend only filters and sums (ADR-0003: the backend never computes headways or waits).

**Simple method (MVP)**: a rider's wait is the time from their `rider_arrival` to the **next departure of any bus from their stop**. Full buses are ignored.

**Why this priority**: it is the key metric of the project (AGENTS.md) and the decision model needs it. The simple method is enough for the workshop. The FIFO method (capacity and rejections, "full bus included") is Evolution.

**Independent Test**: from raw `rider_arrival` events and `silver.stop_visits` departures, an independent script computes, per stop and band, the number of riders and how many wait ≤ 5, ≤ 10 and ≤ 15 min. Its output must equal the stored counts and the read query.

**Acceptance Scenarios**:

1. **Given** a rider arrives at a stop at time `a` and the next departure from that stop is at `d`, **When** `d − a ≤ t`, **Then** the rider is counted in `n_board_le_t`.
2. **Given** a rider with no departure yet, **When** the elapsed time since arrival is still ≤ t, **Then** the rider stays open: counted in `n_riders` but not in any `n_board_le_t`.
3. **Given** an open rider whose elapsed time exceeds t with still no departure, **When** counts are read, **Then** the rider is definitively not counted for that t (and may still be counted for a larger t only if a departure arrives within it). A rider is never counted as ≤ t without a departure as evidence.
4. **Given** a rider arrives exactly at a departure time, **When** the wait is computed, **Then** the rule for equal timestamps is the same as in the oracle and is documented (assumed: a departure at the arrival instant counts, wait = 0).
5. **Given** the stored counts, **When** the corridor and per-stop probability is read over a range of bands through the provided query or view, **Then** `P(board ≤ t) = Σ n_board_le_t / Σ n_riders`, with a null (not 0) result when `Σ n_riders = 0`.
6. **Given** the same bronze events, **When** the pipeline reruns or gold is rebuilt, **Then** counts are identical, and each row carries `rules_version` and `max_bronze_id`.
7. **Given** a duplicated `rider_arrival` (same `source` and `event_id`), **When** counts are computed, **Then** the rider is counted once.
8. **Given** a rider whose stop never sees a departure in the run, **When** the run ends, **Then** the rider appears in `n_riders` only.

---

### User Story 5 - An Impossible Position Must Not Take the Gold Cycle Down (Priority: P2) — finding H-5

One bad `bus_position` must not stop every other bus from getting a new snapshot. A `distance_along_m = 99999` passes validation today (the schema only has `minimum: 0`). When it is the bus's newest report, the whole cycle fails with a `ValidationError` in `CorridorNowV100`, because there is no previous or next stop for it, and **no bus** gets a new snapshot.

**Why this priority**: a single event can blind the dispatcher (Principle III, ingestion and observability must survive bad inputs). It is P2 only because the simulator never produces it; a real feed can.

**Independent Test**: two cases. (a) Send the event through ingestion and check it is rejected. (b) Insert the row straight into bronze (as if ingestion had been bypassed or the route changed) and run a cycle.

**Acceptance Scenarios**:

1. **Given** a `bus_position` with `distance_along_m` above the last stop's `distance_along_m` in `config.ref_stops` (5,119.4 m) or below 0, **When** it reaches ingestion, **Then** it is rejected with the existing reason `value_out_of_range`, stored in `bronze.rejections` with the original message, and nothing is written to bronze events.
2. **Given** a position of exactly 0 or exactly 5,119.4 m, **When** it reaches ingestion, **Then** it is accepted.
3. **Given** a row with `distance_along_m = 99999` inserted directly into bronze as the newest report of a bus, **When** the gold cycle runs, **Then** the cycle completes, a new snapshot is written, that bus is treated as not reporting (`estimated`, no alert from it), and the other buses keep their normal state.
4. **Given** the case above, **When** the same bus later sends a valid position, **Then** it returns to `live` on the next cycle.
5. **Given** the route bounds cannot be read at ingestion time (reference data not loaded), **When** an event arrives, **Then** ingestion keeps capturing events (Principle III) and the pipeline protection of scenario 3 still holds.
6. **Given** the new rule, **When** the `contracts/` JSON Schemas are compared with the commit before this story, **Then** they are unchanged: the bound comes from reference data, not from the schema.

---

### User Story 6 - A Future-Dated Event Must Not Hijack the Clock (Priority: P2) — finding H-4

A single bus cannot move the reference time far ahead of the others. With `REFRESH_CLOCK=data`, the reference time is `max(event_ts)` of the bus reports (`refresh/run.py`). One schema-valid `bus_position` with `event_ts = 2030-01-01` moved the clock to 2030: the other buses became `estimated` and the corridor `estimated`. Because bronze is insert-only, it stays that way.

**Constraint**: the simulated clock (`event_ts`, 2026-11-24 22:00Z onward) is not the wall clock (`arrival_ts`). A check of "`event_ts` ahead of `arrival_ts`" would reject every simulator event, so this story does **not** use it.

**Required behavior**: the reference time ignores a bus whose latest report is more than `ESTIMATED_AFTER_S` (120 s, existing threshold in `rules/__init__.py`) ahead of the other buses' latest reports, and that bus is reported as not trustworthy.

**Why this priority**: same reasoning as US5: one event can blind the dispatcher, and bronze immutability makes the damage permanent.

**Independent Test**: run a normal simulated feed, inject one `bus_position` dated 2030-01-01, and run cycles.

**Acceptance Scenarios**:

1. **Given** a normal feed and one injected event with `event_ts = 2030-01-01`, **When** the next cycle runs, **Then** `as_of_ts` stays in the simulated day and the other buses stay `live`.
2. **Given** the same case, **When** the corridor and source status are read, **Then** the injected bus is reported as not trustworthy (treated as `estimated`, listed as down) and no alert or recommendation targets it.
3. **Given** a bus whose latest report is ahead of the others by no more than 120 s, **When** the cycle runs, **Then** it is a normal bus and the reference time is the same as before this story.
4. **Given** the injected event is already in bronze, **When** the same bus later reports valid, in-range times, **Then** its latest report is the newest by event time among its valid reports and it returns to `live`. (The future event stays in bronze; it never again moves the clock.)
5. **Given** only one bus is reporting at all, **When** the cycle runs, **Then** the reference time is that bus's latest report (nothing to compare with); this is documented as a limit.
6. **Given** a feed from the simulator at its normal pace, **When** the suite runs, **Then** no simulator event is rejected or ignored by the new rule (the golden hashes of US1 are unchanged by this item).

---

### Edge Cases

- A stop with no departures, or with one departure, in the window: not computable, no zero (US3.5).
- Departure at a stop made by a broken-down bus: it still counts as a departure for riders and for headways unless the bus was `estimated` (this story does not change broken-down handling).
- Band boundaries: a rider arriving at 17:14:59 local belongs to band 68; the departure that serves them may fall in band 69. The rider is attributed to the **arrival** band.
- Daylight saving: none; local time is a fixed UTC−5 offset (`timebands.py`).
- SIMM hours with no data: the build already falls back to the overall mean with a warning; this story must keep that behavior after the hour conversion.
- Position exactly equal to a stop distance (0 m or 5,119.4 m): valid.
- Several future-dated buses at once: each is ignored if it is more than 120 s ahead of the group of the rest; with all buses far apart there is no trustworthy reference (US6.5 limit).
- Backward position jumps and unknown stop ids are **out of scope** (H-6, H-7); they do not change behavior here.

## Requirements *(mandatory)*

### Functional Requirements

**Process**

- **FR-001**: Tests MUST be written before the code of each item and MUST fail on the unfixed code (Principle V). Each defect (US1–US2, US5–US6) MUST have a regression test that reproduces the review evidence.
- **FR-002**: Every new rule MUST be deterministic code in `rules/` or the pipeline; no LLM judges data (Principle III).
- **FR-003**: No file under `contracts/` and no ADR text is changed by this story. The affected documents are listed in "Affected Documents" below for the data owner.

**US1 — local hour (H-1)**

- **FR-010**: The reference build MUST convert the SIMM `FECHAHORA` UTC hour to local hour (UTC−5, the offset of `rules/timebands.py`) before grouping, so factor `h` describes local hour `h`.
- **FR-011**: `data/reference/congestion_factor.csv` MUST be regenerated locally from `data/raw/` and committed. `data/reference/SOURCES.md` MUST state that `FECHAHORA` is UTC and is converted to local hour.
- **FR-012**: The simulator golden hashes (seeds 42 and 7, 3,600 s) MUST be updated, and the old and new values MUST be recorded in this story's verification notes.
- **FR-013**: The simulator (`ref.congestion[hour_of(t)]`) and M1 (`hour_band`) MUST continue to read the factor by local hour, unchanged.

**US2 — terminal departure (H-10)**

- **FR-020**: The time a bus ahead "passed" a distance of 0 m MUST be its departure from the first stop, not the time of its waiting samples.
- **FR-021**: The headway rule MUST NOT raise or return a negative value when the bus ahead has not yet departed; the behavior for that case is defined by US2.4.
- **FR-022**: There MUST be a unit test of the headway rule for a waiting leader at 0 m, and an integration test on C1 seed 42 for the three snapshots named in US2.2.

**US3 — stop-based EWT (H-17, H-11)**

- **FR-030**: EWT MUST be computed per stop from headways between consecutive departures in `silver.stop_visits`, with the formulas in US3 and the planned headway from `config.corridor_settings`.
- **FR-031**: The corridor EWT MUST combine stops by summing `Σh` and `Σh²` (and `Σhp`, `Σhp²`), not by averaging per-stop EWT.
- **FR-032**: A headway that involves a departure made while the bus was `estimated` MUST be excluded. "Estimated at departure" uses the same rule as the existing freshness classification (no report within `ESTIMATED_AFTER_S` = 120 s of the departure).
- **FR-033**: `gold.service_metric` MUST keep its columns (`n_headways`, `mean_wait_s`, `scheduled_wait_s`, `ewt_s`, `computable`, `rules_version`, `max_bronze_id`) and its one-row-per-snapshot shape, with the new definition. Per-stop rows MUST be stored in an additional object keyed by snapshot and stop, carrying the additive sums (`n_headways`, `Σh`, `Σh²`, `Σhp`, `Σhp²`) and lineage.
- **FR-034**: The `gold.service_metric` row of each snapshot MUST use a trailing 15-minute window ending at the snapshot's `as_of_ts` (see assumption A-1). In addition, for each closed, clock-aligned 15-minute local band (`m2_band`, the same bands as US4), the system MUST store one row per stop with the additive sums `n_headways`, `Σh`, `Σh²`, `Σhp`, `Σhp²` and lineage (`rules_version`, `max_bronze_id`). A band is closed once `as_of_ts` has passed its end; its rows are recomputed identically from the same bronze. Reports and payment MUST read the band rows, not the trailing-window rows.
- **FR-035**: A stop or a corridor with no headway in the window MUST be not computable (`ewt_s` null, `computable` false), never 0.
- **FR-036**: The old spatial EWT function MUST NOT be used for `gold.service_metric` anymore. Whether it stays as a helper for other rules is a plan decision.

**US4 — P(board ≤ t)**

- **FR-040**: For each stop and 15-minute local band (`m2_band`), the system MUST store additive counts: `n_riders` (arrived), `n_board_le_5`, `n_board_le_10`, `n_board_le_15`.
- **FR-041**: A rider counts in `n_board_le_t` only if a departure from their stop exists at most `t` minutes after their arrival. A rider with no such departure MUST NOT be counted as ≤ t.
- **FR-042**: A rider is attributed to the band of their arrival time (local time).
- **FR-043**: Each row MUST carry `rules_version` and `max_bronze_id`. Rebuilding from the same bronze MUST give identical rows.
- **FR-044**: A read query or view MUST return P(board ≤ t) for the corridor and per stop over a range of bands, as `Σ n_board_le_t / Σ n_riders`, with null when there are no riders.
- **FR-045**: The method is the simple one (next departure of any bus). Full-bus FIFO is Evolution and MUST NOT be implemented.

**US5 — impossible position (H-5)**

- **FR-050**: Ingestion MUST reject a `bus_position` whose `distance_along_m` is below 0 or above the largest `distance_along_m` in `config.ref_stops`, with reason `value_out_of_range` and a rejection record that keeps the original message (ADR-0001/0002).
- **FR-051**: Ingestion MUST keep capturing events if the bound cannot be read (Principle III); it MUST NOT stop or crash.
- **FR-052**: The gold pipeline MUST NOT fail the cycle because of a position that cannot be placed between two stops. That bus MUST be treated as not reporting (`estimated`), and other buses MUST be unaffected.
- **FR-053**: `contracts/` JSON Schemas MUST NOT change.

**US6 — future-dated event (H-4)**

- **FR-060**: The reference time under `REFRESH_CLOCK=data` MUST ignore any bus whose latest report is more than `ESTIMATED_AFTER_S` ahead of the latest reports of the other buses.
- **FR-061**: An ignored bus MUST be reported as not trustworthy (treated as `estimated` and listed in `sources_down`), and no alert or recommendation may target it.
- **FR-062**: No new threshold is introduced; the value is `ESTIMATED_AFTER_S` (120 s).
- **FR-063**: The rule MUST NOT compare `event_ts` with `arrival_ts` or any wall clock.
- **FR-064**: Normal simulator output MUST NOT be affected (the rule has no effect when all buses are within 120 s of each other).

### Key Entities

- **Congestion factor (reference)**: speed factor per local hour (0–23) built from SIMM; used by the simulator and M1.
- **Stop visit (silver)**: paired arrival and departure of a bus at a stop; the source of departures for EWT and P(board ≤ t).
- **Stop headway**: time between two consecutive departures from the same stop; excluded when either departure was made while the bus was `estimated`.
- **Stop service metric (gold, new)**: per snapshot and stop, additive sums (`n_headways`, `Σh`, `Σh²`, planned `Σhp`, `Σhp²`) from which stop and corridor EWT are derived.
- **Corridor service metric (gold, `service_metric`)**: one row per snapshot, same columns, new definition.
- **Boarding count (gold, new)**: per stop and 15-minute local band: `n_riders`, `n_board_le_5`, `n_board_le_10`, `n_board_le_15`, with lineage.
- **Boarding probability (read query or view)**: corridor and per-stop P(board ≤ t) over a band range.
- **Reference time**: the instant a snapshot describes (`as_of_ts`); in data-clock mode it comes from the bus reports and must not be pulled ahead by one bus.
- **Not-trustworthy bus**: a bus whose report is impossible (off-route position) or too far ahead in time; treated as `estimated`.

## Affected Documents (for the data owner; **not edited by this story**)

| Document | Section | Why it is affected |
|---|---|---|
| ADR-0007 (on `docs/data-contract`) | Decision: EWT before and after | Compares EWT at two snapshots. EWT is now stop-based over a trailing window, so "EWT before/after" values and the `c1_bunching` fixture numbers change meaning and size. |
| `docs/data-contract.md` v0.2 | Q4 (service KPI) | `gold.service_metric` keeps its columns but changes definition (stops, departures, window). The Q4 example (`ewt_s=-27.5`, one headway) no longer represents the metric. |
| `docs/data-contract.md` v0.2 | §3B H4 (`report_quality_band`) and Q12 | H4 sums are defined from spatial headways per snapshot; they must be defined from stop headways. The P(board ≤ t) columns now have a producer (`n_board_le_5/10/15`, `n_riders`). |
| ADR-0006 (on `docs/data-contract`) | §6 history layer | Names the history layer that will consume these sums; the sums change definition. |
| ADR-0003 and `contracts/read/` | `service_metric`, gate decision on EWT | Read contract 1.0.0 describes the EWT but has no field changes. Only the meaning wording may need an update. |
| ADR-0002 and `contracts/turn1-events/` | Rejection reason `value_out_of_range` | Reason reused for off-route positions; the schema is unchanged but the documented meaning grows. |
| `specs/002-silver-gold-baselines/` | FR-024, SC-007 | Defined EWT from spatial headways. Superseded by this story. |
| `specs/004-scenario-injectors/` | Phase 3 (effect table) | Out of scope here, but it will use the new EWT. |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (US1)**: The 24 factors of the regenerated CSV equal an independent recomputation from the raw SIMM file grouped by `UTC hour − 5`, with a maximum difference of 0 at the 4 decimals stored. The 17:00 local factor is 0.4816 (it was 0.5011).
- **SC-002 (US1)**: The simulator golden hashes for seeds 42 and 7 equal the documented new values; old and new hashes are both recorded.
- **SC-003 (US2)**: On C1 seed 42, 0 of the snapshots at 22:20:35, 22:30:40 and 22:40:35 report a `gap` caused by the terminal wait, and the headway at each is between 300 s and 900 s (was 1,235 s, 1,835 s, 2,435 s).
- **SC-004 (US2)**: The snapshot EWT at those three instants is not 211, 467 or 731 s.
- **SC-005 (US3)**: Per-stop and corridor EWT in gold equal an independent recomputation from `silver.stop_visits` exactly, for C1 seed 42, with and without the hold. This holds for both the trailing 15-minute window of each snapshot and the per-stop additive sums of each closed clock-aligned 15-minute band (0 differences in `n_headways`, `Σh`, `Σh²`, `Σhp`, `Σhp²`).
- **SC-006 (US3)**: On C1 seed 42, stops P-888..P-900, departures 22:28:55–22:44:55 (the oracle's reference window, read directly from `silver.stop_visits`; the same sums grouped by closed clock-aligned band must also add up to the oracle's totals for that band): EWT is +40.6 s (±0.1 s) without the hold and +23.6 s (±0.1 s) with the 90 s hold approved at 22:23:35. The value with the hold is lower than without it.
- **SC-007 (US3)**: In the C1 snapshot where B-103 is bunched 195 s behind B-102, EWT is greater than 0 (was −202 s).
- **SC-008 (US3)**: Adding or removing a bus that has no departure in the window changes the EWT by 0 s (no ±200 s swing).
- **SC-009 (US4)**: For seeded runs of C1 and of the base case, per stop and band counts of `n_riders`, `n_board_le_5`, `n_board_le_10`, `n_board_le_15` equal an independent recomputation from the raw events: 0 differences.
- **SC-010 (US4)**: A rider with no departure is counted in 0 of the `n_board_le_t` columns (checked on a case with at least one such rider).
- **SC-011 (US4)**: Rebuilding gold twice from the same bronze gives identical count rows (0 differences).
- **SC-012 (US5)**: An injected `distance_along_m = 99999` event through ingestion is rejected 100 % of the time with `value_out_of_range`. Inserted straight into bronze, the cycle still writes a snapshot, and the 4 other in-service buses keep their state.
- **SC-013 (US6)**: After injecting one event dated 2030-01-01, `as_of_ts` stays within the simulated day (on or after 2026-11-24 22:00Z and not in 2030) and the other buses stay `live` in 100 % of the cycles run after the injection.
- **SC-014**: The full test suite passes with coverage above 80 %, the existing contract and read-fixture tests pass without edits to `contracts/`, and `git diff` of `contracts/` and `docs/adr/` against `feature/004-scenario-injectors` is empty.

## Assumptions

- **A-1 (window)**: A trailing 15-minute window ending at `as_of_ts` is used for the snapshot EWT. Justification from the repository: M2 and the report bands use 15-minute local bands (`timebands.py`, `WINDOW = 15 min`), and the review reference window (22:28:55–22:44:55, 16 min of departures) is of that size. A trailing window gives a value for every snapshot; a clock-aligned band gives none until the band closes. Decided by the data owner on 2026-11-21 (Clarifications): the trailing window feeds the live headline EWT, and closed clock-aligned bands feed reports and payment, so both are kept.
- **A-2**: The review numbers (+40.6 s and +23.6 s) were produced by the data owner's oracle on C1 seed 42 and are reproducible with the same seed; they are stated "about", so the criterion uses ±0.1 s.
- **A-3**: The planned headway for every stop is the single `headway_planned_s` of `config.corridor_settings` (600 s). Per-stop or per-band plans are Evolution.
- **A-4**: The route end is the largest `distance_along_m` in `config.ref_stops` (5,119.4 m today), read from reference data at ingestion. The bound is data, not contract.
- **A-5**: "Not trustworthy" reuses the existing `estimated` state and `sources_down` listing; no new status value is added to the read contract.
- **A-6**: A rider is counted for the stop named in `rider_arrival`. If the event names an unknown stop, the rider is counted nowhere (stop validity is H-7, out of scope).
- **A-7**: Riders whose wait is still open are never removed from `n_riders`; the stored counts are recomputed each cycle, so a later departure can move an open rider into the ≤ t columns.
- **A-8**: ADR-0006, ADR-0007 and `docs/data-contract.md` exist only on `docs/data-contract`. They are read from there; they are not merged into this branch by this story.
- **A-9 (time of day)**: The reference data already varies by local hour: the demand shape (Metro line A, peak 0.105 at 17:00), train arrivals per hour (40 at 17:00 and 18:00) and the SIMM congestion factor. After US1, the slowest factor falls at 18:00 local (0.458).
- **A-10 (limitation, planned headway)**: The planned headway is 600 s at every hour (`config.corridor_settings`). There is no timetable by hour of day. EWT, which compares observed waits with this plan, is therefore measured against the same plan at peak and off-peak.
- **A-11 (limitation, weekday only)**: The GTFS `service_id` is `Laboral` (weekday). There are no weekends or holidays.
- **A-12 (known bias, SIMM period)**: SIMM covers only January 2021, a vacation month in Colombia. Traffic may be lighter than in a typical month, so the congestion factors may be biased toward faster travel.
- **Dependencies**: story 004 phases 1–2 (scenarios, hold loop, `silver.stop_visits`). Story 006 (decision model) depends on this story.

## Out of Scope (Evolution or later stories)

- Decision model and recommendations (story 006).
- Recommendation effect table (story 004 phase 3).
- History and reports layer of `docs/data-contract.md` §3B (H1–H4 tables). This story only produces the sums that H4 will use.
- Performance of the cycle (H-8).
- Backward position jumps and unknown stop ids (H-6, H-7).
- Minor findings H-9 and H-16.
- FIFO method for P(board ≤ t) with capacity and rejections ("full bus included").
- Any change to `contracts/` JSON Schemas or to ADR text.
