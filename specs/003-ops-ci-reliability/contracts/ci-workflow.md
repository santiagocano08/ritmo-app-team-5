# Contract — CI workflow (`.github/workflows/ci.yml`)

Owner: data team for the three jobs below; the DevOps owner adds further jobs. Status: Phase 1.

## Interface seen by GitHub

| Item | Value |
|---|---|
| Workflow name | `CI` |
| Triggers | `pull_request` (any base branch) and `push` to `main` |
| Permissions | `contents: read` |
| Secrets | none; `.env` is created from `.env.example` |
| Concurrency | group `ci-<workflow>-<ref>`; in-progress runs cancelled for pull requests only |
| Runner | `ubuntu-latest` for every job |

## Jobs (the required status checks)

| Job id and name | Command | Red when |
|---|---|---|
| `test` | `docker compose --profile tools build tests && docker compose --profile tools run --rm tests` (unchanged) | a test fails or coverage < 80 % |
| `contract` | `uv run --frozen --extra dev pytest src/data/tests/contract/test_read_fixtures.py -p no:cacheprovider --no-cov` | a fixture is invalid or has no schema, or a read schema is invalid |
| `build` | `docker compose --profile tools build` | any service image fails to build |

Rules:

1. The jobs are independent (no `needs`) and a run is green only when all three pass.
2. The job ids and names are the names a repository admin selects as required checks. Renaming a
   job silently removes it from protection, so a test asserts the three names.
3. New jobs (lint, security scanning) are added beside these; none of these three is edited for them.
4. The 80 % gate comes from the compose command and `pyproject.toml`; the workflow never repeats or
   lowers it.

Branch protection for `main` (manual, admin only) is described in `docs/ops/ci-branch-protection.md`.
