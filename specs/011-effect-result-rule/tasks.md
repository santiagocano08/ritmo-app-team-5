# Tasks: Effect Result Rule

**Input**: `/specs/011-effect-result-rule/` (spec.md, data-model.md, research.md, contracts/effect_result_rule.md, quickstart.md). `plan.md` is still the unfilled template, so tasks derive from spec, data model, research and contract.

**Tests**: Included (default ON; spec does not opt out). Tests MUST be written first and MUST FAIL before the rule exists.

**Scope**: Exactly two files change (FR-008, SC-003): `src/data/rules/effect_result.py` and `src/data/tests/unit/test_effect_result.py`. No database, pipeline or contract change. Data contract impact: none.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

No setup tasks. `src/data/rules/` and `src/data/tests/unit/` already exist.

## Phase 2: Foundational

No foundational tasks. The rule is a pure function with no shared infrastructure.

---

## Phase 3: User Story 1 - Classify the outcome of a recommendation (Priority: P1) 🎯 MVP

**Goal**: `classify_effect_result` returns `worked`, `partial`, `did_not_work` or `no_data` per ADR-0007.

**Independent Test**: Run `src/data/tests/unit/test_effect_result.py` alone; every rule-table row is covered and the module has 100 % coverage.

### Tests for User Story 1 (write first, must FAIL)

- [X] T001 [US1] Create `src/data/tests/unit/test_effect_result.py` with a keyword-argument helper that builds a baseline input set and imports `classify_effect_result` from `src.data.rules.effect_result` (follow the import style of `src/data/tests/unit/test_headway.py`). Use fixed values, no randomness.
- [X] T002 [US1] In `src/data/tests/unit/test_effect_result.py` add worked/partial boundary cases: saving exactly 50 % of expected → `worked`; just below 50 % (saving > 0) → `partial`; saving above 50 % → `worked`.
- [X] T003 [US1] In `src/data/tests/unit/test_effect_result.py` add saving ≤ 0 cases: headway closer to `headway_planned_s` after than before (`|after − planned| < |before − planned|`) → `partial`; headway not closer → `did_not_work`; headway before or after `None` → `did_not_work`.
- [X] T004 [US1] In `src/data/tests/unit/test_effect_result.py` add `no_data` cases: `coverage_ratio` 0.89 → `no_data` and 0.90 → evaluated normally; `expected_saving_s` `None`, 0 and negative → `no_data`; `ewt_before_s` `None` and `ewt_after_s` `None` → `no_data` (no zero saving assumed); expected saving 0 with observed saving 0 → `no_data`; several failing conditions at once → `no_data`.
- [X] T005 [US1] In `src/data/tests/unit/test_effect_result.py` add configurability cases (SC-004): changing `worked_ratio`, `min_coverage` and `headway_planned_s` each flips the result for the same measurements.
- [X] T006 [US1] Run the new test file and confirm it fails because the module is missing: `set -a; . ./.env; set +a; export DATABASE_URL="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:${POSTGRES_PORT:-5432}/$POSTGRES_DB"; uv run --frozen --extra dev pytest src/data/tests/unit/test_effect_result.py -q --no-cov -p no:cacheprovider` (never print `.env` or the DSN).

### Implementation for User Story 1

- [X] T007 [US1] Create `src/data/rules/effect_result.py` with `classify_effect_result(*, ewt_before_s, ewt_after_s, expected_saving_s, headway_before_s, headway_after_s, headway_planned_s, coverage_ratio, worked_ratio, min_coverage) -> EffectResult`, where `EffectResult = Literal["worked", "partial", "did_not_work", "no_data"]`. Types per data-model.md: EWT, expected saving and headways `float | None`; `headway_planned_s`, `coverage_ratio`, `worked_ratio`, `min_coverage` `float`. Pure, no I/O, no settings read, no raise on `None`.
- [X] T008 [US1] In `src/data/rules/effect_result.py` implement the decision flow, first match wins: (1) `no_data` if `coverage_ratio < min_coverage`, `expected_saving_s` is `None` or ≤ 0, or either EWT is `None`; (2) `worked` if `observed_saving >= worked_ratio * expected_saving_s` with `observed_saving = ewt_before_s − ewt_after_s`; (3) `partial` if `observed_saving > 0` or headway is closer to plan (`|after − planned| < |before − planned|`, `None` is never closer); (4) otherwise `did_not_work`.
- [X] T009 [US1] Run the test file from T006 and confirm all cases pass.
- [X] T010 [US1] Verify 100 % coverage of the module (SC-002): `uv run --frozen --extra dev pytest src/data/tests/unit/test_effect_result.py -q -p no:cacheprovider --cov=src/data/rules/effect_result --cov-report=term-missing --cov-fail-under=100`, with the same env loading as T006. Add missing cases to `src/data/tests/unit/test_effect_result.py` if any line is uncovered.

**Checkpoint**: User Story 1 is complete and independently testable.

---

## Phase 4: Polish

- [X] T011 Run `.venv/bin/ruff check src/data/rules/effect_result.py src/data/tests/unit/test_effect_result.py` and `.venv/bin/mypy` on the same files, then fix findings in those two files only.
- [X] T012 Run `git status` and confirm only `src/data/rules/effect_result.py` and `src/data/tests/unit/test_effect_result.py` are added under `src/` (SC-003). Do not commit or push.

---

## Dependencies & Execution Order

- T001 → T002–T005 (same file, sequential) → T006 (tests fail) → T007 → T008 → T009 → T010 → T011 → T012.
- Tests MUST be written and MUST FAIL (T006) before implementation (T007).
- No task is marked `[P]`: all test tasks edit one file, and the implementation tasks edit one file.

## Parallel Example

None. The feature has one story and two files; the test file is edited sequentially.

## Implementation Strategy

MVP is User Story 1, the whole feature. Write the tests, see them fail, implement the rule, confirm pass and 100 % coverage, then lint and check the two-file footprint. Out of scope (left for #26): settings, effect table, pipeline step, reading recommendations, live check, the older 30 s rule (T046).
