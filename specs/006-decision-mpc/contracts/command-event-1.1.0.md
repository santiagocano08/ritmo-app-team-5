# Command event schema 1.1.0: optional `reason` (phase 4, cut second)

File: `contracts/read/command_event.schema.json` (CODEOWNERS). Additive. Cut together with the shift log (FR-032, FR-033).

## Exact changes

| Where | 1.0.0 | 1.1.0 |
|---|---|---|
| `title` | `Command Event (v1.0.0)` | `Command Event (v1.1.0)` |
| `properties.schema_version.enum` | `["1.0.0"]` | `["1.0.0", "1.1.0"]` |
| `oneOf[decision].properties.payload.properties` | `rec_id`, `action`, `user_id`, `ts` | add `reason`: `{"type": "string", "minLength": 1, "maxLength": 200}`; description: "Why the dispatcher discarded. Optional. Copied to `gold.decision_log.reason`; data never uses it in a computation." |
| `oneOf[decision].payload.required` | `rec_id`, `action`, `user_id`, `ts` | unchanged (`reason` is optional) |
| `incident_report`, `confirmation` payloads | | unchanged |

## Compatibility

- A 1.0.0 `decision` without `reason` stays valid (fixture `c1_discard_legacy`).
- A 1.0.0 envelope carrying `reason` is also accepted. The schema does not tie the payload field to the envelope version, because backend writers can lag and the field is harmless.
- The backend requires `reason` on `discard` (data contract §4.6); that rule is the backend's, not the schema's.
- The bronze table has no schema check on backend events (they are written directly); the data pipeline reads `payload->>'reason'` and tolerates its absence.

## Fixtures

- `contracts/read/fixtures/c1_discard_reason/command_event.json`: `decision`, `discard`, `reason` "Driver not available", 1.1.0.
- `contracts/read/fixtures/c1_discard_legacy/command_event.json`: `decision`, `discard`, no `reason`, 1.0.0.

## Tests (written first)

1. Both fixtures validate; `reason` of 0, 201 characters, or a non-string fails.
2. `test_bronze_builders` validator accepts a Builder `command_decision(reason=...)`.
3. `payload->>'reason'` for a row without it gives `NULL` in `gold.decision_log` (SC-015).
4. Static test: no logging call in `src/data/` interpolates `reason` (it is free text).

There is no generated model for `command_event` and none is added (the Makefile's `READ_SCHEMAS` does not list it).
