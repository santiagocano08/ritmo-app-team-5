# Phase 1 Data Model: Sidebar SVG Icons

Feature: `008-frontend-sidebar-svg-icons`

This feature introduces **no persisted data, no message contract and no domain
model**. It is a presentational change in the dispatcher console. The only
model affected is the in-memory shape of the sidebar's navigation items inside
`src/frontend/src/components/shell/Sidebar.tsx`. No PostgreSQL, Redis, Pydantic
or OpenAPI artifact is touched (FR-009).

## UI model: `NavItem`

The component-local `NavItem` interface changes only in the `icon` field type.

| Field | Before | After | Notes |
|---|---|---|---|
| `section` | `ActiveSection` | `ActiveSection` | Unchanged. Union `"live_central" \| "alerts" \| "day_plan"`. |
| `label` | `string` | `string` | Unchanged visible wording (FR-007). |
| `icon` | `string` (glyph) | `ReactNode` (inline `<svg>`) | Decorative SVG element, `aria-hidden="true"`, `stroke="currentColor"` (FR-002, FR-004, FR-005). No `any` (strict TS). |
| `href` | `string` | `string` | Unchanged (`#live`, `#alerts`, `#plan`). |

`NAV_ITEMS` keeps three entries in the same order with the same `section`,
`label` and `href`; only each `icon` value becomes an inline SVG.

### Validation / invariants

- Exactly three navigation entries; order and labels preserved (FR-007).
- `aria-current="page"` is derived from `section === activeSection` — logic
  unchanged (FR-008; guarded by `TextNotColor.test.tsx`).
- Each entry renders exactly one `<svg aria-hidden="true">` (FR-002, FR-005).

## Non-`NavItem` icons

| Position | Element | Size | Colour | Decorative |
|---|---|---|---|---|
| Logo | pulse `<svg>` path `M2 12h4l3-8 4 16 3-8h6` | 26×26 | `#FBBF24` (`text-logo`) | `aria-hidden="true"` (FR-001, FR-005) |
| Cerrar sesión | exit `<svg>` | 18×18 | `currentColor` | `aria-hidden="true"` (FR-003, FR-005) |

These are rendered directly in JSX (not through `NAV_ITEMS`), mirroring the
current structure.

## State transitions

None. The sidebar has no stateful icon behaviour; active/inactive styling is a
pure function of the `activeSection` prop (unchanged).
