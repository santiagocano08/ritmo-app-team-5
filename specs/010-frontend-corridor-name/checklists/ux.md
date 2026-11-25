# UX / Display Requirements Quality Checklist: Real Corridor Name in Header

**Purpose**: Requirements-quality review ("unit tests for English") for US-12 — the header corridor-selector label. Validates that the requirements for the displayed label, its states, and its layout invariants are complete, clear, consistent, measurable, and cover the needed scenarios — before implementation.
**Created**: 2026-11-21
**Feature**: [spec.md](../spec.md) · UI contract: [contracts/corridor-label.md](../contracts/corridor-label.md)

**Focus areas**: (1) Clarity & Measurability of the exact label strings and the copy change; (2) Scenario / edge-case coverage and consistency across spec, UI contract, data-model and tasks.
**Depth**: Standard · **Audience**: Reviewer (PR gate, pre-implementation).

**Review Ownership**: This checklist is a reviewer-owned requirements-quality review artifact. Mark an item `[x]` only when the reviewer determines the requirements-quality criterion is satisfied.
**Marker Semantics**: `[x]` means the criterion has been reviewed and satisfied for requirements quality. It does not mean implementation work is complete.

## Requirement Completeness

- [ ] CHK001 Are requirements defined for every observable state of the selector label (snapshot present, no snapshot yet, snapshot then no data)? [Completeness, Spec §Edge Cases]
- [ ] CHK002 Is the source of the pre-snapshot corridor id explicitly specified as a requirement rather than left to implementation (the "configured corridor identifier")? [Completeness, Spec §FR-003, §Key Entities]
- [ ] CHK003 Are requirements stated for what the label shows when `direction` is absent vs present, independently of implementation wiring? [Completeness, Spec §FR-002/§FR-003]
- [ ] CHK004 Is the layout-preservation requirement (label + button + chevron) enumerated element by element so "unchanged" is objectively checkable? [Completeness, Spec §FR-005, Contract §I2]
- [ ] CHK005 Does the spec state a requirement for the removal scope of `[Corredor piloto]` (what "anywhere in the app" includes/excludes), not only that it must disappear? [Gap, Spec §FR-004/§SC-003]

## Requirement Clarity & Measurability

- [ ] CHK006 Is the snapshot-present label pinned as an exact string (`C6-008 · Estación → barrio`) including the separator and arrow characters, leaving no room for interpretation? [Clarity, Spec §SC-001, Contract §L1]
- [ ] CHK007 Is the separator specified precisely (middle dot U+00B7 with leading and trailing spaces) rather than described loosely as "a dot"? [Clarity, Contract §Output rules]
- [ ] CHK008 Is the direction glyph specified as the exact arrow `→` (U+2192) so the acceptance string is unambiguous? [Clarity, Contract §Output rules]
- [ ] CHK009 Are the success criteria SC-001/SC-002 phrased so the label can be verified by exact-string comparison (measurable), not by subjective judgement? [Measurability, Spec §SC-001/§SC-002]
- [ ] CHK010 Is "no direction suffix" defined precisely enough to distinguish `C6-008` from `C6-008 ·` or `C6-008 · ` (trailing separator ambiguity)? [Ambiguity, Spec §FR-003, Contract §L2]
- [ ] CHK011 Is the copy change from `Estación → casa` to `Estación → barrio` documented as an explicit requirement (not only an assumption), including that the old copy must not remain? [Clarity, Research Decision 3, Contract §I4]

## Requirement Consistency

- [ ] CHK012 Does the exact label string agree across spec (SC-001), the UI contract (L1), and the data-model output table? [Consistency, Spec §SC-001 vs Contract §L1 vs data-model]
- [ ] CHK013 Is the direction-to-text mapping (`direction === 1` → `Estación → barrio`) stated consistently across FR-007, the contract, and research Decision 3? [Consistency, Spec §FR-007, Contract §Output rules]
- [ ] CHK014 Is the SC-003 wording "anywhere in the app" reconciled with the task/quickstart verification scope (`grep … src/frontend/src`), so the requirement and its acceptance check agree on scope (e.g. excluding generated `coverage/`/`dist/` artifacts)? [Consistency, Spec §SC-003 vs tasks T011 / quickstart §6]
- [ ] CHK015 Do the "inert button" requirement (FR-006) and the "layout unchanged" requirement (FR-005) agree on whether the chevron `▾` remains, since a chevron normally signals an interactive menu? [Consistency, Spec §FR-005/§FR-006]
- [ ] CHK016 Are the prop names and types in data-model (`CorridorSelectorProps`, `HeaderProps`) consistent with the fields the spec/contract require the label to be derived from? [Consistency, data-model §Component contract]

## Acceptance Criteria Quality

- [ ] CHK017 Does every functional requirement (FR-001..FR-007) have at least one measurable acceptance check mapped to it in the UI contract's check table (C1–C6)? [Coverage, Contract §Acceptance checks]
- [ ] CHK018 Is SC-004 ("no visual regression in that region") expressed as an objectively reviewable criterion (which elements, which classes), or does it rely on subjective "looks the same" judgement? [Measurability, Spec §SC-004]
- [ ] CHK019 Is SC-005 (frontend quality gate) stated with concrete pass thresholds (coverage > 80 %, lint 0 warnings, type check clean, build green) so "gate stays green" is unambiguous? [Measurability, Spec §SC-005]

## Scenario & Edge-Case Coverage

- [ ] CHK020 Are requirements defined for the "snapshot then later no data" transition, explicitly stating the label must not revert to `[Corredor piloto]`? [Edge Case, Spec §Edge Cases]
- [ ] CHK021 Is the behaviour for a `direction` value other than `1` (future/unexpected) specified as a requirement, or deliberately declared out of scope? [Coverage, Spec §Assumptions, Research Decision 3]
- [ ] CHK022 Is the inert-selector interaction (clicking does nothing) captured as a requirement with an acceptance check, not only narrated? [Scenario Coverage, Spec §Edge Cases/§FR-006, Contract §I3]
- [ ] CHK023 Are accessibility expectations for the unchanged chevron (`aria-hidden="true"`) stated as a requirement so a reviewer can confirm the attribute is preserved? [Coverage, Contract §Surface]

## Dependencies & Assumptions

- [ ] CHK024 Is the assumption that `[Corredor piloto]` is rendered by exactly one component (not duplicated elsewhere) stated and independently verifiable? [Assumption, Spec §Assumptions]
- [ ] CHK025 Is the assumption that the configured corridor id (`C6-008`) is already available to the header without a snapshot documented and traceable to its source? [Assumption, Spec §Assumptions, data-model §Configured corridor identifier]
- [ ] CHK026 Is the dependency on the unchanged `CorridorNow` read contract (fields `corridor_id`, `direction`) stated as a requirement boundary (no contract/generated-type change in scope)? [Dependency, Spec §Assumptions, plan §Constitution Check II]
- [ ] CHK027 Is the Turn-1 / Adaptive-lane scope boundary (single corridor, single direction, no corridor switching) recorded as an explicit assumption that bounds the requirements? [Assumption, Spec §Assumptions, plan §Turn-scope note]

## Ambiguities & Conflicts

- [ ] CHK028 Is the expected-to-change Header test (dropping `Estación → casa`) distinguished in the requirements from an accidental regression, so reviewers do not flag it as a broken test? [Ambiguity, Spec §Assumptions, Research Decision 3]
- [ ] CHK029 Does any requirement leave the pre-snapshot id source ambiguous between "snapshot corridor_id" and "configured fixture constant" in a way a reviewer must resolve before implementation? [Ambiguity, Spec §FR-001/§FR-003 vs data-model data-flow]

## Notes

- Mark items `[x]` only after review confirms the requirement-quality criterion is satisfied.
- Leave items unchecked when they still require clarification, correction, or reviewer evaluation.
- `/speckit.implement` reads checklist checkbox state as a gate and must not modify markers.
- `checklists/requirements.md` has a separate built-in lifecycle maintained by `/speckit.specify` and `/speckit.clarify`.
- Highest-risk requirement items to confirm first: CHK014 (scope mismatch between SC-003 "anywhere in the app" and the `src/frontend/src` grep) and CHK005 (removal scope definition).
