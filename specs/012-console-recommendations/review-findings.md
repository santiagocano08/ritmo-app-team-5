# Review findings: 012-console-recommendations

Run: 2026-11-26 (post-implementation review). Converge outcome: `converged`. `tasks.md` unchanged (T001–T022 all `[X]`).

Coverage minimum: 80 %, source: constitution Principle V / Gate 2 (and `AGENTS.md`).

## Auto-fixed

- Mypy errors in `src/api/tests/contract/test_recommendations_contract.py` (deliberately invalid inputs typed as constructor args). Switched to `RecommendationsResponse.model_validate({...})`. Re-ran: mypy clean on that file, ruff clean, 5 tests pass.

## Findings (not fixed)

### MEDIUM

- **F1 (checklist)** `checklists/requirements-quality.md` has 25 unchecked items. They are reviewer-owned and were not modified. Remediation: reviewer completes the checklist before the PR.
- **F2 (coverage)** Whole-tree backend coverage was not measured: the session rules forbid running the whole suite. Scoped run of `src/api/tests` (39 passed): `corridor_read.py` 97 %, `gold_reads.py` 94 % (uncovered lines are pre-existing paths: 62, 70, 90, 106). The `src/api` total in that run is dominated by unrelated `src/data` code (43 % of the files measured). Remediation: CI runs `make test` for the global ≥ 80 % gate.

### LOW

- **F3 (lint, pre-existing)** `ruff check src` reports 275 errors, none in this feature's files (`ruff check` on the 5 changed Python files passes). Command: `.venv/bin/ruff check src`. One is in `src/api/tests/integration/test_read_api_endpoints.py:105` (unused `noqa`), a file this feature did not create.
- **F4 (typecheck, pre-existing)** `mypy --ignore-missing-imports src` reports 243 errors in 66 files, none in this feature's files after the fix above. Remediation: separate cleanup.
- **F5 (format, pre-existing)** `ruff format --check` would reformat the 5 changed Python files, and Prettier flags 36 frontend files (including 8 touched by this feature). The same flags hit untouched files, so neither formatter appears to be enforced. Formatting was not applied, to avoid noise diffs. Remediation: team decides on the formatter, then runs it repo-wide in one PR.

## Validation results

| Check | Result |
|---|---|
| Backend tests `src/api/tests` | 39 passed |
| Frontend tests (Node container, no `-e TZ`) | 24 files, 86 tests passed |
| Frontend coverage | 98.36 % statements (≥ 80 %) |
| ESLint `--max-warnings 0` | pass |
| `tsc --noEmit` | pass |
| ruff / mypy on changed Python files | pass |
| Repo-wide ruff / mypy / formatters | pre-existing failures (F3–F5) |

## Verdict

No blocking items for this feature. Before the PR: complete the requirements-quality checklist (F1) and let CI confirm the global coverage gate (F2).
