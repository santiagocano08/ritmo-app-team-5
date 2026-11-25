# Review Findings: 011-effect-result-rule

Run: 2026-11-25 (post-implementation review)

Converge outcome: `converged`. `tasks.md` is unchanged. All FR-001..FR-008 and SC-001..SC-004 are satisfied. Only the two allowed files were added under `src/`.

Coverage minimum: 80 % from the constitution (Principle V / Gate 2). The spec adds a 100 % target for the rule module (SC-002).

## Results

| Check | Command | Result |
|---|---|---|
| Feature tests | `pytest src/data/tests/unit/test_effect_result.py` | 17 passed |
| Module coverage | same, `-o addopts="" --cov=src.data.rules.effect_result` | 100 % (target 100 %) |
| Area fast tests | `pytest src/data/tests/unit --no-cov` | 652 passed |
| Linter | `.venv/bin/ruff check` on the 2 files | pass |
| Types | `.venv/bin/mypy` on the 2 files | pass |
| Formatter | `.venv/bin/ruff format --check` on the 2 files | fail (F-1) |

The whole-tree coverage gate (`--cov-fail-under=80` over `src`) was not run, per the session rule against running the whole suite.

## LOW

### F-1 (format, LOW): the two new files are not `ruff format` clean
- Area: `src/data/rules/effect_result.py`, `src/data/tests/unit/test_effect_result.py`.
- Command: `.venv/bin/ruff format --check <both files>`. Output: "2 files would be reformatted" (blank line after the module docstring, lines over 88 chars).
- Not auto-fixed. The project does not enforce `ruff format` (no config, not in `make lint` or CI), and 13 of 14 files in `src/data/rules` also fail the check. Reformatting only these two would be inconsistent with the repo.
- Remediation: leave as is, or adopt the formatter repo-wide in a separate change.

### F-2 (converge, LOW): `plan.md` is the unfilled template
- Area: `specs/011-effect-result-rule/plan.md`.
- `tasks.md` states this and derives from spec, data model, research and contract instead. I did not edit `plan.md`.
- Remediation: run create-plan if a plan is required for the PR.
