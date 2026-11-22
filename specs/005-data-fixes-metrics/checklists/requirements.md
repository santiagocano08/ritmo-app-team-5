# Specification Quality Checklist: Data Fixes and Boarding-Probability Metrics

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-21
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — no language, framework or API is named. Domain objects (`gold.service_metric`, `silver.stop_visits`, `config.ref_stops`) appear because the data owner's brief and the review findings name them; no code or design is given.
- [x] Focused on user value and business needs
- [ ] Written for non-technical stakeholders — partial: this is a data-layer story for the data owner and the decision-model team, so it keeps table and rule names. Each story opens with the dispatcher-facing consequence.
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — resolved 2026-11-21 (EWT window, see Notes)
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details) — they use the review's numbers, oracle recomputations and injected events, not tools
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Iteration 2 of 3 (2026-11-21). The EWT window question was answered by the data owner (both: trailing 15 min for the live headline, closed clock-aligned bands for reports and payment). Spec updated in Clarifications, FR-034, A-1, SC-005 and SC-006; assumptions A-9 to A-12 added (time of day, flat 600 s plan, weekday only, SIMM January 2021 bias). 0 markers remain.
- Only open item: "Written for non-technical stakeholders" stays unchecked (data-layer story, keeps table and rule names).
- Check for the plan: SC-006 keeps the oracle's reference window (22:28:55–22:44:55, 16 min). A trailing 15-minute window ending at 22:44:55 starts at 22:29:55, so the headline value of that snapshot may differ from +40.6 s / +23.6 s. The plan must confirm which window reproduces those numbers.
- ADR-0006, ADR-0007 and `docs/data-contract.md` are not on this branch (they are on `docs/data-contract`). The spec cites them from there (A-8).
- Review numbers (+40.6 s / +23.6 s) are taken from the brief and have not been re-run by this spec.
- Items marked incomplete require spec updates before `/speckit.clarify` or `/speckit.plan`.
