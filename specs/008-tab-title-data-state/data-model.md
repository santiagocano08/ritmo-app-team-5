# Data Model: Tab Title Shows Data State

No persisted or exchanged data. No contract impact.

| Concept | Source | Rule |
|---------|--------|------|
| `SourceStatusValue` (`live`, `estimated`, `no_data`) | existing `src/frontend/src/api/types` | Read only. |
| Tab title | derived | `PulsoFlota · ` + `STATUS_LABELS[status]`; any other value maps to `STATUS_LABELS.no_data`. |

| status | title |
|--------|-------|
| `live` | `PulsoFlota · En vivo` |
| `estimated` | `PulsoFlota · Estimado` |
| `no_data` / unrecognized / no response | `PulsoFlota · Sin datos` |
