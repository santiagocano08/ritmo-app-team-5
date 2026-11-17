# Research — Turn-1 Run Environment and Base Simulator

**Feature**: 001-base-simulator | **Turn**: 1 (active) | **Date**: 2026-11-17

Resolves every `NEEDS CLARIFICATION` from the Technical Context and the open
points raised by the feature spec, the accepted contract (`contracts/turn1-events`
v1.0.0) and ADR-0001 / ADR-0002. Non-interactive run: each unknown is resolved with
the simplest option that still honors the constitution and the turn-1 scope.

## How to read this file

Each entry: **Decision** (what was chosen), **Rationale** (why), **Alternatives
considered** (what else was evaluated). Decisions marked *turn-1 scope* stay; the
rest is recorded as **Evolution** for later turns per `docs/turns-ritmo.md`.

---

## R1 — Dependency management and packaging

**Decision**: `uv` (Astral) manages the project and a single virtual environment.
`pyproject.toml` declares Python `>=3.12` and the runtime/dev split; no
`requirements.txt`, no Poetry, no pip-compile.

**Rationale**: the user mandated `uv`; it is fast, lockfile-based and pins exact
versions, which supports the turn-2 supply-chain gate later. One tool, one
lockfile (`uv.lock`), simplest for a 4–5 hour review window.

**Alternatives**: pip + `requirements.txt` (no lockfile by default, weaker
reproducibility); Poetry (heavier, another format). Both rejected to keep one
tool.

---

## R2 — Database driver and query style

**Decision**: `psycopg` 3 (binary wheel) with **parameterized SQL** (`%s`
placeholders) and plain SQL init scripts. No ORM, no Alembic, no query builder.

**Rationale**: the user mandated psycopg 3 with parameterized SQL, no ORM and no
Alembic. Parameterized queries satisfy the no-cost security baseline (A05,
injection). Plain SQL init scripts (versioned files in `db/init/`) keep schema
changes auditable and avoid a migration framework for a tiny turn-1 schema.

**Alternatives**: SQLAlchemy ORM (rejected — adds weight, hides SQL, not
requested); asyncpg (rejected — async adds complexity the tiny turn-1 volume
does not need; psycopg 3 sync is enough at 7 buses / 5 s). Alembic (rejected —
no migrations needed; the schema is created by idempotent init scripts run once
on container start).

---

## R3 — Pydantic V2 model generation (Contract-First)

**Decision**: Pydantic V2 models are **generated** from the accepted JSON
Schemas in `contracts/turn1-events/` with `datamodel-code-generator`
(`datamodel-codegen`). The generated package lives at `src/pulsoflota/models/`
and is treated as a build artifact — never hand-written or hand-edited. A
Makefile target (`make generate`) regenerates it; CI asserts the committed
generated file matches a fresh generation (drift = gate failure).

**Rationale**: Principle II (Contract-First) + the user mandate ("generated,
never hand-written"). Generating from the authoritative schema guarantees the
code uses exactly the contract fields (no invented fields, no drift). The
contract examples in `contracts/turn1-events/examples/` become the contract test
fixtures. `datamodel-codegen` maps JSON Schema `oneOf` + `const` discriminators
to discriminated unions and `additionalProperties: false` to `model_config =
ConfigDict(extra='forbid')`, which is exactly the strict boundary behavior
RNF-3.3.1 requires.

**Alternatives**: hand-written Pydantic models (rejected — violates the mandate
and Principle II; drifts from the contract); runtime JSON-Schema validation via
`jsonschema` only (rejected — slower per event, no typed payload access, and the
mandate is Pydantic V2).

**Note on the conditional `rider_arrival`**: the schema uses `if/then/else` for
`train_trip_id` (required when `origin == "train"`, forbidden otherwise).
`datamodel-codegen` emits this as a model with a custom validator; the generated
validator is the source of truth. If generation produces a weak validator, the
task adds a thin generated-compliant post-check — never a hand-written
loosening. This is recorded so `implement-code` verifies the conditional rule is
enforced.

---

## R4 — Container topology and the "simulator/ingestion" service

**Decision**: `docker-compose.yml` defines **three** services:

1. `db` — PostgreSQL 16 (official image, plain SQL init scripts mounted into
   `/docker-entrypoint-initdb.d/`).
2. `ingestion` — the simulator + ingestion in one container. Entry point pipes
   the simulator's JSON-lines stdout into the ingestion reader:
   `python -m src.simulator.main --seed "$SEED" --duration "$DURATION" | python
   -m src.ingestion.run`. The ingestion reader validates each envelope against
   the generated Pydantic models and writes valid → `bronze.events`,
   invalid/duplicate → `bronze.rejections`.
3. `api` — FastAPI + uvicorn serving **only** `GET /healthz`.

**Rationale**: Principle III (isolated ingestion) is non-negotiable from turn 1.
Three separate services mean stopping `api` cannot stop `ingestion` (US-2). The
simulator and ingestion share one container because the turn-1 transport is a
direct write to the bronze table (ADR-0001: "the simulator writes to the
PostgreSQL bronze table"); splitting them into two containers would need an
inter-process channel Redis/broker — which is deferred. One container with a
pipe keeps the real-time path deterministic and free of external services
(Principle III).

**Alternatives**: simulator and ingestion as two containers connected by a
queue (rejected — needs Redis/broker, deferred to turn 3); one container
running everything including the API (rejected — violates isolation, the API
would take ingestion down with it).

---

## R5 — Simulator → ingestion transport (determinism and testability)

**Decision**: the simulator emits one JSON envelope per line on **stdout**
(JSON-lines). The ingestion reader consumes stdin. Both are also importable as
Python modules with stable functions:

- `src.simulator.engine.run(seed, duration) -> Iterator[dict]` (yields
  envelope dicts; no DB, no I/O) — used by US-4 determinism tests.
- `src.ingestion.bronze.ingest(conn, envelope_dict) -> IngestResult` — used by
  US-3 crafted-event tests with a real DB connection.

**Rationale**: decouples the deterministic simulator from persistence (US-4
needs no persistence layer to test output) and lets US-3 feed crafted events
without the live simulator. The pipe is only the deployment glue; the modules
are independently testable.

**Alternatives**: the simulator writes directly to bronze itself (rejected —
couples simulation to the DB, breaks the US-4 "no persistence required" test
and the US-3 "without the live simulator" test); a REST/HTTP ingestion endpoint
(rejected — adds an HTTP server on the real-time path, unnecessary in turn 1;
the API service is health-only).

---

## R6 — Stop ids for corridor C6-008

**Decision**: `data/reference/stops.csv` uses the **real stops of C6-008**, not
invented ids. The build (`src/reference/build.py`) reads
`data/raw/metro_capas/paradas_alimentadoras.geojson` and keeps the 35 features
whose `properties.ruta == "C6-008"`, filtered to **direction 1 (Prado outbound)**
using the direction carried in
`data/raw/metro_capas/rutas_alimentadoras.geojson` (the C6-008 route lines, which
carry `properties.sentido`). Each retained stop yields a row with columns
`stop_id`, `stop_name`, `distance_along_m`, `segment_id`:

- `stop_id` = `"P-<objectid>"`, derived from the real `objectid` of that feature
  (e.g. `P-312`). No invented `S-NNN` ids.
- `stop_name` = the real stop name (`parada` / `label`, e.g.
  `Cra 20A con Cll 56A`).
- `distance_along_m` = distance from the corridor origin, computed by
  **projecting the stop point onto the direction-1 route line**.
- `segment_id` = the corridor segment (1..17) the projected stop falls in, from
  `tramos_c6008_s1_osm.csv`.

The build is deterministic, so the same raw inputs always yield the same
`stop_id` ↔ stop mapping. Fixtures and the contract examples' stop references
use these real ids (FR-003, FR-008). `stop_id` is a string in the event schema,
so adopting `P-<objectid>` needs **no schema version change**; the fixtures and
contract examples are updated to the real ids during implementation.

**Rationale**: the feeder GeoJSON **does** contain C6-008: the 35
`ruta == "C6-008"` features carry a real stop name (`parada`/`label`), a real
`objectid`, `itinerario` and `linea` (`C6-008 La Libertad - Estacion Prado`);
`rutas_alimentadoras.geojson` carries the C6-008 route lines with `sentido`
(direction). The earlier draft of this entry was factually wrong — it claimed the
feeder GeoJSON carried no C6-008 route and only C3-004 routes. Using the real
stops with ids derived from their real `objectid` is what "real C6-008 stops
with their real stop ids" should mean, and it keeps fixtures and examples honest
(no invented ids that would drift from the data). Filtering to direction 1
matches the turn-1 corridor (station → neighborhood); projecting onto the
direction-1 route line gives the distance-along-corridor the simulator and
metrics need.

**Alternatives**: invented `S-NNN` ids ordered by distance (rejected — the real
stops and real `objectid`s are available, so invented ids misrepresent the data
and force fixtures/examples onto fake ids); UUID stop ids (rejected — opaque,
not human-reviewable in fixtures); free-text stop names as ids (rejected — names
drift and are hard to reference from fixtures).

---

## R7 — Congestion factor aggregation from SIMM

**Decision**: `data/raw/plata/simm_corredor_c6008.csv` (real speed measurements
on the corridor, ~22 MB) is aggregated **by hour** into
`data/reference/congestion_factor.csv` with columns `hour` (0–23) and
`congestion_factor`. For each hour the factor is:

  `congestion_factor[hour] = mean(SIMM VELOCIDAD for that hour) /
     free_flow_speed_of_the_corridor`

where the corridor free-flow speed is the **length-weighted mean of
`v_libre_kmh`** across the 17 segments in
`data/raw/plata/tramos_c6008_s1_osm.csv` (one weighted value for the whole
corridor, used as the denominator for every hour). Aggregation is deterministic
(group by hour, sort, round). **No tuning constant is applied to force the
result into any range.** The 0.43–0.56 band from the spec is only an **expected
sanity check**: if the computed hourly values fall outside it, the build emits a
warning and **keeps the values as computed** (FR-005, FR-007).

**Rationale**: the spec's 0.43–0.56 range is an expectation, not a constraint to
manufacture; the factor must come from the data (mean measured speed over the
corridor's free-flow speed). A length-weighted corridor free-flow speed is the
correct denominator because longer segments should weigh more. Hourly
aggregation is the natural grain for the 5 s-step simulator (it looks up the
factor by the event's wall-clock hour). The 22 MB source is too large to ship;
the aggregated CSV is tiny and reproducible, keeping `data/reference/` under 1 MB
(FR-001). Reporting a warning (not failing) when values fall outside the band
keeps the build honest without fabricating a tuning constant.

**Alternatives**: ship the raw 22 MB (rejected — violates the <1 MB budget);
per-segment congestion (rejected — over-fits turn 1; the simulator formula uses
a single hourly factor per FR-019); a tuning constant to hit 0.43–0.56
(rejected — falsifies the measurement; the band is a sanity check, not a
target).

---

## R8 — Train arrivals from the Metro GTFS

**Decision**: `data/reference/train_arrivals.csv` is built from
`data/raw/metro/GTFS-Metro_de_Medellin_2025.zip` by selecting line-A trips that
serve Prado station, joining `stop_times.txt` (arrival times) + `trips.txt` +
`calendar.txt` for the **weekday** service calendar, and emitting one row per
arriving train: `train_trip_id`, `arrival_time`, `service_id` (weekday).
`train_trip_id` is the GTFS `trip_id` (e.g. the examples' `METRO-A-0815` pattern),
used by `rider_arrival` events with `origin == "train"` (FR-004, FR-021).

**Rationale**: the contract's `rider_arrival` carries `train_trip_id` for train
origins; the simulator needs the real Prado weekday arrivals to model rider
batches. GTFS is the authoritative source; the weekday calendar matches the
turn-1 operating day.

**Alternatives**: hard-code a few arrival times (rejected — not reproducible,
not "real"); use the Metro afluencia XLSX (rejected — that is ridership volume,
not the schedule).

---

## R9 — Demand parameters

**Decision**: `data/reference/demand_params.csv` (or `.json`) holds the hourly
shape of Metro line A (from `data/raw/metro/Afluencia_Metro_2025.xlsx`) and the
**feeder share of basin 6** computed from
`data/raw/medata/pasajeros_movilizados_mensual_metro_de_medellin.csv` — the
basin-6 series (`METRO_CUENCA_6`) over the line-A series (`METRO_LINEA_A`), as
FR-006 states — as declared parameters the simulator scales rider arrivals by.
One row per hour, plus a single feeder-share constant (FR-006, FR-021). **The
EOD (`data/raw/plata/eod_macrozonas.csv`) is not used in this story.**

**Rationale**: the simulator needs an hourly demand shape and a basin-6 feeder
share to produce realistic, reproducible rider arrivals. FR-006 fixes the
feeder-share source as the basin-6-vs-line-A ridership from the MeData monthly
series, not the EOD origin-destination factors; the earlier draft of this entry
pointed at the EOD, which is not the source FR-006 names. Keeping both as small
declared parameters keeps `data/reference/` under 1 MB and reproducible.

**Alternatives**: pull the feeder share from the EOD OD matrices (rejected — not
the source FR-006 names, and the simulator only needs a single share constant);
pull the full EOD matrices at runtime (rejected — large, and unnecessary).

---

## R10 — Reference-data reproducibility and SOURCES.md

**Decision**: `make reference` runs `python -m src.reference.build`, which reads
`data/raw/` (git-ignored) and writes `data/reference/` (committed, <1 MB). The
build is deterministic: fixed sort orders, fixed rounding, no wall-clock
dependence. It also writes `data/reference/SOURCES.md` with one line per output
file recording source URL, license, download date and the transformation applied
(FR-007). A missing required raw source makes the build fail with a clear
message naming the missing source (edge case in spec).

**Rationale**: FR-001 (byte-identical rebuild) + the independent test (rebuild
twice, compare). Determinism is achieved by avoiding floats-in-set iteration,
sorting keys, and seeding nothing (the reference data is descriptive, not
stochastic). `SOURCES.md` is the lineage required for the no-cost baseline and
for turn-2 provenance.

**Alternatives**: a notebook (rejected — not reproducible from the command
line); building inside the DB (rejected — reference data is consumed by the
simulator as files, simpler to keep it as files).

---

## R11 — Bronze schema, immutability and idempotency

**Decision**: see `data-model.md` for the full DDL. In short:

- `bronze.events`: `id BIGSERIAL PK`, `source TEXT NOT NULL`, `event_id UUID NOT
  NULL`, `schema_version TEXT`, `event_type TEXT`, `event_ts TIMESTAMPTZ NOT
  NULL`, `arrival_ts TIMESTAMPTZ NOT NULL`, `payload JSONB NOT NULL`,
  `UNIQUE (source, event_id)`. Insert-only.
- `bronze.rejections`: `id BIGSERIAL PK`, `original_message JSONB`, `reason TEXT
  NOT NULL` (CHECK in the contract enum), `received_ts TIMESTAMPTZ NOT NULL`.

Immutability is enforced two ways, both light: (a) **application discipline** —
`src/ingestion/bronze.py` issues only `INSERT`s, never `UPDATE`/`DELETE`; (b) a
**guard test** (`test_bronze_immutable`) asserts bronze row counts and checksums
do not change across a re-ingest and that no code path issues `UPDATE`/`DELETE`
on bronze. An optional `REVOKE UPDATE, DELETE` grant or a trigger that raises on
`UPDATE`/`DELETE` is noted as a hardening option but is **not required** in turn
1 (the no-cost baseline + test gate is enough). Idempotency is the
`UNIQUE (source, event_id)` constraint: a duplicate insert raises a unique
violation, caught and recorded in `bronze.rejections` with reason
`duplicate_event` (FR-015).

**Rationale**: ADR-0001 decides bronze is insert-only with a `(source,
event_id)` dedup key and rejections in `bronze.rejections`. The unique
constraint is the enforcement mechanism; the test is the gate. A trigger would
add safety but also add DB objects to review inside the 4–5 hour budget, so it
is optional.

**Alternatives**: materialized views for silver/gold (rejected by ADR-0001);
a `status` column on one table (rejected by ADR-0001); app-only dedup without
the DB unique constraint (rejected — a race or a bug could double-insert; the
constraint is the real guarantee).

---

## R12 — Rejection reason mapping

**Decision**: ingestion maps Pydantic V2 `ValidationError` categories and the
contract's explicit checks to the `rejection.schema.json` enum:

- missing required field → `missing_required_field`
- wrong type / out-of-range / enum violation → `wrong_type` or
  `value_out_of_range`
- `additionalProperties` violation (extra field) → `undeclared_field`
- `event_id` not a UUID → `invalid_uuid`
- `event_ts` / `arrival_ts` not date-time → `invalid_timestamp`
- `schema_version` not `1.0.0` → `unsupported_schema_version`
- `event_type` not in the enum → `unknown_event_type`
- unique-violation on `(source, event_id)` → `duplicate_event`

The original message is stored as-is in `bronze.rejections.original_message`
(JSONB when parseable, text otherwise).

**Rationale**: the rejection reasons are fixed by the contract (ADR-0002); a
single, deterministic mapping keeps the rejection audit clean and the contract
tests exact. The mapping lives in `src/ingestion/validate.py` as deterministic
code (no LLM, per the data profile).

---

## R13 — Simulator determinism (seed → byte-identical output)

**Decision**: the simulator uses a single `random.Random(seed)` (and
`numpy`'s seeded `Generator` only if lognormal is easier there — kept optional
to avoid a hard numpy dependency; a pure-`random` lognormal via
`math.log` + `random.gauss` is the default). **All** randomness — event ids,
travel-time noise, boardings/alightings, rider arrivals — draws from this one
seeded generator in a fixed call order. Event ids are generated with a seeded
`uuid.UUID` (deterministic v4 from the seeded RNG bytes) so the same seed yields
identical `event_id`s (spec assumption). Output is JSON-lines with a stable key
order (`json.dumps(..., sort_keys=True)`), so the byte stream is identical
across runs (SC-001, FR-025).

**Rationale**: determinism is a success criterion (SC-001) and the spec's
assumption explicitly allows a seeded generator for event ids. Stable JSON key
order + a single seeded RNG + fixed call order is the standard way to get
byte-identical output. Pure-`random` avoids a numpy pin in turn 1.

**Alternatives**: unseeded UUIDs (rejected — not deterministic); multiple
independent RNGs (rejected — ordering fragility); `numpy` mandatory (rejected
— extra dependency, not needed at this volume).

---

## R14 — Travel-time, dwell and trip-duration model

**Decision**: per FR-019/FR-020/FR-026:

- Travel time per segment = `length_m / (free_flow_kmh * 3.6 * congestion_factor)
  * lognormal_noise`, where `congestion_factor` is the hourly value from
  `congestion_factor.csv` for the event's hour, and `lognormal_noise` is
  `exp(mu=0, sigma=SIGMA)` with a single **declared** `SIGMA` (default 0.20),
  seeded by the run seed. Tunable so the running time ≈ 19.5 min holds.
- Dwell = `10 + 3*boarded + 2*alighted` seconds (FR-020, TCQSM), minimum 10 s
  when no boardings/alightings (edge case).
- Peak hour = the hour with the lowest congestion factor (spec assumption).
- A peak-hour end-to-end trip ≈ 19.5 min running + 5.7 min dwell = 25 min,
  asserted within ±20 % by `test_simulator_travel_time`.

**Rationale**: directly from the spec's FR and assumptions. A single declared
`SIGMA` keeps the model tunable and reviewable; the test pins the target so a
bad constant fails the gate rather than silently drifting.

**Alternatives**: per-segment congestion (rejected — FR-019 uses one hourly
factor); fixed dwell (rejected — FR-020 is board/alight-dependent).

---

## R15 — Boarding, capacity and rejected riders

**Decision**: riders wait FIFO at a stop; when a bus arrives, board up to
`40 - occupancy` (capacity 40); the excess is counted as `rejected` and does not
board; `occupancy` never exceeds 40 (FR-022, FR-023, edge case). `stop_arrival`
records `occupancy` on arrival; `stop_departure` records `occupancy` on
departure (both per the contract). Alightings use a simple per-stop probability
applied to onboard riders (spec assumption), tuned so peak dwell ≈ 5.7 min.

**Rationale**: the contract payloads carry `boarded`, `alighted`, `rejected`,
`occupancy`; the simulator must populate them consistently. FIFO + a hard
capacity cap is the simplest correct model and is directly testable
(`test_simulator_capacity`: occupancy never exceeds 40; rejected = surplus).

---

## R16 — Reserve buses and emitted event types

**Decision**: B-101..B-105 are in service; B-106..B-107 are in the fleet roster
as available but are **not dispatched** and emit no `bus_position` (no decision
engine in scope — spec edge case + FR-017). The base simulator emits exactly
four event types: `bus_position` (every 5 s per in-service bus), `stop_arrival`,
`stop_departure`, `rider_arrival`. `driver_confirmation` and `incident_report`
exist in the contract but are **not emitted** by the base simulator (FR-023).

**Rationale**: FR-017/FR-023 + the out-of-scope list. Reserve buses stay parked;
the two non-emitted types arrive with the decision engine / scenario injectors,
which are later stories.

---

## R17 — API scope and health endpoint

**Decision**: the `api` service is a FastAPI + uvicorn app exposing **only**
`GET /healthz` → `200 {"status": "healthy"}` (FR-011). No other routes, no DB
dependency on the health path (the health check does not need bronze to answer).
Versioned base path `/api/v1` is reserved but unused in this story.

**Rationale**: FR-011 mandates only a health endpoint; the user said "FastAPI
health check only." Keeping the health check DB-free means the API can report
healthy even while the DB is briefly unreachable, which is fine — the health
check proves the API process is up, not that bronze is current. Bronze growth is
verified separately (US-2 independent test).

---

## R18 — Testing, coverage and gates (turn 1)

**Decision**: `pytest` + `pytest-cov`, target coverage **> 80 %**. Three test
tiers: `tests/contract/` (valid/invalid contract examples), `tests/unit/`
(reference build, simulator determinism/capacity/travel-time, validation
mapping), `tests/integration/` (bronze ingest valid/invalid/duplicate, bronze
immutability, isolation: stop API → ingestion keeps writing, health endpoint).
Turn-1 gates only: Gate 1 = Pydantic schema validation (no SAST); Gate 2 =
tests + coverage > 80 % (no SCA); Gate 4 = N/A (no recommendations in this
story). CI marks the build failed on any principle violation.

**Rationale**: `docs/turns-ritmo.md` §3.2 adopts only Gate 1 (schema) and Gate 2
(tests + coverage) for turn 1; SAST/SCA, RBAC/JWT, HMAC, secret manager are
turn-2 evolution and **must not** be blocking findings here.

---

## R19 — Security no-cost baseline (turn 1 only)

**Decision**: apply only the no-cost security baseline the turn map adopts:
parameterized queries (R2), no secrets in the repository (DB DSN via an env var
in the container, never committed; no `.env` committed), and error responses
without stack traces (FastAPI default error handler returns a generic message;
no `DEBUG=True` in the api service). RBAC, JWT, MFA, mTLS, HMAC, security
headers, SAST/SCA and the secret manager are **deferred to turn 2** and recorded
as Evolution — not implemented, not a blocking finding.

**Rationale**: `docs/turns-ritmo.md` §3.2 explicitly limits turn-1 security to
the no-cost baseline; the constitution's "Phased Adoption" says a deferred norm
MUST NOT be a blocking finding in the active turn. Building them now would
violate turn scope (data-profile review: "Do not implement deferred items just
in case").

---

## R20 — Makefile as the single entry point

**Decision**: a single `Makefile` at the repo root provides the documented
commands: `make generate` (regenerate Pydantic models from the contract),
`make reference` (build `data/reference/`), `make up` / `make down` (docker-
compose), `make test` (pytest + coverage), `make lint`, `make clean`. The
reference-data build is `make reference` → `python -m src.reference.build`.

**Rationale**: the user asked for "a single Makefile or script for reference-data
build"; one Makefile also gives the reviewer one place to see every command,
which matters for a 4–5 hour review window.

---

## Evolution (deferred norms — NOT built in this story)

Per `docs/turns-ritmo.md`, recorded as evolution (not blocking):

- Redis Pub/Sub / `database-redis` service (turn 3).
- PostGIS, lat/lon geometry, TimescaleDB, time partitioning (turn 3).
- Throughput targets 1,000 events/s, P99 ≤ 500 ms (turn 3).
- Silver and gold layers and derived metrics (later story).
- Scenario injectors C1–C5 and data faults beyond basic idempotency (later
  story / turn 3).
- Decision/recommendation engine and the human approval loop (later story).
- ML models, anomaly detection, route diversion (US-03, turn 4).
- Security turn-2 norms: RBAC, JWT, MFA, mTLS, HMAC, secret manager, security
  headers, SAST (Bandit), SCA (pip-audit/Trivy) (turn 2).
- The dispatcher web console and interactive map (adaptive lane, later).
