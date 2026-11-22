# Phase 1 Data Model: Dispatcher Console — Fleet State and Headway

The console owns **no persisted data and no business logic**. Every entity below is a read-only view model derived from the approved read contracts (`contracts/read/corridor_now.schema.json` and `source_status.schema.json`, v1.0.0) plus purely client-side UI state. States, headways, counts and data quality are computed by the backend/data layer; the frontend formats and arranges them.

## Contract-derived entities (generated types — do not hand-edit)

### CorridorNow (from `corridor_now.schema.json` v1.0.0)
| Field | Type | Notes |
|---|---|---|
| `schema_version` | `"1.0.0"` | Contract version guard. |
| `snapshot_id` | UUID | Same value as `source_status.snapshot_id` for one cycle; use to detect a new snapshot (FR-014). |
| `as_of_ts` | ISO datetime (UTC) | When the gold view was computed. |
| `corridor_id` | string | `"C6-008"` this turn. |
| `direction` | `1` | Only direction served. |
| `buses` | `Bus[]` | Already ordered leader-first (distance descending); render as-is (R5). |
| `summary` | `Summary` | Corridor counts. |

### Bus (item of `CorridorNow.buses`)
| Field | Type | UI meaning |
|---|---|---|
| `bus_id` | enum `B-101..B-107` | Row identity. |
| `direction` | `1` | — |
| `prev_stop_id` / `next_stop_id` | string | Position context ("between P-… and P-…"). |
| `distance_along_m` | number 0–5119.4 | Position along corridor (no map). |
| `headway_ahead_s` | number \| **null** | Gap to bus ahead; `null` ⇒ leader or broken-down ⇒ no comparison (R5). |
| `headway_planned_s` | number ≥ 1 | Planned headway (600 s peak) for the actual-vs-planned display (FR-002). |
| `bus_state` | enum `leader\|regular\|bunched\|gap\|broken_down` | Drives StateTag + visual distinction (FR-002/FR-004). Rendered with text, not color alone (FR-012). |
| `data_quality` | enum `live\|estimated` | `estimated` labels the bus; never alerts (FR-008). |
| `ts` | ISO datetime (UTC) | Freshness of this bus's last event. |

### Summary (from `CorridorNow.summary`)
| Field | Type | UI meaning |
|---|---|---|
| `buses_in_service` | int ≥ 0 | Count shown in corridor summary (FR-005). |
| `n_bunched` | int ≥ 0 | Bunched count. |
| `n_gaps` | int ≥ 0 | Gap count. |

### SourceStatus (from `source_status.schema.json` v1.0.0)
| Field | Type | UI meaning |
|---|---|---|
| `schema_version` | `"1.0.0"` | Version guard. |
| `snapshot_id` | UUID | Matches `corridor_now.snapshot_id` for the same cycle. |
| `as_of_ts` | ISO datetime (UTC) | When computed. |
| `status` | enum `live\|estimated\|no_data` | Drives the status indicator and the data-state badge; banner shown only for `estimated`/`no_data` (FR-006/FR-007). |
| `sources_down` | `{bus_id, since}[]` | Buses silent > 2 min; empty when `live`. Explains the `estimated` banner. |

### NoDataEnvelope (API-level, from US-05 FR-008/FR-011)
Returned by either endpoint at HTTP 200 when gold is empty or the corridor is unsupported. Not part of the `corridor_now` contract document — handled as a sibling case.
| Field | Type |
|---|---|
| `status` | `"no_data"` |
| `corridor_id` | string (echoes the request) |
| `sources_down` | `[]` (source-status variant only) |

## Client-side UI state (not from any contract)

### FleetViewState (derived per refresh cycle)
| Field | Type | Source / rule |
|---|---|---|
| `connection` | `"ok" \| "stale"` | `"stale"` when the latest refresh failed to reach the backend (TanStack `isError` with a prior snapshot kept). Independent of `SourceStatus` (R4). |
| `lastSnapshot` | `CorridorNow \| null` | Last successful body; retained while stale so the view never blanks (FR-010). |
| `lastSourceStatus` | `SourceStatus \| NoDataEnvelope \| null` | Last successful status body. |
| `isEmpty` | boolean | True when `buses_in_service === 0` or a no-data envelope was returned ⇒ empty state with zero counts (FR-013). |
| `lastUpdated` | ISO datetime | `as_of_ts` of the current snapshot, shown to the dispatcher. |

### NavigationContext (shell state, FR-011; presentational only)
Styled per `tickets/US-06-frontend-home/US-06-escritorio-estilos.md` (§4–§8).
| Field | Type | Notes |
|---|---|---|
| `activeCorridor` | `"C6-008"` | Only option this turn; selector present but single-valued ("[Corredor piloto] · Estación → casa"). |
| `activeSection` | `"live_central" \| "alerts" \| "day_plan"` | Dispatcher sections (Central en vivo / Alertas / Plan del día); active one marked with `aria-current="page"`. Defaults to `live_central`. |
| `now` | clock time | Current time in the header (Space Grotesk 22/700). |
| `dataStateBadge` | mirror of `SourceStatus.status` + stale flag | `role="status"` pill; live/estimated/no-data palette from reference §2/§8. |
| `userIdentity` | `{ name: "Usuario demo", role: "dispatcher" }` | Footer avatar "UD" + name + role; display only — the console decides no access control. The "Cerrar sesión" link is presentational this turn. |

## Derived display values (formatting only, no business logic)

| Display | Rule |
|---|---|
| Headway delta | Show `headway_ahead_s` and `headway_planned_s`; indicate direction/magnitude of deviation. No comparison when `headway_ahead_s` is `null`. Classification (`bunched`/`gap`) is **not** recomputed — it comes from `bus_state`. |
| Position label | Derive from `prev_stop_id`/`next_stop_id` and `distance_along_m`; presentation only. |
| State tag | Map `bus_state` to a text label (+ redundant color/icon) — FR-012. |
| Quality tag | Map `data_quality` to "Live"/"Estimated" text (+ redundant styling). |
| Banner text | Shown only for `estimated` (operator source down) and `no_data` (rely on the day's plan); hidden for `live` (FR-007). |

## State transitions (view-level, between refresh cycles)

```
live  ──source goes silent >2min──▶  estimated (banner appears, no alert)
estimated ──all buses report again──▶ live (banner clears)
any ──no events > no-data threshold──▶ no_data (banner: rely on day plan)
ok  ──refresh fails to reach backend──▶ stale (keep last snapshot, retry next cadence)
stale ──next refresh succeeds──▶ ok (connection flag clears)
```

All transitions happen on the next refresh without a manual reload (FR-009/FR-014, SC-002/SC-006). `connection` (stale) is orthogonal to `status` (live/estimated/no_data): a snapshot can be `estimated` while the connection is `ok`, or `ok`-labelled `live` data can go `stale` if the next poll fails.

## Validation rules

- Generated types enforce the contract shape; the client additionally asserts `schema_version === "1.0.0"` and surfaces a mismatch rather than rendering unknown data.
- The frontend never invents or defaults a missing contract field; a malformed body is treated as a failed refresh (stale), consistent with 004's "no silent defaults" rule.
- No field outside the approved contracts is read or displayed (Principle II; `data-profile-review` contract rule).

## Contract impact

**No data-contract impact.** This feature is a pure consumer of `corridor_now` v1.0.0 and `source_status` v1.0.0; it adds, removes or changes no field, table, view, metric or rule. Per the data-owner rule, no update to `docs/data-contract.md`, `contracts/read/` or data ADRs is required.
