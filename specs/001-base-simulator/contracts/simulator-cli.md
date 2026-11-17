# Contract: Base Simulator CLI

**Authority**: this feature (FR-017..FR-026). The base simulator produces a
deterministic stream of contract-valid fleet and rider events for corridor
C6-008, direction 1.

## Command

```
python -m src.simulator.main --seed <S> --duration <D>
```

| Flag | Type | Required | Notes |
|---|---|---|---|
| `--seed` | int | yes | Seeds the single RNG; same seed → byte-identical output (FR-025, SC-001). |
| `--duration` | int (seconds) | yes | Simulated run length. Shorter than one trip emits partial-trip events (edge case). |

## Output

One JSON **envelope per line** on stdout (JSON-lines), keys sorted
(`json.dumps(..., sort_keys=True)`) for byte-identical reproducibility. Each
line is a full envelope per `contracts/turn1-events/envelope.schema.json`
(**without** `arrival_ts`, which ingestion stamps).

## Emitted event types (FR-023, R16)

- `bus_position` — every 5 s per **in-service** bus (B-101..B-105). Reserve buses
  (B-106..B-107) emit nothing (roster only).
- `stop_arrival`, `stop_departure` — at each stop along the trip.
- `rider_arrival` — per boarding attempt.

`driver_confirmation` and `incident_report` exist in the contract but are
**not emitted** by the base simulator.

## Behavioural invariants (asserted by tests)

- Determinism: two runs with the same `--seed` produce a byte-identical stream
  (identical output hash), including `event_id`s (R13).
- Travel time: `length / (free_flow * 3.6 * congestion_factor) * lognormal`
  per segment (FR-019); a single declared `SIGMA` (default 0.20), seeded.
- Dwell: `10 + 3*boarded + 2*alighted` seconds, minimum 10 s (FR-020).
- Capacity: occupancy never exceeds 40; surplus riders are `rejected` and do
  not board (FR-022).
- Trip duration: a peak-hour end-to-end trip ≈ 25 min (≈19.5 running + ≈5.7
  dwell) within ±20 % (FR-026, SC-006).

## Library / tests

- `src.simulator.engine.run(seed, duration) -> Iterator[dict]` yields envelope
  dicts with no DB and no I/O — used by the determinism/capacity/travel-time
  tests (US-4 needs no persistence layer).

## Non-goals (this story)

- No persistence (the simulator does not write to bronze; ingestion does).
- No scenario injectors, no decision engine, no direction 2, no map.
- No throughput targets (the exercise fleet 5 + 2 buses, 5 s step is in scope).
