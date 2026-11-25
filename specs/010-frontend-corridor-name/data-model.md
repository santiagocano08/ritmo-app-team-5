# Phase 1 Data Model: Real Corridor Name in Header

**Feature**: US-12 — `feature/US-12-frontend-corridor-name`
**Date**: 2026-11-21

This feature introduces **no new persisted entity** and **no contract change**. It reads two fields of an existing read-contract type and derives a display string. The "model" here is the small set of inputs/outputs the formatting helper and the component props work with.

## Source entities (existing, unchanged)

### CorridorNow snapshot (read contract — `CorridorNowV100`)

Defined in `src/frontend/src/api/generated/corridor-now.ts` (generated — do not edit). Only the fields this feature reads are listed.

| Field | Type | Notes (from contract JSDoc) |
|---|---|---|
| `corridor_id` | `string` | Corridor identifier. Turn 1: `'C6-008'`. |
| `direction` | `1` (literal) | Travel direction. Turn 1 supports direction 1 only (station to neighbourhood). |

Exposed to app code as `CorridorNow` (`src/frontend/src/api/types.ts`). In `App.tsx`, `snapshot = fleet.lastSnapshot` has type `CorridorNow | null`.

### Configured corridor identifier (existing constant)

`corridorId = "C6-008"` exported from `src/frontend/src/mocks/fixtures.ts`. Available to the header before any snapshot arrives. Used by `App.tsx` as the query key input and as the pre-snapshot fallback.

## Derived value (new)

### Corridor label (a formatted string, not persisted)

Produced by the new pure helper `formatCorridorLabel(corridorId, direction?)`.

| Input state | `corridorId` | `direction` | Output label |
|---|---|---|---|
| Snapshot present, Turn-1 direction | `"C6-008"` | `1` | `"C6-008 · Estación → barrio"` |
| No snapshot yet | `"C6-008"` (configured) | `undefined` | `"C6-008"` |
| Snapshot seen, later no data | `"C6-008"` (configured) | `undefined` | `"C6-008"` |

Formatting rule:
- `directionText(direction)` = `"Estación → barrio"` when `direction === 1`, else `undefined`.
- label = `directionText` present → `` `${corridorId} · ${directionText}` ``; otherwise `corridorId`.
- Separator is the middle dot `·` (U+00B7) with surrounding spaces, matching the existing mockup separator.

## Component contract (props)

### `CorridorSelectorProps` (new)

```ts
interface CorridorSelectorProps {
  corridorId: string;
  direction?: number; // snapshot provides literal 1; widened at the boundary
}
```

Behaviour: renders the unchanged `CORREDOR` label, an inert `<button type="button">` whose text node is `formatCorridorLabel(corridorId, direction)`, and the `▾` chevron (`aria-hidden="true"`). No `onClick`, no local state.

### `HeaderProps` (extended)

Existing:
```ts
interface HeaderProps {
  status: SourceStatusValue;
  statusDetail?: string;
  stale?: boolean;
}
```
Add:
```ts
  corridorId: string;
  direction?: number;
```
`Header` forwards `corridorId` and `direction` straight to `<CorridorSelector>`.

## Data flow (composition root → leaf)

```
useCorridorNow(corridorId)            // TanStack Query, existing
  → deriveFleetViewState(...)         // existing
  → snapshot = fleet.lastSnapshot     // CorridorNow | null, existing
App.tsx:
  corridorId = snapshot?.corridor_id ?? corridorId   // fixtures constant fallback
  direction  = snapshot?.direction                   // 1 | undefined
  <Header corridorId=... direction=... />
    → <CorridorSelector corridorId=... direction=... />
        → formatCorridorLabel(corridorId, direction)
```

No mutation of query data; all reads. No new fetching.

## Validation rules

- Type safety only; no runtime validation needed. `direction` is already validated at the ingestion/contract boundary (out of scope here). The helper treats any non-`1` or missing direction as "no direction suffix", which is the correct Turn-1 fallback and the edge-case behaviour (`FR-003`, "snapshot then no data").

## State transitions

Not applicable — the label is a pure function of its inputs. The only observable "transition" is pre-snapshot (`C6-008`) → snapshot present (`C6-008 · Estación → barrio`), driven entirely by the existing query returning data.
