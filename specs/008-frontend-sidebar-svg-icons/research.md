# Phase 0 Research: Sidebar SVG Icons

Feature: `008-frontend-sidebar-svg-icons` · Branch `feature/US-11-frontend-sidebar-svg-icons`

The Technical Context has no open `NEEDS CLARIFICATION` markers: the spec,
`tickets/US-06-frontend-home/US-06-escritorio-estilos.md` §4.1–4.3 and the
current `Sidebar.tsx` fully determine the shapes, sizes, colours and attributes.
The decisions below record the approach and the alternatives rejected.

## R1 — Icon delivery mechanism: inline SVG in the component

- **Decision**: Render each icon as an inline `<svg>` element written directly
  in the JSX of `Sidebar.tsx`. Menu-item icons use `stroke="currentColor"`;
  the logo uses the brand highlight colour; all carry `aria-hidden="true"`.
- **Rationale**: FR-009 forbids a new third-party icon dependency. Inline SVG
  guarantees identical rendering across machines and fonts (SC-002), inherits
  the active/inactive text colour via `currentColor` (FR-004), and keeps the
  icon markup inside the already-tested component so the coverage gate does not
  regress (SC-005). It matches the frontend-web steering rule to use the design
  tokens and decorative `aria-hidden` icons.
- **Alternatives considered**:
  - *Icon library (lucide-react, heroicons)* — rejected: adds a dependency
    (violates FR-009), enlarges the SCA/bundle surface, and the library glyphs
    may not match the spec's exact `M2 12h4l3-8 4 16 3-8h6` pulse path.
  - *External `.svg` files imported as components / `<img>`* — rejected: `<img>`
    cannot inherit `currentColor` for active/inactive states (FR-004); a new
    file per icon adds surface outside the single-file surgical edit and risks
    coverage-include changes. Inline keeps the change in one file.
  - *Keep Unicode glyphs with a web font* — rejected: that is the current defect
    (font-dependent rendering, SC-002 fails).

## R2 — SVG shapes, sizes and colours (authoritative values)

- **Decision**: Use the exact values from US-06 style spec §4.1–4.3:
  - **Logo (pulse)**: `viewBox` sized 26×26, `path d="M2 12h4l3-8 4 16 3-8h6"`,
    `stroke` `#FBBF24` (token `text-logo`), `strokeWidth={2}`,
    `strokeLinecap="round"`, `strokeLinejoin="round"`, `fill="none"`.
  - **Menu items** 20×20, `strokeWidth={2}`, `stroke="currentColor"`,
    `fill="none"`: *Central en vivo* = pulse, *Alertas* = bell,
    *Plan del día* = calendar.
  - **Cerrar sesión** = exit icon, 18×18, `stroke="currentColor"`.
- **Rationale**: The spec Assumptions name these values authoritative. The pulse
  path is given verbatim; bell, calendar and exit are standard 24-grid stroke
  shapes scaled to the stated box.
- **Alternatives considered**: Inventing new sizes/colours — rejected by the
  "do not invent new tokens" rule in frontend-web steering and by SC-001/SC-002.

## R3 — Typing `NavItem.icon` under strict TypeScript

- **Decision**: Change `NavItem.icon` from `string` to a React element type that
  holds the inline SVG, e.g. `icon: ReactNode` (or a `() => ReactElement`
  component), imported from `react`. No `any`.
- **Rationale**: The icon is no longer a glyph string; it is JSX. A `ReactNode`
  (or small icon component reference) is the minimal strict-typed change and
  keeps ESLint (`no-explicit-any` = error) and `tsc --noEmit` green.
- **Alternatives considered**:
  - *Keep `icon: string` holding an SVG path string* — rejected: reintroduces
    stringly-typed markup, needs `dangerouslySetInnerHTML` or manual `<path>`
    assembly, and loses per-icon attribute typing.
  - *Separate `iconName` enum + lookup map* — rejected as premature abstraction
    (KISS/YAGNI) for five fixed icons; inline keeps it simplest.

## R4 — No contracts artifact

- **Decision**: Do not generate `specs/008-frontend-sidebar-svg-icons/contracts/`.
- **Rationale**: FR-009 states the change must not alter data contracts or
  generated types and adds no external interface. There is no API, schema, CLI
  or message contract to document. Per the plan workflow, the contracts step is
  skipped when the project exposes no new interface.
- **Alternatives considered**: Documenting a "UI contract" for the icons —
  rejected: the visual contract already lives in the US-06 style spec and the
  spec's FRs; duplicating it here would violate Balanced-DRY.

## R5 — Protecting the coverage gate

- **Decision**: Keep all icon JSX inline in `Sidebar.tsx` (already exercised by
  the Sidebar tests) and add assertions, rather than extracting icons into a new
  untested module.
- **Rationale**: Coverage thresholds (lines/functions/branches/statements ≥ 80 %)
  are enforced across `src/**` in `vite.config.ts`. New uncovered files would
  risk a regression; inline markup rendered by the existing Sidebar tests stays
  covered. New assertions (one `<svg aria-hidden="true">` per entry and the
  logout link; no residual glyph `⬳◉✚▦⇥`) raise confidence without new files.
- **Alternatives considered**: A new `icons/` module with its own test file —
  rejected for this surgical, single-component change; it adds surface and test
  burden for no functional gain.

## Open questions

None. All Technical Context items are resolved; ready for Phase 1.
