# Recommendation schema 1.1.0 (phase 2)

File: `contracts/read/recommendation.schema.json` (CODEOWNERS). Additive. Version rule: SemVer, same as the 1.0.0 file.

## Exact changes

| Where | 1.0.0 | 1.1.0 |
|---|---|---|
| `title` | `Recommendation (v1.0.0)` | `Recommendation (v1.1.0)` (generated class `RecommendationV110`) |
| `description` | "produced by the backend decision engine" | "produced by the data layer's decision model (MPC)"; the dispatcher approval sentence is kept |
| `properties.schema_version.enum` | `["1.0.0"]` | `["1.0.0", "1.1.0"]`; description: "producers write 1.1.0; 1.0.0 is still read" |
| `properties.action.properties.type.enum` | `hold`, `adjust_departure`, `reserve_dispatch` | add `slow_down`, `skip_stop` |
| `properties.action.properties.type.description` | three types | add: `slow_down`: the bus travels slower for `duration_s`; `skip_stop`: the bus does not stop at stops with an empty queue from `stop_id` on |
| `properties.action.properties.duration_s.description` | hold, adjust, reserve | add `slow_down`: 1..1800 s; `skip_stop`: always null |
| `properties.action.properties.speed_reduction_pct` | absent | new optional number, `0 < x <= 50`, required by an `allOf` conditional when `type = slow_down`, forbidden otherwise (below) |
| root `if/then/else` on `duration_s` | hold 0..90, else adjust -600..600, else null | hold 0..90, else adjust -600..600, **else slow_down 1..1800**, else null |

Unchanged: `case` enum (`C1`, `C2`, `C5`, `D1`), `rank` 1..3, `status`, `lineage` (closed: `model_version`, `rule_version`, `snapshot_id`), every `required` list, `additionalProperties: false`.

Shape of the new else-branch (illustrative, not code to paste):

```json
"else": { "if": {"properties": {"action": {"properties": {"type": {"const": "slow_down"}}}}},
          "then": {"properties": {"action": {"properties": {"duration_s": {"type": "number", "minimum": 1, "maximum": 1800}}}}},
          "else": {"properties": {"action": {"properties": {"duration_s": {"type": "null"}}}}} }
```

placed where the existing last `else` (null) is.

## `action.speed_reduction_pct` (plan decision 2, data owner 2026-11-22)

DECIDED: the slow-down intensity is a structured field in the same 1.1.0 bump.

| Property | Definition |
|---|---|
| `properties.action.properties.speed_reduction_pct` | `{"type": "number", "exclusiveMinimum": 0, "maximum": 50, "description": "Speed reduction in percent while a slow_down is active (10 means the bus travels at 90 % of its speed). Required when type is slow_down; absent for every other type."}` |
| `required` of `action` | unchanged (`type`, `bus_id`, `stop_id`, `duration_s`); the field is **not** added here, so a 1.0.0 document stays valid |
| `additionalProperties` of `action` | stays `false` (the field is declared, so only it is added) |

**Range, justified.** The values the model uses are 10 and 20, from `config.decision_model.slow_shares = {0.10, 0.20}` (data-model M1). Because that list is a data-owner parameter that can change without a schema bump (FR-010), the schema does not enumerate 10 and 20. It bounds the field to `0 < x <= 50`, which keeps a hand-written or future value physically sensible and still rejects 0, negatives and 100 %. The model itself only writes a value taken from `slow_shares` (× 100), and a test asserts that every published `speed_reduction_pct` is in `{p × 100 for p in slow_shares}`. The model's key (research R7) uses this same value, so approving "slow down 20 %" can never turn into 10 %.

**Conditional, like `duration_s`.** The existing `if/then/else` chain on `duration_s` is not reused for this field; a second, separate `allOf` entry keeps each rule readable:

```json
"allOf": [
  { "if":   {"properties": {"action": {"properties": {"type": {"const": "slow_down"}}}}},
    "then": {"properties": {"action": {"required": ["speed_reduction_pct"]}}},
    "else": {"properties": {"action": {"not": {"required": ["speed_reduction_pct"]}}}} }
]
```

(illustrative, not code to paste; if the file already has a root `allOf`, the entry is appended). Effects:

- `slow_down` without `speed_reduction_pct`: invalid.
- `slow_down` with `speed_reduction_pct` 10 or 20 (and `duration_s` 1..1800): valid.
- Any other type (`hold`, `adjust_departure`, `reserve_dispatch`, `skip_stop`) with the field present: invalid.
- A 1.0.0 document (no `slow_down` type exists there): unaffected.

**Consequences elsewhere in the plan.**

- `reason` text still names the intensity for the human ("slow down B-103 by 20 % for 5 min at P-888 saves 14 s per rider"); the number is built from the same field, never parsed back.
- `gold.recommendation.params` no longer carries `share`. It keeps only what is not in `doc`: `{"ready_s": 120}` for `reserve_dispatch`, `{}` for the others. The simulator reads `action.speed_reduction_pct` and `action.duration_s` from `doc` (contracts/execution.md).
- The `key` is `type|bus|stop|duration|speed_reduction_pct` (read from the action).
- The generated class `RecommendationV110` gains `speed_reduction_pct: float | None` (the generator turns the conditional into a plain optional field; the conditional is enforced by the JSON Schema contract test and by the model's own pre-insert validation against the schema, not by the class alone, as is already the case for `duration_s`).

## Fixtures (new directories; the file stem must equal the schema name)

- `contracts/read/fixtures/c1_slow_down/recommendation.json`: `slow_down`, `duration_s` 300, `speed_reduction_pct` 20, `schema_version` 1.1.0, `case` C1.
- `contracts/read/fixtures/c2_skip_stop/recommendation.json`: `skip_stop`, `duration_s` null, `case` C2.

No existing fixture is edited. `test_there_are_18_fixtures` becomes 20 after phase 2 and 22 after phase 4 (a count that is only updated, never relaxed).

## Generated model

`make generate-read` regenerates `src/pulsoflota/models/read/recommendation.py`. CI already asserts the committed file equals a fresh generation. The only importer of the old class name was the seed loader (deleted).

## Tests (written first)

1. The existing 18 fixtures validate against the 1.1.0 schema (no change).
2. Each new fixture validates; each "invalid" variant fails: `hold` with 91 s, `slow_down` with 0 or 1801 or null, `skip_stop` with a number, `reserve_dispatch` with a number, an unknown `type`, an extra `action` field; and, for the new field: `slow_down` without `speed_reduction_pct`, `slow_down` with 0, -5 or 51, a `hold`, `adjust_departure`, `reserve_dispatch` or `skip_stop` that carries `speed_reduction_pct`. A `slow_down` with 10 validates as well as one with 20.
3. `RecommendationV110.model_validate` accepts the fixtures and a document with `schema_version` 1.0.0.
3b. Every `slow_down` row the model publishes has `speed_reduction_pct` in `{p × 100 : p in config.decision_model.slow_shares}` and passes JSON Schema validation (the conditional is checked there, not only by the class).
4. `make generate-read` leaves `git diff` empty on a second run.
