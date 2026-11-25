# UI Contract: Console Sections (US-10)

Scope: component interfaces inside `src/frontend/`. No REST/WebSocket, `contracts/read/*`
or generated OpenAPI type changes (FR-010).

## Module `src/components/shell/sections.ts`

```ts
export type SectionId = "live_central" | "alerts" | "day_plan";

export interface SectionDef {
  readonly id: SectionId;
  readonly label: string;
  readonly icon: string;
  readonly href: string;
  readonly hasContent: boolean;
}

export const SECTIONS: readonly SectionDef[];
```

Values are listed in `data-model.md`.

## Component `Sidebar` (`src/components/shell/Sidebar.tsx`)

```ts
interface SidebarProps {
  activeSection: SectionId;
  onSelect: (section: SectionId) => void;
}
```

Observable behavior (what tests assert):

| # | Behavior |
|---|----------|
| S1 | Renders `<nav aria-label="Secciones">` with one `<a href>` per entry in `SECTIONS`, in order. |
| S2 | Exactly the item whose `id === activeSection` has `aria-current="page"` and classes `bg-surface text-sidebar`; the others have no `aria-current` and `text-sidebar-inactive`. |
| S3 | Click or Enter on an item calls `preventDefault()` on the event and `onSelect(item.id)` once. The URL hash does not change. |
| S4 | Selecting the active item still calls `onSelect` with the same id; the parent treats it as a no-op. |
| S5 | *Cerrar sesión* (`#logout`) is unchanged and never calls `onSelect`. |
| S6 | Logo and user footer render as today. |

Breaking change: `onSelect` is a new **required** prop. The only caller is `App.tsx`; the
existing `Sidebar.test.tsx` renders must pass it.

## Component `SectionPlaceholder` (`src/components/status/SectionPlaceholder.tsx`)

```ts
function SectionPlaceholder(): JSX.Element; // no props
```

| # | Behavior |
|---|----------|
| P1 | Renders `data-testid="section-placeholder"` containing exactly «Contenido de la sección: se define en las próximas historias.» |
| P2 | Classes realize style spec §7: `flex flex-1 items-center justify-center rounded-card border-2 border-dashed border-border-placeholder p-6 text-center text-[15px] text-text-secondary`. |

## `App` composition (`src/App.tsx`)

| # | Behavior |
|---|----------|
| A1 | `activeSection` starts as `"live_central"`. |
| A2 | `<h1>` text equals the active section's `label`. |
| A3 | `hasContent === true` → current fleet view (`StaleIndicator`, `EmptyState` or `CorridorSummary` + `FleetList`), unchanged. |
| A4 | `hasContent === false` → `SectionPlaceholder` only; no fleet view, no `StaleIndicator`. |
| A5 | `Header` and `DataStateBanner` render in every section with the same props as today. |
| A6 | `useCorridorNow` / `useSourceStatus` are called unconditionally, so polling continues in every section. |
