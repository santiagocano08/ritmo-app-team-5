# `gold.recommendation`, `gold.mpc_evaluation`, `gold.decision_log` (phases 2 and 4)

Columns are in `data-model.md` (M5, M6, M7). This note fixes the read queries and write rules the backend, the simulator and tests rely on.

## Writers and readers

| Object | Writer | Readers |
|---|---|---|
| `gold.recommendation` | `pipeline/recommend.py` in the cycle transaction (INSERT, and UPDATE of derived columns) | backend (Q13), simulator poller (read-only session), `pipeline/holds.py`, `pipeline/decision_log.py`, tests |
| `gold.mpc_evaluation` | same step (DELETE + INSERT) | tests, data owner |
| `gold.decision_log` | `pipeline/decision_log.py` (DELETE + INSERT) | backend (Q11) |

The backend and the simulator have `SELECT` only on these tables. The model has no write access to bronze.

## Q13: active recommendations (console)

```sql
SELECT doc FROM gold.recommendation
WHERE doc->>'status' = 'proposed'
ORDER BY (doc->>'rank')::int;
```

Unchanged from data contract v0.3 §4.5. By the data owner's decision (2026-11-22, DECIDED), rows with `stale = true` are included: they are still `proposed` until they expire, and they keep their last rank and frozen numbers. SC-003 counts only the current top 3. Hiding them would take `AND NOT stale` in the console query; it is not planned.

## Q11: shift log

```sql
SELECT rec_id, "case", action, proposed_ts, outcome, decided_ts, user_id, reason,
       instruction_status, effect_result
FROM gold.decision_log
WHERE proposed_ts >= %(shift_start)s AND proposed_ts < %(shift_end)s
ORDER BY proposed_ts DESC;
```

As in the contract. The test runs this exact text.

## Status derivation (the only source of `status`)

1. The first `decision` per `rec_id` by bronze id (`hold_orders.sql`, with `reason` added in phase 4): `apply` gives `applied`, `discard` gives `discarded`.
2. Otherwise `expired` when `as_of > expires_ts` or the bus has passed the stop (a `silver.stop_visits` row for the bus and stop with `arrival_ts >= proposed_ts`).
3. Otherwise `proposed`.

The backend never writes a status. A `decision` for an unknown `rec_id` is ignored by the data side (no row is created).

## Executor contract (what the hold loop reads)

`pipeline/holds.py` and the simulator poller read, for each approved `rec_id`: `doc.action.type`, `bus_id`, `stop_id`, `duration_s`, `speed_reduction_pct` (slow down), `doc.expires_ts`, and `params` (only `ready_s` for a reserve). For `hold` they apply the 004 rules unchanged (cap 90 s, tolerance 15 s, strictly-after matching, conflict, breakdown). `gold.instruction_status` keeps its columns and constraints.

## Idempotency and determinism

- Same bronze and same cycle sequence give the same rows, `rec_id`s and order (SC-001, SC-007).
- Rest (DECIDED): a key rests 5 minutes from `close_ts`, which is the expiry or passing time for an expired row and the decision's event time for an applied or discarded row.
- Immutable columns: `rec_id`, `key`, `proposed_ts`, `expires_ts`, `first_snapshot_id`, `params`.
- A rolled-back cycle leaves no row (the step is inside the cycle transaction).
- Rows are kept after they close; no retention rule in this story.
