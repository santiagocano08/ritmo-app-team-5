# Research: Recommendation Reason in Spanish

No `NEEDS CLARIFICATION` items.

## Decision 1: Change only `_reason()` in `src/data/rules/mpc.py`
- **Rationale**: it is the single place that builds the text from `Action` and the action doc, so FR-001 (never parsed back) holds.
- **Alternatives**: a translation layer in the API or console (rejected: spec keeps the console unchanged and says the model writes Spanish); i18n catalog (rejected: YAGNI, one language).

## Decision 2: Keep `_g()` number formatting
- **Rationale**: FR-004; `18.2 s` and `60 s` stay as today.
- **Alternatives**: locale formatting with a decimal comma (rejected: changes published text beyond scope).

## Decision 3: Advance/delay keyed on the sign of `shift_s`
- **Rationale**: same rule as today (`shift_s < 0` → `adelantar`, otherwise `retrasar`), with `abs(shift_s)` as `{s}`.

## Decision 4: Leave the test lab's English-to-Spanish translation and archived reasons alone
- **Rationale**: FR-008 and the out-of-scope assumption; old archived runs still need it.

## Decision 5: No schema or version bump
- **Rationale**: `reason` is free text in the recommendation schema; only the documentation line and example text change.
