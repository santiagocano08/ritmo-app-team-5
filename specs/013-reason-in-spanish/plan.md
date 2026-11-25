# Implementation Plan: Recommendation Reason in Spanish

**Branch**: `013-reason-in-spanish` | **Date**: 2026-11-25 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/013-reason-in-spanish/spec.md`

## Summary

`_reason()` in `src/data/rules/mpc.py` builds the recommendation `reason` in English from the action document. Rewrite its five branches to the Spanish templates of FR-002, keep number formatting (`_g`), update the tests that assert the text, and add one line to the recommendation section of `docs/data-contract.md`. The recommendation schema, its version and the console do not change.

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: none new (existing Pydantic V2 contract validation, pytest)

**Storage**: N/A (the text is written to existing `gold.recommendation` JSON docs; no DDL)

**Testing**: pytest, run with uv against the development Postgres (`src/data/tests/unit/test_mpc_ranking.py`, `test_mpc_lifecycle.py`, fixtures validation tests)

**Target Platform**: Linux container (`ingestion-service`/data pipeline)

**Project Type**: data pipeline rule (disciplined lane, Turn 1)

**Performance Goals**: none; string formatting only, no change to the critical path

**Constraints**: `reason` built from structured fields, never parsed back; schema unchanged

**Scale/Scope**: one function, 3 test/fixture-support files, 1 doc line

**Assumptions**: the six `contracts/read/fixtures/*/recommendation.json` reasons are already Spanish with the target templates; the plan only verifies them (FR-005). `src/data/tests/fixtures/rec_support.py` builds an English reason string for test data; it is updated to Spanish for consistency.

## Constitution Check

*Gate: passed before Phase 0, re-checked after Phase 1.*

- I Risk-first: no new risk; data text only. Pass.
- II Contract-first: schema unchanged, `reason` stays free text; contract impact is one documentation line (see Data contract impact). Pass.
- III Isolated deterministic path: pure string formatting, no external or AI call. Pass.
- IV Human gate: recommendations stay suggestions. Pass.
- V Test-first: existing assertions updated to the Spanish text first; coverage unchanged. Pass.
- Turn 1 (`docs/turns-ritmo.md`): only adopted norms touched. Evolution (not designed here): translating archived or stored reasons, console changes.

Result: PASS, no violations, no Complexity Tracking needed.

## Data contract impact

- `docs/data-contract.md`, §4.5 Recommendations: add one line stating `reason` is plain Spanish text for the dispatcher, built from the same fields as the document.
- Q7 seed example (§Q7) is a seeded demo in English prose; left as is (not produced by the model). No schema or version change (ADR-0002/0003 rule not triggered).
- `contracts/read/fixtures/*/recommendation.json`: verify they validate; no edit expected.

## Project Structure

### Documentation (this feature)

```text
specs/013-reason-in-spanish/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── spec.md
```

No `contracts/` directory: no interface is added or changed.

### Source Code (files touched)

```text
src/data/rules/mpc.py                              # _reason(): Spanish templates
src/data/tests/unit/test_mpc_ranking.py            # expected reasons (lines ~112-118)
src/data/tests/unit/test_mpc_lifecycle.py          # endswith(...) at line ~79
src/data/tests/fixtures/rec_support.py             # fixture reason text
docs/data-contract.md                              # one line in §4.5
```

**Structure Decision**: edit in place in the current Turn-1 tree; `src/data/test_lab/` translation is left untouched (FR-008).

## Complexity Tracking

None.
