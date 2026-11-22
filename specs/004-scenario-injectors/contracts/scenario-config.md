# Scenario file, CLI and truth record

## Command line

```text
python -m src.data.simulator.main --seed S --duration D [--pace P]
    [--scenario-file PATH] [--truth-path PATH] [--holds on|off]
```

The first three flags are the 001 contract and do not change. The new flags default from
`SIM_SCENARIO_FILE`, `SIM_TRUTH_PATH` and `SIM_HOLDS`. Stdout stays JSON-lines envelopes of
`contracts/turn1-events/`; nothing else is ever written to stdout. An invalid scenario file exits non-zero
**before the first event**, with one JSON line on stderr naming the scenario `id` and the field.

## Scenario file

A JSON array. Strict: unknown fields are errors. Times are integer simulated seconds after the run start
(17:00 local, 22:00:00Z).

```json
[
  {"type": "D1_SILENCE", "id": "d1-silent-b101", "start_s": 250, "bus": "B-101", "duration_s": 300},
  {"type": "C1", "id": "c1-b102", "start_s": 700, "bus": "B-102", "stop": "P-885", "extra_s": 400},
  {"type": "C5", "id": "c5-b104", "start_s": 2400, "bus": "B-104", "duration_s": 240}
]
```

(The example shows the shape only; the demo values are fixed by a dry run in Phase 4.)

| `type` | Required fields | Effect |
|---|---|---|
| `C1` | `id`, `start_s`, `bus`, `stop`, `extra_s` | extends the dwell of `bus` at `stop` by `extra_s` at its first arrival at or after `start_s` |
| `C2` | `id`, `start_s`, `bus`, `delay_s` | delays the next future departure of `bus` from P-883 by `delay_s` |
| `C5` | `id`, `start_s`, `bus`, `duration_s` | the bus stops while driving for `duration_s`; one `incident_report` (`bus_breakdown`, `reported_by: script`, `duration_min = duration_s / 60`) |
| `D1_SILENCE` | `id`, `start_s`, `bus`, `duration_s` | removes the bus's `bus_position`, `stop_arrival`, `stop_departure` in `[start_s, start_s + duration_s)` |
| `D1_DUPLICATES` | `id`, `start_s`, `count` | writes each of the next `count` events twice |

Ranges: see `data-model.md` E1. Rejected at start: unknown `type`, missing or negative `start_s`, unknown bus
(only B-101..B-105) or stop (C1 only P-884..P-899), a value outside its range, a repeated `id`, an unknown
field, two of C1, C2, C5 on the same bus. `start_s` at or beyond `--duration` is valid and gives
`fired: false`.

Guarantees: with no file, or `[]`, the stream is byte-identical to the 001 simulator for the same seed and
duration. The same file, seed and duration give the same stream and the same truth.

## Truth record

One JSON object per line (file `SIM_TRUTH_PATH` or stderr). Fields: `data-model.md` E2. Example:

```json
{"scenario_id": "c5-b104", "type": "C5", "bus": "B-104", "stop": null, "fired": true,
 "effective_ts": "2026-11-24T22:40:00Z", "params": {"start_s": 2400, "duration_s": 240}}
```

Rules: written when the injector fires; unfired records are appended at the end of the run; never read by
ingestion, silver, gold, refresh or ops (static test); no payloads, secrets or PII.
