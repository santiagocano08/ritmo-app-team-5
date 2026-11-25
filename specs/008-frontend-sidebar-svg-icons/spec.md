# Feature Specification: Sidebar SVG Icons

**Feature Branch**: `feature/US-11-frontend-sidebar-svg-icons`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "Replace the five text-glyph icons in the dispatcher console sidebar (logo, three menu items, and the logout link) with inline stroke SVG icons per the style spec, so the menu looks the same on every computer and matches the design. Frontend only, Turn 1, Adaptive lane; no backend or contract changes; icons in the fleet list and the header chevron are out of scope."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent sidebar icons across machines (Priority: P1)

As a dispatcher, when I open the console sidebar on any workstation, I see the
logo, the three navigation entries (*Central en vivo*, *Alertas*, *Plan del
día*) and the *Cerrar sesión* link rendered with crisp, consistent icons that
look identical regardless of which computer or installed fonts the workstation
has.

**Why this priority**: This is the entire feature. Text-glyph icons render
differently on each machine and drift from the approved design, undermining the
visual trust the dispatcher places in the supervisory console. A single
consistent icon set is the deliverable; without it there is nothing to ship.

**Independent Test**: Open the dispatcher console on two different environments
and confirm the sidebar shows the same six icons (logo, three menu entries,
logout) with the shapes, sizes and the logo colour defined in the design
reference, and that no residual text-glyph placeholders appear.

**Acceptance Scenarios**:

1. **Given** the sidebar is rendered, **When** a reviewer inspects each
   navigation entry and the logout link, **Then** each one shows exactly one
   decorative icon and none of the previous text-glyph placeholders remains.
2. **Given** the sidebar is rendered, **When** a reviewer inspects the logo,
   **Then** it shows the pulse icon in the brand highlight colour at the logo
   size defined by the design reference.
3. **Given** the sidebar is viewed on two machines with different installed
   fonts, **When** the dispatcher compares them, **Then** the sidebar icons look
   the same on both.

---

### User Story 2 - Accessible, label-preserving navigation (Priority: P2)

As a dispatcher who relies on readable labels and assistive technology, I want
the new icons to be purely decorative and the visible menu wording to stay
exactly as before, so the meaning of each entry is still carried by its text
and screen readers are not cluttered by decorative shapes.

**Why this priority**: The icons carry no information that the text label does
not already carry; the labels (*Central en vivo*, *Alertas*, *Plan del día*,
*Cerrar sesión*) are the accessible source of truth. Changing or hiding a label,
or exposing a decorative icon to assistive technology, would regress
accessibility. This protects the existing behaviour rather than adding new
value, so it ranks below Story 1.

**Independent Test**: Run the existing accessibility check and confirm it still
passes, that every visible menu label and the logout label read exactly as
before, and that the icons are marked decorative (ignored by assistive
technology).

**Acceptance Scenarios**:

1. **Given** the existing accessibility check, **When** it runs against the
   updated sidebar, **Then** it still passes.
2. **Given** the updated sidebar, **When** a reviewer reads the navigation and
   logout labels, **Then** the wording is unchanged from before the icon
   replacement.
3. **Given** assistive technology navigates the sidebar, **When** it reaches an
   icon, **Then** the icon is treated as decorative and announces no extra
   content.

---

### Edge Cases

- What happens to the active navigation entry? Its active indication must stay
  intact after the icon swap, and the icon must remain visible and legible
  against the active entry's background.
- What happens if an icon shape fails to render? Because each icon is decorative
  and the text label always carries the meaning, a missing icon must never hide
  or change an entry's label or break navigation.
- What happens when the viewport is narrow or text is zoomed? Icons keep their
  defined sizes and must not overlap or push the labels out of view.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The sidebar MUST display the brand logo as the pulse icon using
  the shape, the logo size and the brand highlight colour defined in the design
  reference (sections 4.1–4.3 of the US-06 desktop style spec).
- **FR-002**: Each of the three navigation entries MUST display its own
  decorative icon at the menu-item icon size defined by the design reference:
  *Central en vivo* a pulse icon, *Alertas* a bell icon, *Plan del día* a
  calendar icon.
- **FR-003**: The *Cerrar sesión* link MUST display an exit icon at the logout
  icon size defined by the design reference.
- **FR-004**: The navigation and logout icons MUST adopt the surrounding text
  colour so they match each entry's state (active, inactive).
- **FR-005**: Every icon in the sidebar MUST be marked decorative so assistive
  technology ignores it.
- **FR-006**: No text-glyph placeholder icon (`⬳`, `◉`, `✚`, `▦`, `⇥`) may
  remain in the sidebar after the change.
- **FR-007**: The visible wording of every navigation entry and of the logout
  link MUST remain unchanged.
- **FR-008**: The active navigation entry's active indication MUST remain
  present and visually correct after the icon replacement.
- **FR-009**: The icon change MUST be confined to the dispatcher console
  frontend; it MUST NOT alter backend behaviour, data contracts, or
  generated types, and MUST NOT add a new third-party icon dependency.

### Key Entities

- **Sidebar navigation entry**: a dispatcher console menu item with a visible
  label, a decorative icon, a target section, and an active/inactive state. The
  three entries are *Central en vivo*, *Alertas* and *Plan del día*.
- **Sidebar logo**: the brand mark at the top of the sidebar, shown as the pulse
  icon in the brand highlight colour.
- **Logout control**: the *Cerrar sesión* link at the foot of the sidebar, shown
  with an exit icon.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the sidebar's icon positions (logo, three navigation
  entries, logout) show the design-defined icon, and 0 text-glyph placeholders
  remain.
- **SC-002**: The sidebar renders the same six icons on every workstation
  regardless of installed fonts, as confirmed by comparing two environments.
- **SC-003**: The existing accessibility check continues to pass and every
  visible sidebar label is unchanged from before the change.
- **SC-004**: All sidebar icons are decorative and contribute no extra announced
  content to assistive technology.
- **SC-005**: The frontend quality gate stays green after the change (static
  analysis, type check, tests with coverage above 80%, and a successful build).

## Assumptions

- The design reference for icon shapes, sizes and the logo colour is sections
  4.1–4.3 of `tickets/US-06-frontend-home/US-06-escritorio-estilos.md`, with
  UXUI-03 as the sidebar layout reference; the ticket's listed values (logo
  26×26, menu items 20×20, logout 18×18, stroke width 2, round caps/joins, logo
  colour `#FBBF24`) are authoritative.
- The three navigation entries and the logout control already exist; this change
  only replaces their icon presentation, not the navigation structure or labels.
- Icons in the fleet list and the header chevron are explicitly out of scope and
  are not touched.
- This is a Turn-1, Adaptive-lane, frontend-only change; no new data is
  introduced, so no message contract or persisted schema is affected.
- The existing dispatcher console (US-06) and its sidebar component are the
  starting point; the feature modifies only the sidebar presentation within the
  frontend service.
