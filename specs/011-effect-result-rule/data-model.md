# Data Model: Effect Result Rule

No persisted entities. In-memory values only.

**Effect inputs** (all arguments):

| Name | Type | Notes |
|---|---|---|
| `ewt_before_s` | float \| None | None → `no_data` |
| `ewt_after_s` | float \| None | None → `no_data` |
| `expected_saving_s` | float \| None | None or ≤ 0 → `no_data` |
| `headway_before_s` | float \| None | None is never "closer" |
| `headway_after_s` | float \| None | None is never "closer" |
| `headway_planned_s` | float | input, not fixed |
| `coverage_ratio` | float | fraction 0..1 |
| `worked_ratio` | float | 0.5 in the ADR |
| `min_coverage` | float | 0.9 in the ADR |

**Effect result**: `worked` \| `partial` \| `did_not_work` \| `no_data`.

Derived: `observed_saving = ewt_before_s − ewt_after_s`; `closer = |after − planned| < |before − planned|`.

Decision flow (first match wins):
1. `no_data` conditions → `no_data`
2. `observed_saving >= worked_ratio * expected_saving_s` → `worked`
3. `observed_saving > 0` or `closer` → `partial`
4. otherwise → `did_not_work`
