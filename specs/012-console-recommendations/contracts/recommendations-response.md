# Contract: `GET /api/v1/corridor/{corridor_id}/recommendations`

Read-only. HTTP 200 for all three states. Unhandled errors use the app's generic 500 body with `correlation_id`.

```json
{
  "status": "ok | stale | no_data",
  "corridor_id": "C6-008",
  "recommendations": [ /* 0..3 items, each valid against recommendation.schema.json v1.1.0 */ ]
}
```

| status | recommendations | when |
|---|---|---|
| `ok` | 0..3, `proposed` only, ordered by `rank` | latest snapshot committed ≤ 15 s ago (wall time) |
| `stale` | `[]` | snapshot committed more than 15 s ago |
| `no_data` | `[]` | no snapshot, or `corridor_id` other than `C6-008` |

Pydantic: `extra="forbid"`, `status` a `Literal`, `recommendations` `max_length=3`; stale and no_data variants use `max_length=0` (mirrors `NoDataSourceStatus`). Only GET is defined. The mock fixture is `contracts/read/fixtures/c1_bunching/recommendation.json`.
