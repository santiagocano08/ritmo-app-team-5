# ADR-0006: Backend data consumption: freshness, simulated clock, recommendation door and history layer

- Status: Proposed
- Date: 2026-11-21
- Decided by: data owner, 2026-11-21 (decisions recorded from `docs/data-contract.md` v0.2). The backend owner must still accept items 1–5.
- Turn: Turn 1 — Data and Minimal Loop (active)
- Addresses: Principle II (Contract-First and Data Ownership), Principle IV (Human Gate: nothing
  reaches `applied` without a dispatcher `decision`), turn-1 risk (data integrity: stale, mis-timed
  or recomputed-by-the-wrong-owner data contaminates the metric and the recommendations), RF-2.2 and
  RF-2.3, and the reporting needs of MVP-4 (shift log and effect) and MVP-5 (quality indicators,
  payment-relevant) in "PulsoFlota · Mock-ups v2".

## Context

ADR-0003 defines three doors (query, push, command) and the read schemas, but leaves open how the
backend physically reads gold, how it knows data is stale, which clock it writes, how the decision
engine hands recommendations to data, and how history is served. `docs/data-contract.md` v0.2
describes these points. It was verified on 2026-11-21 on a throwaway database (§7 of that document).
Findings that drive this ADR:

- `gold.snapshots.as_of_ts` is simulated time, so it cannot show staleness. A local stack whose
  simulator had finished hours earlier returned `age_s = 28404` while `as_of_ts` still looked valid
  (§7, item 7).
- An incident written with wall time landed two days "in the past", was already closed and never
  appeared as active (§1.4 and §7, item 5).
- The backend has no door to give recommendations to data; the demo uses a seed
  (`config.seed_recommendation`).
- MVP-3 requires a discard reason, but the `decision` payload has no field for it.
- MVP-4 and MVP-5 need history. ADR-0003 says the backend never computes headways or EWT.

## Options considered (max. 3)

1. **The database is the interface (chosen).** The backend reads gold and `config` with SQL, listens
   on `gold_snapshot`, and inserts command events into `bronze.events`.
   - Pros: no new service; matches ADR-0001 and ADR-0003 (`LISTEN/NOTIFY`, `source = 'backend'` in
     bronze); one consistent snapshot per read; bronze stays the single audit trail.
   - Cons: the backend depends on table layout until public "latest" views exist; the shared turn-1
     DB user is not least-privilege.
2. **A data-owned HTTP API.**
   - Pros: layout hidden behind an API; easy to add auth later.
   - Cons: a second API to build, secure and run; adds a hop and a failure point on the 10 s path;
     duplicates the backend's role. Not needed for one corridor.
3. **A backend-owned table for recommendations and decisions.**
   - Pros: the backend controls its own schema and status.
   - Cons: data would read facts from a store it does not own, which breaks Principle II (owner and
     contract at the boundary) and splits the audit trail away from bronze. Principle IV would no
     longer be checkable from one place.

## Decision

Adopt option 1, with these six decisions.

### 1. The database is the interface

- The backend reads `gold` and `config` with SQL, and `ops.ingestion_health` optionally.
- It listens on the `gold_snapshot` channel (its own long-lived connection) and inserts command
  events into `bronze.events` with `source = 'backend'`, validated against
  `command_event.schema.json` first. Idempotency key: `(source, event_id)`.
- The backend never reads `silver`, never writes `silver`, `gold`, `config` or `ops`, and never
  updates or deletes bronze.
- There is no data-owned HTTP API.

### 2. Freshness rule

`age_s` = wall-clock seconds since `gold.snapshot_commits.committed_at` of the latest snapshot.

| Condition | Backend behaviour |
|---|---|
| `age_s ≤ 15` and `source_status.status = 'live'` | Normal |
| `source_status.status = 'estimated'` | Warning. No recommendation targets a bus in `sources_down` |
| `age_s > 15` | The backend neither proposes nor applies any recommendation. The console shows "data out of date (N s ago)" |
| `age_s > 30`, or no snapshot | System down. Warning only |

Reasons for 15 s (data-contract §2.1):
- it is 3 refresh cycles of 5 s, so one or two late cycles do not make the console flicker;
- it equals the ingestion healthcheck (`INGESTION_HEALTH_MAX_AGE_S=15`), so console and ingestion
  alerts fire together;
- with a real feed (1:1 clock), 15 s is about 75 m of bus travel, or 2.5 % of the 600 s planned
  headway;
- in the demo (5× pace, `SIM_PACE_S=1`) 15 s of wall time is 75 s of corridor time, still below the
  decision thresholds (bunched: headway under 300 s; gap: headway over 900 s);
- each recommendation also expires by itself at `expires_ts`.

30 s is the same threshold as the `refresh` healthcheck. `as_of_ts` must never be used to judge
staleness.

### 3. Simulated clock

The `event_ts` of every command event is the `as_of_ts` of the latest snapshot at the moment of the
click, never wall time. `arrival_ts` is wall time (`clock_timestamp()`). Verification (data-contract
§1.4 and §7, item 5): an incident written with wall time (`2026-11-22T00:30Z`, 30 min) landed two
days "in the past" in a simulated day that starts at `2026-11-24T22:00:00Z`, was already closed and
was never active. The incident written in simulated time was active and listed in
`decision_inputs.active_incidents`.

### 4. Recommendation door (option A)

- New `command_event` `event_type = 'recommendation'`. Its payload is the full
  `recommendation.schema.json` object (v1.0.0, unchanged) with `status = 'proposed'`.
  `lineage.snapshot_id` is the `decision_inputs` snapshot the engine used.
- Data publishes `gold.recommendation`, one row per `rec_id`, rebuilt each cycle. The `status` in
  `doc` is derived by data from facts: `proposed` (received, no decision, `as_of_ts ≤ expires_ts`),
  `applied` or `discarded` (first `decision` for that `rec_id` by bronze order), `expired`
  (`as_of_ts > expires_ts`, no decision).
- The backend never writes a status. Nothing reaches `applied` without a dispatcher `decision`,
  which keeps Principle IV checkable.
- The seeds in `config.seed_recommendation` become ordinary `recommendation` events.

### 5. Discard reason

The `decision` payload gets an optional `reason` (string, 1–200 characters). The backend requires it
when `action = 'discard'`. Data copies it to `gold.decision_log.reason`.

### 6. History layer in gold

Append-only facts and additive aggregates, written in the cycle transaction. The backend only filters
and sums (ADR-0003: the backend never computes headways or EWT).

| Object | Content |
|---|---|
| `gold.hist_bus_state` | One row per bus per snapshot; same content as `corridor_now.buses` |
| `gold.decision_log` | One row per recommendation: case, action, `proposed_ts`, `expires_ts`, derived `outcome`, `decided_ts`, `user_id`, `reason`, `instruction_status`, `effect_result`, lineage |
| `gold.report_quality_band` | One row per day × 15-minute band × operator: counts and sums (headways, planned headways, riders, `n_board_le_5/10/15`, events, rejections, bus snapshots, estimated bus snapshots) |

Rules for the bands:
- 15-minute bands of local time (America/Bogota, fixed UTC−5), band 0–95, same bands as M2.
- Additive counts, not ratios; the query divides, so sums over bands and days stay exact.
- Deterministic: a band row is rebuilt from bronze up to `max_bronze_id`; same bronze and same rules
  give the same row.
- Lineage on every band row: `rules_version`, `contract_version`, `computed_at` (wall time),
  `max_bronze_id`.
- Named bands (`evening_peak`, `off_peak`, `whole_day`) are rows in `config.report_bands`, so changing
  them never needs a recompute.
- The payable coverage threshold is `config.report_settings.payable_coverage` (0.90, still to be
  agreed with the client).
- P(board ≤ t) uses the simple method in the MVP (wait until the next departure of any bus from the
  rider's stop, ignoring full buses).

## Consequences

- **Easier:** no second API; one consistent snapshot per response; stale data is blocked by a
  measurable rule; recommendations and decisions are audited in bronze; the demo seed follows the
  same path as the real engine; MVP-4 and MVP-5 are answered by queries over additive rows, with the
  same result on every run.
- **Harder:** the backend depends on table layout until the public views exist; the backend needs a
  dedicated `LISTEN` connection; data must build `gold.recommendation` and the history layer
  (estimated in data-contract §6: about 4–6 h for the door, 7–9 h for all of §3B); the backend
  owner must write `event_ts` from the latest snapshot on every command.

## Affected contract

- `contracts/read/command_event.schema.json` **1.0.0 → 1.1.0** (minor, non-breaking), caused by
  items 4 and 5:
  - item 4 adds the enum value `recommendation` to `event_type`, with its payload branch;
  - item 5 adds the optional field `reason` to the `decision` payload.
- Existing 1.0.0 messages stay valid. Under the ADR-0002/0003 versioning rule a new enum value and a
  new optional field are a minor bump.
- **The schema file is NOT edited in this ADR.** The bump ships with the story that implements the
  door, so schema, generated models and code change together.
- This changes an existing contract: review by the data owner (CODEOWNERS) is required. The backend
  owner must accept items 1–5.
- No change to `recommendation.schema.json` (1.0.0). Items 1, 2, 3 and 6 add no field to any schema.
  The gold tables of item 6 are internal to data and are not JSON Schema contracts in turn 1.

## Evolution

- Public "latest" views (`gold.v_source_status`, `v_corridor_now`, `v_decision_inputs`) and a
  `backend_reader` role (SELECT on gold views and `config`, INSERT on `bronze.events`, LISTEN).
- Full P(board ≤ t) with full buses (FIFO queue per stop); M-4 data quality per operator.
- Data consuming `confirmation` (for example `no_confirmation` raising an alert), a turn-2 candidate.
- Redis push replaces `LISTEN/NOTIFY` (turn 3).

## Open questions

- [NEEDS CLARIFICATION] Payable threshold (90 % coverage) and the payment formula: still to be agreed
  with the client (data-contract §6, item 11).
- [NEEDS CLARIFICATION] Expiry window: MVP-3 says 2 min; the engine will set `expires_ts` and the
  seed uses its own value (data-contract §6, item 12). The backend must align.
- [NEEDS CLARIFICATION] Operators: every bus reports `operator = 'OP-01'`, so MVP-5 shows one row
  unless the simulator assigns more operators (data-contract §6, item 10).
