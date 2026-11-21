# Hold loop: command door as read by the simulator

## The door (unchanged contract)

The backend writes `command_event` rows to `bronze.events` (ADR-0003 gate decision 4):
`source = "backend"`, `event_type = "decision"`, payload `{rec_id, action, user_id, ts}` as in
`contracts/read/command_event.schema.json`. These rows do not pass the ingestion boundary (it lists only the
six turn-1 event types); the backend inserts them directly, and tests do the same. This story adds no
column, table or event type to that door.

## What the simulator reads

With `SIM_HOLDS=on`, a daemon thread polls every `SIM_HOLD_POLL_S` seconds, read-only
(`default_transaction_read_only=on`, 2 s connect and statement timeouts):

```text
decisions: source = 'backend' AND event_type = 'decision' AND id > last_seen_id, in id order
decided_at_sim: newest event_ts among non-backend bus reports with a smaller id (null if none)
```

The query lives in `src/data/rules/sql/hold_orders.sql`, shared with the pipeline so both sides apply one
definition. `event_ts` of the decision is not used (the backend's clock is wall time; the simulated clock is
2026-11-24 22:00Z onward).

If the database is unreachable the poller logs one `hold_poll_failed` line, keeps the orders it has, and
retries each interval; the event stream is never delayed.

## Seed recommendations (until the recommendation door exists)

`src/data/seeds/recommendations.json`: a JSON array of objects that validate against
`contracts/read/recommendation.schema.json` v1.0.0. This story uses entries with `action.type = "hold"`:

| Field used | Meaning |
|---|---|
| `rec_id` | key that the `decision` payload carries |
| `action.bus_id`, `action.stop_id` | target bus and stop |
| `action.duration_s` | requested hold, 0 to 90 s (the schema rejects more, the generated model does not; the hold executor and the seed loader enforce the bound) |
| `ewt_saving_s`, `horizon_s` | expected EWT saving and effect window (effect table) |
| `expires_ts` | end of the validity window; written in **simulated** time (2026-11-24T22:xx:xxZ) |

Data loads the same file into `config.seed_recommendation`. It is demo and test data, not a contract; the
real door is a backend integration item.

## Order rules (simulator and data apply the same ones)

| Situation | Result |
|---|---|
| `action = apply`, known hold `rec_id`, bus arrives at the stop strictly after `decided_at_sim` and not after `expires_ts` | the bus leaves no earlier than `arrival + hold_s` (total dwell; a longer natural dwell is kept), unless the seeded draw says non-compliance |
| `action = discard`, no decision, unknown `rec_id`, a non-hold recommendation | nothing changes (Principle IV) |
| bus already departed when the decision was written | order cannot run; `not_executed` at `expires_ts` |
| hold above 90 s | loads, then refused by the executor (`hold_order_refused`, reason `over_cap`); `not_executed` |
| second order for the same bus and stop | first by bronze id applies; the second is `not_executed` |
| same `rec_id` seen twice | one order |
| `bus_breakdown` fires on the bus before the visit | order cancelled; `not_executed` |
| non-compliance | draw `SHA-256("{seed}\|hold\|{rec_id}")` as a fraction of 1; non-compliant when below `SIM_HOLD_NONCOMPLIANCE`; the bus keeps its natural dwell |

## What data publishes back

`gold.instruction_status` (see [gold-read-access.md](gold-read-access.md)): `executed` when the observed
dwell is within ±15 s of the requested hold, `not_executed` otherwise, with the departure time as the
status time. Data never writes a `confirmation` or any bronze row.

## Backend integration items (not built here)

1. The recommendation door: how the backend hands bus, stop, duration, `ewt_saving_s` and `horizon_s` to data.
2. `inst_id` and `text` of the instruction are backend-owned; the backend joins the data status by `rec_id`
   (plan open question 3).
3. A null-duration backend `incident_report` failed the silver `end_ts NOT NULL` insert (002). Fixed in
   Phase 1 of this story: an unknown duration is an open-ended incident (`end_ts = 'infinity'`, research R6).
