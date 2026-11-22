# Implementation Plan: Data Fixes and Boarding-Probability Metrics

**Branch**: `feature/005-data-fixes-metrics` (stacked on `feature/004-scenario-injectors`, phases 1–2 committed, head `8351274`; not merged) | **Date**: 2026-11-21 | **Spec**: [spec.md](spec.md) (approved, commit `130b8dc`, Clarifications included: live EWT over a trailing 15-minute window plus per-band additive rows for reports)

**Input**: Feature specification from `/specs/005-data-fixes-metrics/spec.md`

**Note**: `setup-plan.sh` was not executable (permission denied), so it was run with `bash`. It reported the
branch as `005-data-fixes-metrics`; the git branch is `feature/005-data-fixes-metrics`.
`.specify/extensions.yml` does not exist, so no before-plan or after-plan hooks apply. ADR-0006, ADR-0007 and
`docs/data-contract.md` were read from `origin/main` (the local `main` ref is stale; PR #15 is merged there).

**Human gate (data owner, 2026-11-21)**: the three open questions are DECIDED (see [Decisions at the human gate](#decisions-at-the-human-gate)).
The only oracles are the post-US1 numbers; there is no frozen pre-005 reference.

## Summary

Fix six data defects found in the 2026-11-21 review and add the boarding probability, in data only.
(1) The reference build converts the SIMM `FECHAHORA` UTC hour to local hour (UTC−5), so the committed
`congestion_factor.csv` becomes the old file rotated by five rows; the simulator golden hashes change and are
re-recorded. (2) The headway rule takes the leader's departure from the first stop as the moment it "passed" 0 m,
read from `silver.stop_visits`. (3) EWT moves from spatial headways to headways between consecutive departures at
each stop: a trailing 15-minute value in `gold.service_metric` (same columns), a per-stop row for each snapshot
and per-stop additive rows for each closed 15-minute local band. (4) P(board ≤ t) is stored as additive counts per
stop and band and read through documented queries and one view. (5) Ingestion rejects a `bus_position` outside
0–5,119.4 m, and silver treats such a position as "not reporting" so one bad row can no longer fail the cycle.
(6) The data-clock reference time ignores a bus whose latest report is more than 120 s ahead of the median of the
others, and that bus is reported as `estimated`.

**Approach** (from [research.md](research.md)): no new service, no new dependency, no change under `contracts/` or
in any ADR. New derivations are pure functions in `src/data/rules/` (stop headways and sums, boarding waits, clock
guard); pipeline modules read silver and write gold in the cycle transaction, as 002 does. One new init script,
`008_data_fixes_metrics.sql`. Every number below was measured or recomputed on 2026-11-21 with throwaway scripts
(not committed). The oracles are the post-US1 ones: the data owner's mock, re-run on a copy of the repository with the
rotated congestion file, gives +25.8 s (27 intervals) without the hold and +10.6 s (28) with it, and the plan's own
recomputation from raw events matches exactly. Four phases, each ending green and committable on its own; Phase 1 ends
with the data owner's verifier on the regenerated CSV.

## Technical Context

**Language/Version**: Python 3.12+ (unchanged).

**Primary Dependencies**: unchanged. `psycopg` 3, Pydantic V2 (existing generated read models), stdlib `bisect`,
`statistics`, `decimal`. No `pyproject.toml` or `uv.lock` change.

**Storage**: PostgreSQL 16 only. `008_data_fixes_metrics.sql`: one column on `config.corridor_settings`
(`min_stop_headways`, default 5), one column on `silver.stop_visits` (`estimated_at_departure`) plus an index, three
gold tables (`service_metric_stop`, `stop_ewt_band`, `stop_boarding_band`) and one view. Bronze stays insert-only
and untouched. An existing database volume does not re-run init scripts: the file is applied by hand, as 007 was
(see [quickstart.md](quickstart.md)).

**Testing**: pytest + pytest-cov, tests first, throwaway database per module (002 R10). Oracles are independent
recomputations from the raw simulator events (as the data owner's mock does), not from the tables under test.
Gate 2: coverage above 80 % through the unchanged CI-ready command.

**Target Platform**: Linux containers via `docker-compose` (existing `db`, `ingestion`, `api`, `refresh`, `tests`).

**Project Type**: data story inside the existing single Python project (rules, pipeline, ingestion, refresh, reference build).

**Performance Goals** (measured on a throwaway database on the pre-US1 stream, research R12; the post-US1 C1 run has
2,881 events instead of 2,877, so the figures stand): baseline cycle at demo length (C1, 2,700 s,
2,877 bronze rows) median 48 ms, p95 68 ms, max 81 ms. Prototype queries for the new steps add about 17 ms
(4.3 + 6.3 + 3.2 + 3.0 clock). Budget for the finished steps: cycle p95 ≤ 250 ms at demo length (5 % of the 5 s
interval). At 4 simulated hours (15,410 rows) the baseline cycle is 1.27–1.31 s and the prototypes add about 106 ms.

**Constraints**: PostgreSQL only; no new service; bronze insert-only; no change to `contracts/` or to ADR text; no
new event type or field; no LLM and no third party on the path; no wall clock inside rules (the clock guard compares
event times only, FR-063); config via `config` or env with safe defaults and no secrets; ingestion keeps capturing
when reference data is missing (Principle III).

**Scale/Scope**: 1 corridor, 5 + 2 buses, 18 stops (P-883..P-900, route end 5,119.4 m), about 3,831 events per
simulated hour (seed 42, post-US1); a demo run is 2,700 s; per-snapshot stop rows are 18 per snapshot (about 9,700 rows per demo run).

## Key decisions (numbers and where they are justified)

| Decision | Value | Research |
|---|---|---|
| US1 conversion | `local_hour = (UTC hour − 5) mod 24` through `timebands.local_hour_band`; new CSV = old CSV rotated by 5 rows (max difference 0 at 4 decimals); 17 h local 0.5011 → **0.4816**; slowest hour 23 h → **18 h** (0.4575); highest speed factor 03 h local (0.5656) | R1 |
| New golden hashes (dry run, to be recorded on regeneration) | seed 42, 3,600 s: `8bae0e52…690bc` (3,831 lines, 1,433,630 B); seed 7: `27a8206e…d4df7e` (3,844 lines, 1,437,557 B). Old: `51a5e9b3…39e1` / `6bd20707…0132` | R1 |
| Tests that move with US1 | 18: 9 golden-hash tests and 9 tests that pin arrival seconds of the C1 hold run (`test_scenario_injectors` 5, `test_hold_loop` 3, `test_hold_poller` 1) | R1 |
| Oracle policy | **Post-US1 oracles only** (decision 2). 16-minute window P-888..P-900: **+25.8 s (27 intervals) without the hold, +10.6 s (28) with it**; hold saving 15.2 s. No frozen pre-005 reference. Every oracle test runs on the current reference. The data owner's verifier re-runs the mock on the regenerated CSV at the end of Phase 1 and must get exactly these numbers | R2 |
| US2 pass time at 0 m | `pass_time(history, distance, origin_m, departure_ts)`: for `distance ≤ origin_m` return the leader's first-stop departure (from `silver.stop_visits` for the leader's position trip); fallback to the leader's last sample at the origin; never the first waiting sample. Post-US1 oracle (mock): terminal headways 1,240 / 1,835 / 2,440 s become 615 / 595 / 605 s | R3 |
| US3 definition | Per stop, headways between consecutive departures from `silver.stop_visits`, attributed to the **closing** departure; `EWT = Σh²/(2Σh) − Σhp²/(2Σhp)`; corridor = sum of stop sums | R4 |
| Estimated departure | `silver.stop_visits.estimated_at_departure` = the bus's previous report (any of the 3 bus event types, strictly earlier `event_ts`) is more than `ESTIMATED_AFTER_S` = 120 s before the departure; both headways touching it are excluded and counted in `n_excluded` | R4 |
| Live window | `(as_of − 15 min, as_of]` over closing departures (`timebands.WINDOW`); no new setting | R5 |
| Oracle window mapping | 16-minute oracle window (22:28:55, 22:44:55] = 27 / 28 intervals, tested through the pure rule with an explicit window. Live trailing 15 min = 25 / 27 intervals (+21.0 / +1.8 s on P-888..P-900; 33 / 35 intervals, +17.6 / +2.8 s on all 18 stops). Band rows are checked against the same oracle grouped by band: band 69 = 6 / 5, band 70 = 25 / 27 intervals | R5 |
| Minimum sample | `config.corridor_settings.min_stop_headways = 5` (same as M1 `min_sample_count`); below it the corridor row has `computable = false` and null values. Re-checked on the post-US1 stream: +7.5 s at n = 1, +151.6 s at n = 3, +124.0 s at n = 4, +104.8 s at n = 5; the value stays between +99.8 and +127.8 s for n = 4 to 17 | R6 |
| Band tables | `gold.stop_ewt_band` (closed bands, sparse) and `gold.stop_boarding_band` (every band with riders, including the open one); key (`local_date`, `band`, `stop_id`); replaced every cycle with the cycle's lineage; column names follow H4 (`sum_headway_s`, `sum_headway_sq_s`, `sum_planned_s`, `sum_planned_sq_s`) | R7 |
| US4 method | Next departure of any bus from the rider's stop, `departure ≥ arrival` (wait 0 counts), `departure ≤ as_of`; open riders count in `n_riders` only; riders of stops outside `config.ref_stops` count nowhere | R8 |
| US4 oracle (post-US1 stream, spec definition: open riders in `n_riders`, as_of 22:44:55Z) | band 68: 9 riders, 3 / 9 / 9; band 69: 16 riders, 10 / 16 / 16; band 70: 21 riders, 9 / 14 / 15 (open riders: 6). 46 riders, 37 at P-883 (80.4 %). The mock counts departed riders only (band 70: 15 riders, 60 % / 93 %); the spec governs (decision 3) | R8 |
| US5 ingestion | `value_out_of_range` when `distance_along_m` is above `max(config.ref_stops.distance_along_m)`; read through the ingestion connection, cached after success, retried at most every 5 s after a failure, fail-open (accept) while unreadable | R9 |
| US5 pipeline | Silver ignores out-of-range positions (history, state, waiting test) and marks a bus `estimated` while its newest position is out of range. The measured failure is the read schema bound (`distance_along_m ≤ 5119.4` in `CorridorNowV100`), not a missing stop | R10 |
| US6 clock guard | `rules/clock.py`: per bus the newest report by arrival (`id`); a bus is untrusted when its newest event time is more than 120 s ahead of `median_low` of the others'; fewer than 2 buses reporting: newest unfiltered, nobody untrusted; the set goes to silver as `untrusted_buses` and those buses become `estimated` | R11 |
| Cycle time | New steps budget ≤ 100 ms at demo length (prototypes 17 ms); cycle p95 ≤ 250 ms; 4 h stress ≤ 1.5 s | R12 |
| Rules version | `RULES_VERSION` 1.1.0 → 1.2.0 (P1) → 1.3.0 (P2) → 1.4.0 (P3) → 1.5.0 (P4); one bump per phase that changes a derivation | R13 |
| New config / env | `config.corridor_settings.min_stop_headways` (default 5). No new environment variable | R6, R9 |

## Constitution Check

*GATE: evaluated before Phase 0; re-checked after Phase 1 design (below).*

Constitution v1.2.0; turn 1 active (`docs/turns-ritmo.md` §3). The five Core Principles apply; other norms only as
adopted in §3.2. Read from `.specify/memory/constitution.md` and `AGENTS.md`.

| Principle | Status | Evidence |
|---|---|---|
| **I. Risk-First Order** | PASS | Disciplined lane, turn-1 Level 1 risk (data integrity). Every item protects the metric or the cycle: a shifted congestion factor, a false gap, an EWT that reads "better than planned" during bunching, a bad position that blinds the dispatcher, a future-dated event that moves the clock. No adaptive-lane feature (no endpoint, no console, no decision engine). Phase order puts the metric definitions (P1–P3) before the guards (P4), as the spec ranks them. |
| **II. Contract-First & Data Ownership** | PASS | Interfaces are written before code in [contracts/](contracts/README.md): the gold tables and read queries, the guards, the reference build. Each new table has an owner (data) in [data-model.md](data-model.md). Nothing under `contracts/` and no ADR line changes (SC-014); the range bound comes from reference data, not from the schema. The list of documents that will need the data owner's later contract step is in [contracts/README.md](contracts/README.md). |
| **III. Isolated Ingestion & Deterministic Real Time** | PASS | Ingestion gains one read of `config.ref_stops` and is fail-open: if the bound cannot be read it keeps capturing (FR-051). No call to the web, an LLM or a third party. The clock guard uses only event times (no wall clock, FR-063). All new derivations are deterministic code; the cycle stays far inside the 5 s interval (R12). |
| **IV. Unbreakable Human Gate** | PASS | Nothing here issues, approves or executes an action. The rules only make the inputs of recommendations (EWT, headway, state of a bus) correct. An untrusted or unplaceable bus is `estimated`, which classification already treats as "no alert". |
| **V. Test-First & Automated Gates** | PASS | Each phase starts with failing tests ([quickstart.md](quickstart.md)); each defect has a regression test that fails on the unfixed code (FR-001). Coverage stays above 80 % through the unchanged CI-ready command; the new pure rules aim at near 100 % (CODEOWNERS review applies to `src/data/rules/`). |

**Turn-1 adopted norms (§3.2)**: RNF-3.2.1 / 3.2.2: PASS, no service added. RNF-3.3.1 (boundary validation of 100 %
of packets): reinforced by the range check, `value_out_of_range` is an existing reason. RF-2.1 / RF-2.2: the
corrected EWT and headway feed them. Gate 1 (schema validation only): PASS, new gold tables are typed and checked;
the read objects are still built through the generated models. Gate 2: PASS. Gate 4 (human approval): unchanged.
Security baseline: parameterized SQL only, no secrets, JSON log lines without stack traces.

**Deferred norms (Evolution, not blocking)**: Redis, PostGIS, 1,000 events/s, SAST/SCA, RBAC, HMAC, secret manager,
route diversion. Story-level evolution: FIFO P(board ≤ t) with capacity, planned headway by hour, history and report
layer H1–H4, performance of the cycle (H-8), backward position jumps (H-6), unknown stop ids (H-7).

**Post-design re-check**: PASS, with these points checked explicitly.

1. `config` gains one column on an existing settings table. ADR-0001's addendum allows "settings and reference data only".
2. `silver.stop_visits` gains a derived column. Silver is deleted and rebuilt every cycle, so the change loses no data.
3. `RULES_VERSION` changes four times. Snapshot ids hash the version; tests that pin `"1.1.0"` (`test_rules_version.py`)
   are updated per phase; the baseline tests already read the constant.
4. The `contracts/` JSON Schemas and ADR text are unchanged. `gold.service_metric` keeps its columns; only the
   definition changes. This is the main impact for the data owner (see contracts/README.md).
5. The per-snapshot table has a foreign key to `gold.snapshots`; the test helpers that delete snapshots must delete it first (listed in R14).
6. Decisions at the human gate change nothing in the gates: no frozen fixture or substitution helper is added (less test
   surface, Principle V unchanged), the lost-departure limit is recorded as turn-1 evolution, and the Phase 1 exit gains a
   human check by the data owner's verifier (supports Gate 4's explicit-approval intent; it does not replace any gate).

## Phases

Each phase starts with failing tests, ends with the whole suite green, and is one commit (the commit is made by the
user, not by the agent). Time is agent time; the total is 6.0 h.

| # | Phase | Stories | Time | Exit criteria |
|---|---|---|---|---|
| 1 | Reference hour and terminal headway | US1 + US2 | 1.25 h | 24 factors equal the rotated old file (one-off check against the file in git, recorded in `verification.md`) and the independent recomputation from raw; new golden hashes recorded; the 9 time-pinned 004 tests re-pinned; C1 seed 42 snapshots at 22:20:40, 22:30:35, 22:40:40 have headway 300–900 s (615 / 595 / 605 s); `RULES_VERSION` 1.2.0. **Data owner's verifier:** the mock re-run on the regenerated CSV gives exactly **+25.8 s (27 intervals)** without the hold and **+10.6 s (28)** with it, slowest hour 18 h and the hold at P-887 from 17:27:45 to 17:29:15 local |
| 2 | Stop-based EWT | US3 | 2.25 h | stop EWT equals the independent oracle on the current reference: +25.8 s (27) / +10.6 s (28); live and band rows match the oracle exactly; `gold.service_metric` keeps its columns; cycle p95 ≤ 250 ms; `RULES_VERSION` 1.3.0 |
| 3 | P(board ≤ t) | US4 | 1.0 h | counts equal the oracle on C1 (bands 68 / 69 / 70 = 9 / 16 / 21 riders) and the base case; a rider without a departure is in no `n_board_le_t`; two rebuilds identical; `RULES_VERSION` 1.4.0 |
| 4 | Guards | US5 + US6 | 1.25 h | 99,999 m rejected through ingestion and, inserted straight into bronze, the cycle still writes a snapshot; a 2030 event leaves `as_of_ts` in the simulated day; `RULES_VERSION` 1.5.0; `verification.md` closed |
| | Verification notes | all | 0.25 h | `verification.md` with old and new hashes, oracle table, cycle times, coverage |

Phase detail (what each phase touches, in order; tasks come later with `/speckit.tasks`):

1. **Phase 1.** Write: a committed-CSV test (24 rows, 17 h = 0.4816, slowest 18 h, 03 h highest), the `build.py`
   conversion test (skips without `data/raw/`, as the existing build tests do), `pass_time` unit tests with a
   waiting leader, the integration test on C1 seed 42. Then: `build.py`, regenerate and commit the CSV,
   `SOURCES.md`, `headway.py`, `gold.py` (first-stop departures), the golden-hash test and the nine re-pinned tests.
   Last: hand the regenerated CSV to the data owner's verifier (the mock, no database needed; command in
   [quickstart.md](quickstart.md)). Phase 1 is not closed until it prints +25.8 s (27) and +10.6 s (28).
2. **Phase 2.** Write the pure-rule tests, the oracle module and the gold
   integration tests (they fail: the tables do not exist). Then: `008` (config column, `stop_visits` column and index,
   `service_metric_stop`, `stop_ewt_band`), `silver_stop_visits.sql`, `rules/stop_metrics.py`,
   `rules/service_metric.py` (rewritten), `pipeline/stop_metrics.py`, `gold.py`, `cycle.py`; update `test_gold_contract`,
   `test_schema_init` and the table lists of the test helpers.
3. **Phase 3.** Write `rules/boarding.py` tests and the oracle comparison; then the rule, `stop_boarding_band`,
   the view and the read-query tests.
4. **Phase 4.** Write the guard tests (ingestion range, silver unplaceable position, clock guard with 0, 1, 2 and 5
   buses, exactly 120 s and 121 s). Then: `route_bounds.py`, `bronze.py`, `validate.py`, silver SQL, `silver.py`,
   `cycle.py`, `rules/clock.py`, `refresh/run.py`.

## Project Structure

### Documentation (this feature)

```text
specs/005-data-fixes-metrics/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0: decisions with numbers (R1–R14)
├── data-model.md        # Phase 1: tables, columns, derivations, state rules
├── quickstart.md        # Phase 1: validation scenarios and commands
├── contracts/
│   ├── README.md              # index + impacts for the data owner's later contract step
│   ├── gold-stop-metrics.md   # new gold tables, view and read queries
│   ├── guards.md              # ingestion range check, silver unplaceable position, clock guard
│   └── reference-congestion.md  # US1 build rule, regeneration and hash procedure
├── checklists/requirements.md
├── verification.md      # created during implementation (not by this command)
└── tasks.md             # /speckit.tasks (NOT created by this command)
```

### Source Code (repository root)

```text
data/reference/congestion_factor.csv         # P1: regenerated (rotated by 5 rows)
data/reference/SOURCES.md                    # P1: FECHAHORA is UTC, converted to local hour

src/data/
├── db/init/008_data_fixes_metrics.sql       # P2–P3: new (config col, silver col + index, 3 gold tables, 1 view)
├── reference/build.py                       # P1: local-hour conversion
├── reference/sources.py                     # P1: the sentence that generates SOURCES.md ("by UTC hour")
├── rules/
│   ├── __init__.py                          # RULES_VERSION bumps; MIN_BUSES_FOR_CLOCK_GUARD, BOARDING_THRESHOLDS_S
│   ├── headway.py                           # P1: origin pass time
│   ├── service_metric.py                    # P2: rewritten over sums (old spatial function removed)
│   ├── stop_metrics.py                      # P2: new, stop headways and additive sums
│   ├── boarding.py                          # P3: new, rider waits and counts
│   ├── clock.py                             # P4: new, trusted reference time
│   └── sql/
│       ├── silver_stop_visits.sql           # P2: estimated_at_departure
│       ├── silver_position_history.sql      # P4: in-range positions only
│       └── silver_bus_current_state.sql     # P4: valid position, estimated flags
├── pipeline/
│   ├── gold.py                              # P1: first-stop departures; P2: stop metric rows and corridor row
│   ├── stop_metrics.py                      # P2–P3: new, band rebuilds and snapshot rows
│   ├── silver.py                            # P4: untrusted_buses parameter
│   └── cycle.py                             # P2–P4: band rebuild step, untrusted_buses parameter
├── ingestion/
│   ├── route_bounds.py                      # P4: new, cached bound read
│   ├── validate.py                          # P4: range predicate
│   └── bronze.py                            # P4: reject with value_out_of_range
├── refresh/run.py                           # P4: resolve_clock, log field
└── tests/
    ├── fixtures/oracle_stop_metrics.py                    # P2–P3: independent oracle from raw events
    ├── unit/   test_headway.py, test_service_metric.py, test_stop_metrics.py, test_boarding.py,
    │           test_clock_guard.py, test_reference_build.py, test_simulator_golden_hash.py,
    │           test_scenario_injectors.py, test_refresh_loop.py, test_rules_version.py, test_route_bounds.py
    └── integration/ test_terminal_headway.py, test_stop_ewt_gold.py, test_stop_boarding_gold.py,
                     test_range_guard.py, test_clock_guard_refresh.py, test_gold_contract.py, test_schema_init.py,
                     test_hold_loop.py, test_hold_poller.py, test_scenarios_gold.py (table lists)

src/pulsoflota/config.py, .env.example, docker-compose.yml   # unchanged (no new environment variable)
contracts/, docs/adr/                                        # unchanged (SC-014)
```

**Structure Decision**: single Python project, same layout as 002–004. Pure rules in `rules/`, orchestration in
`pipeline/`, SQL for silver and for set-based reads, Python for the stop headways and boarding waits because they are
unit-testable without a database and use the one `timebands` offset (no second copy of UTC−5 in SQL).

## Complexity Tracking

No Constitution Check violation. Two choices add surface and are justified in research:

| Addition | Why needed | Simpler alternative rejected because |
|---|---|---|
| `silver.stop_visits.estimated_at_departure` (R4) | FR-032 needs "estimated at departure"; the departure event itself is a report, so the literal freshness rule is always false at that instant. The flag uses the gap before it. | Computing it in gold from bronze would make gold read bronze for a per-row fact; silver already owns freshness (`bus_current_state`, `segment_traversals.travelled_while_estimated`). |
| Arrival-order (`id`) latest report in the clock guard (R11) | US6.4 requires the bus to return to `live` after a valid report, while a 2030 event stays in bronze forever. Event-time "latest" would keep it untrusted. | Ordering by event time never clears the flag. |

## Risks

| Risk | Likelihood / size | Mitigation |
|---|---|---|
| US1 changes the stream: 18 tests move and the demo numbers change (the same 16-minute window now gives +25.8 / +10.6) | Certain; measured | Phase 1 re-pins the nine time-pinned tests; every oracle is post-US1 (decision 2); the data owner's verifier checks the regenerated CSV at the end of Phase 1, so a wrong regeneration is caught before Phase 2 builds on it |
| `spec.md` (SC-006, US3 scenarios 1–2, A-2) and `checklists/requirements.md` still quote the pre-US1 review numbers | Certain; found while applying decision 2 | The spec is approved and outside this update. The data owner amends those lines to +25.8 / +10.6 s before the Phase 2 test is written; the plan treats the post-US1 numbers as governing |
| A departure lost while a bus is silent (D1) inflates a stop headway; one lost departure in a window of 25 intervals adds about +24 s. **Accepted as a turn-1 limit** (decision 1) | Medium; arithmetic | Recorded in research R4. The silence shows as the bus being `estimated` (`sources_down`); a headway touching a departure reported after a gap of more than 120 s is counted in `n_excluded`. The lost departure itself leaves no row, so it is not counted. No bracket rule; kept as Evolution |
| The last band's P(board ≤ t) is lower than the mock's table because open riders count in `n_riders` (band 70: 42.9 % vs 60 % at ≤ 5 min; 66.7 % vs 93 % at ≤ 10 min) | Certain; measured | The spec definition governs (decision 3); reports read only `final` bands; the view exposes `closed` and `final` |
| P(board ≤ t) barely discriminates (80.4 % of riders at P-883 where departures are regular; finding O-1) | Certain | Per-stop values are provided with the corridor value; limitation documented; the demand model is not touched |
| Existing tests ingest positions above 5,119.4 m and start failing once ingestion rejects them | Low | Checked: the five timeline builders peak at 4,320 m and the simulator at 5,119.4 m; the full suite runs at the end of Phase 4 |
| Baseline cycle grows linearly with bronze: 1.28 s at 15,410 rows, so about 60,000 rows (about 16 simulated hours) reach 5 s | Known (H-8, out of scope) | Not touched; recorded in `verification.md` so 006 does not assume a day-long run |
| A database volume created before this story lacks the new objects | Certain on existing volumes | `008` is idempotent; apply by hand (quickstart); the refresh service logs `cycle_failed` until applied |

## Decisions at the human gate

Data owner, 2026-11-21. Nothing is left open.

1. **DECIDED. Lost departures during a silence: accepted as a turn-1 limit.** No silence-bracket rule is added (the
   +0.5 h of Phase 2 is not spent). The limit is recorded in research R4 and in the read contract. It stays visible through
   the estimated-bus count (`sources_down`) and `n_excluded` (which counts headways touching a departure reported after a
   gap of more than 120 s; a departure that was never reported leaves no row and cannot be counted).
2. **DECIDED. Oracle numbers: the post-US1 oracles are the only oracles.** Source: the data owner's mock re-run on a copy
   of the repository whose `congestion_factor.csv` is the old file rotated (new hour `h` = old hour `(h + 5) mod 24`),
   `resultados-post-us1.md`, confirmed by the plan's own recomputation from raw events. The frozen pre-005 reference
   (`fixtures/reference_pre005/`, `frozen_reference.py`) is removed from the plan together with every test and step that
   used it. Phase 1 exit gains the data owner's verifier: the mock on the regenerated file must give exactly +25.8 s (27)
   and +10.6 s (28). The demo text uses the post-US1 numbers.
3. **DECIDED. Open riders: the spec governs.** A rider without a departure counts in `n_riders` (A-7). Reports read only
   bands marked `final`. The mock's departed-riders-only percentages are not oracles for band 70.

## Evolution (deferred, not designed here)

FIFO method with capacity and rejections; planned headway by hour (A-10); history and report layer H1–H4 built on
these sums; per-operator split; EWT percentiles P85 / P95 over band rows; cycle performance (H-8); backward
position jumps and unknown stop ids (H-6, H-7); a silence-bracket exclusion for lost departures (decision 1).
