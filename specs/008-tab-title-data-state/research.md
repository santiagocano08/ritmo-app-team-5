# Research: Tab Title Shows Data State

No `NEEDS CLARIFICATION` items. Decisions:

## D1. Where the title is set
- **Decision**: A `useTabTitle(status)` hook with `useEffect` that assigns `document.title`, called in `App` with the already-resolved `status`.
- **Rationale**: `App` already derives `status` for the badge, so title and badge share one source (SC-001, SC-002). The effect is a DOM sync, not data fetching.
- **Alternatives**: `react-helmet` (new dependency, YAGNI); setting the title inside `Header` (mixes presentation with a side effect).

## D2. Labels
- **Decision**: Export the existing `LABELS` map from `StatusBadge.tsx` as `STATUS_LABELS` and build `PulsoFlota · ${label}`.
- **Rationale**: One source of truth for badge and title (FR-001).
- **Alternatives**: Duplicate the strings (can drift).

## D3. Unrecognized status
- **Decision**: `tabTitle` falls back to the `no_data` label when the value is not a key of `STATUS_LABELS` (FR-003). Before the first response, `App` already resolves `no_data`.
- **Rationale**: The safe, non-reassuring state.

## D4. Initial static title
- **Decision**: `index.html` is not edited (FR-005). The title is overwritten on the first render.

## D5. Time zone / locale
- The title has no time or locale formatting, so no TZ pinning is required. Tests pass without `-e TZ`.
