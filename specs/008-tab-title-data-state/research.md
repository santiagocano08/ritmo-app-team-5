# Research: Tab Title Data State

No `NEEDS CLARIFICATION` items.

## Decision 1: Where the state comes from
- **Decision**: Reuse `status` from `resolveSourceStatus` in `App.tsx`.
- **Rationale**: The badge uses the same value, so title and badge always agree (FR-004, SC-003).
- **Alternatives**: Recompute from the query data in a new hook. Rejected: it would define a second rule.

## Decision 2: How to set the title
- **Decision**: A `useDocumentTitle(status)` hook with `useEffect` that assigns `document.title`.
- **Rationale**: `document.title` is a browser side effect, not backend data fetching, so the `useEffect` ban in the coding standards does not apply. Effects run in background tabs, so the title still updates.
- **Alternatives**: React 19 `<title>` element rendering. Rejected: it hoists into `<head>` but is harder to assert in tests and would clash with the static `index.html` title.

## Decision 3: Label source
- **Decision**: Export `STATUS_LABELS` from `StatusBadge.tsx` and build `PulsoFlota · ${label}`.
- **Rationale**: One label table means a rename changes both places.
- **Alternatives**: A duplicate table in the hook. Rejected: it can drift from the badge.

## Decision 4: Time zone
- **Decision**: No action needed. The feature formats no dates.
