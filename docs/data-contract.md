# PulsoFlota — Data Contract for the Backend (v0.2, draft)

- **Owner:** data owner (see `.github/CODEOWNERS`). **Consumer:** backend (BE).
- **Status:** Proposed, 2026-11-21. Decisions recorded in ADR-0006 (backend data consumption; Proposed until the backend owner accepts items 1–5) and ADR-0007 (recommendation effect rule; Accepted by the data owner).
  - v0.2 adds the freshness rule (§2.1), history and reporting (§3B), the recommendation door (§4.5) and the discard reason (§4.6). It was aligned with the team's "PulsoFlota · Mock-ups v2 (MVP and improvements)".
  - It also records the new "worked" rule (H3); ADR-0007 proposes it to replace ADR-0003 gate decision 6.
- **Scope:** Turn 1. Corridor C6-008, direction 1, buses B-101..B-105 in service and B-106/B-107 in reserve, stops P-883..P-900.
- **Source of truth:** the JSON Schemas in `contracts/read/` and `contracts/turn1-events/`, plus ADR-0001, ADR-0002 and ADR-0003. This document says **how the BE reads and writes**. It adds no field to any schema. If this document and a schema disagree, the schema wins.

**Change rule (data owner, 2026-11-21):** every data change reviews this contract. Specs and plans list the affected sections, or "no contract impact" with the reason. Verification checks that the queries, examples and versions here still hold. When there is an impact, this document is updated in the same PR or the very next one. See `.kiro/steering/data-contracts.md`.

**Availability tags used below:**
- `[main]`: already in `main` (stories 001–003).
- `[004]`: arrives when story 004 (`feature/004-scenario-injectors`) is merged.
- `[proposed]`: not built yet.

---

## 1. Database structure

### 1.1 Connection

PostgreSQL 16, service `db` in `docker-compose.yml`, database `pulsoflota`.
- Inside compose: `DATABASE_URL=postgresql://<user>:<password>@db:5432/pulsoflota`.
- From the host: `localhost:5432`.
- Credentials come from `.env`; never hard-code them.
- Turn 1 uses one shared user. A dedicated read-only `backend_reader` role is `[proposed]` (see §6).

### 1.2 Schemas and what the BE may do in each

| Schema | Layer | Written by | BE access |
|---|---|---|---|
| `bronze` | Raw, immutable events (insert-only, ADR-0001) | ingestion; **BE for command events only** | **INSERT** into `bronze.events` (command events, §4). Never UPDATE or DELETE |
| `silver` | Per-bus state rebuilt from bronze | data pipeline | **None.** Internal; may change without notice |
| `gold` | Read objects, one JSON document per snapshot | data pipeline | **SELECT** only, on the objects listed in §3 |
| `config` | Reference data and settings | data (init and seed loader) | **SELECT** only (§3.9) |
| `ops` | Health views | data | **SELECT** only (optional, §3.8) |

### 1.3 The snapshot model (read this before writing any query)

The pipeline (service `refresh`) runs a **cycle every 5 s**. Each cycle creates **one snapshot**. All gold objects of that cycle share its `snapshot_id`.

```
gold.snapshots              ← one row per cycle; the "clock" of gold
  snapshot_id   UUID  PK
  as_of_ts      TIMESTAMPTZ        -- simulated time the snapshot describes
  rules_version TEXT
  max_bronze_id BIGINT             -- last bronze row included
        │ 1:1
        ├── gold.source_status   (snapshot_id PK, status TEXT, doc JSONB, rules_version, max_bronze_id)
        ├── gold.corridor_now    (snapshot_id PK, doc JSONB, rules_version, max_bronze_id)
        ├── gold.decision_inputs (snapshot_id PK, doc JSONB, rules_version, max_bronze_id)
        ├── gold.service_metric  (snapshot_id PK, n_headways INT, mean_wait_s, scheduled_wait_s,
        │                         ewt_s NUMERIC, computable BOOLEAN, rules_version, max_bronze_id)
        │ 1:N                                                                          [004]
        └── gold.incident        (snapshot_id, inc_id) PK, active BOOLEAN, doc JSONB, ...
            gold.incident_current  VIEW: incidents of the latest snapshot

Not per snapshot:
  gold.instruction_status  (rec_id PK, bus_id, stop_id, hold_s, observed_dwell_s,
                            status 'executed'|'not_executed', ts_by_status JSONB, ...)     [004]
  gold.m1_baseline / gold.m2_baseline   -- already inside decision_inputs; the BE does not read them
```

**Rules:**
1. **`doc` is the contract.** Each `doc` column is exactly one instance of its JSON Schema (`additionalProperties: false`, `schema_version: "1.0.0"`). The BE returns it as is, or maps it 1:1 to the generated Pydantic models in `src/pulsoflota/models/read/`. Do not parse the other columns of these tables: they are lineage.
2. **Latest snapshot** = `ORDER BY as_of_ts DESC, max_bronze_id DESC LIMIT 1`. Always use both keys.
3. **Consistency:** when one response combines several objects (for example, fleet plus data status), read the `snapshot_id` **once** and use it for every object. Never mix "latest" from separate queries.
4. **Append-only:** past snapshots stay. The BE can read history by `snapshot_id` or by a range of `as_of_ts`.

### 1.4 Clock: simulated time, not wall time

Gold time (`as_of_ts`, and every timestamp inside `doc`) is the **simulated clock**: the simulated day starts at `2026-11-24T22:00:00Z` and moves at the simulator's pace (`REFRESH_CLOCK=data`).

**Consequence for the BE:**
- To know "now" in the system, read `as_of_ts` of the latest snapshot. Do not use `now()`.
- The `event_ts` of every command event must be written in simulated time (§4.1).

This was **verified**: an incident written with wall time (`2026-11-22T00:30Z`, 30 min) landed two days "in the past", was already closed and **never appeared as active**.

---

## 2. How data is delivered

There are three doors (ADR-0003). There is no data-owned HTTP API: the database is the interface, and the BE owns the HTTP API.

| Door | Direction | Mechanism | Frequency |
|---|---|---|---|
| **Query** | data → BE | `SELECT doc FROM gold.<object> …` (§3) | On demand, when the BE serves a request |
| **Push** | data → BE | PostgreSQL `LISTEN gold_snapshot`. Payload: `{"snapshot_id": "<uuid>"}` | Once per **new** snapshot (≈ every 5 s while events flow) |
| **Command** | BE → data | `INSERT INTO bronze.events` with `source = 'backend'` (§4) | When the dispatcher acts |

**Push details:**
- The notification is sent **in the same transaction** that commits the snapshot. When it arrives, the rows are already readable.
- No snapshot means no notification. This happens when the feed stops, which is also when `refresh` turns unhealthy.
- `LISTEN` needs **its own long-lived connection**. A pooled connection that gets recycled will lose the subscription.
- Recommended BE flow: on each notification, read Q1 + Q2 (+ Q5) with that `snapshot_id`, then forward to the console over WebSocket or SSE. Nobody polls every second.
- On BE start or reconnect, read the latest snapshot once (Q0) before waiting for notifications.

### 2.1 Freshness rule (mandatory before any decision)

Gold carries **two clocks**:

| Clock | Column | Answers |
|---|---|---|
| Business time (simulated) | `gold.snapshots.as_of_ts` and every time inside `doc` | Which moment of the corridor does this snapshot describe? |
| Wall time | `gold.snapshot_commits.committed_at` | How long ago was this snapshot computed? |

`as_of_ts` **cannot** tell whether data is stale, because it is simulated time. Staleness is always measured in wall time: `age_s = clock_timestamp() − committed_at` of the latest snapshot (returned by Q0).

| Condition | BE behaviour |
|---|---|
| `age_s ≤ 15` and `source_status.status = 'live'` | Normal: show data, propose recommendations |
| `source_status.status = 'estimated'` | Show data with a warning. **No recommendation that targets a bus listed in `sources_down`** (case D1) |
| `age_s > 15` | Console shows **"data out of date (N s ago)"**. The BE **neither proposes nor applies** any recommendation |
| `age_s > 30`, or no snapshot | System down (same threshold as the `refresh` healthcheck). Show the warning only |

**Why 15 s:**
- It is **3 refresh cycles** (one every 5 s): one or two late cycles do not flicker the console.
- It equals the ingestion healthcheck (`INGESTION_HEALTH_MAX_AGE_S=15`), so the console and the ingestion alert fire together.
- With a real feed (1:1 clock), 15 s is about 75 m of bus travel, or 2.5 % of the 600 s planned headway.
- In the demo the simulator runs at 5× (`SIM_PACE_S=1`), so 15 s of wall time is 75 s of corridor time. That is still below the decision thresholds: bunched is a headway under 300 s, gap is a headway over 900 s.
- Each recommendation also expires by itself at `expires_ts`.

A snapshot from yesterday has `age_s ≈ 86 400` and is blocked automatically. `ops.ingestion_health` (Q8) gives the reason for the staleness.

---

## 3. What the BE needs, why, and the exact query

Parameters use psycopg style (`%(name)s`). All example outputs are **real**: they come from the verification run in §7 (seed 42, 20 simulated minutes), except where a fixture is named.

### Q0. Latest snapshot `[main]`
**Why:** the base for every consistent read, the system "now" (`as_of_ts`, simulated) and the data age (`age_s`, wall seconds) that the freshness rule (§2.1) checks.
```sql
SELECT s.snapshot_id, s.as_of_ts, s.rules_version,
       extract(epoch FROM clock_timestamp() - c.committed_at) AS age_s
FROM gold.snapshots s
JOIN gold.snapshot_commits c USING (snapshot_id)
ORDER BY s.as_of_ts DESC, s.max_bronze_id DESC
LIMIT 1;
```
```
snapshot_id=7b9e3fcb-2861-4bb2-8b4f-005275c56335  as_of_ts=2026-11-24 22:19:55+00  rules_version=1.1.0  age_s=3.2
```
(`age_s` is illustrative here: the value depends on when the query runs.)

### Q1. Data status `[main]`
**Screen:** US-03, the data quality banner. **Schema:** `source_status.schema.json`.
**Why:** tells the dispatcher whether the data can be trusted (`live`, `estimated` or `no_data`) and which buses went silent.
```sql
SELECT doc FROM gold.source_status WHERE snapshot_id = %(snapshot_id)s;
```
```json
{"schema_version": "1.0.0", "snapshot_id": "7b9e3fcb-…", "as_of_ts": "2026-11-24T22:19:55Z",
 "status": "live", "sources_down": []}
```
When a bus is silent, from fixture `d1_source_outage`:
```json
{"status": "estimated", "sources_down": [{"bus_id": "B-103", "since": "2026-11-24T08:01:30Z"}], "...": "..."}
```

### Q2. Live fleet panel `[main]`
**Screen:** US-04. **Schema:** `corridor_now.schema.json`.
**Why:** shows where each bus is, its gap to the bus ahead and its state.
- `buses` is ordered leader first.
- `bus_state` is one of `leader`, `regular`, `bunched`, `gap`, `broken_down`.
```sql
SELECT doc FROM gold.corridor_now WHERE snapshot_id = %(snapshot_id)s;
```
```json
{"schema_version": "1.0.0", "snapshot_id": "7b9e3fcb-…", "as_of_ts": "2026-11-24T22:19:55Z",
 "corridor_id": "C6-008", "direction": 1,
 "buses": [
   {"bus_id": "B-101", "bus_state": "leader", "prev_stop_id": "P-895", "next_stop_id": "P-896",
    "distance_along_m": 4272.0, "headway_ahead_s": null, "headway_planned_s": 600.0,
    "data_quality": "live", "direction": 1, "ts": "2026-11-24T22:19:55Z"},
   {"bus_id": "B-102", "bus_state": "regular", "prev_stop_id": "P-889", "next_stop_id": "P-890",
    "distance_along_m": 2820.1, "headway_ahead_s": 545.0, "headway_planned_s": 600.0,
    "data_quality": "live", "direction": 1, "ts": "2026-11-24T22:19:55Z"}],
 "summary": {"buses_in_service": 2, "n_bunched": 0, "n_gaps": 0}}
```
Only 2 buses appear because the simulated day starts at 22:00 (night service). At peak, all 5 appear.

### Q3. Decision engine input `[main]` (internal: never sent to the console)
**Consumer:** the BE decision engine (cases C1, C2, C5, D1). **Schema:** `decision_inputs.schema.json`.
**Why:** everything the engine needs in one document: the fleet (as in Q2), M1 travel time per segment, M2 demand for the next 15 min, free reserves and drivers, active incidents, action costs and enabled stops.
```sql
SELECT doc FROM gold.decision_inputs WHERE snapshot_id = %(snapshot_id)s;
```
```json
{"...": "same fields as corridor_now, plus:",
 "travel_time_forecast": [{"segment_id": 1, "forecast_travel_s": 99.86}, {"segment_id": 2, "forecast_travel_s": 55.75}, "… 17 segments"],
 "demand_15min": {"window_start_ts": "2026-11-24T22:30:00Z", "window_end_ts": "2026-11-24T22:45:00Z", "arrivals_forecast": 17},
 "resources": {"reserve_free": ["B-106", "B-107"], "drivers_free": 2},
 "active_incidents": ["11111111-1111-4111-8111-111111111111"],
 "action_cost": {"hold_penalty_s": 0.0, "early_departure_penalty_s": 0.0},
 "enabled_stops": ["P-883", "…", "P-900"]}
```

### Q4. Service KPI: excess waiting time `[main]`
**Screen:** dashboard KPI. This is **not a JSON Schema object**: it is plain columns.
**Why:** the headline metric. EWT = mean wait − scheduled wait. It can be **negative**, which means better than planned. If `computable = false`, there are not enough headways: show "—", not 0.
```sql
SELECT s.as_of_ts, m.n_headways, m.mean_wait_s, m.scheduled_wait_s, m.ewt_s, m.computable
FROM gold.service_metric m JOIN gold.snapshots s USING (snapshot_id)
WHERE m.snapshot_id = %(snapshot_id)s;
```
```
as_of_ts=2026-11-24T22:19:55Z  n_headways=1  mean_wait_s=272.5  scheduled_wait_s=300  ewt_s=-27.5  computable=true
```

### Q5. Active incidents `[004]`
**Screen:** US-12. **Schema:** `incident.schema.json`.
**Why:** lists the breakdowns and closed stops, whether reported by the dispatcher through the BE or injected by the simulator. They also feed `decision_inputs.active_incidents` and the `broken_down` state.
```sql
SELECT doc FROM gold.incident_current WHERE active;
-- for a specific snapshot: SELECT doc FROM gold.incident WHERE snapshot_id = %(snapshot_id)s AND active;
```
```json
{"schema_version": "1.0.0", "inc_id": "11111111-1111-4111-8111-111111111111", "type": "bus_breakdown",
 "target_id": "B-104", "since": "2026-11-24T22:10:00Z", "until": null, "duration_s": 1800.0,
 "reported_by": "dispatcher"}
```
`inc_id` equals the `event_id` of the `incident_report` that created the incident. That lets the BE match its own report.

### Q6. Execution status of an approved hold `[004]`
**Screen:** US-10, driver instruction status. The BE builds `instruction.schema.json` by merging:
- its own fields (`inst_id`, `text`, `sent`, `received`);
- this data status, joined by `rec_id`.

**Why:** data decides `executed` / `not_executed` from what the bus actually did: the observed dwell has to be within ±15 s of the requested hold. The BE never self-declares execution.
```sql
SELECT status, ts_by_status, observed_dwell_s, hold_s, bus_id, stop_id
FROM gold.instruction_status WHERE rec_id = %(rec_id)s;
```
- **No row = still pending.** This was verified: right after the `apply` decision, the table is empty until the bus visits the stop or the recommendation expires.
- With a row (illustrative values, not from the run): `status = 'executed'` and `ts_by_status = {"executed": "2026-11-24T22:16:40Z"}`. The map has a single key, matching `status`, and the time is the bus departure.

### Q7. Recommendations: temporary seed `[004]`
**Why:** the decision engine and the "recommendation door" do not exist yet. Until they do, the demo recommendations live in `config.seed_recommendation`, one row per `rec_id`, each a valid `recommendation.schema.json`. The BE lists them, the dispatcher approves or discards (§4.2), and the BE owns the `status` shown on screen.
```sql
SELECT doc FROM config.seed_recommendation ORDER BY doc->>'rank';
```
```json
{"schema_version": "1.0.0", "rec_id": "a1b2c3d4-0001-4000-8000-000000000001", "case": "C1",
 "action": {"type": "hold", "bus_id": "B-103", "stop_id": "P-887", "duration_s": 90},
 "reason": "B-103 closes on B-102; holding it 90 s at P-887 restores the headway (seeded demo recommendation)",
 "ewt_saving_s": 55, "horizon_s": 300, "data_quality": "live", "expires_ts": "2026-11-24T22:35:00Z",
 "conflicts_with": [], "rank": 1, "status": "proposed",
 "lineage": {"model_version": "1.0.0", "rule_version": "1.1.0", "snapshot_id": "a1b2c3d4-0001-4000-9000-000000000001"}}
```

### Q8. Pipeline health (optional) `[main]`
**Why:** lets the BE expose a "data is stale" reason or a readiness check. It always returns one row and uses the database clock (wall time).
```sql
SELECT observed_at, last_insert_age_s, events_60s, rejections_60s, duplicates_60s, rejection_rate_60s
FROM ops.ingestion_health;
```
```
last_insert_age_s=11.3  events_60s=1259  rejections_60s=0  duplicates_60s=0  rejection_rate_60s=0
```

### Q9. Reference data (load once at BE start) `[main]`
**Why:** static lists for the console and for validating dispatcher input: stop order and distances, fleet roles, planned headway.
```sql
SELECT stop_seq, stop_id, distance_along_m, segment_id FROM config.ref_stops ORDER BY stop_seq;   -- 18 rows, P-883..P-900
SELECT bus_id, role FROM config.fleet_roster ORDER BY bus_id;                                    -- in_service | reserve
SELECT corridor_id, headway_planned_s FROM config.corridor_settings;                              -- C6-008, 600
```
`config.ref_stops` has no stop names. If the console needs names, raise it with data: it would be a new reference column.

---

## 3B. History and reporting `[proposed]`

The live objects (§3) answer "what is happening now", with one JSON document every 5 s. The reporting screens of the MVP mock-ups ("PulsoFlota · Mock-ups v2", 2026-11-20) ask "how did we do":
- **MVP-4, Shift log and effect** (dispatcher): every decision of the shift; for each applied one, the headway between the buses involved from −6 to +10 min against plan, expected vs observed EWT, data coverage and result.
- **MVP-5, Quality indicators** (manager, disciplined lane, affects payment): P(board ≤ t) for t = 5, 10 and 15 min, EWT and coverage, by operator and time band, flagged "not payable" below 90 % coverage. The same query must always give the same result, and each value must show when it was computed and with which contract version.

Data owns these metrics (ADR-0003: the BE never computes headways or EWT). So data keeps a **history layer** in gold: append-only facts written in the cycle transaction, plus additive aggregates per 15-minute band. The BE only filters and sums.

**Design rules:**
- **15-minute bands** of simulated **local** time (`band` 0–95), the same bands as M2. Local time is America/Bogota, a fixed UTC−5 offset (`src/data/rules/timebands.py`). The simulated day starts at 22:00Z, which is 17:00 local, the evening peak. Named bands ("evening peak", "off-peak", "whole day") are rows in `config.report_bands`, so changing them never needs a recompute.
- **Additive counts, not ratios.** Band rows store counts and sums, and the query divides. Summing several bands or days then stays exact.
- **Determinism.** A band row is rebuilt from bronze up to `max_bronze_id` (DELETE + INSERT for that band) and carries `rules_version`, `contract_version` and `computed_at`. Same bronze and rules give the same row.

### H1. `gold.hist_bus_state`: one row per bus per snapshot
| Column | Type | Note |
|---|---|---|
| `snapshot_id` | UUID | FK `gold.snapshots`; PK with `bus_id` |
| `as_of_ts` | TIMESTAMPTZ | Copied from the snapshot for range scans; index `(bus_id, as_of_ts)` |
| `bus_id` | TEXT | |
| `distance_along_m` | NUMERIC | |
| `headway_ahead_s` | NUMERIC NULL | NULL for the leader |
| `headway_planned_s` | NUMERIC | |
| `bus_state` | TEXT | Same enum as `corridor_now` |
| `data_quality` | TEXT | `live` / `estimated` |
| `rules_version` | TEXT | |

It is the same content as `corridor_now.buses`, written as rows in the same transaction.

**Q10. Headway around an applied recommendation (MVP-4 chart)**
```sql
SELECT as_of_ts, bus_id, headway_ahead_s, headway_planned_s, data_quality
FROM gold.hist_bus_state
WHERE bus_id = ANY(%(bus_ids)s)
  AND as_of_ts BETWEEN %(t0)s - interval '6 minutes' AND %(t0)s + interval '10 minutes'
ORDER BY as_of_ts, bus_id;
```
`t0` is when the instruction was executed (Q6 `ts_by_status`) or decided. Rows with `data_quality = 'estimated'` are drawn as gaps, never as zero.

### H2. `gold.decision_log`: one row per recommendation
| Column | Type | Note |
|---|---|---|
| `rec_id` | UUID PK | |
| `case` | TEXT | C1 / C2 / C5 / D1 |
| `action` | JSONB | The recommendation's `action` object |
| `proposed_ts` | TIMESTAMPTZ | `event_ts` of the `recommendation` command event (§4.5) |
| `expires_ts` | TIMESTAMPTZ | |
| `outcome` | TEXT | `proposed` / `applied` / `discarded` / `expired` (derived by data, §4.5) |
| `decided_ts` | TIMESTAMPTZ NULL | |
| `user_id` | TEXT NULL | From the `decision` |
| `reason` | TEXT NULL | Discard reason (§4.6) |
| `instruction_status` | TEXT NULL | From Q6: `executed` / `not_executed` |
| `effect_result` | TEXT NULL | From `gold.recommendation_effect.doc.result` |
| `rules_version`, `max_bronze_id` | | Lineage |

It is rebuilt each cycle from bronze (`recommendation`, `decision`), `gold.instruction_status` and `gold.recommendation_effect`.

**Q11. Shift log (MVP-4 list)**
```sql
SELECT rec_id, "case", action, proposed_ts, outcome, decided_ts, user_id, reason,
       instruction_status, effect_result
FROM gold.decision_log
WHERE proposed_ts >= %(shift_start)s AND proposed_ts < %(shift_end)s
ORDER BY proposed_ts DESC;
```

### H3. `gold.recommendation_effect`: one row per applied recommendation `[004]`
This is already designed in story 004, phase 3: `doc` is exactly `recommendation_effect.schema.json`.
```sql
SELECT doc FROM gold.recommendation_effect WHERE rec_id = %(rec_id)s;
```
**"Worked" rule (decided by the data owner, 2026-11-21; replaces ADR-0003 gate decision 6):**

| Result | Rule |
|---|---|
| `worked` | observed saving ≥ **50 %** of `ewt_expected_s` |
| `partial` | 0 < observed saving < 50 % of expected, **or** the headway got closer to plan while EWT did not improve |
| `did_not_work` | observed saving ≤ 0 and the headway did not improve |
| `no_data` | data coverage in the window < **90 %**, or `ewt_expected_s` is null (D1) |

Where:
- **observed saving** = EWT before − EWT after;
- **EWT before** = from the last snapshot at or before the decision;
- **EWT after** = from the first snapshot at or after the decision + `horizon_s`.

**Why it changed:** the old rule (`ewt_expected_s − ewt_observed_s ≥ 30`) subtracted an absolute EWT from a promised saving. It could say "worked" even when EWT got worse. Story 004 had flagged this as a semantic mismatch for the data owner. The new rule compares saving with saving, which is what the MVP-4 screen shows ("expected / observed").

**Contract impact:** `recommendation_effect.schema.json` 1.0.0 → **1.1.0**:
- `ewt_observed_s` is redefined as the observed saving;
- new optional fields `ewt_before_s` and `coverage_ratio`;
- the `result` description is updated;
- the `c1_bunching` fixture is updated.

This needs an ADR (an amendment of gate decision 6). The 50 % and 90 % thresholds live in `config.effect_settings`, as a hypothesis to validate with the dispatcher.

**Window:** evaluation uses each recommendation's `horizon_s`. The engine sets `horizon_s = 600` (10 min), as in the mock-up, and the seed is updated to match. The MVP-4 chart always shows −6 to +10 min (Q10).

### H4. `gold.report_quality_band`: one row per day × band × operator
| Column | Type | Note |
|---|---|---|
| `day` | DATE | Simulated local date (UTC−5) |
| `band` | SMALLINT | 0–95 (15-minute band) |
| `band_start_ts` | TIMESTAMPTZ | PK with `operator` |
| `operator` | TEXT | From `bus_position.operator` (today only `OP-01`) |
| `corridor_id` | TEXT | |
| `n_snapshots_expected`, `n_snapshots` | INT | Missed snapshots lower the coverage |
| `n_headways`, `sum_headway_s`, `sum_headway_sq_s` | INT, NUMERIC, NUMERIC | Observed headways |
| `sum_planned_s`, `sum_planned_sq_s` | NUMERIC | Planned headways for the same intervals |
| `n_riders` | INT | `rider_arrival` events in the band |
| `n_board_le_5`, `n_board_le_10`, `n_board_le_15` | INT | Riders whose wait until the next departure from their stop is ≤ t min (simple method, below) |
| `n_events`, `n_rejected` | INT | Accepted and rejected events, duplicates excluded |
| `n_bus_snapshots`, `n_bus_estimated` | INT | Bus × snapshot rows, and how many of them were `estimated` |
| `rules_version`, `contract_version`, `computed_at`, `max_bronze_id` | | Lineage. `computed_at` is wall time |

**Formulas (in the query, not stored):**
- mean wait = `sum_headway_sq_s / (2 × sum_headway_s)`;
- scheduled wait = `sum_planned_sq_s / (2 × sum_planned_s)`;
- **EWT** = mean wait − scheduled wait (can be negative);
- **P(board ≤ t)** = `n_board_le_t / n_riders`;
- **% rejected** = `n_rejected / (n_events + n_rejected)`;
- **% estimated** = `n_bus_estimated / n_bus_snapshots`;
- **coverage** = 1 − % rejected − % estimated;
- **payable** = coverage ≥ `config.report_settings.payable_coverage` (0.90; the threshold is still to be agreed with the client).

**P(board ≤ t), simple method (MVP):** each rider's wait is the time from its `rider_arrival` to the next departure of any bus from that stop (`silver.stop_visits`). It ignores full buses. The full method, a FIFO queue per stop that uses each departure's `boarded` and `rejected` ("full bus included", as the mock-up says), is an improvement.

**Q12. Quality indicators (MVP-5)**
```sql
SELECT r.operator,
       sum(r.n_board_le_10)::numeric / nullif(sum(r.n_riders), 0)             AS p_board_le_t,  -- pick column by t
       sum(r.sum_headway_sq_s) / nullif(2 * sum(r.sum_headway_s), 0)
     - sum(r.sum_planned_sq_s) / nullif(2 * sum(r.sum_planned_s), 0)          AS ewt_s,
       sum(r.n_rejected)::numeric / nullif(sum(r.n_events + r.n_rejected), 0) AS pct_rejected,
       sum(r.n_bus_estimated)::numeric / nullif(sum(r.n_bus_snapshots), 0)    AS pct_estimated,
       max(r.computed_at) AS computed_at, max(r.contract_version) AS contract_version,
       max(r.rules_version) AS rules_version
FROM gold.report_quality_band r
JOIN config.report_bands b ON r.band BETWEEN b.start_band AND b.end_band
WHERE b.name = %(band_name)s AND r.corridor_id = %(corridor_id)s
  AND r.day BETWEEN %(day_from)s AND %(day_to)s
GROUP BY r.operator
ORDER BY r.operator;
```
The BE computes coverage and "payable" from `pct_rejected` and `pct_estimated`. If the screen shows P85/P95 of EWT, they come from the EWT of each band row in the range (`percentile_cont` over bands), not from a stored value.

**`config.report_bands` (initial rows):**

| name | start_band | end_band | simulated local time |
|---|---|---|---|
| `evening_peak` | 68 | 75 | 17:00–19:00 |
| `off_peak` | 40 | 63 | 10:00–16:00 |
| `whole_day` | 0 | 95 | 00:00–24:00 |

### MVP vs improvements

| MVP (workshop) | Improvements (later, or as an in-class simulation) |
|---|---|
| H1 `hist_bus_state` · H4 with EWT, coverage and simple P(board ≤ t) | Full P(board ≤ t) with full buses · M-4 data quality per operator (p95 latency, rejections by cause, gaps per bus) · M-5 alerts inbox · M-6 plan of the day (uses the existing M2 baseline) |
| H2 `decision_log` and H3 effect: designed now, built after story 004 and the recommendation door | |

---

## 4. Messages the BE writes (command door)

### 4.1 Common rules (all three types)

| Field | Rule |
|---|---|
| table | `bronze.events`. **INSERT directly.** Command events do **not** go through the ingestion service, which only accepts the six turn-1 types |
| `source` | always `'backend'` |
| `event_id` | new UUID v4 per action. The BE keeps it for idempotency |
| `schema_version` | `'1.0.0'` |
| `event_type` | `decision` / `incident_report` / `confirmation` |
| `event_ts` | **simulated time**: `as_of_ts` of the latest snapshot (Q0) at the moment of the click. See §1.4 |
| `arrival_ts` | `clock_timestamp()` (wall time of the insert) |
| `payload` | exactly the `payload` of `contracts/read/command_event.schema.json` for that type |
| validation | validate the full message against `command_event.schema.json` **before** inserting |
| idempotency | `ON CONFLICT (source, event_id) DO NOTHING`. A retry with the same `event_id` inserts nothing. This was verified |
| immutability | never UPDATE or DELETE. A correction is a new event |

Effect timing: the next cycle (≤ 5 s) includes the new row. The BE sees the effect through Q5, Q6 and the usual `gold_snapshot` notification.

### 4.2 `decision`: the dispatcher approves or discards a recommendation (Principle IV)
```sql
INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload)
VALUES ('backend', %(event_id)s, '1.0.0', 'decision', %(sim_now)s, clock_timestamp(),
        jsonb_build_object('rec_id', %(rec_id)s, 'action', %(action)s,      -- 'apply' | 'discard'
                           'user_id', %(user_id)s, 'ts', %(sim_now)s))
ON CONFLICT (source, event_id) DO NOTHING
RETURNING id;
```
**What data does with it:**
- With `apply` on a `hold` recommendation, the simulator holds the bus (when `SIM_HOLDS=on`), and data publishes the outcome in Q6.
- With `discard`, nothing changes on the road.
- For the hold order, data uses the **bronze order** of the decision, not its `event_ts`.
- Rules (`specs/004-scenario-injectors/contracts/hold-loop.md`): at most 90 s; the first order per bus and stop wins; a breakdown cancels the order.

### 4.3 `incident_report`: the dispatcher reports an incident
```sql
INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload)
VALUES ('backend', %(event_id)s, '1.0.0', 'incident_report', %(sim_now)s, clock_timestamp(),
        jsonb_build_object('incident_type', %(incident_type)s,   -- bus_breakdown | stop_closed | other
                           'target_id', %(target_id)s,           -- bus_id or stop_id
                           'duration_min', %(duration_min)s,     -- number, or NULL if unknown
                           'reported_by', 'dispatcher'))
ON CONFLICT (source, event_id) DO NOTHING
RETURNING id;
```
**What data does with it:** creates the incident with `inc_id = event_id`, active from `event_ts` for `duration_min`. `NULL` means open-ended (`until` stays null). The incident appears in Q5, in `decision_inputs.active_incidents`, and as `broken_down` for a bus. This was verified end to end.

### 4.4 `confirmation`: driver instruction status
```sql
INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload)
VALUES ('backend', %(event_id)s, '1.0.0', 'confirmation', %(sim_now)s, clock_timestamp(),
        jsonb_build_object('inst_id', %(inst_id)s,
                           'status', %(status)s,   -- sent | received | no_confirmation | radio | executed | not_executed
                           'ts', %(sim_now)s))
ON CONFLICT (source, event_id) DO NOTHING;
```
**What data does with it:** stores it for audit only. **Data does not read `confirmation` in turn 1.** `executed` / `not_executed` come from observed behaviour (Q6), not from this message. The "I told the driver by radio" mark of MVP-3 fits here as `status = 'radio'`, with no contract change.

### 4.5 `recommendation`: the BE engine hands a recommendation to data `[proposed]`

**Today:** the BE has no door for this, so the demo recommendations are seeded (Q7). This door replaces the seed.

**Proposal (option A, agreed with the data owner, 2026-11-21; to be accepted by the BE owner):**
- **Same command door, new type.** `event_type = 'recommendation'` in `command_event.schema.json`. Adding a value to the enum is non-breaking: **1.0.0 → 1.1.0**, which needs an ADR (it can be the same ADR as the freshness rule).
- **The payload is the whole `recommendation.schema.json` object** (v1.0.0, unchanged), with `status = 'proposed'`.
- `lineage.snapshot_id` must be the `decision_inputs` snapshot the engine used, so every recommendation can be explained.

```sql
INSERT INTO bronze.events (source, event_id, schema_version, event_type, event_ts, arrival_ts, payload)
VALUES ('backend', %(event_id)s, '1.1.0', 'recommendation', %(sim_now)s, clock_timestamp(),
        %(recommendation_doc)s::jsonb)   -- a valid recommendation.schema.json object, status 'proposed'
ON CONFLICT (source, event_id) DO NOTHING
RETURNING id;
```

**What data does with it:** it publishes `gold.recommendation`, one row per `rec_id`, rebuilt each cycle. `doc` is the recommendation with **`status` derived by data from the facts**:

| Derived status | When |
|---|---|
| `proposed` | Received, no decision yet, `as_of_ts` ≤ `expires_ts` |
| `applied` / `discarded` | A `decision` with that `rec_id` and `action` = `apply` / `discard` (the first one by bronze order wins) |
| `expired` | `as_of_ts` > `expires_ts` with no decision |

The BE never writes a status. This keeps Principle IV checkable: nothing reaches `applied` without a dispatcher `decision`.

```sql
-- Q13. Active recommendations for the console (MVP-3)
SELECT doc FROM gold.recommendation
WHERE doc->>'status' = 'proposed'
ORDER BY (doc->>'rank')::int;
```

The seeds then become ordinary `recommendation` events, so the demo follows the same path as the real engine. The simulator and `hold_orders.sql` read the hold from bronze instead of from the seed file.

### 4.6 Discard reason `[proposed]`

MVP-3 requires a reason when the dispatcher discards, but the `decision` payload (`rec_id`, `action`, `user_id`, `ts`) has no field for it. **Proposal:** add an optional `reason` (string, 1–200 characters) in the same 1.1.0 bump. It is required by the BE when `action = 'discard'`, and data copies it to `gold.decision_log.reason` (H2).

---

## 5. Guarantees and limits

**Data guarantees:**
- Every `doc` validates against its schema v1.0.0.
- Same bronze, same reference time and same rules version give the same gold.
- Reads never block the cycle (MVCC).
- The simulator's hidden scenario truth is never reachable from gold.
- A breaking change to any read object needs a new major version plus an ADR (ADR-0003 versioning rule). Additive optional fields are a minor bump.

**The BE must not:**
- write to `silver`, `gold`, `config` or `ops`;
- compute headways, states or EWT from bronze;
- read `silver.*`;
- depend on non-`doc` columns other than those named in Q0, Q4, Q6 and Q8;
- use wall time as `event_ts`;
- propose or apply a recommendation when `age_s > 15` (§2.1);
- use `as_of_ts` to judge staleness.

---

## 6. Open items

| # | Item | Owner | Status |
|---|---|---|---|
| 1 | **Recommendation door** (§4.5): option A, a new `recommendation` command event plus `gold.recommendation` with derived status. Replaces the seed (Q7) | BE accepts; data builds | Proposed. Data effort ~4–6 h, after 004 |
| 2 | `gold.recommendation_effect` (US-11, H3) | data | `[004]` phase 3, not built |
| 3 | Public views `gold.v_source_status`, `v_corridor_now`, `v_decision_inputs` ("latest") + role `backend_reader` (SELECT on gold views and `config`, INSERT on `bronze.events`, LISTEN), so the BE does not depend on table layout | data | `[proposed]`, ~1–1.5 h, after 004 |
| 4 | Story 004 merged to `main` (Q5, Q6, Q7 depend on it) | data | In progress |
| 5 | Stop names for the console, if needed | BE/front → data | To confirm |
| 6 | Should data consume `confirmation` (for example, `no_confirmation` → alert)? | BE + data | Turn 2 candidate |
| 7 | **History layer** (§3B): H1 `hist_bus_state` + H4 `report_quality_band` (EWT, coverage, simple P(board ≤ t)) for the workshop; H2 `decision_log` after the door | data | Proposed. H1 + H4 ~4–5 h; all of §3B ~7–9 h |
| 8 | **Discard reason** (§4.6): optional `reason` in `decision`, in the same 1.1.0 bump | BE + data | Proposed |
| 9 | **"Worked" rule:** option B decided (H3). Next steps: ADR amending ADR-0003 gate decision 6; `recommendation_effect.schema.json` 1.1.0; update the 004 spec, plan and tasks of phase 3 (FR-025, SC-009, T047) and the `c1_bunching` fixture **before** phase 3 is built; seed `horizon_s = 600` | data (Kiro builds, Claude verifies) | **Decided 2026-11-21**; amendment pending |
| 10 | **Operators:** MVP-5 shows several operators, but every bus today reports `operator = 'OP-01'`. The table will show one row unless the simulator assigns more operators | team | To confirm |
| 11 | **Payable threshold** (90 % coverage) and the payment formula: still to be agreed with the client (MVP-5 note) | team / client | Open; stored in `config.report_settings` |
| 12 | **Expiry window:** MVP-3 says a recommendation expires after 2 min. The engine sets `expires_ts` accordingly; the seed uses its own value | BE | To align |

---

## 7. Verification (2026-11-21, by Claude; nothing pushed)

On a throwaway database (`contract_check`) built from `src/data/db/init/001…007` (working tree of `feature/004-scenario-injectors`, including uncommitted changes):
1. Ran the simulator: seed 42, 1200 s → ingestion: 1256 events accepted, 0 rejected.
2. Inserted 3 BE command events. All 3 validate against `command_event.schema.json`. A retry with the same `event_id` inserted 0 rows.
3. Ran `python -m src.data.pipeline.compute --as-of 2026-11-24T22:19:55Z`.
4. Q0–Q9 all run. The `doc` of `source_status`, `corridor_now`, `decision_inputs` and `incident` **validate** against their schemas.
5. The incident reported in simulated time is active in Q5 and listed in `decision_inputs.active_incidents`. The incident reported in wall time is never active (§1.4).
6. `gold.instruction_status` stays empty while the hold is pending, as documented.
7. The freshness query (Q0 with `age_s`) ran on the developer's local stack, whose simulator had finished its day hours earlier. It returned `age_s = 28404` (about 7.9 h) while `as_of_ts` still read `2026-11-24 22:59:55`. Under §2.1 the BE would block every recommendation, and the `refresh` service was already `unhealthy`. This is exactly the "decide on yesterday's data" case, and it is caught.
8. **Not verified:** Q10–Q13 and every `[proposed]` object (§3B, §4.5, §4.6). They are designs and the objects do not exist yet. They get verified when the stories that build them run.
