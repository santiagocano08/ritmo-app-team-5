# Contracts — 004-scenario-injectors

Feature-local interface notes, written before the code (Principle II). Nothing under the top-level
`contracts/` changes and no ADR line changes (spec FR-018, SC-013). Promoting any of these to
`contracts/` needs an ADR and is not part of this story.

| File | Interface | Consumer |
|---|---|---|
| [scenario-config.md](scenario-config.md) | the scenario file, the CLI/env, the truth record | the team (tests, demo), the demo script |
| [hold-loop.md](hold-loop.md) | the command door as read by the simulator, the seed shape, order rules | the simulator, the backend owner (integration) |
| [gold-read-access.md](gold-read-access.md) | `gold.incident`, `gold.instruction_status`, `gold.recommendation_effect` | the backend (reads gold), tests |

## Environment variables (new)

All go into `.env.example` (committed, no secrets) and into the `ingestion` service of
`docker-compose.yml` as `${VAR:-default}`. With the defaults nothing changes in the stack. Getters live in
`src/pulsoflota/config.py`; invalid values stop the process at start with a clear message.

| Variable | Default | Read by | Meaning |
|---|---|---|---|
| `SIM_SCENARIO_FILE` | unset | simulator `main.py` | path of the scenario JSON file; unset or empty = no scenario |
| `SIM_TRUTH_PATH` | unset | simulator `main.py` | file for the truth records; unset = stderr |
| `SIM_HOLDS` | `off` | simulator `main.py` | `on` starts the read-only decision poller |
| `SIM_HOLD_POLL_S` | `1` | poller | wall seconds between polls; must be > 0 |
| `SIM_HOLD_NONCOMPLIANCE` | `0.10` | hold executor | probability that a driver does not comply, 0 to 1 (assumption from the story brief) |
| `SEED_RECOMMENDATIONS_PATH` | `src/data/seeds/recommendations.json` | simulator, `pipeline/seeds.py` | seed recommendations keyed by `rec_id` |

Existing variables used unchanged: `SIM_SEED`, `SIM_DURATION_S`, `SIM_PACE_S`, `SIM_PLANNED_HEADWAY_S`,
`REFRESH_CLOCK`, `REFRESH_INTERVAL_S`, `DATABASE_URL`, `LOG_LEVEL`. The demo script exports its own
`DEMO_POSTGRES_PORT` (default 55433) and `DEMO_API_PORT` (default 58001); they are script settings, not
application variables.

CLI flags (`--scenario-file`, `--truth-path`, `--holds {on,off}`) override the variables.

## Log lines

Plain JSON lines on stderr, no stack trace, no connection detail, no secret (FR-028). New events:
`scenario_truth` (the record, R2), `hold_poll_failed` and `hold_poll_recovered` (one each per outage),
`hold_order_ignored` (`reason`: `unknown_rec`, `not_a_hold`, `duplicate`), `hold_order_refused`
(`reason`: `over_cap`, `conflict`).

## Validation

Each file is checked by a test: the scenario files and the seed file by their models and the read schema,
the gold objects by `jsonschema` against `contracts/read/*.schema.json`, the env table by
`tests/unit/test_env_example.py`.
