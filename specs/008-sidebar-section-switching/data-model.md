# Data Model: Sidebar Section Switching (US-10)

This feature has **no persisted or exchanged data**. The entities below are client-side UI
state in `src/frontend/`. No backend model, `contracts/` schema or generated type changes
(FR-010).

## Section (static, read-only)

Defined once in `src/components/shell/sections.ts`.

| Field | Type | Values / rule |
|-------|------|---------------|
| `id` | `SectionId` = `"live_central" \| "alerts" \| "day_plan"` | Unique. Same ids the current `Sidebar` already uses. |
| `label` | `string` | `"Central en vivo"`, `"Alertas"`, `"Plan del día"` (style spec §8, *Despachador*). Shown in the sidebar and in the `h1`. |
| `icon` | `string` | Existing glyphs (`◉`, `✚`, `▦`), decorative (`aria-hidden`). Line icons are US-11. |
| `href` | `string` | `"#live"`, `"#alerts"`, `"#plan"`. Kept for link semantics; navigation is intercepted (research R2). |
| `hasContent` | `boolean` | `true` only for `live_central` in Turn 1. `false` renders `SectionPlaceholder`. |

**Validation rules**

- The list order is the sidebar order: *Central en vivo*, *Alertas*, *Plan del día*.
- The list is a `readonly` constant; it is never mutated at runtime.
- The *Gestor* entry (*Indicadores de calidad*) is out of scope (Turn 2, RBAC).

## Active section (UI state)

| Field | Type | Owner | Initial |
|-------|------|-------|---------|
| `activeSection` | `SectionId` | `App` (`useState`) | `"live_central"` (FR-007) |

**Derived values (never stored)**

- Highlighted sidebar item: the item whose `id === activeSection` gets `aria-current="page"`
  and the active classes (`bg-surface text-sidebar`); all others get none (FR-002).
- Page title: `SECTIONS.find(s => s.id === activeSection).label` (FR-003).
- Main content: fleet view (`StaleIndicator` + `EmptyState` or `CorridorSummary` + `FleetList`)
  when `hasContent`, otherwise `SectionPlaceholder` (FR-004, FR-005).

## State transitions

```text
            select(alerts)               select(day_plan)
live_central ───────────────▶ alerts ───────────────────▶ day_plan
     ▲  ▲                       │  ▲                          │
     │  └──── select(live) ─────┘  └──── select(alerts) ──────┤
     └───────────────────────── select(live) ─────────────────┘

select(x) when activeSection === x  →  no change (edge case: no reset, no blank view)
initial load                        →  live_central
full page reload                    →  live_central (not persisted)
```

Every transition is a single `setActiveSection(id)` call. Polling queries
(`corridor-now`, `source-status`) are unaffected by any transition (research R3).
