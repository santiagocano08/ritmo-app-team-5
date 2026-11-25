# Feature Specification: Sidebar Section Switching with Placeholder

**Feature Branch**: `feature/US-10-frontend-sidebar-sections`

**Created**: 2026-11-24

**Status**: Draft

**Input**: User description: ticket `tickets/US-10-frontend-sidebar-sections/US-10-frontend-sidebar-sections.md` (GitHub issue #52, label `demo`) — "feat(frontend): sidebar items switch sections with a placeholder (US-10)". As a dispatcher, I want the sidebar items to switch sections, so the navigation behaves like the design even before the sections have content.

**RITMO context**: Turn 1 — "Data and minimal loop". Lane: Adaptive. Risk level: 1. Visual reference: style spec `tickets/US-06-frontend-home/US-06-escritorio-estilos.md` (UXUI-03), §4.2 (menu items), §7 (main area and placeholder), §10 (accessibility).

## Context

Today the dispatcher console sidebar lists three sections: *Central en vivo*, *Alertas* and *Plan del día*. Only *Central en vivo* works. Clicking *Alertas* or *Plan del día* does nothing visible: the highlighted item and the page title stay fixed on *Central en vivo*. The design defines an active state for whichever item is selected and a placeholder for sections whose content is not built yet. This story closes that gap without building any real content for the new sections.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Switch to a section that is not built yet (Priority: P1)

A dispatcher working in *Central en vivo* clicks *Alertas* (or *Plan del día*) in the sidebar. The clicked item becomes the highlighted, current item; the page title changes to that item's label; and the fleet view is replaced by a placeholder that says the section's content will come in later stories.

**Why this priority**: This is the reported gap. Without it, two of the three menu items look broken and the console does not behave like the approved design.

**Independent Test**: Open the console, click *Alertas*, and check the highlighted item, the page title and the placeholder. Repeat with *Plan del día*. Delivers navigation that matches the design.

**Acceptance Scenarios**:

1. **Given** the console is open on *Central en vivo*, **When** the dispatcher clicks *Alertas*, **Then** *Alertas* is the only item marked as the current page, the page title reads *Alertas*, and the placeholder is shown instead of the fleet view.
2. **Given** the console is open on *Central en vivo*, **When** the dispatcher clicks *Plan del día*, **Then** *Plan del día* is the only item marked as the current page, the page title reads *Plan del día*, and the placeholder is shown instead of the fleet view.
3. **Given** the dispatcher is on *Alertas*, **When** they click *Plan del día*, **Then** *Plan del día* becomes the only current item, the title reads *Plan del día*, and the placeholder remains shown.
4. **Given** a placeholder section is shown, **When** the dispatcher reads the main area, **Then** it shows the text «Contenido de la sección: se define en las próximas historias.» centered inside a dashed-border box, as defined in style spec §7.

---

### User Story 2 - Return to the live fleet view (Priority: P1)

A dispatcher who visited a placeholder section clicks *Central en vivo* and gets the live fleet view and summary back, still refreshing with current data.

**Why this priority**: Switching away must never cost the dispatcher the live view. Losing live data after navigating would be a regression in the console's core purpose.

**Independent Test**: Navigate to *Plan del día*, then back to *Central en vivo*; confirm the fleet view and summary reappear and keep updating with new data.

**Acceptance Scenarios**:

1. **Given** the dispatcher is on *Plan del día*, **When** they click *Central en vivo*, **Then** the fleet view and summary are shown again, *Central en vivo* is the only current item, the title reads *Central en vivo*, and data keeps refreshing at the usual interval.
2. **Given** the console has just been opened, **When** the page first renders, **Then** *Central en vivo* is the active section and the fleet view is shown, exactly as today.

---

### Edge Cases

- Clicking the item that is already active keeps the same section and does not reset or blank the view.
- Switching sections several times in a row always leaves exactly one item marked as current, and the title always matches it.
- While on a placeholder section, the header (corridor, data-state badge, clock) and the data-state banner keep working, since they describe the whole console and not one section.
- If the data source becomes stale or unavailable while the dispatcher is on a placeholder section, the shared header badge and banner still reflect it; on return to *Central en vivo* the fleet view shows the current state.
- Keyboard users can reach each sidebar item and activate it with the keyboard, with the same result as a click.
- The *Cerrar sesión* link in the sidebar footer is not a section and is not affected by this story.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The console MUST let the dispatcher switch the active section by activating (click or keyboard) any of the sidebar items *Central en vivo*, *Alertas* or *Plan del día*.
- **FR-002**: Exactly one sidebar item MUST be marked as the current page at any time, both visually (active style from style spec §4.2: white background, dark text) and for assistive technology (current-page marker on that item only).
- **FR-003**: The main page title MUST show the label of the active section.
- **FR-004**: When *Central en vivo* is active, the main area MUST show the existing fleet view and summary, unchanged from current behavior.
- **FR-005**: When *Alertas* or *Plan del día* is active, the main area MUST show, instead of the fleet view, the placeholder defined in style spec §7: dashed border 2 px `#A3ACB9`, radius 12 px, padding 24 px, filling the remaining height, text `#4A5361` at 15 px centered on both axes, reading «Contenido de la sección: se define en las próximas historias.»
- **FR-006**: Returning to *Central en vivo* MUST show the fleet view with current data, and live data refresh MUST continue without requiring a page reload.
- **FR-007**: On first load the active section MUST be *Central en vivo*.
- **FR-008**: The header, data-state badge and data-state banner MUST remain visible and functional in every section.
- **FR-009**: Section switching MUST happen within the page, without a full page reload and without adding a routing library (ticket constraint).
- **FR-010**: This story MUST NOT change the backend, the data contracts or the generated client types; it is limited to the dispatcher console.

### Key Entities

- **Section**: One of the console's navigable areas. Attributes: identifier, visible label (*Central en vivo*, *Alertas*, *Plan del día*), and whether its content is built (only *Central en vivo* in this turn).
- **Active section**: The single section currently selected by the dispatcher; it drives the highlighted sidebar item, the page title and the main-area content.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100 % of section switches (any order, any number of times), exactly one sidebar item is marked as current and the page title matches its label.
- **SC-002**: A dispatcher reaches any of the three sections with a single click or key press from any other section.
- **SC-003**: After returning to *Central en vivo* from a placeholder section, fleet data updates again within one normal refresh interval, with no page reload.
- **SC-004**: The placeholder matches style spec §7 on every measured attribute (border width, style and color, radius, padding, text color, size and content) in a visual review against the mockup.
- **SC-005**: The console's automated quality gates stay green, including test coverage above 80 %.

## Assumptions

- Only the *Despachador* role menu is in scope; the *Gestor* variant (*Indicadores de calidad*) and role-based menus are deferred to Turn 2 (RBAC), per the ticket.
- No real content for *Alertas* or *Plan del día* is built; that belongs to later stories.
- Live data keeps refreshing while a placeholder section is shown, because the header badge and banner depend on it and the ticket asks that refresh "continues" on return. Pausing refresh on other sections is not required.
- Keeping the selected section across a full page reload or a shared link is not required; a fresh load opens *Central en vivo*. Using the existing in-page links is allowed by the ticket, so if the chosen approach preserves the section on reload, that is acceptable but not tested as a requirement.
- Sidebar icons remain as they are today; replacing them with the design's line icons is a separate story (US-11).
- Dependency: the existing console shell from US-06 (sidebar, header, banner, fleet view) is in place on the branch.
- Constitution check: Principle II (contract-first) is not triggered because no data exchange changes; Principle IV (human gate) is not affected because no regulation action is involved; Principle V applies through the console's test and coverage gates.
