# Implementation Plan: Tab Title Shows Data State

**Branch**: `008-tab-title-data-state` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-tab-title-data-state/spec.md`

## Summary

Set `document.title` to `PulsoFlota · {En vivo | Estimado | Sin datos}` from the same `status` value that drives the header badge. A small hook `useTabTitle(status)` is called from `App`. The status-to-label mapping is reused from `StatusBadge` (exported), so title and badge cannot diverge. Frontend only.

## Technical Context

**Language/Version**: TypeScript (strict), React 19

**Primary Dependencies**: React, Vite, Vitest + Testing Library (all existing)

**Storage**: N/A

**Testing**: Vitest (jsdom). The title is not time- or locale-dependent, so no TZ pinning is needed.

**Target Platform**: Browser (dispatcher console)

**Project Type**: web-application (frontend only)

**Performance Goals**: Title changes in the same render commit as the badge (SC-002).

**Constraints**: Static `index.html` title unchanged (FR-005). No backend, contract or generated-type changes.

**Scale/Scope**: 1 hook, 1 export, 1 call site, 1 test file.

## Constitution Check

*Active turn: 1 (`docs/turns-ritmo.md`). Adaptive lane (web console).*

| Gate | Result |
|------|--------|
| I Risk-First | Pass. No Level 1 risk touched. |
| II Contract-First / data ownership | Pass. No data exchange or schema change. **Data contract impact: none** (reads the existing `status` value only; `docs/data-contract.md` and `contracts/` untouched). |
| III Isolated ingestion / deterministic real time | Pass. No ingestion or critical-path change. |
| IV Human gate | Pass. Display only; no commands. |
| V Test-first and gates | Pass. Tests planned (FR-004); frontend-ci (ESLint, `tsc`, Vitest, coverage > 80 %) stays green. |
| Coding standards | Pass. Surgical edit. `useEffect` only syncs `document.title`; it is not backend fetching. |

Post-design re-check: still passes, no violations. Complexity Tracking not needed.

**Evolution (deferred per turn map)**: favicon or notification cues, and any alerting, are out of scope.

## Project Structure

### Documentation (this feature)

```text
specs/008-tab-title-data-state/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md   # created by /speckit.tasks
```

`contracts/` is omitted: the feature exposes no new interface.

### Source Code (repository root)

```text
src/frontend/
├── src/
│   ├── App.tsx                              # call useTabTitle(status)
│   ├── components/shell/StatusBadge.tsx     # export STATUS_LABELS
│   └── hooks/useTabTitle.ts                 # new: tabTitle(status) + hook
└── tests/hooks/useTabTitle.test.tsx         # new
```

**Structure Decision**: Web application, frontend only, in `src/frontend/`, following the existing `hooks/` and `tests/hooks/` layout.

## Complexity Tracking

None.
