# Implementation Plan: Silver and Gold Layers with M1/M2 Baselines

**Branch**: `feature/002-silver-gold-baselines` (stacked on `feature/001-base-simulator`) | **Date**: 2026-11-18 (gate decisions applied 2026-11-18) | **Spec**: [spec.md](spec.md) (approved, commit `61b5268`)

**Input**: Feature specification from `/specs/002-silver-gold-baselines/spec.md`

**Note**: `.specify/scripts/bash/setup-plan.sh` could not be executed in this session (the shell
refused to run it). This file was created from `.specify/templates/plan-template.md` by hand, for
the feature recorded in `.specify/feature.json` (`specs/002-silver-gold-baselines`).

## Summary

Turn the bronze events of story 001 into the layers the console and the decision engine read. The
layers are a silver per-bus state (with the 2-minute Estimated rule, stop visits, segment
traversals and incidents), gold `source_status` and `corridor_now` with headway, bunched/gap
classification and the corridor mean wait / EWT, M1/M2 median baselines with a declared
reference-data fallback, `decision_inputs`, and a 5 s refresh loop that emits one PostgreSQL
`NOTIFY` per snapshot. Before any of that, Phase 0 fixes the 001 simulator so its base case has the
planned 600 s headway (research R14); without it the "normal" state would already look bunched.

**Approach** (from [research.md](research.md)): each cycle is one `REPEATABLE READ` transaction
with a fixed reference time. It rebuilds silver from bronze with plain parameterized SQL, applies
the per-bus rules in small pure Python functions under `src/rules/`, and appends a snapshot with a
deterministic id and lineage (`rules_version`, `max_bronze_id`). The same transaction calls
`pg_notify`, so the notification is delivered only when the snapshot is readable. The same cycle
function backs a `compute` CLI (one snapshot or a replay) and the `refresh` compose service. No
new runtime dependency is added; the dev extra gets `jsonschema` + `rfc3339-validator` so tests can
validate real outputs against the JSON Schemas (SC-001).

## Technical Context

**Language/Version**: Python 3.12+ (same as 001).

**Primary Dependencies**: unchanged at runtime: `psycopg` 3, `pydantic` V2 (models generated from
`contracts/read/{source_status,corridor_now,decision_inputs}.schema.json` with the existing
`datamodel-code-generator`). Dev extra adds `jsonschema` and `rfc3339-validator`, locked in
`uv.lock` (research R9).

**Storage**: PostgreSQL 16 only. New tables in `silver`, `gold`, and a small `config` schema for
static configuration (DECIDED, research R11; ADR-0001 gets a one-line addendum). Bronze is read
only. No TimescaleDB, PostGIS, Redis or broker.

**Testing**: pytest + pytest-cov, tests first. A throwaway database per test module (research
R10); crafted bronze inserted through `src.ingestion.bronze.ingest`; JSON Schema validation of
stored objects; fixture comparison for SC-002. Gate 2: coverage > 80 %; `src/rules/` close to
100 %.

**Target Platform**: Linux containers via `docker-compose`: existing `db`, `ingestion`, `api`,
`tests`, plus one new `refresh` service (Phase 4).

**Project Type**: data pipeline inside the existing single Python project (one `pyproject.toml`).

**Performance Goals**: one snapshot per 5 s (FR-036). The cycle duration is measured, not assumed:
it is logged per cycle (`duration_ms`) and checked by SC-009 (≥ 95 % of intervals at 5 s ± 1 s).
Throughput SLOs are deferred (turn 3).

**Constraints**: deterministic (same bronze + `as_of_ts` + `rules_version` → identical silver and
gold); event time only; no AI or external call on the path; refresh off the capture path; no
contract changes; turn-1 no-cost security baseline (parameterized SQL, no secrets, no stack traces
in outward messages).

**Scale/Scope**: 1 corridor, direction 1, 18 stops, 17 segments, 5 + 2 buses; about 4,000 bronze
events per simulated hour (3,986 in the 001 seed-42 run before the R14 fix; recount after Phase 0).
M1 = 17 × 24 rows; M2 = 96 rows.

**Decisions from the human gate (data owner, 2026-11-18)**, all recorded in [research.md](research.md)
and none open:

| Item | Decision | Used in |
|---|---|---|
| R3 live reference time | `REFRESH_CLOCK=wall\|data`. `data`: `as_of_ts = max(event_ts)` of non-backend bus reports, default for the simulator demo. `wall`: current UTC, for real telemetry (FR-004 applies to this mode). Tests and replays use a fixed time. | Phase 4 |
| R8 negative headway | clamp to 0 | Phase 2 |
| R11 configuration tables | `config` schema; one-line addendum to ADR-0001 | Phase 0 |
| R12 M2 sample | a (day, 15-minute band) counts only if the band has ended and the simulator was running in it | Phase 3 |
| R13 M2 rounding | round half away from zero (cast to `numeric` before `round`) | Phase 3 |
| R14 base-case headway | fix the 001 simulator: buses start 600 s apart, the layover stands in for the return leg, trip *n+1* is dispatched at `start_at + n × 3000 s` or immediately if late; headway and cycle from configuration | Phase 0 |

No confirmation tasks are needed. The implementation tasks the decisions create are listed in
Phase 0 and in Readiness.

## Constitution Check

*GATE: evaluated before Phase 0 research; re-checked after Phase 1 design (below).*

Constitution v1.1.0; turn 1 active (`docs/turns-ritmo.md` §3). The five Core Principles apply;
other norms only as adopted in §3.2.

| Principle | Status | Evidence |
|---|---|---|
| **I. Risk-First Order** | PASS | Mitigates the turn-1 Level 1 risk (data integrity): missing or duplicated data must not contaminate metrics or recommendations. Disciplined lane. No adaptive-lane work is included. |
| **II. Contract-First & Data Ownership** | PASS | Outputs are instances of the accepted `contracts/read/` v1.0.0 schemas (ADR-0003). Models are generated from them, and tests validate real outputs against the JSON Schemas. The one new interface (`NOTIFY` payload) gets a schema before code ([contracts/](contracts/README.md)). Every new table has the data module as owner ([data-model.md](data-model.md)). |
| **III. Isolated Ingestion & Deterministic Real Time** | PASS | `refresh` is a separate service that nothing depends on; `ingestion` is unchanged (FR-041, SC-010). All rules are deterministic SQL/Python with no AI or third-party call. Transport is `LISTEN/NOTIFY`. |
| **IV. Unbreakable Human Gate** | PASS (nothing to gate) | Produces inputs only: no recommendation, no action, no write to bronze or to dispatch. `decision_inputs` is internal to the backend (FR-035). |
| **V. Test-First & Automated Gates** | PASS | Each phase starts with failing tests and ends with an executable check ([quickstart.md](quickstart.md)). Coverage > 80 % runs in the existing `tests` service. |

**Turn-1 adopted norms (§3.2)**: RNF-3.2.1/3.2.2: PASS (compose; ingestion isolated; refresh
separate). RNF-3.3.1: unchanged, boundary validation stays in 001 ingestion and crafted test events
go through it. RF-2.1–2.3: data inputs only, consumed by the backend later. Gate 1 (schema
validation): PASS, every stored object is schema-validated in tests. Gate 2 (tests + coverage
> 80 %): PASS by plan. Gate 4: N/A, no recommendations. Security baseline: parameterized SQL,
config holds no secrets, error logs without tracebacks in outward messages.

**Deferred norms (Evolution, not blocking)**: Redis/`database-redis`, PostGIS/TimescaleDB,
1,000 events/s and P99 ≤ 500 ms, incremental silver, out-of-order/impossible-position/burst faults,
per-stop and P85/P95 metrics, P(board ≤ t), SAST/SCA, RBAC/JWT/MFA, mTLS, HMAC, secret manager,
endpoints, decision engine. Listed in research R15.

**Post-design re-check** (re-run after the gate decisions): the design artifacts add no deferred norm
as a requirement and weaken no principle. Four points were checked explicitly.
(1) The `config` schema (R11, DECIDED) is not derived data and holds no secrets. ADR-0001's "no
fourth schema" referred to rejections, and the data owner decided on a one-line addendum listing
`config` as a fourth schema for static configuration, with no other ADR change.
(2) The `NOTIFY` payload is a new inter-module message. It has a JSON Schema and a test,
satisfying Principle II, and promotion to `contracts/read/` is left to an ADR.
(3) The simulator fix (R14) changes schedule generation in 001 code and no event type, field or
contract, so Principle II is untouched. It touches neither the ingestion boundary nor the bronze
writer, so Principle III (isolation, deterministic path) is unchanged. It stays seeded and
deterministic, and it is built test-first (Principle V): the acceptance test is written before the
change. It also serves Principle I, because it removes a data-integrity risk (false `bunched` states
in the base case) before any later story builds on it.
(4) `REFRESH_CLOCK=data` (R3) keeps the critical path free of external calls. Only the source of
`as_of_ts` changes, and `wall` keeps FR-004 for real telemetry.
**No violations; Complexity Tracking is empty.**

## Project Structure

### Documentation (this feature)

```text
specs/002-silver-gold-baselines/
├── spec.md              # approved (61b5268)
├── plan.md              # this file
├── research.md          # Phase 0 output (R1–R16, all decided)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output (per-phase validation)
├── contracts/           # Phase 1 output (feature-local interfaces)
│   ├── README.md
│   ├── gold-read-access.md
│   ├── notify-channel.md
│   ├── gold_snapshot_notify.schema.json
│   └── compute-and-refresh.md
├── checklists/          # from /speckit.specify
└── tasks.md             # /speckit.tasks (NOT created here)
```

### Source Code (repository root)

New (N) and changed (C) paths only. Everything else from 001 is untouched.

```text
pyproject.toml                         # C: dev extra += jsonschema, rfc3339-validator; packages += src/rules, src/pipeline, src/refresh
uv.lock                                # C: relocked
Makefile                               # C: + generate-read target
docker-compose.yml                     # C: + refresh service (Phase 4); tests += ./db:/app/db:ro
.env.example                           # C: + REFRESH_INTERVAL_S, REFRESH_CLOCK=data (demo; code default is wall), SIM_PLANNED_HEADWAY_S=600 (no secrets)
docs/adr/0001-data-layers-and-ingestion-semantics.md   # C: one-line addendum listing `config` as a fourth schema (R11); nothing else changes

db/init/
├── 003_config.sql                     # N: config tables + seed (FR-034)
├── 004_silver.sql                     # N: silver tables
└── 005_gold.sql                       # N: gold tables

src/
├── simulator/                         # C: Phase 0 base-case fix (R14)
│   ├── model.py                       #    remove START_HEADWAY_S and LAYOVER_S constants
│   └── engine.py                      #    600 s start spacing; trip n+1 at start_at + n × cycle, or at once if late
├── pulsoflota/config.py               # C: + get_sim_planned_headway_s() (SIM_PLANNED_HEADWAY_S, default 600)
├── pulsoflota/models/read/            # N: GENERATED (make generate-read), never hand-edited
│   ├── source_status.py
│   ├── corridor_now.py
│   └── decision_inputs.py
├── rules/                             # N: data-owner rules (CODEOWNERS)
│   ├── __init__.py                    #    RULES_VERSION
│   ├── timebands.py                   #    local hour band, 15-min band, next window
│   ├── headway.py                     #    pass-time interpolation, headway (FR-020)
│   ├── classify.py                    #    bus_state, FR-011 suppression, summary, source status
│   ├── service_metric.py              #    mean wait / EWT (FR-024)
│   ├── snapshot_id.py                 #    deterministic UUID (R5)
│   └── sql/
│       ├── silver_position_history.sql
│       ├── silver_incidents.sql
│       ├── silver_bus_current_state.sql
│       ├── silver_stop_visits.sql
│       ├── silver_segment_traversals.sql
│       ├── gold_m1_baseline.sql
│       └── gold_m2_baseline.sql
├── pipeline/                          # N: orchestration, no thresholds
│   ├── __init__.py
│   ├── reference.py                   #    load data/reference/*.csv into config.ref_*
│   ├── silver.py                      #    run the silver SQL
│   ├── gold.py                        #    build objects via generated models, insert gold rows
│   ├── cycle.py                       #    one transaction: lock, M, silver, baselines, gold, notify
│   └── compute.py                     #    CLI: --as-of | --from/--to/--step, --no-notify
└── refresh/                           # N: Phase 4
    ├── __init__.py
    └── run.py                         #    5 s loop, clock selector, JSON logs, retry connect

tests/
├── fixtures/
│   └── bronze_builders.py             # N: deterministic crafted bronze (scenario timelines)
├── conftest.py                        # C: + throwaway-database fixture (R10)
├── contract/test_read_fixtures.py     # N
├── unit/
│   ├── test_simulator_base_headway.py # N: Phase 0 acceptance (R14), written before the engine change
│   ├── test_simulator_*.py            # C: the 001 tests that depend on the old spacing (R14)
│   ├── test_timebands.py  test_headway.py  test_classify.py
│   ├── test_service_metric.py  test_snapshot_id.py
│   ├── test_no_bronze_writes.py  test_refresh_loop.py
└── integration/
    ├── test_schema_init.py  test_silver.py  test_rebuild.py
    ├── test_gold_fixtures.py  test_gold_d1.py  test_gold_contract.py  test_idempotency.py
    ├── test_baselines.py  test_decision_inputs.py  test_replay_60min.py
    └── test_refresh_failure.py  test_notify.py  test_refresh_live.py
```

**Structure Decision**: keep the single 001 project and add three packages. `src/rules/` holds
every rule (SQL and Python) so CODEOWNERS and the data-profile review apply to one place.
`src/pipeline/` holds orchestration. `src/refresh/` holds the loop service. The generated read
models sit next to the generated event models under `src/pulsoflota/models/`. The `refresh`
service reuses the existing image (`prod` target); `src/` is already copied into it.

## Phases and time budget

The budget is about 4–5 hours of agent work plus verification (workshop 2026-11-24). The phases
are ordered by value, so each one leaves something usable and verified. The shares below are
planning estimates, not measurements.

| # | Phase | Share | Ends with (executable) | Delivers |
|---|---|---|---|---|
| 0 | **Foundations**: **simulator base-case fix (R14, first)**, read models, dev deps, DDL + seed (`config` schema), ADR-0001 addendum, reference loader, test DB fixture, bronze builders | ~20 % | seeded 2-hour base run: median headway at P-883 = 600 s ± 60 s and none below 300 s; updated 001 simulator tests green; fixtures valid under JSON Schema; DDL/seed test green ([quickstart §0](quickstart.md#phase-0--foundations)) | a clean base case and the base every later test needs |
| 1 | **Silver current state** (US1, P1) | ~25 % | US1 scenarios 1–6 green, Estimated boundary, rebuild equality, bronze untouched | trustworthy per-bus state; Estimated rule |
| 2 | **Gold `source_status` / `corridor_now` + service metric + `compute` CLI** (US2, P2) | ~25 % | SC-002 on 5 fixtures (`c1_bunching` fixed by T075), SC-003, SC-004, SC-007, SC-008, schema validation, negative headway clamped to 0 | what the console reads; on-demand snapshots |
| 3 | **M1/M2 + `decision_inputs`** (US3, P3) | ~20 % | SC-006 oracles (M2 half-away rounding, R12 sample rule), `decision_inputs` schema-valid and equal to `corridor_now`, SC-001 60-min replay, SC-005 | complete inputs for the decision engine |
| 4 | **Refresh loop + NOTIFY + compose service** (US4, P4) | ~10 % | no-overlap, failed-cycle and clock-selector unit tests, compose test, short live check, SC-010; (CUT-1) failure, notify and 10-minute SC-009 tests | push without polling |

Within each phase: write the failing tests, implement, run the phase check, then continue. Inside
Phase 0 the order is fixed: the R14 acceptance test and the simulator fix come first, because every
later fixture and replay depends on the corrected base case.

### What is cut if time runs out (in this order)

> Update 2026-11-18 (data owner gate): CUT-1 is narrowed in `tasks.md`.
> `tasks.md` is authoritative for the cut list.

1. **CUT-1, only the expensive Phase 4 checks** (`tasks.md` wins): `test_refresh_failure.py` (T066),
   `test_notify.py` (T067), the 10-minute live cadence test (T068) and the 10-minute part of T071.
   The loop (T064, T065, T069, T070: `refresh` service, `REFRESH_CLOCK`, failed-cycle case in T064)
   and the short T071 check (a notification within 15 s, first-minute cadence about 5 s, SC-010)
   are not cuttable, because without the loop nobody recomputes gold in the live demo.
   `pg_notify` stays in the cycle.
2. **SC-001 at full density**: run the 60-minute replay at `--step 60` instead of `--step 5` (60
   snapshots instead of 720), keep it marked `slow`, and record the reduced density in
   `verification.md`.
3. **M2 observed path tests beyond one case** (CUT-3, T054): the R12 sample-rule edge cases. Keep
   the reference fallback (always active in the workshop, because there are fewer than 5 days of
   history) fully tested, one crafted 5-day observed case, and the x.5 rounding case per path (T053).

Not cuttable: Phases 0–3 except CUT-2 and CUT-3 (including the R14 simulator fix, the T075 fixture
fix, the M1 and M2 reference fallbacks, `decision_inputs` schema validity, idempotency and lineage
tests; Principles II and V, data profile mandatory tests), plus T064, T065, T069, T070 and the short
check of T071. That is the minimum delivery.

## Risks

| Risk | Mitigation |
|---|---|
| The simulator fix (R14) changes the 001 seeded output, so 001 tests and quoted numbers go stale | Acceptance test first; run the full 001 suite in Phase 0 and update only the tests that depend on the old spacing; no event type, field or contract changes; recount event numbers. |
| The 600 s start spacing and 3,000 s cycle do not hold under travel-time noise (a bus arrives late) | A late bus is re-dispatched at once, which is the decided rule. The acceptance bounds (median 600 s ± 60 s, no gap below 300 s) are checked for seeds 42 and 7 over 2 hours. |
| Planned headway in the simulator and in `config.corridor_settings` drift apart | A Phase 0 test asserts both are 600. |
| `REFRESH_CLOCK=data` cannot show a total outage live (the clock stops) | Accepted in R3. Estimated is tested with fixed reference times (SC-003); the D1 demo silences one bus. |
| Live reference time does not match the synthetic simulator clock (R3) | Decided: `REFRESH_CLOCK=data` for the demo, `wall` for real telemetry. The cycle takes `as_of_ts` as an argument; tests and replays use fixed times; the clock choice is isolated in Phase 4. |
| A full recompute is slower than 5 s on a long-running stack | `duration_ms` is logged per cycle; FR-039 skips late ticks; incremental silver recorded as evolution. A workshop restart with `down -v` resets volume. |
| Crafted bronze does not reproduce fixture headways exactly | SC-002 compares order, states, quality, status, `sources_down` and counts, not headway values; builders use constant speeds and staggered starts so classes are unambiguous. |
| `c1_bunching` fixture defect (B-102 `gap` at 752 s) | Fixed 2026-11-18 by the data owner (B-102 `headway_ahead_s` 752 → 960, Phase 0 task T075); `c1_bunching` is now in SC-002. |

## Complexity Tracking

> No Constitution Check violations. Intentionally empty. The design adds one service (allowed by
> the constraints), no broker, no ORM, no runtime dependency, and no contract change.

## Readiness

Plan complete through Phase 1 design, with every research item decided. It is ready for
`/speckit.tasks`. No data-owner confirmation tasks are needed. The tasks must include the work the
decisions create, each placed before the phase that needs it:

- Phase 0, first: the R14 acceptance test, then the simulator fix, then the update of the 001
  simulator tests that depend on the old spacing, plus the test that the simulator's planned
  headway equals `config.corridor_settings.headway_planned_s`.
- Phase 0: the one-line ADR-0001 addendum for the `config` schema (R11), and `SIM_PLANNED_HEADWAY_S`,
  `REFRESH_INTERVAL_S` and `REFRESH_CLOCK` in `.env.example`.
- Phase 2: the negative-headway clamp test (R8).
- Phase 3: the R12 sample-rule tests and the R13 half-away rounding tests on both M2 paths.
- Phase 4: the `REFRESH_CLOCK` selector and its test (R3).
