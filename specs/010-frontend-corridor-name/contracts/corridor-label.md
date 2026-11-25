# UI Contract: Corridor Selector Label

**Feature**: US-12 — `feature/US-12-frontend-corridor-name`
**Date**: 2026-11-21
**Type**: Frontend display contract (the UI surface this feature exposes). No network/API contract is added or changed.

> This is **not** a data/API contract. The backend read contract (`contracts/read/`, `CorridorNowV100`) is unchanged. This document pins the user-visible behaviour of the header corridor selector so tests and review have a single reference. Data-contract impact: **none**.

## Surface

Component: `src/frontend/src/components/shell/CorridorSelector.tsx`, rendered by `src/frontend/src/components/shell/Header.tsx`, composed in `src/frontend/src/App.tsx`.

Structure (layout unchanged from current):
- A `CORREDOR` label (`<span>`, uppercase, tracking preserved).
- An inert `<button type="button">` containing the corridor label text node followed by a chevron `▾` (`<span aria-hidden="true">`).

## Inputs

Pure formatter: `formatCorridorLabel(corridorId: string, direction?: number): string`
(`src/frontend/src/components/shell/corridorLabel.ts`).

| Parameter | Type | Source |
|---|---|---|
| `corridorId` | `string` | `snapshot.corridor_id` when present, else the configured `corridorId = "C6-008"` (`mocks/fixtures.ts`). |
| `direction` | `number \| undefined` | `snapshot.direction` (literal `1` in Turn 1) when a snapshot is present, else `undefined`. |

## Output rules

| # | Condition | Rendered button text |
|---|---|---|
| L1 | `direction === 1` | `` `${corridorId} · Estación → barrio` `` → e.g. `C6-008 · Estación → barrio` |
| L2 | `direction` is `undefined` or any value ≠ `1` | `corridorId` → e.g. `C6-008` |

- Separator: `· ` (middle dot U+00B7 with a leading and trailing space), as `` `${corridorId} · ${text}` ``.
- Direction text for Turn 1: exactly `Estación → barrio` (arrow is `→` U+2192). No other direction text exists in Turn 1.

## Invariants

- **I1**: The string `[Corredor piloto]` MUST NOT appear in the rendered output anywhere in the app (FR-004, SC-003).
- **I2**: The `CORREDOR` label, the button and the `▾` chevron keep their existing position, order and styling classes (FR-005, SC-004).
- **I3**: The button is inert — no `onClick`, no handler, no state; clicking does nothing (FR-006).
- **I4**: The old copy `Estación → casa` MUST NOT remain; it is replaced by `Estación → barrio`.

## Acceptance checks (map to tests)

| Check | Input | Expected | Spec ref |
|---|---|---|---|
| C1 | snapshot `{ corridor_id: "C6-008", direction: 1 }` | button reads `C6-008 · Estación → barrio` | FR-001/002/007, SC-001 |
| C2 | no snapshot (configured id only) | button reads `C6-008` | FR-003, SC-002 |
| C3 | either state | `[Corredor piloto]` not present | FR-004, SC-003 |
| C4 | either state | `CORREDOR` label + button + `▾` present and in place | FR-005, SC-004 |
| C5 | `formatCorridorLabel("C6-008", 1)` | returns `"C6-008 · Estación → barrio"` | FR-002/007 |
| C6 | `formatCorridorLabel("C6-008", undefined)` | returns `"C6-008"` | FR-003 |

These checks are realized in `tests/shell/CorridorSelector.test.tsx` (C1–C4), the updated `tests/shell/Header.test.tsx` (new copy, I4), and optionally `tests/shell/corridorLabel.test.ts` (C5–C6).
