# Phase 0 Research: Real Corridor Name in Header

**Feature**: US-12 — `feature/US-12-frontend-corridor-name`
**Date**: 2026-11-21

The Technical Context has no open `NEEDS CLARIFICATION`. The spec, the generated contract type, and the existing frontend code fully determine the approach. This file records the decisions that shaped the Phase 1 design.

## Decision 1 — Where the label is formatted

**Decision**: Add a pure function `formatCorridorLabel(corridorId: string, direction?: number): string` in a new file `src/frontend/src/components/shell/corridorLabel.ts`, and call it from `CorridorSelector`.

**Rationale**:
- Keeps `CorridorSelector` presentational (SRP, per coding standards and `frontend-web` steering).
- A pure string function is trivially unit-testable with no rendering, which makes the > 80 % coverage gate cheap to satisfy and covers both branches (snapshot present / absent) directly.
- Mirrors the existing colocated pure helper `statusDetail.ts` in the same `shell/` folder — consistent with repo conventions, no new pattern introduced.

**Alternatives considered**:
- *Inline the ternary inside `CorridorSelector`'s JSX.* Rejected: harder to unit-test in isolation and mixes formatting logic with markup; the coverage gate would depend on component rendering for branch coverage.
- *Put the helper in a shared `utils/` module.* Rejected: it is only used by the shell header; colocation matches `statusDetail.ts` and keeps the change surgical.

## Decision 2 — How the data reaches the component

**Decision**: Thread the values from the composition root. `App.tsx` already computes `snapshot = fleet.lastSnapshot` (`CorridorNow | null`) and imports `corridorId` from `mocks/fixtures.ts`. Pass `snapshot?.corridor_id ?? corridorId` and `snapshot?.direction` into `<Header>`, extend `HeaderProps`, and forward them to `<CorridorSelector>`.

**Rationale**:
- No new data source, no new hook, no `useEffect` fetching — satisfies the "No Manual Fetching in React Components" rule and Principle III (data already flows via `useCorridorNow`, a TanStack Query hook).
- The `?? corridorId` fallback gives the pre-snapshot state (`C6-008`) directly from the configured id constant, exactly as FR-003 requires.
- Query data is read, never mutated (immutability rule).

**Alternatives considered**:
- *Call `useCorridorNow` again inside `CorridorSelector` or `Header`.* Rejected: duplicates the query ownership, violates single composition root, and risks a second fetch / divergent cache read. The snapshot already exists in `App.tsx`.
- *Read a global/context value.* Rejected: no such context exists; props are the simplest correct wiring (YAGNI).

## Decision 3 — Direction-to-text mapping

**Decision**: `direction === 1` → `"Estación → barrio"`. Any other value or `undefined` → no direction suffix (id only). The label is `"{corridorId} · {directionText}"` when a direction text exists, otherwise `"{corridorId}"`.

**Rationale**:
- The generated type `CorridorNowV100.direction` is typed `1` and its JSDoc states "Turn 1 supports direction 1 only (station to neighbourhood)". The contract header comment names corridor `C6-008`, direction `1`.
- FR-002/FR-007 require direction 1 → `Estación → barrio`. The id-only fallback covers FR-003 (no snapshot) and the edge case "snapshot then no data" (never reverts to placeholder).
- Note the copy change: the old mockup said `Estación → casa`; the real/contract-aligned wording is `Estación → barrio` ("barrio" = neighbourhood). The existing Header test asserting `casa` must be updated.

**Alternatives considered**:
- *A full `Record<number, string>` direction map.* Rejected as speculative — Turn 1 has one direction only (YAGNI). A single `=== 1` check with an id-only fallback is enough and extends cleanly later.

## Decision 4 — Prop shape for `CorridorSelector`

**Decision**: Pass the raw inputs, not a pre-built string: `{ corridorId: string; direction?: number }`. The component calls the helper internally.

**Rationale**: Keeps the formatting rule in one tested place and keeps `Header`/`App` free of presentation strings. The `direction` type is widened to `number | undefined` at the prop boundary (the snapshot provides the literal `1`), so the helper owns the mapping and the component stays strict-typed with no `any`.

**Alternatives considered**:
- *Pass a single formatted `label: string`.* Viable and also acceptable; rejected as the primary choice because it pushes formatting up into `App`/`Header` or a caller, spreading the rule. Either shape satisfies the spec; the plan records the prop-based shape as recommended.

## Decision 5 — Keep the button inert

**Decision**: No `onClick`, no handler, no state. Preserve the exact `CORREDOR` label, button classes and the `▾` chevron (`aria-hidden`).

**Rationale**: FR-005/FR-006 and the Human-in-the-Loop principle — corridor switching is out of scope for Turn 1. Only the button's text node changes.

## Testing approach (confirmed, no unknowns)

- Stack: Vitest + Testing Library + jsdom; `renderWithQuery()` wraps TanStack Query; MSW in `tests/setup.ts`. `CorridorSelector` takes plain props, so most tests need no query wrapper; `renderWithQuery` remains available if a test renders through `App`/`Header` with the hook.
- Update `tests/shell/Header.test.tsx` to assert the new copy and drop `Estación → casa`.
- Add `CorridorSelector` tests for both states (snapshot present → `C6-008 · Estación → barrio`; none → `C6-008`) and assert `[Corredor piloto]` is absent.
- Optionally add direct unit tests for `formatCorridorLabel` to lock the branch behaviour cheaply.

**Output**: All Technical Context items resolved. Ready for Phase 1.
