# Implementation Plan: Effect Result Rule

**Branch**: `feature/011-effect-result-rule` | **Date**: 2026-11-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-effect-result-rule/spec.md`

## Summary

Add one pure function, `classify_effect_result`, that classifies the outcome of an approved recommendation as `worked`, `partial`, `did_not_work` or `no_data` from EWT and headway before and after, the expected EWT saving, the planned headway and the window coverage. The worked ratio (0.5), the minimum coverage (0.9) and the planned headway are arguments, not constants. The rule follows the ADR-0007 table. Check order is fixed: `no_data` conditions first, then `worked`, then `partial`, then `did_not_work`. This is a subtask of #26 (story 004 phase 3, US-11). No database, pipeline, settings or contract change.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: standard library only (`typing.Literal`)

**Storage**: N/A (in-memory values, no persistence)

**Testing**: pytest, unit tests in `src/data/tests/unit/test_effect_result.py`, 100 % coverage target for the rule module

**Target Platform**: Linux container (ingestion/pipeline code under `src/data/rules/`), run on host for tests

**Project Type**: pure rule function inside the existing backend data package

**Performance Goals**: N/A (constant-time arithmetic, no I/O)

**Constraints**: deterministic, side-effect free, never raises on `None` inputs, no LLM or external call (Principle III), only the rule module and its test file change (FR-008)

**Scale/Scope**: one function, one private helper, two files

### Design decisions (from research.md and the implementation)

- ADR-0007 governs; the older 30 s rule (ADR-0003 decision 6, task T046) is out of scope (research D1).
- Check order `no_data` → `worked` → `partial` → `did_not_work` (D2). A null input never becomes a zero saving.
- Thresholds and planned headway are keyword-only parameters; the function does not read settings. `config.effect_settings` is wired in #26 (D3).
- Boundaries: `saving >= worked_ratio * expected` is `worked`; `coverage < min_coverage` is `no_data`, so 0.90 is evaluated (D4).
- Result type is `Literal[...]` whose strings equal the `result` enum of `contracts/read/recommendation_effect.schema.json`; no new class (D5).
- **Extra `no_data` guards.** Beyond the coverage check in the ADR-0007 table, the rule also returns `no_data` when the expected saving is `None` or ≤ 0, and when EWT before or after is missing (spec FR-001, edge cases). Reason: without an expected saving the `worked` threshold is meaningless (a 0 expected saving with a 0 observed saving would otherwise read as `worked`), and a missing EWT must not be treated as a zero saving. These guards are an addition to the ADR text.
- **Deferred to the data owner (#26).** Updating ADR-0007 and data-contract section H3 to state these guards is not done here. This feature changes neither document (FR-008); the data owner reviews and updates them under #26.

## Constitution Check

*GATE: checked before Phase 0 and re-checked after Phase 1. Constitution v1.4.0; active turn 1 per `docs/turns-ritmo.md` (disciplined lane, Level 1 data-integrity risk).*

| Gate | Result | Note |
|---|---|---|
| I. Risk-First Order | Pass | The rule protects metric integrity (turn 1, Level 1). No adaptive-lane work. |
| II. Contract-First and Data Ownership | Pass | The function contract is written first (`contracts/effect_result_rule.md`); result strings match the existing schema enum. Tests precede the rule (FR-007). Owner: data rules module. |
| III. Isolated Ingestion, Deterministic Real Time | Pass | Pure function, no I/O, no AI or third-party call. |
| IV. Human Gate | Pass | Classifies the effect of an already approved recommendation; issues no on-road action. |
| V. Test-First and Automated Gates | Pass (to confirm in CI) | Unit tests for every ADR-0007 row; 100 % target on the module; overall coverage gate stays > 80 %. |
| Turn-1 norms (Gate 1 schema validation, Gate 2 tests, parameterized SQL, no secrets) | Pass | No SQL, no secrets, no schema change. |
| Data contract review (data owner rule) | Pass | No contract impact: no table, view, metric definition or published field changes. H3 wording update deferred to #26. |

Deferred norms (evolution, not blocking in turn 1): SAST/SCA, RBAC/JWT/MFA, HMAC, Redis, PostGIS, 1,000 events/s. None applies to this function.

**Post-design re-check**: Pass. Design added no persisted entity, interface or dependency. No Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/011-effect-result-rule/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── effect_result_rule.md
├── checklists/
│   └── requirements.md
├── spec.md
├── tasks.md             # /speckit.tasks output
└── review-findings.md
```

### Source Code (repository root)

```text
src/data/
├── rules/
│   └── effect_result.py            # classify_effect_result (new)
└── tests/
    └── unit/
        └── test_effect_result.py   # unit tests, one case per ADR-0007 row (new)
```

**Structure Decision**: Existing backend data package. The rule sits in `src/data/rules/` with the other deterministic quality rules, and its tests in `src/data/tests/unit/`. The target `src/backend/` reorganization is not part of this feature.

## Evolution (deferred, tracked under #26)

- Settings wiring (`config.effect_settings`), the recommendation-effect table, the pipeline step, reading recommendations and the live check.
- Updating ADR-0007 and data-contract H3 with the extra `no_data` guards, and replacing the 30 s rule in task T046.

## Complexity Tracking

No constitution violations; nothing to justify.
