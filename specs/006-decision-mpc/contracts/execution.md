# Simulator execution contract (phases 2 and 3)

The simulator is a separate container and never writes to the database. It reads `gold.recommendation` through the story-004 poller (read-only session, `connect_timeout=2`, `statement_timeout=2000`). If the database is down it logs one line, keeps the orders it already has, and the event stream is never delayed (004 SC-011, FR-023).

## Poll

1. `fetch_decisions(last_id)`: the shared `hold_orders.sql` query (backend `decision` rows after `last_id`).
2. For each decision, `SELECT rec_id, doc, params FROM gold.recommendation WHERE rec_id = ANY(%s)`. Order fields come from `doc.action` (and `params.ready_s` for a reserve). A `slow_down` row without `speed_reduction_pct` cannot exist (the schema requires it); if one is read anyway, the order is not created and one log line is written.
3. `apply` on a row whose type is executable becomes an order; `discard`, unknown ids and non-executable types do not. An id not yet found is retried at the next poll.

## Orders (simulated seconds since the run start)

| Type | Order fields | Effect in the engine | Phase |
|---|---|---|---|
| `hold` | bus, stop, `hold_s` (≤ 90), `from_s` (the decision), `until_s` (= `expires_ts`) | `dwell_end` returns `max(natural_end, t + hold_s)` for a complying driver (004; seeded compliance by SHA-256 of `seed|hold|rec_id`) | 2, 3a |
| `slow_down` | bus, `share = doc.action.speed_reduction_pct / 100` (read from the recommendation `doc`, not from `params`), `from_s`, `until_s = from_s + duration_s` (`doc.action.duration_s`) | while driving in `(from_s, until_s]`: `drive_t += STEP_S × (1 − share)`; reported `speed_kmh` × (1 − share) | 3b |
| `reserve_dispatch` | reserve bus, `from_s`, `start_s = from_s + ready_s` | at `t ≥ start_s` the reserve joins `buses` and starts a trip at P-883; it emits events like any bus; after the last stop it stops emitting | 3c |
| `adjust_departure`, `skip_stop` | none | counted: `ignored_not_executed[type] += 1`, one JSON log line `not_executed_in_this_story` per `rec_id`; the bus is unchanged | 2 |

## Demo demand: `SIM_DEMAND_SCALE` (phase 2)

`simulator/main.py` reads `SIM_DEMAND_SCALE` (default `1.0`, the real reference demand; accepted 0.1 to 10; anything else stops the simulator before the first event) and passes it to `engine.run(demand_scale=...)`, through `scenario_events` when a scenario or board is active. It changes only how many riders the simulator creates. It is not a field of any message, is not stored, and the model, the rules and the pipeline never read it. With the default the stream and the golden hash are unchanged. The demo runs C1 with `SIM_DEMAND_SCALE=3`.

## Guarantees

- With no approved order the engine output is byte-identical to story 004 for the same seed (SC-009). The hooks are guarded by `if order exists`; no random number is drawn for an order that does not exist.
- A reserve start draws exactly one trip profile from the run's `random.Random`, at the step fixed by `start_s`. The same decisions in bronze therefore give the same stream.
- Orders never touch bronze. Nothing runs for a `proposed` row (Principle IV): only an `apply` decision creates an order.
- A breakdown cancels pending orders of the bus (004 rule, kept).

## Truth records

The existing truth sink gets one record per consumed order (`type`: `HOLD`, `SLOW`, `RESERVE`, with `rec_id`, bus, effective time, `complied` where it applies). Records are written only when the order is consumed, so a run without orders writes none (same as 004).

## Tests

Forced mode with decisions inserted before the run: hold dwell within ±15 s of the recommended time; slow-down speeds with `speed_reduction_pct` 10 and 20 read from the doc (`speed_kmh` ratio and later arrival by `share/(1−share)` of the covered time); reserve first event at `start_s` within one 5 s step and `B-106` present in `corridor_now` after it; not-executed counters for `adjust_departure` and `skip_stop`; poller with the database stopped keeps streaming; golden hash unchanged with no orders.
