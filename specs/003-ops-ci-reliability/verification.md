# Verification: 003-ops-ci-reliability

Branch `feature/003-ops-ci-reliability`. Times are UTC, 2026-11-21.

## Baseline (T001)

Phase 1 start: 04:23:18. Command (Andon, unchanged):
`docker compose --profile tools build tests && docker compose --profile tools run --rm tests`

Result: **422 passed, 4 skipped, 0 failed**, coverage **91.97 %**, 120.20 s (124 s with build).
Same as the 002 end state.

## Red confirmation (T004)

`uv run pytest tests/unit/test_ci_workflow.py tests/unit/test_ops_docs.py -q --no-cov`
before implementation: 2 failed, 10 errors. Reasons: `workflow not found: .github/workflows/ci.yml`
and `doc not found: docs/ops/ci-branch-protection.md`, plus the missing compose mounts. No import or
syntax errors.

## Action versions (T006)

Confirmed with `git ls-remote --tags` on 2026-11-21: latest major tags are `actions/checkout` v7
and `astral-sh/setup-uv` v7 (research R9 had written v4 / v6 as a placeholder, to be confirmed).
The workflow uses `actions/checkout@v7` and `astral-sh/setup-uv@v7` with uv `0.9.5`. These could not
be exercised here; the first GitHub run (T010) will show whether they work. Pinning to commit SHAs is
deferred to turn 2 (R9).

## Local equivalents of the jobs (T008)

| Job | Command | Result |
|---|---|---|
| contract | `uv run --frozen --extra dev pytest src/data/tests/contract/test_read_fixtures.py -p no:cacheprovider --no-cov` | 33 passed |
| build | `docker compose --profile tools build` | exit 0 |

## Phase 1 verification (T009)

| Step | Command | Result |
|---|---|---|
| 1 | host `uv run pytest` (04:26:12 to 04:30:04) | 437 passed, 1 skipped, 0 failed, coverage 91.97 %, 231 s |
| 2 | Andon command (04:30:09 to 04:32:20) | 434 passed, 4 skipped, 0 failed, coverage 91.97 %, 116 s |
| 3 | `uv run pytest tests/unit/test_ci_workflow.py tests/unit/test_ops_docs.py -q --no-cov` | 12 passed |
| 3 | contract command | 33 passed |
| 3 | `docker compose --profile tools build` | exit 0 |

Passed count: Andon 434 = 422 baseline + 12 new tests. Host has 1 skipped instead of 4 because the
host environment runs tests the container skips.

Untouched check: `git status --short` shows only `docker-compose.yml` (3 added lines, two read-only
mounts and a comment), `.github/workflows/`, `docs/ops/`, the two new tests and spec files. No change
to `contracts/`, `bronze.py`, `validate.py`, init scripts, `CODEOWNERS`, `docs/adr`, `.drill-input/`
or `drill-out/`.

Rework: none. No test was weakened. No new dependency (PyYAML is already in the `dev` extra).
No secret is used by the workflow; `.env` was never printed.

End of Phase 1: 04:32:25. T010 (push, probes P1 to P3) is a human task and is not done.
