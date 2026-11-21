# Quickstart — validating 002-silver-gold-baselines

A run and validation guide. Each phase ends with a check you can execute. The test file names are
the ones planned in [plan.md](plan.md); `/speckit.tasks` may refine them. Rules and shapes are in
[data-model.md](data-model.md) and [contracts/](contracts/README.md).

## Prerequisites

- Story 001 working: see `specs/001-base-simulator/verification.md` ("How to run it").
- `.env` copied from `.env.example`, with `POSTGRES_PASSWORD` set. This feature adds
  `REFRESH_INTERVAL_S`, `REFRESH_CLOCK` (`data` for the simulator demo; `wall` is for real
  telemetry) and `SIM_PLANNED_HEADWAY_S` (600) to `.env.example`, with no secrets.
- A fresh database volume, because the new init scripts run only on first start:

```bash
docker compose down -v
docker compose up -d --build          # db, ingestion, api (+ refresh after Phase 4)
```

- Tests create their own throwaway databases (research R10), so the live simulator data never
  enters a test. The `tests` service mounts `./db` read-only for this.

Run the whole suite (Gate 2, coverage > 80 %):

```bash
docker compose --profile tools run --rm tests
```

Run one file during development (coverage gate off):

```bash
docker compose --profile tools run --rm tests python -m pytest src/data/tests/integration/test_silver.py --no-cov -q
```

---

## Phase 0 — Foundations

The R14 simulator fix is first: write its acceptance test, see it fail on the old spacing, then fix
the simulator.

| Check | Command / test | Expected |
|---|---|---|
| Base-case headway (R14) | `src/data/tests/unit/test_simulator_base_headway.py`: `run(seed, 7200)` for seeds 42 and 7, `stop_arrival` events at P-883 ordered by `event_ts`, gaps between consecutive ones | median gap 600 s ± 60 s; no gap below 300 s. The test fails before the fix. |
| Planned headway from configuration | same file | the simulator default (`SIM_PLANNED_HEADWAY_S`, 600) equals the seeded `config.corridor_settings.headway_planned_s`; setting the variable to another value changes the spacing |
| 001 simulator tests updated | whole 001 unit suite, run with the compose `tests` service | green; only tests that depended on the old spacing changed (no event type, field or contract changed; the 001 contract tests still pass) |
| Read models generate cleanly | `make generate-read`, then `git diff --exit-code src/pulsoflota/models/read/` | no diff after a second run |
| Fixtures validate against the read schemas | `src/data/tests/contract/test_read_fixtures.py` | all 18 fixtures valid (draft 2020-12 with format checks), matching the 001 verification |
| Notify payload schema is valid | same test file | `gold_snapshot_notify.schema.json` passes the metaschema check |
| DDL and seed apply | `src/data/tests/integration/test_schema_init.py` | `config`, `silver`, `gold` tables exist; seed values equal FR-034 (600, 2, 0, 0, 18 stops, 5); reference tables equal the CSVs |
| ADR-0001 addendum | `grep -n "config" docs/adr/0001-data-layers-and-ingestion-semantics.md` | the one-line addendum listing `config` as a fourth schema is present; no other line of the ADR changed (`git diff` shows one added line) |

## Phase 1 — Silver current state (US1)

| Check | Test | Expected |
|---|---|---|
| Latest position per bus | `src/data/tests/integration/test_silver.py` | B-101..B-105 each have one row, with the values of their latest `bus_position` (ties by bronze id) |
| Estimated boundary | same | report age 120 s → `live`; 121 s → `estimated`; position unchanged |
| Return to live | same | a new report → `live` in the next build |
| Backend rows ignored | same | a `source = backend` event does not refresh `last_report_ts` |
| Traversal and flags | same | `travel_s = t_arr(i+1) − t_dep(i)`; the Estimated / breakdown flags set by crafted gaps and incidents; no row without the arrival |
| Rebuild equality | `src/data/tests/integration/test_rebuild.py` | drop and recreate `silver`, rebuild at the same `as_of_ts` → identical rows (ordered dump compared) |
| Bronze untouched | `src/data/tests/unit/test_no_bronze_writes.py` + row-count/checksum check | no write statement targets `bronze.`; bronze count and checksum unchanged by a build |

## Phase 2 — Gold console views (US2)

| Check | Test | Expected |
|---|---|---|
| SC-002 fixture scenarios | `src/data/tests/integration/test_gold_fixtures.py` | crafted bronze for `normal`, `c1_bunching`, `d1_source_outage`, `c2_gap`, `c5_breakdown` (5 fixtures) → bus order, `bus_state`, `data_quality`, `status`, `sources_down`, summary counts equal the fixture. `c1_bunching` uses the fixture fixed by T075 (B-102 `headway_ahead_s` 960). |
| FR-011 / edge cases | `src/data/tests/unit/test_classify.py` | Estimated bus and its follower `regular`; two consecutive Estimated buses; thresholds exactly 300 s and 900 s → `regular`; equal distance → 0 and `bunched`; broken-down leader; single bus |
| Headway interpolation | `src/data/tests/unit/test_headway.py` | known histories give the expected pass time; a negative difference is clamped to 0 (R8, DECIDED), and the follower is `bunched` unless FR-011 forces `regular` |
| SC-007 metric | `src/data/tests/unit/test_service_metric.py` | {300, 900} → 375 / 75; 4 × 600 → 300 / 0; no headway → not computable |
| SC-003 D1 timing | `src/data/tests/integration/test_gold_d1.py` | estimated in the first snapshot with age > 120 s (≤ 125 s at a 5 s step); live again after a report; 0 bunched/gap/broken_down attributable |
| SC-004 idempotency | `src/data/tests/integration/test_idempotency.py` | re-ingest the batch → all `duplicate_event`; recompute at the same `as_of_ts` → no new snapshot, identical silver and gold, same `max_bronze_id` |
| Schema validity + lineage | `src/data/tests/integration/test_gold_contract.py` | every stored `doc` validates; every gold row has `rules_version` and `max_bronze_id`; shared `snapshot_id` |
| No data | same | empty bronze → `no_data`, empty buses, zero counts |

Manual check against the live stack:

```bash
docker compose run --rm ingestion python -m src.data.pipeline.compute --as-of "<a UTC time inside the simulated run>"
```

The command prints one JSON line with a `snapshot_id`. `SELECT doc FROM gold.corridor_now WHERE
snapshot_id = '<id>'` returns a schema-shaped object. The simulator's event times start at
2026-11-24 22:00:00Z (17:00 local), so pick a reference time inside the simulated hour.

## Phase 3 — M1/M2 and decision inputs (US3)

| Check | Test | Expected |
|---|---|---|
| SC-006 reference values | `src/data/tests/integration/test_baselines.py` | all 408 M1 and 96 M2 rows carry a source and `n_samples`; `reference` values equal an oracle computed from the CSVs (M1 ±0.1 s, M2 exact, rounded half away from zero, R13) |
| SC-006 observed values | same | with ≥ 5 crafted eligible traversals (or ≥ 5 days of crafted rider arrivals) → `observed` and the median of the samples; flagged traversals are not counted; an even count with an x.5 median (for example {2, 3}) gives 3 |
| M2 sample rule (R12) | same | a band that has not ended, or one with no non-backend `bus_position` in it, is not a sample; a completed band with the simulator running and no riders is a sample of 0 |
| decision_inputs | `src/data/tests/integration/test_decision_inputs.py` | validates against its schema; `buses`/`summary` equal `corridor_now`; 17 forecasts for the hour of `as_of_ts`; window = next 15-min boundary; `reserve_free` = [B-106, B-107] while undispatched; `drivers_free` 2; penalties 0; 18 enabled stops; active incident ids |
| SC-001 60-minute replay | `src/data/tests/integration/test_replay_60min.py` (marked `slow`) | seed 42, 3,600 s simulated, piped through `ingest` into a test DB; `compute --from/--to --step 5 --no-notify` → 100 % of the three objects valid |
| SC-005 full rebuild | `src/data/tests/integration/test_rebuild.py` | after a replay, drop and recreate silver and gold, recompute at the last `as_of_ts` → silver, M1/M2 and that snapshot are identical |

## Phase 4 — Refresh loop with NOTIFY (US4; the loop is not cuttable, only its expensive checks)

Minimum delivery: Phases 0–3 plus T064, T065, T069, T070 and the short T071 check. Rows marked
(CUT-1) can be dropped: failure test, notify test, 10-minute cadence run.

| Check | Test / command | Expected |
|---|---|---|
| No overlap, late tick skipped, failed cycle | `src/data/tests/unit/test_refresh_loop.py` (injected clock and a slow fake cycle) | no concurrent cycles; the tick during the slow cycle is skipped; a fake cycle that raises once is logged and the next tick runs normally (FR-040) |
| Failed cycle (CUT-1) | `src/data/tests/integration/test_refresh_failure.py` | forced error → no snapshot row, no notification, one JSON error line without a traceback; the next cycle succeeds |
| Notify after readable (CUT-1) | `src/data/tests/integration/test_notify.py` | a listener receives exactly one payload per new snapshot; the payload validates against `contracts/gold_snapshot_notify.schema.json`; the snapshot is readable on receipt |
| Clock selector (R3) | `src/data/tests/unit/test_refresh_loop.py` | `data`: `as_of_ts` = max `event_ts` of non-backend bus reports (backend events ignored; wall clock used while there are none); `wall`: current UTC from the injected clock; unset: `wall` |
| SC-009 live cadence (CUT-1; the short T071 check keeps an informal first-minute smoke of about 5 s) | `src/data/tests/integration/test_refresh_live.py` (marked `live`, run with the stack up and `REFRESH_CLOCK=data`) | ≥ 95 % of the intervals between consecutive notifications are 5 s ± 1 s over 10 minutes |
| SC-010 isolation | host commands below | the bronze count keeps growing with `refresh` stopped |

```bash
docker compose stop refresh
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) FROM bronze.events"
sleep 120
docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) FROM bronze.events"   # higher
docker compose start refresh
```

## Done

All phases green, coverage > 80 % (Gate 2), rules in `src/data/rules/` covered close to 100 %
(SC-011), and the gate decisions of 2026-11-18 (R3, R8, R11, R12, R13, R14) implemented as recorded in
[research.md](research.md).
