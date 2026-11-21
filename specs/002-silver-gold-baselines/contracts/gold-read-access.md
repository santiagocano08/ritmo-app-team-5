# Gold read access (query door, data side)

The backend story implements the REST endpoints. This file only fixes what the data layer
guarantees to a reader of gold.

## Guarantees

1. **Complete or invisible.** A snapshot and its four rows (`source_status`, `corridor_now`,
   `decision_inputs`, `service_metric`) commit in one transaction (FR-037). A reader that sees a
   `gold.snapshots` row can always read all four.
2. **Schema-exact objects.** `gold.source_status.doc`, `gold.corridor_now.doc` and
   `gold.decision_inputs.doc` are valid instances of `contracts/read/<name>.schema.json` v1.0.0. A
   reader can return `doc` as is.
3. **Latest snapshot** = the `gold.snapshots` row with the highest `as_of_ts`.
4. **Retention**: none in turn 1. Any `snapshot_id` referenced by a recommendation stays readable
   (FR-016).
5. **Audience**: `decision_inputs`, `m1_baseline` and `m2_baseline` are internal to the backend
   decision engine and must not be forwarded to the frontend (FR-035, ADR-0003 gate decision 7).

## Reference queries (parameterized)

```sql
-- latest snapshot
SELECT snapshot_id, as_of_ts FROM gold.snapshots ORDER BY as_of_ts DESC LIMIT 1;

-- one read object for a snapshot (from a notification or a recommendation)
SELECT doc FROM gold.corridor_now WHERE snapshot_id = %(snapshot_id)s;
```

## Not provided here

No endpoints, no roles, no RBAC (turn 2), no WebSocket/SSE fan-out (backend story).
