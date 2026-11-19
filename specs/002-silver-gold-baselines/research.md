# Research — Silver and Gold Layers with M1/M2 Baselines

**Feature**: 002-silver-gold-baselines | **Turn**: 1 (active) | **Date**: 2026-11-18 (gate decisions
applied 2026-11-18)

Each entry has a **Decision**, a **Rationale** and the **Alternatives considered**. The data owner
answered every item that was OPEN at the human gate of 2026-11-18. Those entries (R3, R8, R11, R12,
R13) are marked **DECIDED** and state the answer first. R14 is a new finding from the same gate,
also **DECIDED**. No OPEN item remains, so `/speckit.tasks` needs no confirmation task for them. It
does need the implementation tasks that the decisions create (see the plan, Phase 0 and Readiness).

Numbering: the former R14 (refresh service in compose) is now **R16**, because R14 is the
base-case headway finding.

Inputs read: `spec.md` (with Clarifications), ADR-0001/0002/0003, `contracts/read/` and its fixtures,
`data/reference/`, the 001 plan, research, data model and verification, and the 001 code
(`src/pulsoflota/`, `src/ingestion/`, `src/simulator/`, `src/api/main.py`, `db/init/`,
`docker-compose.yml`, `Dockerfile`, `.dockerignore`, `.env.example`, `pyproject.toml`, `Makefile`,
`tests/`).

---

## Facts from story 001 that shape this design

| Fact | Where | Consequence here |
|---|---|---|
| `bronze.events` has `id BIGSERIAL`, `UNIQUE(source,event_id)`, `event_ts`, `arrival_ts`, `payload JSONB` | `db/init/002_bronze.sql` | `max_bronze_id` = `max(id)` read by the cycle; all payload fields are read with `payload->>'…'`. |
| `silver` and `gold` schemas exist and are empty | `db/init/001_schemas.sql` | New DDL goes in new init scripts; nothing in 001 is changed. |
| Init scripts run only on a fresh volume | postgres image behaviour | A run with the new tables needs `docker compose down -v` (verification of 001 already does this). |
| The simulator's `event_ts` is synthetic: day 2026-11-24 starting 17:00 local, and `SIM_PACE_S=1` runs 5 simulated seconds per wall second | `src/simulator/engine.py`, `.env.example` | "Reference time = current UTC time" (FR-004) does not line up with simulator events in a live run. Resolved by R3 (`REFRESH_CLOCK`). |
| After P-900 the simulator dwells, waits a fixed 300 s layover (`LAYOVER_S`) with the same `trip_id`, then starts trip *n+1* at P-883 | `engine.py` | "Reached P-900" = a `stop_arrival` at the terminus stop for the bus's current trip (R7). The fixed layover is replaced by R14. |
| Initial spacing between in-service buses is 300 s (`START_HEADWAY_S`), the planned headway is 600 s, and only direction 1 is simulated | `src/simulator/model.py` | With the fixed 300 s layover a 5-bus cycle is about 28 min, not 5 × 600 s, so real headways at P-883/P-891/P-899 are about 20–560 s (mostly 300–400 s). This is a **defect for this story**, not expected behaviour: see R14 (DECIDED, fixed in Phase 0). |
| The tests share the compose database with the running ingestion container | `tests/conftest.py`, 001 tests use fresh UUIDs | Silver/gold derive from *all* bronze, so tests need their own database (R10). |
| No JSON Schema validator is installed | `pyproject.toml`, `uv.lock` | SC-001 needs one (R9). |
| A 1-hour seeded run produced 3,986 events before the R14 fix | 001 `verification.md` | Same order of magnitude after the fix (the start spacing changes, not the demand). A full silver recompute per cycle reads a few thousand rows per simulated hour (R2). Recount after Phase 0. |
| `tests` compose service mounts `tests/`, `contracts/`, `data/`, but not `db/` | `docker-compose.yml`, `Dockerfile` copies only `src/` and `data/reference/` | The test DB fixture needs `./db:/app/db:ro` mounted (R10). |

---

## R1 — Where rules live and what is SQL versus Python

**Decision**:

- `src/rules/sql/*.sql`: plain, parameterized SQL that derives silver from bronze and computes the
  M1/M2 medians and fallbacks. This covers latest position, last report, the Estimated flag,
  stop visits, segment traversals with their exclusion flags, and incidents.
- `src/rules/*.py`: pure Python functions for the per-snapshot rules applied to at most 7 buses:
  time headway by interpolation (FR-020), `bus_state` with the FR-011 suppression (FR-022), summary
  counts (FR-023), the service metric (FR-024), local time bands and the next 15-minute window
  (FR-026, FR-030, FR-032), and the snapshot id (R5).
- `src/rules/__init__.py` holds the single `RULES_VERSION` string (FR-006). Initial value `"1.0.0"`;
  any change to a rule in `src/rules/` bumps it.
- `src/pipeline/` holds orchestration only (load reference tables, run the cycle transaction, build
  and store the gold objects). It contains no rule thresholds.

**Rationale**: the user fixed "plain SQL for derivations". Set-based derivations over bronze are
natural in SQL. The per-bus classification is a handful of rows per snapshot and holds the rules
that protect the metric. As Python it gets pytest-cov line coverage near 100 % (SC-011) and unit
tests without a database. Putting both under `rules/` matches the data profile ("quality rules =
deterministic code in `rules/`") and brings them under the data owner's CODEOWNERS review.

**Alternatives**: everything in SQL. Headway interpolation and FR-011 neighbour logic need window
functions and lateral joins, and pytest-cov cannot measure SQL coverage. Everything in Python is
also rejected: it contradicts the "plain SQL for derivations" constraint and moves bronze rows into
the process for no benefit.

---

## R2 — Full recompute of silver each cycle

**Decision**: each cycle deletes and rebuilds every silver table from bronze inside the cycle
transaction. It uses `DELETE`, not `TRUNCATE`, so concurrent readers keep seeing the previous
committed version (MVCC) instead of blocking on an `ACCESS EXCLUSIVE` lock. M1/M2 tables in gold are
replaced the same way. Snapshot tables in gold are append-only.

**Rationale**: FR-001 and SC-005 require "rebuild from scratch = cycle-by-cycle". When every cycle
*is* a rebuild, the two are equal by construction, and the idempotency tests become simple. The
turn-1 volume is small: about 4,000 events per simulated hour (3,986 in the 001 run before R14). Incremental maintenance
would add state that can drift. The real cycle time is measured in Phase 4. If a cycle exceeds 5 s,
FR-039 skips ticks, and incremental silver is recorded as evolution (turn 3, 1,000 events/s).

**Alternatives**: incremental silver keyed by `max_bronze_id`, rejected for now (more code, drift
risk, unneeded at this volume). Materialized views are rejected by ADR-0001 (option 2).

---

## R3 — Reference time in live operation (DECIDED)

**Problem**: FR-004 says that in live operation the reference time is the current UTC time. The 001
simulator stamps synthetic event times (2026-11-24 from 17:00 local, 5× faster than wall time with
`SIM_PACE_S=1`). In a live compose run with `as_of_ts = now()`, either every event is in the future
(nothing qualifies, so the status is `no_data`) or every bus is older than 120 s (everything is
`estimated`). Fixed reference times in tests and replays are not affected.

**Decision (data owner, 2026-11-18)**: the refresh loop takes a clock selector
`REFRESH_CLOCK=wall|data`.

- `data`: `as_of_ts = max(event_ts)` of the non-backend bus reports visible to the cycle (`id <= M`,
  R4). It is the **default for the demo with the simulator**: `.env.example` and
  `docker-compose.yml` set `REFRESH_CLOCK=data`.
- `wall`: `as_of_ts` = current UTC time. It is for real telemetry. FR-004's "current UTC time"
  applies to this mode. The code default, when the variable is unset, stays `wall` so that FR-004
  holds unless someone opts out.
- Tests and replays keep the fixed reference time: the cycle function always takes `as_of_ts` as an
  argument, and the `compute` CLI is not affected by `REFRESH_CLOCK`.
- `REFRESH_CLOCK` is added to `.env.example` (no secret), next to `REFRESH_INTERVAL_S`.

**Consequences, stated so they are not a surprise**:

- In `data` mode the clock stops when all buses go silent, so the "all buses silent" case cannot turn
  Estimated in a live demo. This is accepted: the Estimated rule is covered by tests with fixed
  reference times (SC-003), and the D1 demo silences one bus, not all.
- **Declared limitation (R3/R5, 2026-11-18)**: in `REFRESH_CLOCK=data` mode, if the whole feed
  stops, `as_of_ts` freezes, the snapshot key `(as_of_ts, rules_version, max_bronze_id)` repeats
  (R5 inserts nothing and sends no `NOTIFY`), and buses do not turn Estimated. Single-bus outages
  (D1) work because the other buses advance the clock. `wall` mode detects a whole-feed outage.
  No design change.
- If bronze has no bus report yet, `data` mode has no maximum to read. The cycle then falls back to
  the wall clock for that tick, which yields `no_data` as FR-018 requires. Planning assumption, to
  be pinned by a unit test.
- SC-009 (cadence) measures wall-clock intervals between notifications, so it does not depend on
  the clock mode or on `SIM_PACE_S`.

**Rationale**: the demo works with the 001 simulator unchanged in its time stamps, and real telemetry
keeps the literal FR-004 behaviour. The selector is isolated in Phase 4.

**Alternatives**: wall clock only (the demo breaks); a hybrid data clock that adds the wall time
elapsed since the last report (keeps moving in a total outage, but is exact only at
`SIM_PACE_S=5` and adds a second clock to reason about); changing the simulator to stamp wall-clock
times (touches 001 time stamps, outside this story).

---

## R4 — Which bronze rows a cycle reads (consistency and lineage)

**Decision**: the cycle runs in one `REPEATABLE READ` transaction. It first reads
`M = max(id) FROM bronze.events` (0 if empty) and then only uses bronze rows with `id <= M` and
`event_ts <= as_of_ts`. `M` becomes `max_bronze_id` on every gold row of the cycle (FR-017).
Duplicates never reach `bronze.events`, so re-ingesting a batch does not move `M` (SC-004).

**Rationale**: `REPEATABLE READ` gives every query in the cycle the same view of bronze, so silver,
gold and lineage agree even while ingestion keeps inserting. Filtering `event_ts <= as_of_ts` makes
replays at an earlier reference time meaningful. The single ingestion process inserts in autocommit
order, so ids and commit order match. The `id <= M` filter makes the lineage explicit anyway.

**Alternatives**: `READ COMMITTED` with no filter, rejected because different queries in one cycle
could see different bronze contents. `SERIALIZABLE` is unnecessary with a single writer to silver and
gold (R6).

---

## R5 — Snapshot identity and idempotent recompute

**Decision**: `snapshot_id` is a deterministic UUID with version-4 bits, derived from
`sha256(as_of_ts ISO-8601 UTC | rules_version | max_bronze_id)`. This uses the same technique as the
simulator's seeded event ids (001 R13: `uuid.UUID(int=…, version=4)`). `gold.snapshots.snapshot_id`
is the primary key. A recompute with the same inputs hits `ON CONFLICT DO NOTHING`: no new rows, no
notification. The data owner can veto this choice in favour of option 2 below.

**Rationale**: FR-005, SC-004 and SC-005 require identical gold contents for identical inputs. A
random `uuid4` would differ on every recompute, so a rebuilt gold could never equal the original.
The value matches `format: uuid` in the read schemas, and the version/variant bits are correct.

**Alternatives**: (2) random `uuid4` plus a unique key `(as_of_ts, rules_version, max_bronze_id)`.
This is idempotent too, but a rebuild from scratch gets new ids, so SC-005 would have to compare
"everything except `snapshot_id`". (3) `uuid5`: it is not version 4, while ADR-0003 describes
`snapshot_id` as UUID v4.

---

## R6 — Atomic publish, notification, no overlap

**Decision**:

- One transaction per cycle: rebuild silver → replace M1/M2 → insert the snapshot row and its four
  gold rows → `SELECT pg_notify('gold_snapshot', payload)` → `COMMIT`. PostgreSQL delivers `NOTIFY`
  only at commit, and never on rollback. So a reader can never receive a notification for a
  snapshot that is not yet readable (FR-037, FR-038), and a failed cycle never notifies (FR-040).
  The notify call is skipped when the snapshot insert was a no-op (R5).
- `pg_try_advisory_xact_lock(<constant>)` at the start of the cycle: if another process (for example
  a manual `compute` run) holds the lock, the cycle is skipped and logged.
- The loop is single-threaded. After each cycle it sleeps until the next 5 s boundary that is still
  in the future, so a late tick is skipped and never queued (FR-039).
- Channel `gold_snapshot`. Payload `{"snapshot_id": "<uuid>"}`, contract in
  `contracts/gold_snapshot_notify.schema.json` (this feature directory).

**Rationale**: transactional `NOTIFY` gives the "readable before notified" guarantee for free and
needs no broker (ADR-0001, ADR-0003 push door). The advisory lock costs one call and prevents two
cycles from interleaving their `DELETE`/`INSERT` on silver.

**Alternatives**: a "published" flag column flipped at the end, rejected because transaction
visibility already does this. A `NOTIFY` sent after commit from a separate statement is rejected
because a crash between commit and notify loses the event, and a notify before commit breaks
FR-038.

---

## R7 — Silver semantics that the spec leaves to the design

**Decision** (each item is covered by a test):

- **Bus report** (FR-007): `event_type IN ('bus_position','stop_arrival','stop_departure')` and
  `source <> 'backend'`.
- **Current trip**: the `trip_id` of the bus's latest bus report, ordered by `(event_ts, id)`.
- **On the corridor / in service**: the current trip has no `stop_arrival` at the terminus stop (the
  last row of `stops.csv`, P-900). A bus on the corridor appears in `corridor_now`, and when it is
  Estimated it appears in `sources_down`. A bus that never reported has no row.
- **Operational status** (FR-009): `broken_down` if a `bus_breakdown` incident targets it at
  `as_of_ts`. Otherwise `in_service` if it is on the corridor. Otherwise `reserve` if it is in the
  reserve roster. Otherwise it is off the corridor (between trips or finished).
- **prev/next stop** (FR-009): `prev` = last stop with `distance_along_m <= d`. `next` = first stop
  with `distance_along_m > d`. A bus dwelling exactly at P-891 (3240.5 m) gives prev P-891 and next
  P-892, which matches the `c5_breakdown` fixture.
- **Stop visit counts** (FR-012): `boarded`, `alighted`, `rejected` come from the `stop_departure`
  payload. A visit is recorded once both arrival and departure exist. The simulator writes the same
  counts in both events.
- **Incident activity** (FR-015): active on the half-open interval
  `[event_ts, event_ts + duration_min)`. `duration_min = 0` is never active. Incidents from any
  source count, including `backend`, because dispatcher incident reports arrive as backend command
  events (ADR-0003). Only `incident_type = 'bus_breakdown'` with `target_id` = a bus id makes that
  bus `broken_down`. `active_incidents` lists every active incident of any type.
- **Traversal flags** (FR-014): `travelled_while_estimated` if any two consecutive bus reports of
  that bus inside `[t_departure(i), t_arrival(i+1)]` (both ends included) are more than 120 s apart.
  `broken_down` if a `bus_breakdown` incident for that bus overlaps the interval.
- **Local time** (FR-026): SQL and Python both use the fixed UTC−5 offset already used by the
  simulator (`LOCAL_TZ`); SQL: `extract(hour from (t AT TIME ZONE 'UTC' - interval '5 hours'))`, not
  `AT TIME ZONE 'America/Bogota'` (T032). Colombia has no daylight saving, so this is exact. The
  slim image may lack system tzdata, so Python does not use `zoneinfo`.

**Rationale**: these choices follow the spec's wording and edge cases and the 001 simulator's real
event sequence, and they keep each rule testable in isolation.

---

## R8 — Headway rules that need a decision

**Decision**:

- Pass time (FR-020): from the bus ahead's `bus_position` history on its *current trip*, find the
  first sample with `distance_along_m >= d` (d = follower's current distance). Interpolate linearly
  between that sample and the previous one. If the first sample of the trip is already `>= d`, use
  its time. `headway_ahead_s = follower_position_ts − pass_time`.
- Equal distances: `headway_ahead_s = 0`, by the explicit spec edge case. It overrides the
  interpolation, which would give a positive value when both buses dwell at the same stop.
- **Negative result (DECIDED: clamp to 0)**: a stale follower can get a negative difference, for
  example when it reported 100 s ago and the bus ahead overtook it after that. The schema requires
  `minimum: 0`. The data owner chose to **clamp to 0** (2026-11-18). The follower is then `bunched`
  unless FR-011 forces `regular`. Two buses that crossed are effectively bunched, and when the cause
  is an Estimated bus FR-011 already forces `regular`.
  - Rejected: `null` (the schema allows it only for the leader and broken-down buses, so it changes
    the meaning) and failing the cycle (one stale bus would stop the snapshot).
- Service metric (FR-024): uses the non-null headways of all operational buses, including those
  forced to `regular` by FR-011. The spec's formula names no exclusion. This is noted for the data
  owner because an outage can therefore move EWT, though never a state or a count.

---

## R9 — JSON Schema validation of produced objects (new dev dependency)

**Decision**: add `jsonschema` and `rfc3339-validator` to the **dev** extra only, locked through
`uv.lock` (exact versions are chosen at lock time). Tests validate every produced `source_status`,
`corridor_now` and `decision_inputs`, and the existing fixtures, with `Draft202012Validator` and a
`FormatChecker`. `uuid` is checked by the standard library; `date-time` needs `rfc3339-validator`.
At runtime, the pipeline builds each object through Pydantic V2 models generated from the three
read schemas (`make generate-read`) and stores `model_dump(mode="json")`.

**Rationale**: SC-001 explicitly requires validation against the JSON Schemas (draft 2020-12). 001
verification found that generated Pydantic models accepted numbers as strings, so they are not
proof of schema conformance on their own. A test-only validator keeps runtime dependencies
unchanged.

**Alternatives**: Pydantic only, rejected because it does not verify the schema itself (see the 001
defect). Running `jsonschema` at runtime on every cycle is rejected: it adds a runtime dependency
and gives no extra guarantee once the tests pass on the same builder.

---

## R10 — Test isolation from the live database

**Decision**: a pytest fixture creates a throwaway database per test module (`CREATE DATABASE …
TEMPLATE <session template>`) on the same server. The session template is built once by applying
`db/init/*.sql` in order and loading the reference tables. The fixture drops the database at
teardown. The `tests` compose service gets one extra read-only mount, `./db:/app/db:ro`. Crafted
bronze is inserted through the real boundary `src.ingestion.bronze.ingest`, so the boundary rules
are exercised too.

**Rationale**: the compose database receives live simulator events. Silver and gold derive from all
of bronze, and bronze rows cannot be deleted. A separate database per module gives an "empty
environment" (spec, Independent Test) without touching bronze. `POSTGRES_USER` in the official image
is a superuser, so `CREATE DATABASE` works.

**Alternatives**: parameterizing schema names, rejected because the SQL hard-codes `bronze.events`
and it would be invasive. Requiring the stack to be stopped and the volume reset is rejected as
fragile, and it would also stop the isolation tests.

---

## R11 — Location of static configuration and reference tables (DECIDED)

**Problem**: FR-034 asks for "small static configuration tables". The M1/M2 fallbacks and prev/next
stop lookups need the reference CSVs inside PostgreSQL. ADR-0001 lists the schemas `bronze`,
`silver`, `gold`, and it ruled out a fourth schema for rejections specifically. SC-005 drops and
rebuilds silver and gold, so configuration must survive that.

**Decision (data owner, 2026-11-18)**: use a **`config` schema**: static settings seeded by
`db/init/003_config.sql`, and reference tables loaded from `data/reference/*.csv` by
`src/pipeline/reference.py`. It keeps "drop silver and gold" safe, gives configuration a clear
owner, and keeps the derivation SQL readable.

**ADR change (exactly one line, nothing else in the ADR moves)**: an addendum to
`docs/adr/0001-data-layers-and-ingestion-semantics.md` listing `config` as a fourth schema, for
static configuration only. Suggested wording: *"Addendum 2026-11-18: a fourth schema, `config`,
holds static configuration and reference tables. It holds no derived data and no secrets."* The
file is outside this feature directory, so the plan carries it as a Phase 0 task. This feature does
not edit it.

**Alternatives**: `gold.cfg_*`/`ref_*` tables excluded from the rebuild by name (rejected: mixes
static data with derived data); no tables, parameters passed from Python (rejected: unreadable
SQL).

---

## R12 — M2 sample definition (DECIDED)

**Problem**: FR-030 says "one sample per band per day with data". The simulator runs for a bounded
window (one hour by default). If every past day counted for all 96 bands, bands outside the
simulated window would get false zero samples.

**Decision (data owner, 2026-11-18)**: a (local date, 15-minute band) pair counts as a sample **only
if the band has ended (`band_end <= as_of_ts`) and the simulator was running during it**. "Running"
is read from bronze: at least one non-backend `bus_position` event with `event_ts` inside the band.
The sample value is the count of `rider_arrival` events at the M2 stop (P-883) in that band, which
can be 0. Today's completed bands count, so an early snapshot of a day can already have samples.
The rule cannot invent zeros for bands the simulator never ran, and it is deterministic for a fixed
`as_of_ts`. With the 5-day minimum, M2 is on the reference fallback in the workshop either way.

**Alternatives**: only dates strictly before the local date of `as_of_ts`; every (date, band) of
every date that has any event (invents zeros).

---

## R13 — Medians and rounding

**Decision**:

- M1 median = `percentile_cont(0.5)` over eligible traversal times (the mean of the two middle
  values when the count is even). `forecast_travel_s` is a number, so no rounding.
- M1 reference = `length_m / (free_flow_kmh / 3.6) / congestion_factor(hour)`, unrounded. SC-006
  allows 0.1 s tolerance.
- **M2 rounding (DECIDED: round half away from zero)**, for both paths, so `arrivals_forecast` is
  an integer that follows one rule:
  - Reference = `round(633.92 × metro_line_a_shape(hour) / 4)`, read from `demand_volume.csv` and
    `demand_params.csv`.
  - Observed median of an even sample count: `percentile_cont` can give x.5, and that value is
    rounded the same way.
  - Implementation note: PostgreSQL's `round(numeric)` rounds half away from zero, but
    `round(double precision)` rounds half to even. The SQL must cast to `numeric` before rounding
    (`round(percentile_cont(0.5) WITHIN GROUP (...)::numeric)`). The independent test oracle uses
    `Decimal.quantize(ROUND_HALF_UP)` (values are never negative), not Python's banker's `round`,
    and a unit test pins an x.5 case on each path (for example samples {2, 3} → 3).
  - Rejected: `percentile_disc` (lower middle value) and ceiling.
- M1 hour band = local hour of the traversal's departure. The `decision_inputs` band = local hour
  of `as_of_ts`. M2 band index = `local_hour × 4 + local_minute div 15`. The `demand_15min` window
  is the first clock-aligned window with `window_start_ts >= as_of_ts`.

---

## R14 — Base-case headway of the 001 simulator (DECIDED)

**Finding (independent run, 3 simulated hours, seed 7)**: real headways at P-883, P-891 and P-899
were about 20–560 s, mostly 300–400 s, against the planned 600 s. **Cause**: the 001 simulator runs
direction 1 only, with `START_HEADWAY_S = 300` and a fixed 300 s `LAYOVER_S`. A 5-bus cycle is then
about 28 min instead of 5 × 600 s = 3,000 s. With the `h < 0.5 × planned` rule (FR-022) the base
case would show bunching with nothing injected. That breaks the "normal" scenario and makes the C1
(bunching) scenario of story 003 meaningless. It replaces the earlier note that called this
"expected simulator behaviour".

**Decision (data owner, 2026-11-18)**: fix the simulator in **this story's first phase
(Phase 0, foundations)**. The fix touches schedule generation only: no event type, field or contract
changes (FR-025 holds), and the ingestion boundary is not touched.

- **Start spacing**: buses start 600 s apart (the planned headway), not 300 s.
- **Terminal layover**: it stands in for the return leg, which is not simulated (direction 2 stays
  out of scope). The fixed `LAYOVER_S` is removed.
- **Re-dispatch**: trip *n+1* of each bus is dispatched from P-883 at its scheduled time,
  `start_at + n × cycle`, with `cycle = 5 × 600 s = 3,000 s`. If the bus reaches the terminal late
  and the scheduled time has already passed, trip *n+1* is dispatched immediately.
- **Configuration, not constants**: the planned headway comes from configuration
  (`SIM_PLANNED_HEADWAY_S`, default 600, read through `src/pulsoflota/config.py` like `SIM_SEED`).
  The cycle is derived as `number of in-service buses × planned headway`, so the two cannot drift
  apart. `START_HEADWAY_S` and `LAYOVER_S` leave `src/simulator/model.py`. A small test asserts that
  the simulator default equals `config.corridor_settings.headway_planned_s` (600), because the
  simulator and the gold rules are separate readers of the same planned value.
- **Existing tests**: the 001 simulator tests that depend on the old spacing are updated in the same
  phase. Candidates to check first: `tests/unit/test_simulator_travel_time.py` (completed trips in
  one hour), `tests/unit/test_simulator_capacity.py` (rider-arrival count bounds) and
  `tests/unit/test_simulator_determinism.py`. Phase 0 runs the whole 001 suite to find the rest.
  Fixed numbers quoted elsewhere (for example "3,986 events in the seed-42 hour") change and must be
  recounted.

**Acceptance (executable, Phase 0)**: in a seeded 2-hour base run (`run(seed, 7200)`, no
injections, seeds 42 and 7), take the `stop_arrival` events at P-883 ordered by `event_ts` and
compute the gaps between consecutive ones:

1. the median gap is 600 s ± 60 s;
2. no gap is below 300 s.

**Rationale**: the gold rules classify against `headway_planned_s = 600`. A simulator whose normal
state is already half the planned headway produces false `bunched` states, and data-quality tests
built on it would pass or fail for the wrong reason. Fixing it in Phase 0 means every later phase,
and story 003's injectors, start from a clean base case.

**Alternatives**: lower the planned headway to match the simulator (rejected: 600 s is the corridor
design value in the turn map and in `config.corridor_settings`); simulate direction 2 and the real
return leg (rejected: out of turn-1 scope); tolerate it and exclude the simulator from base-case
checks (rejected by the data owner: it breaks the "normal" scenario and C1).

---

## R15 — Turn-1 scope and deferred items (Evolution)

Not built and not blocking (`docs/turns-ritmo.md` §3.3, spec "Out of Scope"):

- Redis or any broker; `NOTIFY` is the push transport (turn 3).
- PostGIS, geometry, TimescaleDB (turn 3).
- Incremental silver and throughput SLOs (1,000 events/s, P99 ≤ 500 ms) (turn 3).
- Out-of-order, impossible-position and burst faults (turn 3). A `distance_along_m` above 5119.4
  without a terminus arrival would fail schema validation of the snapshot and so fail the cycle,
  which is safe but not handled.
- Per-stop and P85/P95 metrics, P(board ≤ t) (later story).
- REST/WebSocket endpoints, the decision engine, recommendations (backend story).
- Scenario injectors C1/C2/C5/D1 (story 003); tests use crafted bronze events.
- Turn-2 security (RBAC, JWT, mTLS, HMAC, secret manager, SAST/SCA).
- A configuration version in gold lineage: turn-1 lineage is `rules_version` + `max_bronze_id`
  only (ADR-0001). A configuration change does not bump `rules_version`, so a snapshot computed
  before the change cannot be reproduced bit-for-bit after it. This is acceptable while the values
  are fixed for the workshop.
- The return leg and direction 2 of the corridor (turn 4). The R14 layover only stands in for them.

---

## R16 — Refresh service in compose

**Decision**: a fourth compose service `refresh` that uses the existing image (`prod` target) with
command `python -m src.refresh.run` and `DATABASE_URL`, `LOG_LEVEL`, `REFRESH_CLOCK` (R3) and
`REFRESH_INTERVAL_S` (default 5) from `.env`. `depends_on: db (service_healthy)`, and no other
service depends on it. `ingestion` is unchanged and still depends only on `db`, so stopping or
crashing `refresh` cannot stop capture (FR-041). `restart: unless-stopped`. The process connects
with retry, like `src/ingestion/run.py`.

Logs are structured JSON lines made with the standard library: `json.dumps` in a
`logging.Formatter`. A cycle line carries `event`, `snapshot_id`, `as_of_ts`, `max_bronze_id`,
`duration_ms` and `status`. A failure line carries the error class and a correlation id, never a
traceback in the payload or the notification. No new dependency is needed.

**Rationale**: this matches the constraint "one refresh-loop process, separate service, off the
capture path" and the 001 compose conventions. Adding new variables to `.env.example` follows the
existing `.env` convention. No secrets are involved.

**Alternatives**: running the loop inside the `ingestion` container is rejected because it would
put the loop on the capture path (Principle III, FR-041). Running it inside `api` is rejected
because the API story owns that process and the refresh would die with the web tier.
