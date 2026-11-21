# Quickstart — validating 004-scenario-injectors

Validation and run guide. It holds no implementation code. Contracts: [contracts/](contracts/README.md).
Data shapes: [data-model.md](data-model.md). Decisions: [research.md](research.md).

## Prerequisites

- Docker with Compose, `uv`, and a `.env` copied from `.env.example` with `POSTGRES_PASSWORD` set.
- Work on branch `feature/004-scenario-injectors`.
- Baseline before any change (record it in `verification.md`): the Andon command is green with
  **434 passed, 4 skipped, coverage 91.97 %** (003 end state).

```bash
# Andon (CI-ready command, unchanged)
docker compose --profile tools build tests && docker compose --profile tools run --rm tests
```

Fast loop on the host while developing (needs `DATABASE_URL` for integration tests):

```bash
uv run --frozen --extra dev pytest src/data/tests/unit -p no:cacheprovider --no-cov -q
```

## Live-check convention

Live checks start, stop and reset a stack. Never run them on the default project: `down -v` would delete
your volume. Use a dedicated project (003 convention):

```bash
export COMPOSE_PROJECT_NAME=pulsoflota-verify     # live tests
# the demo uses its own project, pulsoflota-demo, set by scripts/demo/run_demo.sh
```

Live tests (`-m live`) skip themselves unless `-m live` is passed and the variable is set.

## Phase 1 — Injectors and incident view

**Red first** (each fails for the stated reason, no import or syntax error):

| Test | Expected failure before the code |
|---|---|
| `test_simulator_golden_hash.py` | none: it is **green on the untouched engine** and stays green (seed 42 `51a5e9b3…39e1`, seed 7 `6bd20707…0132`) |
| `test_scenario_config.py` | module `scenarios.config` missing; covers AC10 (unknown type, missing `start_s`, range, unknown bus, duplicate id, overlap) |
| `test_scenario_injectors.py` | C1 extends the dwell, C2 delays the departure, C5 halts and emits one `incident_report`; no scenario means the baseline |
| `test_scenario_channel.py` | silence drops only the three bus-report types of the target in its window; duplicates repeat exactly `count` lines |
| `test_scenario_truth.py` | records, order, determinism (two runs equal), no secrets or payloads |
| `test_no_truth_reads.py` | static guard; passes once the package exists and nothing reads it |
| `test_incident_gold.py` | `gold.incident` rows validate against `incident.schema.json`; active until `start + duration`; `until` set after |
| `test_scenarios_gold.py` | shape of `c1_bunching`, `c2_gap`, `c5_breakdown`, `d1_source_outage`; D1(b) leaves silver and gold equal to the run without duplicates |

**Run the scenarios by hand** (offline, no database):

```bash
PYTHONPATH=. uv run --frozen python -m src.data.simulator.main --seed 42 --duration 3600 \
  --scenario-file src/data/tests/fixtures/scenarios/c5_demo.json --truth-path /tmp/truth.jsonl | wc -l
cat /tmp/truth.jsonl                       # one line per injector
```

**Pass criteria**

- Baseline hashes unchanged with no scenario file and with an empty array `[]`.
- Same file and seed twice: identical stream hash and identical truth file.
- For each scenario, gold computed with `python -m src.data.pipeline.compute --from … --to …` on the run:
  C1 `n_bunched >= 1` (follower under 300 s); C2 `n_gaps >= 1` (over 900 s); C5 active `bus_breakdown`
  incident, the bus `broken_down` with `headway_ahead_s = null`, `buses_in_service` excludes it, and
  after the duration the incident has `until` set; D1(a) the bus `estimated` and in `sources_down` in the
  first snapshot more than 120 s after its last report (at most 125 s), back to `live` afterwards; D1(b)
  M `duplicate_event` rows.
- Deleting or altering the truth file between simulation and compute changes nothing in bronze, silver or gold.
- The C5 gap-behind check uses the window with three buses on the corridor (research R9, B-102 at about
  1,240 s for 240 s); `buses_in_service` is asserted by rule, not by the fixture's "4 of 5".
- Andon green, coverage above 80 %.

**Commit point**: scenarios plus incident object.

## Phase 2 — Hold loop

**Red first**:

| Test | Expected failure before the code |
|---|---|
| `test_hold_rules.py` | `rules/holds.py` missing: matching (strictly after the decision, up to `expires_ts`), ±15 s (14 and 15 s executed, 16 s not), cap 90, conflict, breakdown, pending |
| `test_hold_compliance.py` | draw reproducible; probability 1 gives all non-compliant, 0 gives none; N = 200 batch count equals the truth count |
| `test_hold_board.py` | fake connection: unknown `rec_id` counted, `discard` no order, same `rec_id` twice one order, database error keeps the board and does not raise |
| `test_scenario_injectors.py` (holds) | total dwell: departure at `max(natural, arrival + D)`; no order or `holds=None` is the baseline hash |
| `test_hold_poller.py` | real throwaway database: read-only session cannot write; new decisions appear; `decided_at_sim` correct; database stop does not raise |
| `test_instruction_status.py` | rows and `ts_by_status` for executed, not executed, expired, breakdown wins; `status`/`ts_by_status` valid against `instruction.schema.json`; no row while pending |
| `test_hold_loop.py` | crafted decision rows + simulator + `compute`: forced compliance → `executed`; forced non-compliance → `not_executed`; hold 120 s refused; decision after departure → `not_executed`; reprocessing leaves rows unchanged |
| `test_loop_isolation.py` | with the poller stopped and the database down for the retry window, the simulator keeps writing and exits only at its duration |

**Pass criteria**

- With `--holds` and an empty bronze the baseline hashes are unchanged.
- Decision rows are inserted directly into `bronze.events` (`source = backend`), as the backend does and
  as `insert_backend_commands` in the builders already does.
- `discard` or no decision: zero holds run (Principle IV).
- Live isolation check (project `pulsoflota-verify`): stop `api`, `refresh` and the poller; bronze row count
  keeps growing (SC-011):

```bash
uv run pytest src/data/tests/integration/test_loop_isolation.py -m live -q --no-cov -s
```

**Commit point**: approved holds execute and are observed.

## Phase 3 — Effect table

**Red first**: `test_effect_rule.py` (29 s → `partial`, 30 s → `worked`, fixture 55 and 22 → `worked`,
no improvement → `did_not_work`, headway improved only → `partial`, nulls → `no_data`, threshold read
from the argument, not coded); `test_recommendation_effect.py` (window open gives no row, window closed
gives one row validating against `recommendation_effect.schema.json`, not executed hold still gives a row,
missing snapshot gives `no_data`, recompute gives the same rows, read-only).

**Pass criteria**: all rows valid; reruns unchanged; cycle time before and after Phase 3 recorded in
`verification.md` (R12); Andon green.

**Commit point**: effect rows.

## Phase 4 — Demo run

Offline first (pace 0, throwaway database): `test_demo_scenario.py` validates `demo.json`, replays it and
asserts, with a tolerance, the gold state at the chosen simulated times: B-101 `estimated` and no alert,
a `bunched` follower, the hold `executed`, an effect row after the horizon, an active `bus_breakdown`
incident.

Then the live run (own project, about 8 minutes, needs `.env`):

```bash
bash scripts/demo/run_demo.sh            # project pulsoflota-demo, own volume, ports 55433 / 58001
# outputs under demo-out/ (git-ignored): samples.csv, gold_steps.txt, truth.log
```

**Pass criteria (SC-010)**

| Step | Evidence in `demo-out/` |
|---|---|
| D1 | a snapshot with `status = estimated`, B-101 in `sources_down`, no `bunched` or incident |
| C1 and hold | a `bunched` follower, a `decision` row, `gold.instruction_status` = `executed` |
| Effect | one `gold.recommendation_effect` row after the horizon; its `result` is printed **as the rule yields it** (not tuned) |
| C5 | an active `bus_breakdown` incident, the bus `broken_down`; no reserve dispatch |
| Close | truth lines match gold (kind, bus, effective time within 5 s) and the run took about 8 minutes |

Evidence goes into `verification.md`: baseline, red confirmations, commands, results, cycle times and the
demo table.

## Clean-up

```bash
COMPOSE_PROJECT_NAME=pulsoflota-demo docker compose down -v      # demo project only
COMPOSE_PROJECT_NAME=pulsoflota-verify docker compose down -v    # live-check project only
rm -rf demo-out
```
