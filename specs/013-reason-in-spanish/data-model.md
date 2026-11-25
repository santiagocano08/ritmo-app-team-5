# Data Model: Recommendation Reason in Spanish

No entity, field, table or schema changes. Only the content of one existing field changes.

**Recommendation** (`gold.recommendation` doc, `recommendation.schema.json` 1.1.0): `reason` (string) is now Spanish.

| Action `type` | Fields used | Template |
|---|---|---|
| `hold` | bus_id, duration_s, stop_id, saving | `retener {bus} {s} s en {stop} ahorra {n} s por pasajero` |
| `slow_down` | bus_id, speed_reduction_pct, duration_s (min if multiple of 60, else s), stop_id | `reducir la velocidad de {bus} un {pct} % durante {min} min en {stop} ahorra {n} s por pasajero` |
| `reserve_dispatch` | bus_id | `despachar la reserva {bus} ahorra {n} s por pasajero` |
| `adjust_departure` | bus_id, stop_id, shift_s | `adelantar {s} s la próxima salida desde {stop} ({bus}) ahorra {n} s por pasajero` (shift < 0) or `retrasar ...` |
| `skip_stop` | bus_id, stop_id | `saltar las paradas sin cola para {bus} desde {stop} ahorra {n} s por pasajero` |

Validation: the sentence is derived from structured fields; the reason is not an input to any rule, key (`rec_id`, `action_key`) or metric.

Assumption: when the duration is not a whole number of minutes, the slow-down text keeps today's fallback (`durante {dur} s`).
