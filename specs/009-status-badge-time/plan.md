# Implementation Plan: Status Badge Readable Time

**Branch**: `009-status-badge-time` | **Date**: 2026-11-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-status-badge-time/spec.md`

## Summary

Add a pure formatting unit that turns the source status (`as_of_ts`, `sources_down[].since`) into the badge detail text, in browser local time, and use it from `resolveSourceStatus` in `src/frontend/src/App.tsx`. Frontend only; no contract, backend or generated-type change. Tests pin the time zone through the Vitest config so results do not depend on the host.

## Technical Context

**Language/Version**: TypeScript (strict), React 19, Vite, Vitest + Testing Library

**Primary Dependencies**: none new

**Storage**: N/A

**Testing**: Vitest (coverage thresholds 80 % already in `vite.config.ts`), ESLint, `tsc --noEmit`; run in the Node container

**Target Platform**: Browser (dispatcher console)

**Project Type**: web application (frontend part only)

**Performance Goals**: N/A (pure string formatting on each render)

**Constraints**: Times in browser local zone, 24 h, zero-padded; tests must be TZ/locale independent (SC-002)

**Scale/Scope**: 1 new module, 1 edited function, 1 config line, 1 test file

## Constitution Check

Active turn: Turn 1 (`docs/turns-ritmo.md`). Adaptive Lane (console).

- I Risk-First: no Level 1 risk touched. Pass.
- II Contract-First: no data exchange change; reads existing `SourceStatusV100` as generated. Data-contract impact: none (FR-007; no silver/gold, metric or event change). Pass.
- III Isolation / real time: frontend display only, no ingestion or synchronous external calls. Pass.
- IV Human gate: no recommendation or command involved; `estimated` raises no alert (D1). Pass.
- V Test-First: unit tests for the formatter plus badge/app test; coverage > 80 %; Gate 1 (types/lint) and Gate 2 (tests) apply. Pass.

Post-design re-check: Pass, no violations. Complexity Tracking not needed.

**Evolution (deferred norms, not designed here)**: SAST/SCA, RBAC/JWT, geographic map, Redis, and the data-contract changes are out of turn 1 scope.

## Project Structure

### Documentation (this feature)

```text
specs/009-status-badge-time/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md             # /speckit.tasks, not created here
```

No `contracts/`: the feature exposes no new interface. The only internal interface is the formatter signature, in `data-model.md`.

### Source Code (repository root)

```text
src/frontend/
├── src/
│   ├── App.tsx                          # resolveSourceStatus uses the formatter
│   └── components/shell/
│       └── statusDetail.ts              # NEW: pure formatter (FR-006)
├── tests/shell/
│   ├── statusDetail.test.ts             # NEW: unit tests
│   └── StatusBadge.test.tsx             # existing; adjust only if it asserts the raw ISO text
└── vite.config.ts                       # test.env TZ pinned
```

**Structure Decision**: Keep the formatter beside `StatusBadge` in `components/shell/`; no new folder (KISS). `StatusBadge` stays presentational and unchanged.

## Complexity Tracking

None.
