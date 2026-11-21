# CI branch protection for `main`

The CI workflow (`.github/workflows/ci.yml`) runs three independent jobs on every pull request and on
every push to `main`. A run is green only when all three pass.

## Required status checks

| Check name | What it proves |
|---|---|
| `test` | The full test suite passes and coverage is at least 80 %. |
| `contract` | Every read-contract fixture is valid against its schema. |
| `build` | Every service image builds. |

## Setting it up (manual step, repository administrator only)

This change does **not** configure branch protection. A repository administrator does it once:

1. Open the repository on GitHub: Settings → Branches (or Settings → Rulesets).
2. Add or edit the rule for `main`.
3. Enable "Require status checks to pass before merging" (require status checks).
4. Search for and select `test`, `contract` and `build`.
5. Save the rule.

Without this rule a red check is still shown on the pull request, but GitHub does not block the merge.

## Renaming a job

The check names are the job ids in the workflow. If a job is renamed, the old name stays in the
protection rule but is never reported again, and the new name is not required. The job silently drops
out of protection. After any rename, update the rule in the same step. A test
(`tests/unit/test_ci_workflow.py`) asserts the three job ids so a rename fails CI.
