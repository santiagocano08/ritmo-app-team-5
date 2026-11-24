# Implementation Plan: Tab Title Data State

**Branch**: `008-tab-title-data-state` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-tab-title-data-state/spec.md`

## Summary

Set `document.title` to `PulsoFlota · <label>` from the same `status` value that `App.tsx` passes to the header `StatusBadge`. The badge labels move to one shared export so the title and the badge cannot drift. Frontend only.

## Technical Context

**Language/Version**: TypeScript (strict), React 19

**Primary Dependencies**: Vite, Tailwind (unchanged); no new dependencies

**Storage**: N/A

**Testing**: Vitest + Testing Library (jsdom)

**Target Platform**: Browser (dispatcher console SPA)

**Project Type**: web-service (frontend part)

**Performance Goals**: Title updates in the same render that changes the badge

**Constraints**: No time or locale formatting is involved, so tests are zone-independent (they also run under UTC with no `TZ` override)

**Scale/Scope**: 1 hook, 1 export change, 1 call in `App.tsx`, 1 test file

## Constitution Check

| Gate | Result |
|------|--------|
| I Risk-first | Pass. Adaptive lane, no open Level 1 risk touched. |
| II Contract-first | Pass. No data exchange, no contract impact (spec Assumptions). |
| III Isolated ingestion / real time | Pass. Not touched. |
| IV Human gate | Pass. Display only, no command. |
| V Test-first / gates | Pass. Vitest tests, coverage > 80 %, ESLint, `tsc --noEmit`. |
| Turn map (turn 1) | Pass. Fleet state display is in scope. Nothing deferred is designed. |

Post-design re-check: no change, all gates pass. No Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/008-tab-title-data-state/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md   # /speckit.tasks, not created here
```

`contracts/` is omitted: the feature exposes no interface.

### Source Code (repository root)

```text
src/frontend/
├── src/
│   ├── App.tsx                              # call useDocumentTitle(status)
│   ├── hooks/useDocumentTitle.ts            # new: sets document.title
│   └── components/shell/StatusBadge.tsx     # export STATUS_LABELS
└── tests/                                   # new useDocumentTitle test + App title assertions
```

**Structure Decision**: Existing `src/frontend/` layout. The hook sits next to the other hooks. `status` already comes from `resolveSourceStatus` in `App.tsx`, which also feeds the badge, so FR-004 holds by construction. The initial `index.html` title stays unchanged (FR-006).

## Complexity Tracking

None.
