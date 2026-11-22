# Specification Quality Checklist: Scenario Injectors, Hold Loop and Effect Table

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-11-21
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs). Note: this is a data story, so layer names (bronze, silver, gold), contract files and the CI-ready command are the stated ground truth, as in stories 001 to 003. No language, library, SQL or file layout is prescribed; the truth-store location and rule version label are left to the plan.
- [x] Focused on user value and business needs (demo script, dispatcher loop, effect table)
- [x] Written for non-technical stakeholders (scenarios and outcomes first; contract references only where they are binding)
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain. The three markers (FR-017, FR-018, FR-029) were resolved on 2026-11-21 and recorded in the Clarifications section.
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable (each is checked by execution with a fixed seed)
- [x] Success criteria are technology-agnostic (verified by execution; tool names appear only where the deliverable is that tool)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded (FR-032 lists the Evolution items)
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria (FR-017, FR-018 and FR-029 are now testable after the 2026-11-21 answers)
- [x] User scenarios cover primary flows (P1 injectors, P2 hold loop, P3 effect table)
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Numbers audit

Every number comes from the repository or the story brief: 600 s planned headway, 50 % and 150 % (300 s and 900 s), 120 s Estimated rule, 90 s maximum hold, ±15 s execution tolerance, 30 s effect threshold, 10 % non-compliance (marked as an assumption), 5 s step and refresh cycle, 5 + 2 buses, capacity 40, 80 % coverage, about 8 minutes of demo. Nothing else is invented.

## Notes

- Validation iteration 2 of 3 (2026-11-21). The three clarification markers were answered by the data owner and applied; all items pass. Ready for `/speckit.plan`.
- Open integration item (not a spec defect): the `decision` event carries only `rec_id`, `action`, `user_id` and `ts`, so recommendations are seeded in this story; the real door is deferred to the backend integration.
- Contract observations for the data owner (not changed here): (1) the `decision` command event carries no bus, stop or duration; (2) ADR-0003 gate decision 6 compares a projected EWT reduction with an observed EWT; (3) the write contract requires a numeric `duration_min` for `incident_report`, while the read schema allows a null `duration_s` (dispatcher reports only).
- Items marked incomplete require spec updates before `/speckit.clarify` or `/speckit.plan`.
