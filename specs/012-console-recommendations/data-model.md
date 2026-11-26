# Data Model

No new persisted entity. The feature reads one.

**Recommendation** (owner: data layer; contract `contracts/read/recommendation.schema.json` v1.1.0, model `src/pulsoflota/models/read/recommendation.py`). Fields used by the console: `rec_id`, `action{type,bus_id,stop_id,duration_s?}`, `reason`, `ewt_saving_s`, `data_quality`, `expires_ts`, `conflicts_with[]`, `rank`, `status`. Only `status = proposed` is read.

**RecommendationsResponse** (API only, see `contracts/recommendations-response.md`): `status`, `corridor_id`, `recommendations[0..3]`.

**State rules**
- No snapshot, or corridor other than C6-008 → `no_data`, `[]`.
- `age_s > 15` → `stale`, `[]`.
- Otherwise `ok`, ordered by `rank`, at most 3 (empty list allowed).

**Display mapping**: action → Retener / Despachar reserva / Ajustar salida / Saltar parada / Reducir velocidad; `ewt_saving_s` 55 → «−55 s de espera»; null `duration_s` → omitted; non-empty `conflicts_with` → «En conflicto»; `expires_ts` → «Vence HH:MM» (simulated time).
