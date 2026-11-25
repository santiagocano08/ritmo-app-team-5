# Contract: `classify_effect_result`

Internal function contract (no HTTP or schema interface). Module: `src/data/rules/effect_result.py`.

```text
classify_effect_result(*, ewt_before_s, ewt_after_s, expected_saving_s,
                       headway_before_s, headway_after_s, headway_planned_s,
                       coverage_ratio, worked_ratio, min_coverage)
    -> Literal["worked", "partial", "did_not_work", "no_data"]
```

Guarantees: pure, deterministic, no I/O, never raises on None inputs. Semantics follow `docs/adr/0007-recommendation-effect-rule.md`; the result strings equal the `result` enum of `contracts/read/recommendation_effect.schema.json` (unchanged here).
