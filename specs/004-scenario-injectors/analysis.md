# Pre-implementation analysis — 004-scenario-injectors

Produced by Kiro `validate-plan` on 2026-11-21. Read-only analysis of spec `d7d674f`, plan `d76fd7f` and tasks `902db1a` (branch `feature/004-scenario-injectors`), plus research, data-model, contracts and quickstart, against constitution v1.1.0 and `docs/turns-ritmo.md` (turn 1). Only this file and `checklists/pre-implementation.md` were written. `.specify/extensions.yml` does not exist, so no hooks ran. `check-prerequisites.sh` is not executable (permission denied); it was run with `bash` and returned the feature directory with `research.md`, `data-model.md`, `contracts/`, `quickstart.md` and `tasks.md`. No commit, no push, no build, no compose command was run.

**Decision: GO, with four conditions.** 0 CRITICAL. Phase 1 can start (T001 to T003 do not depend on any finding). H1 and H2 must be settled before T004 and T012 are written, H3 before T026, and H4 before the first live step (T024 or T025). All four need an edit to approved artifacts, which this gate does not make; they need your OK.

## Findings

Counts: 0 CRITICAL, 4 HIGH, 8 MEDIUM, 7 LOW. Line numbers are from `cat -n` / `grep -n` of the committed files.

### HIGH

- **H1. The `RULES_VERSION` bump to 1.1.0 breaks two assertions of the 002 acceptance tests, and no task edits them** (`plan.md:134`, `research.md:R8`, `tasks.md:50` (T012), `:61` (T020), `:62` (T021), `:72` (T025)).
  - Plan and research say "one existing test pins `1.0.0`". The pin is in two places: `src/data/tests/unit/test_rules_version.py:17` (listed in T012) and `src/data/tests/integration/test_baselines.py:92` and `:159` (`assert rules_version == "1.0.0" and max_id == ...`, the M1 and M2 baseline acceptance tests of story 002). The latter are not in T012.
  - Consequence: T020 sets 1.1.0, then T021 states "the 002 and 003 acceptance tests stay unchanged and green" and T025 requires 0 failed. Both would fail on `test_baselines.py`. Editing a 002 acceptance test is also what the user asked to avoid ("so the 001–003 acceptance tests stay green").
  - Fix: add `test_baselines.py:92` and `:159` to T012 (change only the expected version, ideally to `RULES_VERSION` imported from the package so the next bump needs no edit), correct `plan.md:134` and R8, and add the file to the Phase 1 allowed list of the Untouched check. A one-line note in `verification.md` that an existing acceptance test changed only its pinned version.

- **H2. `end_ts = 'infinity'` cannot be read by the Python pipeline and cannot be subtracted in SQL; T021, T004 and the test helper will fail on the very case the fix introduces** (`research.md:318`, `:328`; `tasks.md:42` (T004), `:55` (T014), `:62` (T021); `src/data/tests/fixtures/silver_support.py:62`).
  - Measured here: `psycopg` 3 raises `DataError: timestamp too large (after year 10K)` when it loads `'infinity'` for `timestamptz`, in text and in binary format. Any `SELECT end_ts` from `silver.incidents` that returns the open-ended row into Python fails.
  - R6 maps `duration_s = (end_ts − start_ts)`. On PostgreSQL 16 (`docker-compose.yml:36`, `postgres:16.11`) subtracting an infinite timestamp is expected to raise an error ("cannot subtract infinite timestamps"; infinite intervals only arrive in 17). T021 says "duration_s = minutes × 60 (null for open-ended)" but `silver.incidents` has no minutes column (`004_silver.sql:17-26`), so the value must come from `end_ts − start_ts`.
  - T004 (b) asserts `end_ts = 'infinity'` and the test builders read silver through `silver_support.py:62` (`SELECT * FROM silver.incidents`), which would raise on that row.
  - The readers that compare only (`silver_bus_current_state.sql:91-93`, `silver_segment_traversals.sql:52-55`, `gold.py:168`) are safe, as R6 says.
  - Fix: state in R6/T021 that `pipeline/incidents.py` computes `duration_s`, `until` and `active` in SQL (`CASE WHEN isfinite(end_ts) ...`) and never selects raw `end_ts`; make T004 assert with `end_ts = 'infinity'::timestamptz` or `isfinite(end_ts)` in SQL; note the `silver_support.py` helper needs the same care. T010's open-ended case will catch it, but only after T014 has shipped a fix that moves the failure from the silver insert to the gold step.

- **H3. The 90 s hold cap is said to be enforced by the generated model at load, and the generated model does not enforce it** (`research.md:222`, `:233`; `data-model.md:72`; `contracts/hold-loop.md:37`; `tasks.md:88` (T026), `:105` (T040)).
  - `contracts/read/recommendation.schema.json` limits hold `duration_s` to 0..90 only through `if/then/else`. Measured: `datamodel-codegen` with the project options produces `duration_s: float | None` with no bounds (output checked in `/tmp`, not in the repository). `jsonschema` is a dev extra (`pyproject.toml:24`), not a runtime dependency (R13 adds none), so the simulator in the image has no schema validator either.
  - So "rejected at load" (R4.2, E3, hold-loop.md) is false as written, and T026's raw 120 s entry "that the schema must reject (the range is checked at load)" has no implementation task behind it. Only the executor defense (`MAX_HOLD_S`, R4.2 line 233) and `observe` (`hold_s <= 90`, R5) work.
  - There is also a spec conflict between two paths. Rejected at load gives an unknown `rec_id`, "ignored and counted", and no `instruction_status` row. AC5 (`spec.md`, US2 scenario 5) and SC-007 want the hold refused and the instruction reported `not_executed`.
  - Fix: pick the AC5 path. The loader must not drop the entry; the order builder refuses it (`hold_order_refused`, `over_cap`) and data reports `not_executed`. Add the explicit range check (constant `MAX_HOLD_S`) to T040, change T026 to say the 120 s entry loads and is refused, and correct the three sentences above.

- **H4. Live checks rely on an exported project variable surviving across separate commands; a bare `docker compose down -v` would hit the default stack** (`tasks.md:19`, `:68` (T024), `:72` (T025), `:97` (T035), `:113` (T045), `:144` (T055)).
  - T024, T025, T045 and T055 write `export COMPOSE_PROJECT_NAME=pulsoflota-verify && docker compose down -v`, then later "finish with `docker compose down -v` (still `pulsoflota-verify`)". When an implementer runs these as separate shell calls (the usual case for an agent, and the case for `cd` in this environment), the variable is gone and the second `down -v` deletes the developer's default `db_data` volume. That is the loss the user asked to rule out.
  - T068 does it right (`COMPOSE_PROJECT_NAME=pulsoflota-demo docker compose down -v` inline). T035 says the live part runs "under `pulsoflota-verify` only" but does not require the guard that the 003 live tests have (`test_ingestion_outage_live.py:43-44`: skip unless `COMPOSE_PROJECT_NAME == "pulsoflota-verify"`); T059 has the guard, T035 does not.
  - Fix: write every destructive or stack-changing command with `-p pulsoflota-verify` (or the inline variable prefix) and add the 003 skip guard to T035. Same convention as T068.

### MEDIUM

- **M1. The step-0 visibility of pre-written decisions has no mechanism in the tasks** (`research.md:217`; `tasks.md:105` (T040), `:109` (T044), AC7 in `spec.md`). R4.1 says a daemon thread polls every `SIM_HOLD_POLL_S`; R4.1 (last bullet) says with a pre-written decision "the order is known from step 0". At `SIM_PACE_S=0` (all the integration tests) a thread started at the same moment races the first steps, and the run is not deterministic. T040 does not say the poller does one synchronous poll (bounded by the 2 s timeouts) before the first step. Add that to T040 and a test in T032/T034 for it, with the note that the initial poll is the only blocking call and happens before the first event.

- **M2. Phase 4 has no allowed-file list, and T067 omits the Untouched check** (`tasks.md:20`, `:177` (T067), `:179` (T069)). The convention says the check is "identical in every phase verification task"; Phases 1 to 3 carry a list, T067 carries none, and T069 compares the whole feature "against the four phase lists". Files that only Phase 4 touches (`scripts/demo/**`, `src/data/simulator/scenarios/demo.json`, `src/data/seeds/recommendations.json` edit in T061, `.gitignore` in T064, `tests/unit/test_demo_script.py`, `test_demo_scenario.py`) are in no list, so the check would flag them as "reported, not accepted". Add the Phase 4 list to T067.

- **M3. The static "no write to bronze" guard does not scan the simulator, so FR-003 has no dedicated guard** (`tasks.md:98` (T036); `src/data/tests/unit/test_no_bronze_writes.py:14`). `SCANNED` is `rules`, `pipeline` and `refresh`. T036 says the new files "fall under the scanned folders"; that holds for `rules/holds.py`, `pipeline/*.py`, `hold_orders.sql`, but not for `src/data/simulator/scenarios/*` (the poller and the injectors). T032 scans the poller module only. FR-003 ("an injector MUST NOT write to bronze, silver or gold directly") is covered only by behavior in T011. Add the `scenarios/` package to a static scan (poller included, with an allowed `SELECT`).

- **M4. FR-023's text and the plan's reading differ, and the spec was not amended** (`spec.md:159`, `:210`; `research.md:32-39` gate decision 2, R7). Spec: `headway_after_s` is "at the target stop after the horizon elapsed". Plan and T047: the held bus's `headway_ahead_s` in the first snapshot at or after `T0 + horizon_s`, with `ewt_observed_s` clamped at 0 (FR-024 says nothing about clamping). This is a recorded data-owner decision, so it is not a blocker, but spec, plan and tasks now disagree in words. Record the deviation and the clamp in `verification.md` (T069) as a spec-reading note, and in the open items for the backend owner (a consumer reading the effect row will assume "at the stop").

- **M5. The null-duration scope addition is in research and tasks only; the spec still says it cannot happen** (`spec.md:107`, `:154`; `contracts/read/command_event.schema.json:91-95`; `docs/adr/0003...` gate decision 3). The spec edge case says the write contract requires a numeric `duration_min`. That is true for `contracts/turn1-events/incident_report.schema.json:20-23` but not for the backend `command_event` incident payload, which allows `null` (ADR-0003 gate 3). FR-021 defines active as "event time plus its duration" and has no open-ended case. T004 and T014 trace to FR-021, FR-026, SC-012 and R6, which satisfies "traces to a research decision", but the behavior (a dispatcher breakdown with unknown duration keeps the bus `broken_down` indefinitely) is a visible product decision. Add it to the CODEOWNERS review list in T069 with that consequence spelled out.

- **M6. The Gate 4 / Principle IV claim for the demo is stronger than the evidence** (`plan.md:117-119`, `tasks.md:169` (T062), `:178` (T068)). Plan: "Gate 4: the explicit approval step is exercised by the demo". The approval in the demo is `approve_hold.py` writing the `decision` row at a fixed simulated time inside `run_demo.sh`; no person approves. Principle IV is enforced from the data side and tested (no decision, no hold: T034), and the data owner approved the stand-in (gate decision 1), so this is not a violation. But `verification.md` and the demo output should say plainly "stand-in for the dispatcher's click; Gate 4 human approval evidence is deferred to the backend/console integration", and `approve_hold.py` should write a recognizable demo `user_id`.

- **M7. FR-005's consistency clause has no assertion** (`spec.md:132`; `tasks.md:44` (T006), `:49` (T011)). FR-005 requires "buses do not overlap or pass each other without an event trail; capacity 40 and the base rules keep holding". R1 argues the ranges (`extra_s <= 600`, `duration_s <= 300`) keep the follower behind and the model has no overtaking rule, but no test checks order preservation or capacity after an injection. Add one assertion to T006 or T011: after each world injector the distance order of buses never inverts and no bus exceeds 40 passengers.

- **M8. The edge case "effect window spans a data fault" has no named test** (`spec.md:108`, `research.md:R7` "Null if ... Estimated there", `tasks.md:130` (T047)). T047 covers a missing snapshot and a non-computable EWT, not a held bus that is Estimated or silent at the "before" or "after" snapshot (D1(a) on the held bus also drops its `stop_arrival` and `stop_departure`, so no visit exists and the order should end `not_executed` at `expires_ts`, R5). Add that case to T047 and T033.

### LOW

- **L1. Stale budget sentence** (`plan.md:258`): "Time estimates ... sum to the 4–5 hour budget". The phase estimates are 2 h + 1 h 30 + 45 min + 1 h = 5 h 15 min, plus 20 min margin = 5 h 35 min (`research.md:510-525`), which the plan's own table and `tasks.md:229` state correctly. Wording only.
- **L2. The Red rule has two unlisted exceptions** (`tasks.md:17`, `:47` (T009)). Only the golden-hash test is declared an exception; T009 (static guard) cannot be seen failing (quickstart `quickstart.md:47` says "passes once the package exists"). Add T009 to the exception in the Red rule.
- **L3. The 003 baseline numbers were not re-measured here** (`tasks.md:36` (T001), `quickstart.md:11`): 434 passed, 4 skipped, 91.97 %. T001 records them at implementation. The golden hashes were measured: seed 42 gives `51a5e9b3…39e1` and seed 7 gives `6bd20707…b0132` on the current engine, equal to T002's pins (`tasks.md:37`).
- **L4. T009's guard scope** (`tasks.md:47`): scans `rules`, `pipeline`, `refresh`, `ingestion`. FR-010 also says the truth is not reachable from the read contract; `src/pulsoflota/` (API) is not scanned. Add it.
- **L5. D1(a) at 120 s or less** (`spec.md` edge case, `tasks.md:43` (T005)): T005 checks the config accepts it; no check that the bus does not become Estimated. The 002 rule is already tested; one assertion in T011 closes the edge.
- **L6. Poller lock discipline** (`research.md:R4.1`, `tasks.md:94` (T032), `:97` (T035)): "the engine never waits for it" is not asserted for a database that accepts the connection and then stalls. Add a unit assertion that the board lock is not held during I/O.
- **L7. Evolution (not blocking, per `docs/turns-ritmo.md` §3.3):** the poller's "read-only" is a session setting on the same DSN as ingestion, not a SELECT-only role; a role split belongs with RBAC and the secret manager (turn 2). The demo uses `.env` for the database password, as stories 001 to 003 do (secret manager deferred). No deferred norm is implemented in this story.

## Gate decisions and scope: reflection check

| Decision | Where it is reflected | Result |
|---|---|---|
| Q1 = A, simulator polls bronze read-only (`spec.md:114`, FR-017 `:147`) | R4.1; T032, T040 (own connection, `default_transaction_read_only`, 2 s timeouts, DB down keeps stream); `hold-loop.md` | Consistent. M1 (step-0 poll), L6, L7. |
| Q2 = C, seeded recommendations keyed by `rec_id`; contract gap open (`spec.md:115`, `:118-120`, FR-018 `:148`) | R4.2, E3; T026, T039, T061; open item in `hold-loop.md:63-67` and T069 (4) | Consistent. H3 (cap enforcement premise). |
| Q3 = B, no reserve dispatch (`spec.md:116`, FR-029 `:168`) | R9, R11; T058 (B-106/B-107 never emit), T068, T069 | Consistent. |
| Stand-in decision script | gate decision 1; T062, T063; not under `src/` (T057) | Consistent. M6 (wording of Gate 4 evidence). |
| After headway at the held bus, observed EWT clamped at 0 | gate decision 2; R7; T047, T053 | Consistent with plan; differs from spec text (M4). |
| Instruction status keyed by `rec_id` | gate decision 3; E7; T033, T043; open item T069 (4) | Consistent. |
| `RULES_VERSION` 1.0.0 → 1.1.0 | gate decision 4; R8; T012, T020 | Inconsistent: H1 (two more pins). |
| Null duration = open-ended, `end_ts = 'infinity'` | gate decision 5; R6; T004, T014, T021 | Design sound for the readers that compare; H2 for the readers that select or subtract; M5 (spec silent). |
| C2 live check on the cut list | `tasks.md:68`, cut table `:219-227` | Consistent. |

## Base case unchanged

- T002 (`tasks.md:37`) is written green on the untouched engine, pins both hashes (verified here), and the next engine-touching tasks (T018 `:59`, T019 `:60`, T041, T027) name it. "No edit to `engine.py` or `main.py` may precede" T002 is stated in T002 and in the dependency order (`tasks.md:189`). The `[]` file case (T019) and `--holds on` against an empty bronze (T027) extend the identity check.
- The compliance draw uses `hashlib` and not the main RNG (R4.3, T029), so the hold feature cannot shift the base stream. After a world injection the stream legitimately differs (R1, risk 2); the same file gives the same bytes (T008, T023).
- Existing-test impact beyond H1: compose tests assert keys, not whole environments (`test_compose_ingestion.py:16-19`), so the new `${VAR:-}` entries are safe; `test_env_example.py`, `test_schema_init.py`, `test_generated_read_models.py` are in T012/T036/T048.

## Isolation, truth and safety

- **Poller never blocks the stream; ingestion never depends on the backend:** thread, own connection, board read is a dictionary lookup, DB down means no new holds (R4.1, T030, T032, T035). `ingestion` keeps `depends_on: {db}` only. Gaps: M1, L6, H4 (guard in T035).
- **Hidden truth never read by the pipeline:** file or stderr, outside every schema (R2); T009 static guard, T011 deletion/alteration test (AC9). Gap: L4 (API not scanned).
- **No change to `contracts/`, ADR lines, bronze definitions, `bronze.py`, `validate.py`, `.github/`, `CODEOWNERS`:** no task edits them; the Untouched check (`tasks.md:20`) lists all of them plus `Dockerfile`, `pyproject.toml`, `uv.lock`. `contracts/` under the feature folder is feature-local. Gap: M2 (Phase 4 list).
- **CODEOWNERS paths (`.github/CODEOWNERS`: `/contracts/`, `/src/data/rules/`, `/docs/adr/`):** touched are `rules/__init__.py` (T020), `rules/sql/silver_incidents.sql` (T014), `rules/holds.py` and `rules/sql/hold_orders.sql` (T038), `rules/effect.py` (T051). All five are in the T069 review list (`tasks.md:179`). `007_scenarios.sql`, `pipeline/*` and `simulator/*` are not owned paths.
- **Live checks and the demo only under dedicated projects:** `pulsoflota-verify` and `pulsoflota-demo`; T057 tests the demo script (own project, own ports, `down -v` only for its project, no credentials). Gap: H4.
- **No secret in code, tests or logs:** `.env.example` entries hold no secret; poller logs carry no connection detail (T030); `run_demo.sh` never prints credentials (T057); truth has no payload (T008). One suggestion: log the exception class only, since a `psycopg` error text can contain the host.

## Test-first order and phase gates

- Tests precede implementation in every phase (T003–T013, T026–T037, T046–T050, T056–T060) and each implementation task names the test it turns green. Each phase ends with host suite, then Andon, then live/untouched checks (T025, T045, T055, T067). Exceptions: M2 (T067 has no Untouched check), L2 (T009).
- Dependency order is sound: `007_scenarios.sql` sections are added in the phase that needs them (T020, T039, T052); `cycle.py` steps are appended in order (incidents, holds, effects); `Makefile`/`READ_SCHEMAS` and the generated models precede the pipeline steps; T050 (cycle time) precedes the Phase 3 code.

## Budget

2 h 00 + 1 h 30 + 45 min + 1 h 00 + 20 min margin = **5 h 35 min**; cuts T059 (15 min) + T024 (10) + T065 (5) save 30 min, giving **5 h 05 min**, which is 15 min above the 4 h 50 min the data owner set and is reported openly in `tasks.md:229` and `research.md:521-525`. The task list is consistent with it (69 tasks, four phases, three cuts). Not counted in the budget: H1–H4 fixes (about 15 to 20 min in total, mostly wording and one extra test file edit) and the initial-poll test (M1). Only L1 (plan sentence) disagrees.

## Coverage summary (requirement → tasks)

All 32 FR and 13 SC have at least one task; no task lacks an FR/SC tag. Thin spots: FR-003 (T011 only, M3), FR-032 (T069 only; a negative requirement), FR-024 (T047, T053, T055; clamping not in spec, M4).

| Requirement | Tasks |
|---|---|
| FR-001 | T002, T003, T005, T011, T015, T018, T019, T023, T027 |
| FR-002 | T006, T011, T017, T018, T023 |
| FR-003 | T011 |
| FR-004 | T003, T005, T011, T012, T015, T019, T022 |
| FR-005 | T006, T011, T018 |
| FR-006 | T006, T011, T018, T024 |
| FR-007 | T006, T011, T018 |
| FR-008 | T007, T011, T017 |
| FR-009 | T007, T011, T017 |
| FR-010 | T008, T009, T011, T016, T023 |
| FR-011 | T008, T016 |
| FR-012 | T028, T030, T034, T038, T040, T044, T062 |
| FR-013 | T028, T031, T034, T038, T041 |
| FR-014 | T029, T031, T034, T040, T042, T044 |
| FR-015 | T028, T033, T034, T038, T043 |
| FR-016 | T028, T031, T033, T034, T038, T041, T043 |
| FR-017 | T027, T030, T032, T035, T036, T040, T042, T045 |
| FR-018 | T026, T030, T039, T040, T061 |
| FR-019 | T033, T039, T043 |
| FR-020 | T026, T034, T057, T062 |
| FR-021 | T004, T010, T014, T020, T021 |
| FR-022 | T047, T052, T053, T055 |
| FR-023 | T046, T047, T051, T053, T055 |
| FR-024 | T047, T053, T055 |
| FR-025 | T046, T047, T048, T051, T052, T053, T055 |
| FR-026 | T004, T010, T020, T021, T033, T043, T047, T053, T055 |
| FR-027 | T010, T020, T021, T047, T048, T052, T053, T055 |
| FR-028 | T025, T030, T032, T035, T040, T045 |
| FR-029 | T056, T058, T066, T068 |
| FR-030 | T001, T013, T025, T037, T045, T049, T050, T054, T055, T060, T067, T069 |
| FR-031 | T012, T015, T022, T036, T042, T057, T063 |
| FR-032 | T069 |
| SC-001 | T002, T003, T006, T008, T018, T019, T023, T025, T027, T041, T044, T069 |
| SC-002 | T011, T025, T069 |
| SC-003 | T011, T024, T025, T069 |
| SC-004 | T010, T011, T021, T025, T069 |
| SC-005 | T007, T011, T025, T069 |
| SC-006 | T008, T009, T011, T023, T024, T025, T058, T068, T069 |
| SC-007 | T026, T028, T030, T031, T033, T034, T038, T041, T043, T044, T045, T069 |
| SC-008 | T029, T045, T069 |
| SC-009 | T046, T047, T051, T053, T055, T069 |
| SC-010 | T056–T066, T068, T069 |
| SC-011 | T032, T035, T045, T069 |
| SC-012 | T004, T010, T014, T033, T034, T043, T045, T047, T053, T055, T069 |
| SC-013 | T001, T012, T022, T025, T036, T045, T048, T055, T067, T069 |

**Unmapped tasks:** none. Tasks that trace to a research decision rather than a spec item: T004 and T014 (R6, gate decision 5), T050 and T054 (R12), T056 (R9).

## Constitution alignment (v1.1.0, turn 1)

| Principle / norm | Result |
|---|---|
| I Risk-First | PASS. Disciplined lane, data-integrity risk; no adaptive-lane item. |
| II Contract-First | PASS. Feature-local interface notes precede code; nothing under `contracts/`. Caveat H3: the generated model does not carry the hold bound the plan relies on. |
| III Isolation | PASS by design; tests T035, T045 (live). Conditions M1, L6, H4. |
| IV Human gate | PASS from the data side (no `apply` decision, no hold; T034). M6 on the demo wording. |
| V Test-first and gates | PASS. Gate 1 (schema only), Gate 2 (coverage > 80 %), Gate 4 approval step. H1 would break Gate 2 at T025 if not fixed. |
| Deferred norms (Redis, PostGIS, 1,000 events/s, SAST/SCA, RBAC, HMAC, secret manager, US-03) | None built. Recorded as `evolution` (LOW, L7). |

## Metrics

- Requirements: 32 FR + 13 SC = 45; tasks: 69 (T001–T069), 3 on the cut list; coverage 100 % of FR and SC.
- Findings: 0 CRITICAL, 4 HIGH, 8 MEDIUM, 7 LOW. Ambiguity count 3 (M1, M4, M5); duplication 0; inconsistencies 5 (H1, H3, M4, M5, L1).

## Next actions

1. Approve edits for H1 to H4 (tasks T012, T020/T021, T004, T026, T040, T024, T025, T035, T045, T055, plus the sentences at `plan.md:134`, `research.md:222`, `data-model.md:72`, `contracts/hold-loop.md:37`). Suggested order: H1 and H2 before T004/T012, H3 before T026, H4 before T024/T025.
2. Fold M1 to M8 into the same edit (each is one sentence or one added test line); L1 to L7 are wording or optional.
3. Review `checklists/pre-implementation.md` (new, 40 items, all unchecked) before Phase 1 starts.

Would you like me to suggest concrete remediation edits for H1 to H4 and M1 to M3? I will not apply any without your approval.

## Fixes applied (2026-11-21)

Applied on the data owner's approval of 2026-11-21, by edits to artifacts inside `specs/004-scenario-injectors/` only. No code was written, nothing was committed or pushed. `spec.md` changed only where a MEDIUM needed a wording fix (M4, M5), keeping the approved meaning. Line numbers are those after the edit (`tasks.md` task ids are unchanged; no task was added or removed).

| Finding | Fix | Where |
|---|---|---|
| H1 | `test_baselines.py:92` and `:159` read `src.data.rules.RULES_VERSION` instead of `"1.0.0"` (same assertion, value from the single source); the file is in the Phase 1 allowed list; a note in `verification.md` | `tasks.md` T012 (`:50`), T020 (`:61`), T025 list (`:72`), conventions (`:20`); `plan.md:136` and the file list near `:238`; `research.md` R8 and the findings table |
| H2 | Choice: keep `end_ts = 'infinity'` (no DDL, no new table; NULL would lift `NOT NULL` and touch every 002 reader). `'infinity'` never reaches Python: gold publishes `duration_s` and `until` as NULL, computed in SQL behind `isfinite(end_ts)`; the helper `silver_support.incidents()` selects explicit columns with `CASE WHEN isfinite(end_ts)`; T004 asserts in SQL | `tasks.md` T004 (`:42`), T014 (`:55`), T021 (`:62`); `research.md` R6 (`:324-347`); `data-model.md` E6 (`:108`); `plan.md` (`:93`, `:351`) |
| H3 | The 0..90 s bound is enforced by the hold executor and the seed loader, not by the generated model. An over-cap entry **loads** (log `hold_seed_over_cap`), the order builder refuses it (`hold_order_refused`, `over_cap`), and data reports `not_executed` (AC5) | `research.md` R4.2 (`:227`, executor paragraph); `data-model.md` E3 and E5, validation list; `contracts/hold-loop.md` (`:37`, `:51`); `tasks.md` T026 (`:88`), T028, T030, T033, T034, T038, T040 (`:105`), T043 (`:108`); `plan.md` hold semantics row |
| H4 | The project name is on the same line as every compose command that starts, stops or resets a stack; no `export` followed by a bare `down -v`. The 003 project guard is required in T035 and every live test; the demo script uses `-p pulsoflota-demo` | `tasks.md` conventions (`:19`), T024 (`:68`), T025 (`:72`), T035 (`:97`), T045 (`:113`), T055 (`:144`), T063 (`:170`); `quickstart.md` live-check convention; `research.md` R10; `plan.md` Phase 4 |
| M1 | One synchronous initial poll before the first simulated event (the only blocking call); tests for it | `research.md` R4.1; `tasks.md` T032 (`:94`), T034 (`:96`), T040 (`:105`); `quickstart.md` Phase 2 criteria |
| M2 | Phase 4 allowed-file list and the Untouched check | `tasks.md` T067 (`:177`), T069 (`:179`) |
| M3 | `src/data/simulator` added to the `test_no_bronze_writes.py` scan (FR-003 static guard) | `tasks.md` T012 (`:50`), T036 (`:98`); `research.md` R10 |
| M4 | FR-023 and FR-024 reworded to the approved reading (held bus's `headway_ahead_s` in the first snapshot at or after `T0 + horizon_s`; `ewt_observed_s` clamped at 0); spec-reading note and backend-owner item in `verification.md` | `spec.md:159-160`; `tasks.md` T069 (`:179`) |
| M5 | Spec edge case and FR-021 now state the open-ended incident and match ADR-0003 gate 3; consequence listed for the CODEOWNERS review | `spec.md:107`, `:154`; `tasks.md` T069 |
| M6 | Gate 4 wording says the demo approval is scripted and human-approval evidence is deferred; `approve_hold.py` writes a recognizable demo `user_id` and says it is a stand-in | `plan.md` Gate 4 sentence (`:118`); `tasks.md` T062 (`:169`), T068 (`:178`), T069 |
| M7 | Assertion that bus order never inverts and capacity stays at or below 40 after each world injector | `tasks.md` T006 (`:44`) |
| M8 | Test for an effect window that spans a data fault (held bus Estimated or silent: null observations, `no_data`; instruction `not_executed` at `expires_ts`) | `tasks.md` T047 (`:130`), T033 (`:95`) |
| L1 | Budget sentence corrected | `plan.md` Phases intro |
| L2 | T009 added to the Red-rule exception; the T013 sentence and the quickstart row say it is green by design | `tasks.md:17`, T013; `quickstart.md` |
| L3 | No change: T001 re-measures the 003 baseline at implementation | none |
| L4 | `src/pulsoflota` added to the static truth-read guard | `tasks.md` T009 (`:47`); `research.md` R10 |
| L5 | D1(a) of 120 s or less leaves the bus `live` (assertion) | `tasks.md` T011 (`:49`) |
| L6 | Board lock not held during I/O (stalling fake connection); logs carry the exception class only | `tasks.md` T030 (`:92`), T040 |
| L7 | Evolution, no edit | none |

### Re-check after the fixes

- **Coverage**: 69 tasks, none added or removed, so the FR/SC table above still holds: all 32 FR and 13 SC have at least one task. Added references: FR-003 now also in T012 (static scan of the simulator package), FR-005 in T006, FR-021 and FR-027 in T004, T014 and T021 (SQL-side open-ended handling), FR-012 and SC-007 in T034 (over-cap case), FR-017 and SC-011 in T032 (initial poll). No task lost its FR/SC tag.
- **Budget**: the fixes add about 20 min inside existing tasks. Research R14 now reads 5 h 55 min in total (2 h 00 + 1 h 30 + 45 min + 1 h 00 + 20 min margin + 20 min fixes) and about 5 h 25 min after the three cuts (T059 15 min, T024 10 min, T065 5 min). That is 35 min above the 4 h 50 min the data owner set. `tasks.md` (Cut List, `:229`), `research.md` R14 and `plan.md` (Phases intro) give the same figures. The earlier "5 h 35 / 5 h 05" figures in the Budget section above are superseded by these.
- **Decision**: the four conditions of the GO (H1 to H4) are covered by edits; they still need the human to read the diff. `checklists/pre-implementation.md` was not edited and its 40 items stay unchecked (CHK018, CHK019 and CHK039 now have answers in the artifacts above).
