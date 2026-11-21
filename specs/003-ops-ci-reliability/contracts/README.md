# Contracts — 003-ops-ci-reliability

Feature-local interface notes, written before the code (Principle II). Nothing under the top-level
`contracts/` changes (event contract, read contract, CODEOWNERS data-owner area). Promotion of any of
these to `contracts/` would need an ADR and is not part of this story.

| File | Interface | Consumer |
|---|---|---|
| [ops-ingestion-health.md](ops-ingestion-health.md) | the `ops.ingestion_health` view and the ingestion healthcheck | the on-call person, the Docker healthcheck, a later alerting story |
| [ingestion-retry-log.schema.json](ingestion-retry-log.schema.json) | JSON log lines of the ingestion retry loop | the on-call person, the drill script, the runbook |
| [ci-workflow.md](ci-workflow.md) | the CI workflow: job names, triggers, required checks | GitHub branch protection, the DevOps owner |

## Environment variables (new)

All go into `.env.example` (committed, no secrets) and into the `ingestion` service of
`docker-compose.yml` as `${VAR:-default}`, following the existing `UPPER_SNAKE` plus `_S` convention.

| Variable | Default | Read by | Meaning |
|---|---|---|---|
| `INGESTION_RETRY_INITIAL_S` | `1` | `src/pulsoflota/config.py`, ingestion | first wait after a failure; doubles each attempt |
| `INGESTION_RETRY_MAX_WAIT_S` | `5` | same | cap of one wait |
| `INGESTION_RETRY_TOTAL_S` | `120` | same | total retry window from the first failure of an outage |
| `INGESTION_HEALTH_MAX_AGE_S` | `15` | `src/data/ingestion/health.py` | freshness threshold of the healthcheck |

Invalid values stop the process (retry settings, at start) or make the probe report
`unhealthy: check failed` (health setting). The values and their reasons are in
[research.md](../research.md) R1 and R5.

## Validation

- The JSON Schema is validated as draft 2020-12, and real log lines captured in tests are validated
  against it (valid and invalid examples).
- The view columns and NULL semantics are tested on a throwaway database.
- The workflow structure is tested from the committed YAML.
