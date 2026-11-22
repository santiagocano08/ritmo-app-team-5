# ADR-0007: Recommendation effect rule: observed saving versus expected saving

- Status: Accepted (data owner, 2026-11-21; this rule depends only on data)
- Date: 2026-11-21
- Decided by: data owner, 2026-11-21 (rule H3 in `docs/data-contract.md` v0.2)
- Amends: **ADR-0003, gate decision 6** (`recommendation_effect.result` thresholds). Gate decision 6
  is replaced by the decision below. The rest of ADR-0003 is unchanged.
- Turn: Turn 1 — Data and Minimal Loop (active)
- Addresses: Principle II (Contract-First and Data Ownership: the schema must say what the field
  means), turn-1 risk (data integrity: a metric that says "worked" while EWT got worse misleads the
  dispatcher), RF-2.4 (SHOULD, prioritize by impact) as a later consumer, and the MVP-4 screen
  ("expected / observed").

## Context

ADR-0003 gate decision 6 says `worked` when `ewt_expected_s − ewt_observed_s ≥ 30`. The field
`ewt_expected_s` is a projected **saving** (seconds of EWT reduction). The field `ewt_observed_s` is
an **absolute** EWT after the horizon. The rule subtracts one from the other, so it can report
`worked` while EWT got worse. Story 004 flagged this as a semantic mismatch for the data owner
(`specs/004-scenario-injectors/spec.md`, assumptions). Phase 3 of story 004 (which builds
`gold.recommendation_effect`) is not built yet, so nothing produces the object today.

## Options considered (max. 3)

1. **Keep the 30 s rule.**
   - Pros: no change to schema or ADR-0003.
   - Cons: compares a saving with an absolute EWT; false `worked` is possible.
2. **Absolute threshold on the observed saving** (for example, saving ≥ 30 s).
   - Pros: fixes the semantic mismatch; simple.
   - Cons: ignores what was promised. A 100 s promise that delivers 30 s counts as `worked`, and a 20 s
     promise that delivers 20 s counts as `partial`.
3. **Ratio of observed saving to expected saving (chosen).**
   - Pros: relative to what the recommendation promised; matches the MVP-4 screen ("expected /
     observed"); one rule for all cases.
   - Cons: needs `ewt_expected_s` (not null) and a coverage check; the 50 % ratio is a hypothesis.

## Decision

Adopt option 3. **This amends ADR-0003 gate decision 6.**

- observed saving = EWT before − EWT after;
- EWT before is taken at the last snapshot at or before the decision;
- EWT after is taken at the first snapshot at or after the decision + `horizon_s`.

| Result | Rule |
|---|---|
| `worked` | observed saving ≥ 50 % of `ewt_expected_s` |
| `partial` | 0 < observed saving < 50 % of `ewt_expected_s`, or the headway got closer to plan while EWT did not improve |
| `did_not_work` | observed saving ≤ 0 and the headway did not improve |
| `no_data` | coverage in the window < 90 %, or `ewt_expected_s` is null |

- "The headway got closer to plan" means
  `|headway_after_s − headway_planned_s| < |headway_before_s − headway_planned_s|`, with no
  tolerance. This is the same working definition as `specs/004-scenario-injectors/spec.md`
  (assumptions).

- The thresholds 50 % and 90 % live in `config.effect_settings`, as a hypothesis to validate with
  the dispatcher (same status as the 30 s floor it replaces).
- The engine sets `horizon_s = 600` (10 min), and the seed is updated to match. The MVP-4 chart
  always shows −6 to +10 min around the decision.
- The rule is deterministic code in `rules/`, with tests. No LLM judges the effect.

## Consequences

- **Easier:** `worked` can no longer be reported when EWT got worse; expected and observed are the
  same quantity (a saving), as the MVP-4 screen shows them; thresholds change without a code
  release.
- **Harder:** the story 004 spec, plan and tasks for phase 3 must be updated before phase 3 is built
  (FR-025, SC-009, T047); the `c1_bunching` fixture changes; the rule needs the EWT at two
  snapshots and a coverage figure per window.

## Affected contract

`contracts/read/recommendation_effect.schema.json` **1.0.0 → 1.1.0**:

- `ewt_observed_s` is redefined as the **observed saving** (EWT before − EWT after);
- `ewt_observed_s` drops `minimum: 0`, because an observed saving is negative when EWT got worse;
- new optional fields `ewt_before_s` and `coverage_ratio`;
- the `result` description is updated to the table above;
- the `c1_bunching` fixture is updated.

**The schema is NOT edited in this ADR.** It ships with story 004 phase 3 (FR-025, SC-009 and T047
are updated before phase 3 is built), so schema, generated models, rule code and fixtures change
together. This changes an existing contract: data owner review (CODEOWNERS) is required.

**Version decision: minor bump (1.1.0), as an explicit exception.** Under the ADR-0002/0003
versioning rule, redefining the meaning of an existing field is breaking, and normally needs a new
major version and a new ADR. A minor bump is acceptable here for three reasons. First, no producer
of `recommendation_effect` exists, because phase 3 is not built, so no document with the 1.0.0
meaning was ever published or stored in gold. Second, 1.0.0 is retired: producers emit only 1.1.0
and the 1.1.0 schema does not accept `schema_version: "1.0.0"`, so a 1.0.0 document can never be
read with the new meaning. Third, a major bump would add a version nobody has used and force
consumers to handle a value that never existed. Once any 1.1.0 document is published, the rule
applies in full: a further change of meaning would be major. Accepted by the data owner, 2026-11-21.

## Evolution

- Calibrate the 50 % and 90 % thresholds with dispatcher feedback after the turn-1 value review.
- Use the effect result to prioritize recommendations by P(board ≤ t) (RF-2.4, turn 4).

## Open questions

- [NEEDS CLARIFICATION] Do the backend or frontend already build against the 1.0.0 meaning of
  `ewt_observed_s` (for example, through the `c1_bunching` fixture)? If yes, the data owner must tell
  them before phase 3. The data owner tells the team when the fixture changes in story 004 phase 3.

## Amendment 2026-11-22 (story 005, data owner)

"EWT before" and "EWT after" are now the **stop-based**, trailing-window EWT of story 005, not the spatial snapshot EWT. Consequences for the rule:
- an "EWT before" early in a run, or after a long silence, can be not computable (fewer than 5 headways), which gives `no_data`, never zero;
- the `c1_bunching` fixture numbers change meaning. The current reference for the same 90 s hold is −15.2 s on the 16-minute window (+25.8 s → +10.6 s, C1 seed 42);
- the clamp at 0 and the "before" and "after" windows of story 004 phase 3 are reviewed before that phase is built (`docs/data-contract.md` v0.3 §6, item 13).

The thresholds of the rule do not change.
