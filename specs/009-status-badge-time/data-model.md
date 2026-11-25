# Data Model: Status Badge Readable Time

No persisted data and no contract change (FR-007). Input is the existing generated `SourceStatusV100` (`src/frontend/src/api/generated/source-status.ts`) or the `no_data` envelope.

## Formatter interface (internal)

`formatStatusDetail(status, asOfTs, sourcesDown) -> string`

| status | Input used | Output |
|---|---|---|
| `live` | `as_of_ts` (UTC ISO) | `Último evento HH:MM:SS` (local, 24 h) |
| `estimated` | min of `sources_down[].since` | `Una fuente no responde desde HH:MM` |
| `no_data` | none | `Sin eventos del corredor` |

Validation and edge cases:
- Zero-padded fields (`07:05:09`); midnight is `00:xx`.
- `estimated` with no parsable `since` → `Una fuente no responde`.
- `live` with unparsable `as_of_ts` → `Último evento`.
- No alert is derived from `estimated` (FR-004); banner and header clock are untouched (FR-005).
