# Research: Effect Result Rule

No NEEDS CLARIFICATION remained. Decisions:

## D1. Rule source
- **Decision**: ADR-0007 table governs; the 30 s rule (ADR-0003 decision 6, task T046) is out of scope.
- **Rationale**: ADR-0007 amends ADR-0003 and fixes the false-`worked` case.
- **Alternatives**: keep 30 s rule; absolute saving threshold (both rejected in ADR-0007).

## D2. Check order
- **Decision**: `no_data` first (coverage < min, expected saving null or ≤ 0, EWT before/after null), then `worked`, then `partial`, then `did_not_work`.
- **Rationale**: FR-001; a null input must never become a zero saving.
- **Alternatives**: none; the order is required by the spec.

## D3. Inputs as arguments
- **Decision**: worked ratio, minimum coverage and planned headway are parameters; the function does not read settings.
- **Rationale**: FR-005; keeps the function pure. `config.effect_settings` is wired in #26.
- **Alternatives**: module constants (rejected: fixed values).

## D4. Boundaries
- **Decision**: `saving >= ratio * expected` is `worked`; `coverage < min` is `no_data` (0.90 evaluates).
- **Rationale**: matches the acceptance scenarios (50 % exactly is `worked`, 0.89 is `no_data`).

## D5. Result type
- **Decision**: `Literal["worked", "partial", "did_not_work", "no_data"]` and keyword-only float arguments.
- **Rationale**: the strings match the existing schema `result` enum; no new class needed (YAGNI).
