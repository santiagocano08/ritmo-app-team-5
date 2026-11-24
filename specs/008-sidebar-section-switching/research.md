# Research: Sidebar Section Switching with Placeholder (US-10)

**Feature**: `specs/008-sidebar-section-switching/spec.md` | **Date**: 2026-11-24

The Technical Context had no `NEEDS CLARIFICATION` items: the stack, test tooling and
target files are fixed by the existing console (US-06). The research below records the
design decisions that the spec left open.

## R1. Where the active section lives

- **Decision**: `useState<SectionId>("live_central")` in `App.tsx`. `Sidebar` becomes a
  controlled component: it receives `activeSection` and an `onSelect(section)` callback.
- **Rationale**: `App` already owns the layout (sidebar, header, banner, `<main>`), so it is
  the lowest common owner of the three things the section drives (highlighted item, `h1`,
  main content). One `useState` satisfies FR-001..FR-003 and FR-007 with no new dependency.
- **Alternatives considered**:
  - *Router library (react-router, TanStack Router)*: forbidden by the ticket (FR-009).
  - *Hash-driven state (`location.hash` + `hashchange` listener)*: survives reloads, but the
    spec does not require that, it needs a subscription (`useSyncExternalStore` or an effect)
    and more test setup. Rejected under YAGNI; it can be added later without changing the
    `Sidebar` contract.
  - *React context*: only one consumer level below `App`; prop passing is simpler.

## R2. Link element and click behavior

- **Decision**: keep the existing `<a href="#live|#alerts|#plan">` elements. The click handler
  calls `event.preventDefault()` and then `onSelect(section)`.
- **Rationale**: style spec §10 requires real links/buttons, and `aria-current="page"` is the
  standard marker on navigation links. Native anchors are focusable and activate with Enter,
  which covers the keyboard edge case without extra key handlers. Preventing the default stops
  the URL from showing a hash that a reload would ignore (R1 keeps state local), so the URL
  never claims a state the app does not honor.
- **Alternatives considered**:
  - *Let the hash change*: harmless, but leaves `#alerts` in the URL while a reload opens
    *Central en vivo*. Rejected as confusing.
  - *Switch to `<button>`*: also valid for §10, but changes the element tests and screen readers
    already rely on, and buttons are not the idiomatic element for page-level navigation.

## R3. Keeping live data refreshing across sections (FR-006, FR-008, SC-003)

- **Decision**: leave `useCorridorNow` and `useSourceStatus` called unconditionally at the top of
  `App`. Only the JSX inside `<main>` branches on the active section.
- **Rationale**: the TanStack Query observers stay mounted, so the 5 s `refetchInterval` keeps
  running on every section. The header badge and data-state banner (FR-008) keep reading fresh
  status, and on return to *Central en vivo* the fleet view renders the latest cached snapshot
  immediately, then refreshes on the next tick. No hook changes are needed.
- **Alternatives considered**:
  - *Pause polling outside the live section* (`enabled: section === "live_central"`): breaks
    FR-008 (badge and banner would go stale) and the spec says pausing is not required.
  - *Move the queries into a `LiveCentral` child*: unmounting it would stop polling and drop
    observers. Rejected.

## R4. Placement of `StaleIndicator` and `EmptyState`

- **Decision**: both stay inside the *Central en vivo* branch of `<main>`.
- **Rationale**: they describe the fleet snapshot shown in that section. The console-wide data
  state is already conveyed by the header badge (`stale` prop) and the banner, which remain
  visible everywhere (FR-008).
- **Alternatives considered**: showing `StaleIndicator` above the placeholder too. Rejected: it
  would claim a stale snapshot is on screen when none is.

## R5. Section labels as a single source

- **Decision**: a small module `src/components/shell/sections.ts` exports the `SectionId` union
  and a read-only `SECTIONS` list (`id`, `label`, `icon`, `href`, `hasContent`). `Sidebar` maps
  over it and `App` reads the label for the `h1`.
- **Rationale**: FR-003 and SC-001 require the title to always match the highlighted item. One
  list removes the chance of the two strings drifting. Keeping it out of `Sidebar.tsx` keeps the
  component file exporting only components.
- **Alternatives considered**: a second label map in `App` (duplicated strings, can drift);
  exporting the list from `Sidebar.tsx` (works, but mixes data and component exports).

## R6. Placeholder component

- **Decision**: new presentational component `SectionPlaceholder` in
  `src/components/status/SectionPlaceholder.tsx`, styled with the existing Tailwind tokens:
  `flex flex-1 items-center justify-center rounded-card border-2 border-dashed
  border-border-placeholder p-6 text-center text-[15px] text-text-secondary`.
- **Rationale**: matches style spec §7 exactly with tokens already in `tailwind.config.ts`
  (`border.placeholder = #A3ACB9`, `card = 12px`, `text.secondary = #4A5361`); no new tokens.
  `EmptyState` uses the same frame, but its content differs; the coding standards prefer small
  UI duplication over a generic frame abstraction.
- **Alternatives considered**: a shared `DashedPanel` wrapper for both. Rejected (premature
  abstraction for two call sites).

## R7. Test strategy

- **Decision**: Vitest + Testing Library + `user-event` (already in `devDependencies`), MSW
  handlers from `tests/setup.ts`.
  - `Sidebar` unit tests: `aria-current` on exactly the `activeSection` item; clicking or
    pressing Enter on an item calls `onSelect` with its id; *Cerrar sesión* does not.
  - `SectionPlaceholder` unit test: renders the exact text.
  - `App` integration test (`tests/shell/SectionSwitching.test.tsx`): live → *Alertas* →
    *Plan del día* → *Central en vivo*; checks `h1`, single `aria-current`, placeholder vs.
    fleet (`B-105` from the normal fixture), header badge still present, and that a new
    `/now` request arrives after returning (MSW `request:start` counter, timeout ≈ 7 s, as in
    `StaleRecovery.test.tsx`).
- **Rationale**: covers FR-001..FR-008 and SC-001..SC-003 at the cheapest level that proves
  each; keeps `frontend-ci` coverage above 80 % (SC-005).
- **Alternatives considered**: fake timers for the polling check. Rejected: TanStack Query with
  MSW is more reliable on real timers, and the repo already uses that pattern.
