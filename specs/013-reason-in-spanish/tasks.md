# Tasks: Recommendation Reason in Spanish

**Input**: `/specs/013-reason-in-spanish/` (plan.md, spec.md, data-model.md, research.md, quickstart.md)

**Prerequisites**: plan.md, spec.md. No `contracts/` directory (no interface changes).

**Tests**: Included (default ON; the spec and constitution do not opt out). Tests MUST be updated first and MUST FAIL before the `_reason()` rewrite.

**Format**: `- [ ] T### [P?] [US1] Description with file path`

**Commands**: run tests as in quickstart.md (uv against the running dev Postgres, `--no-cov`, only the files named here). Never run the full suite.

## Phase 1: Setup

No setup needed: no new dependencies, files or directories (plan.md, Technical Context).

## Phase 2: Foundational

None. No schema, table or version change (research.md, Decision 5).

## Phase 3: User Story 1 - Read each recommendation's reason in Spanish (Priority: P1) 🎯 MVP

**Goal**: every published recommendation `reason` is Spanish, built from structured fields with the FR-002 templates.

**Independent Test**: generate one recommendation per action type and check the reason matches the Spanish template (e.g. `retener B-103 60 s en P-888 ahorra 22 s por pasajero`); the six `contracts/read/fixtures/*/recommendation.json` validate against the unchanged schema with Spanish reasons.

### Tests for User Story 1 (write first, must FAIL before implementation)

- [X] T001 [P] [US1] Update the expected reasons (around lines 112-118) in `src/data/tests/unit/test_mpc_ranking.py` to the five FR-002 templates: hold, slow down (`un {pct} % durante {min} min`), reserve dispatch, adjust departure (`adelantar` for shift < 0, `retrasar` otherwise, `abs(shift_s)`), skip stop; keep `_g()` number formatting (e.g. `18.2 s`, `60 s`).
- [X] T002 [P] [US1] Update the `endswith(...)` assertion (around line 79) in `src/data/tests/unit/test_mpc_lifecycle.py` to the Spanish suffix `ahorra {n} s por pasajero`.
- [X] T003 [P] [US1] Change the English reason string built for test data in `src/data/tests/fixtures/rec_support.py` to the Spanish hold template.
- [X] T004 [US1] Run `src/data/tests/unit/test_mpc_ranking.py` and `src/data/tests/unit/test_mpc_lifecycle.py` and confirm they FAIL on the English text (depends on T001-T003).

### Implementation for User Story 1

- [X] T005 [US1] Rewrite the five branches of `_reason()` in `src/data/rules/mpc.py` to the FR-002 Spanish templates, built only from the action document fields (never parsed back). Keep `_g()` formatting; slow-down keeps the fallback `durante {dur} s` when the duration is not a whole number of minutes; adjust departure uses `shift_s < 0` → `adelantar`, else `retrasar`, with `abs(shift_s)`. Do not touch `src/data/test_lab/` (FR-008).
- [X] T006 [US1] Re-run `src/data/tests/unit/test_mpc_ranking.py` and `src/data/tests/unit/test_mpc_lifecycle.py`; both must pass (depends on T005).
- [X] T007 [P] [US1] Verify the six `contracts/read/fixtures/*/recommendation.json` reasons are Spanish with the same templates (FR-005); edit only if one differs. Locate the fixture validation test with `grep -rl "fixtures" src/data/tests/unit` and run it; all six must validate against the unchanged `recommendation.schema.json` 1.1.0.
- [X] T008 [P] [US1] Add one line to `docs/data-contract.md` §4.5 (Recommendations): `reason` is plain Spanish text for the dispatcher, built from the same fields as the document. Leave the §Q7 seed example unchanged; no schema or version change.
- [X] T009 [US1] Run the area's fast tests in `src/data/tests/unit` once to confirm they stay green (FR-007), and confirm `docs/data-contract.md` §4.5 contains the new line (depends on T006-T008).

**Checkpoint**: User Story 1 is complete and independently verifiable.

## Phase 4: Polish

No polish tasks: no refactor, console, or archived-reason changes (out of scope per spec).

## Dependencies & Execution Order

- Phase 3 is the only phase. Order: T001-T003 (parallel) → T004 → T005 → T006 → T007/T008 (parallel) → T009.
- T001, T002, T003 touch different files. T007 and T008 touch different files.

## Parallel Example: User Story 1

```text
Task: "Update expected reasons in src/data/tests/unit/test_mpc_ranking.py"
Task: "Update endswith assertion in src/data/tests/unit/test_mpc_lifecycle.py"
Task: "Spanish reason in src/data/tests/fixtures/rec_support.py"
```

## Implementation Strategy

MVP is User Story 1, the whole feature: tests first (fail), rewrite `_reason()`, verify fixtures, add the doc line, run the data unit tests once.
