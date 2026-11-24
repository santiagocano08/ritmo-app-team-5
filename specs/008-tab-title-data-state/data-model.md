# Data Model: Tab Title Data State

No persisted data, no API change, no data contract impact.

## View-level mapping

| Source status (`SourceStatusValue`) | Badge label | Tab title |
|---|---|---|
| `live` | En vivo | `PulsoFlota · En vivo` |
| `estimated` | Estimado | `PulsoFlota · Estimado` |
| `no_data` (also: no response yet) | Sin datos | `PulsoFlota · Sin datos` |

Rules: the title is `PulsoFlota · ` followed by the badge label. The state is the `status` already computed by `resolveSourceStatus` in `src/frontend/src/App.tsx`.
