# Quickstart: Real Corridor Name in Header

**Feature**: US-12 — `feature/US-12-frontend-corridor-name`
**Date**: 2026-11-21

A validation/run guide to prove the feature works end to end. Implementation lives in `tasks.md` (after `/speckit.tasks`) and the Build phase; this guide does not contain full implementation code.

## Prerequisites

- Node toolchain for the frontend (already covered by the repo; dependencies installed).
- Working directory: `src/frontend/`.
- No backend required for the unit/component tests (MSW mocks in `tests/setup.ts`; the label tests pass plain props).

## What changed (files)

- `src/frontend/src/components/shell/corridorLabel.ts` — NEW pure helper `formatCorridorLabel`.
- `src/frontend/src/components/shell/CorridorSelector.tsx` — typed props, renders the formatted label, layout unchanged.
- `src/frontend/src/components/shell/Header.tsx` — `HeaderProps` extended with `corridorId` + `direction`, forwarded to `CorridorSelector`.
- `src/frontend/src/App.tsx` — passes `snapshot?.corridor_id ?? corridorId` and `snapshot?.direction` to `<Header>`.
- `src/frontend/tests/shell/Header.test.tsx` — updated to the new copy.
- `src/frontend/tests/shell/CorridorSelector.test.tsx` — NEW (both states + absence of placeholder).
- `src/frontend/tests/shell/corridorLabel.test.ts` — NEW (optional) direct helper tests.

See [contracts/corridor-label.md](./contracts/corridor-label.md) for the exact output rules and [data-model.md](./data-model.md) for the prop shapes.

## Validation scenarios

Run all commands from `src/frontend/`.

### 1. Component + helper tests (primary validation)

```bash
npm run test          # or: npx vitest run
```

Expected:
- `CorridorSelector` with snapshot `{ corridor_id: "C6-008", direction: 1 }` renders `C6-008 · Estación → barrio` (check C1).
- `CorridorSelector` with no snapshot renders `C6-008` (check C2).
- `[Corredor piloto]` is asserted absent (check C3).
- `CORREDOR` label, button and `▾` present and in place (check C4).
- `Header.test.tsx` asserts the new copy and no longer asserts `Estación → casa` (invariant I4).
- Optional `formatCorridorLabel` unit tests pass (checks C5–C6).

### 2. Coverage gate (Gate 2)

```bash
npx vitest run --coverage
```

Expected: lines/functions/branches/statements all ≥ 80 % (thresholds in `vite.config.ts`). The pure helper gives cheap branch coverage for both label states.

### 3. Lint (Gate 1) and type check

```bash
npm run lint          # ESLint, --max-warnings 0
npx tsc --noEmit      # strict, no `any`
```

Expected: 0 ESLint warnings/errors, 0 type errors.

### 4. Build

```bash
npm run build         # tsc + vite build
```

Expected: build succeeds, static assets emitted.

### 5. Manual smoke check (optional)

```bash
npm run dev
```

Open the app:
- Before the first snapshot loads, the header reads `C6-008`.
- Once a snapshot arrives (MSW/dev data, direction 1), it reads `C6-008 · Estación → barrio`.
- The selector button does nothing when clicked (inert).
- Search the running output / source for `[Corredor piloto]` → zero occurrences.

### 6. Repo-wide placeholder check (SC-003)

```bash
grep -rn "\[Corredor piloto\]" src/frontend/src   # expect: no matches
```

## Done when

- All of `vitest`, `--coverage`, `lint`, `tsc --noEmit` and `build` pass (SC-005).
- Header reads `C6-008 · Estación → barrio` with a snapshot (SC-001) and `C6-008` without one (SC-002).
- `[Corredor piloto]` occurs zero times (SC-003); layout unchanged (SC-004).
