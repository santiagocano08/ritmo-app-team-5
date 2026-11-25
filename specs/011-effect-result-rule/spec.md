# Feature Specification: Effect Result Rule

**Feature Branch**: `011-effect-result-rule`

**Created**: 2026-11-25

**Status**: Draft

**Input**: User description: "Effect result rule only (ADR-0007), pure function and unit tests (subtask of #26, story 004 phase 3, US-11). Classify the outcome of an approved recommendation as worked / partial / did_not_work / no_data from EWT and headway before and after, with no database, pipeline or contract change."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Classify the outcome of a recommendation (Priority: P1)

After a dispatcher approves a recommendation, the system must say whether it helped. Given the excess wait time (EWT) and headway measured before and after, the promised EWT saving, the planned headway, the coverage of the measurement window and the two thresholds, the rule returns one of four results: `worked`, `partial`, `did_not_work` or `no_data`.

**Why this priority**: It is the only deliverable of this issue. Later work (stored effects, pipeline step) depends on it, and the result feeds the service-quality metric, so its correctness is critical.

**Independent Test**: Run the new unit test file alone. Each row of the ADR-0007 rule table is covered by at least one case, and the rule module reaches 100 % coverage.

**Acceptance Scenarios**:

1. **Given** an observed saving (EWT before − EWT after) exactly 50 % of the expected saving, **When** the rule is applied, **Then** the result is `worked`; just below 50 % it is `partial`.
2. **Given** a saving ≤ 0 and a headway closer to the planned headway after than before, **When** the rule is applied, **Then** the result is `partial`.
3. **Given** a saving ≤ 0 and a headway not closer to plan (or a null headway), **When** the rule is applied, **Then** the result is `did_not_work`.
4. **Given** coverage of 0.89, **When** the rule is applied, **Then** the result is `no_data`; at 0.90 the outcome is evaluated normally.
5. **Given** a null expected saving, null EWT before or null EWT after, **When** the rule is applied, **Then** the result is `no_data` and no zero saving is assumed.
6. **Given** an expected saving of 0 or negative, **When** the rule is applied with any saving, **Then** the result is `no_data`.
7. **Given** different values for the worked ratio, minimum coverage or planned headway, **When** the rule is applied to the same measurements, **Then** the result changes accordingly.

---

### Edge Cases

- Expected saving of 0 with an observed saving of 0: `no_data`, never `worked` or `did_not_work`.
- Headway before or after null with a saving ≤ 0: `did_not_work`, since an improvement cannot be shown.
- Saving > 0 but below the worked threshold: `partial`, regardless of headway.
- Several conditions failing at once: `no_data` conditions are checked first and win.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The rule MUST return `no_data` when coverage is below the minimum coverage, the expected saving is null or ≤ 0, or EWT before or after is null. This check MUST come before any other.
- **FR-002**: The rule MUST return `worked` when the observed saving is at least the worked ratio times the expected saving.
- **FR-003**: The rule MUST return `partial` when the observed saving is above 0 but below the worked threshold, or when the headway moved closer to the planned headway while EWT did not improve.
- **FR-004**: The rule MUST return `did_not_work` when the observed saving is ≤ 0 and the headway did not move closer to plan.
- **FR-005**: The worked ratio (0.5), the minimum coverage (0.9) and the planned headway MUST be inputs to the rule, not fixed values inside it.
- **FR-006**: The rule MUST be deterministic and free of side effects: no database, no pipeline, no contract change.
- **FR-007**: Unit tests for every case above MUST be written before the rule and MUST pass.
- **FR-008**: Only the rule module and its unit test file are added or changed.

### Key Entities

- **Effect result**: One of `worked`, `partial`, `did_not_work`, `no_data`.
- **Effect inputs**: EWT before and after, expected saving, headway before and after, planned headway, window coverage, worked ratio and minimum coverage.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All six groups of test cases from the issue pass, each producing the stated result.
- **SC-002**: The rule module has 100 % test coverage.
- **SC-003**: The change touches exactly two files, and the full host suite and CI stay green on the pull request.
- **SC-004**: Changing any of the three configurable inputs changes the result in at least one test case.

## Assumptions

- The ADR-0007 rule governs; the older 30 s rule in task T046 is out of scope and will be updated under #26.
- A headway is "closer to plan" when |after − planned| < |before − planned|; with a null headway it is not closer.
- Coverage is a fraction between 0 and 1.
- Settings, the recommendation-effect table, the pipeline step, reading recommendations and the live check are left for #26.
- Data contract impact: none, as no table, view, metric definition or published field changes.
