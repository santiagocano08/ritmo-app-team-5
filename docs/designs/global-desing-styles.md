# PulsoFlota · Global mock-up styles (UXUI-01 to UXUI-12)

A list of the tokens and patterns repeated across the 36 screens on the canvas. The values come from the artboards' code. The screenshots are in `escritorio/`, `celular/` and `historias/`.

On-screen copy is kept in Spanish, as it appears in the app (in «quotes»).

---

## 1. Artboard formats

| Type | Size | Use |
|---|---|---|
| Desktop | 1280 × 800 px | Story screen (interactive) |
| Mobile | 390 × 844 px | Story screen (interactive) |
| Story | 560 × 900 px | User story card: acceptance criteria and notes |

Breakpoints given in UXUI-03: desktop from 1024 px, mobile below 768 px.

---

## 2. Color palette

### 2.1 Neutrals and surfaces
| Token | Hex | Use |
|---|---|---|
| App background | `#F4F6F9` | General background, table headers, quote blocks |
| Surface | `#FFFFFF` | Cards, headers, inputs, active menu item |
| Soft surface | `#F8FAFC` | Recommendations side panel |
| Neutral chip | `#F1F3F6` | Neutral labels («Datos de ejemplo») |
| Soft secondary button | `#EEF2F7` | «Mostrar» button inside the password input |
| Primary text | `#12161C` | Body and titles |
| Strong secondary text | `#3A4250` | Details, table headers, station labels |
| Secondary text | `#4A5361` | Hints, labels, order numbers |
| Standard border | `#DDE1E7` | Cards, header, dividers |
| Control border | `#A3ACB9` | Inputs, secondary buttons, corridor line, placeholders |
| Row divider | `#EEF0F3` | Table and list rows |

### 2.2 Brand
| Token | Hex | Use |
|---|---|---|
| Navy | `#14213D` | Sidebar, bus markers, login brand panel |
| Light navy | `#2B3A5C` | Dividers and avatar on the sidebar |
| Brand amber | `#FBBF24` | Logo icon on dark backgrounds (on mobile, `#B45309` on light backgrounds) |
| Action blue | `#1D4ED8` | Primary button, links, prototype controls |
| Dark blue | `#1E3A8A` | Link hover, text on blue backgrounds |
| Text on navy | `#E2E8F0` / `#CBD5E1` / `#94A3B8` | Menu items, user role, login footer |

### 2.3 Semantic (background / text pairs)
| Meaning | Background | Text |
|---|---|---|
| Success · En vivo · Regular | `#DCFCE7` | `#166534` |
| Warning · Estimado | `#FEF3C7` | `#78350F` |
| Error · Sin datos · Conflict | `#FEE2E2` | `#991B1B` |
| Bunching | `#FFEDD5` (border `#FDBA74`) | `#9A3412` |
| Gap · Information | `#DBEAFE` (border `#93C5FD`) | `#1E3A8A` |
| Story / bridge badge | `#E0E7FF` | `#1E3A8A` |
| Secondary info | `#E0F2FE` | `#0C4A6E` |
| Neutral | `#F1F3F6` | `#3A4250` |
| Destructive action (button) | `#991B1B` | `#FFFFFF` |

Bunched bus on the diagram: background `#C2410C`, white text. Bus with estimated data: dashed border.

---

## 3. Typography

Google Fonts: **Inter** (400, 500, 600, 700) for the interface and **Space Grotesk** (500, 700) for brand, titles, figures and time.

| Role | Font | Desktop size | Mobile size | Weight |
|---|---|---|---|---|
| Login headline | Space Grotesk | 44 px | 34 px | 700 |
| Screen title (h1) | Space Grotesk | 24–26 px (30 px on login) | 22 px | 700 |
| Story card title | Space Grotesk | 28 px | n/a | 700 |
| «PulsoFlota» brand | Space Grotesk | 20 px (26 px on login) | n/a | 700 |
| KPI figures | Space Grotesk | 26 px | 22–24 px | 700 |
| Current time | Space Grotesk | 22 px | 18 px | 700 |
| Section title (h2) | Inter | 15–16 px | 15–17 px | 600–700 |
| Body | Inter | 14–15 px | 14–15 px | 400 |
| Labels and chips | Inter | 12–13 px | 12 px | 600–700 |
| Hints and metadata | Inter | 12–13 px | 12 px | 400–600 |
| Table headers | Inter | 14 px | n/a | 600 |
| Uppercase labels | Inter | 12–13 px, `letter-spacing: .05–.06em` | 11–12 px | 600 |

Most frequently used scale: 12, 13, 14, 15, 16, 20, 22, 24, 26 px. `line-height`: 1.1–1.15 for headlines, 1.4–1.5 for paragraphs.

---

## 4. Spacing, borders and shape

- Usual spacing: 4, 6, 8, 10, 12, 14, 16, 20, 24, 28 px.
- Content padding: 28 px on desktop, 16 px on mobile.
- Radii: 6 px (chips and small buttons), 8 px (buttons, inputs, menu items), 10 px (cards and rows), 12 px (placeholders and panels), 16 px (mobile bottom sheet), 999 px (pills and avatars).
- Borders: `1px solid #DDE1E7` on cards; `1px solid #A3ACB9` on controls; `2px dashed #A3ACB9` on placeholders; `2px dashed #1D4ED8` on prototype controls.
- Shadow: only one is used, `0 8px 24px rgba(18,22,28,.35)`, for floating layers. The rest of the interface is flat.
- Iconography: 2 px stroke, rounded caps and joins, `stroke: currentColor`; 18–22 px, 24 px in the login logo (36 px).

---

## 5. Global components

### 5.1 Navigation
- **Desktop:** 248 px sidebar, background `#14213D`, 44 px items, 8 px radius; the active one is white with `#14213D` text. Footer with a 36 px avatar, role and «Cerrar sesión».
- **Mobile:** 72 px bottom bar, white background, top border `#DDE1E7`, up to 4 items with a 22 px icon above a 12 px label; the last one is «Más» (profile and sign out).

### 5.2 Top header
- **Desktop:** 68 px tall, white background, bottom border `#DDE1E7`. Corridor selector on the left; status badge and time on the right.
- **Mobile:** compact, with corridor, time and the status badge below (`align-self: flex-start`).

### 5.3 Data status badge (pill)
Radius 999 px, padding `6px 12px`, 9–10 px dot, bold label and detail. States: «En vivo», «Estimado», «Sin datos» (colors in 2.3). It always carries text in addition to color.

### 5.4 Alert banner
`role="alert"`, full width below the header, padding `12px 28px` (mobile `10px 16px`), same color pair as the badge.

### 5.5 Buttons
| Type | Style |
|---|---|
| Primary | Background `#1D4ED8`, white text, 8 px radius, 600; 40 px tall (secondary actions), 48 px (forms) |
| Secondary | White background, border `1px solid #A3ACB9`, text `#12161C` |
| Link | Text `#1D4ED8`, 14 px / 600, hover `#1E3A8A` |
| Prototype control | Border `2px dashed #1D4ED8`, text `#1D4ED8`, transparent background |
| Destructive | Background `#991B1B`, white text |
| Accent | Background `#FBBF24`, text `#14213D` |

Minimum touch heights: 40 px on desktop and 44 px on mobile.

### 5.6 Forms
14 px / 600 label above the field with `gap: 6px`. Input 48 px tall, 14 px horizontal padding, border `1px solid #A3ACB9`, 8 px radius, 16 px text, white background. The «Mostrar/Ocultar» button sits inside the field (40 px, background `#EEF2F7`, text `#1E3A8A`, 6 px radius).

### 5.7 Cards and KPIs
White background, `1px solid #DDE1E7`, 10 px radius, padding `12px 16px` to `14px 16px`. KPIs have a 13 px label and a 26 px figure; alert KPIs switch to the matching semantic pair.

### 5.8 Tables
Container with border and 10 px radius (`overflow: hidden`). Header in `#F4F6F9`, text `#3A4250` / 600. Cells with padding `8–10px 16px`, divider `1px solid #EEF0F3`, states as chips with a 6 px radius.

### 5.9 Chips and labels
Padding `3px 8px`, 6 px radius, 12 px / 600–700. Semantic variants (2.3). Story card badges use 999 px pills.

### 5.10 Tabs
44 px tall, 15 px / 700 text, 3 px bottom line on the active tab over a 2 px `#DDE1E7` border; counter in a 22 px pill.

### 5.11 Corridor diagram
4 px `#A3ACB9` line with a 2 px radius, 16 px stations (white, 3 px `#14213D` ring), 12 px / 600 `#3A4250` labels, 12 px / 700 bus markers with a 6 px radius (background `#14213D`, white text).

### 5.12 Bottom sheet (mobile) and side panels (desktop)
- Mobile: sheet with a 16 px top radius, gray handle, background `#F8FAFC`, dimmed backdrop.
- Desktop: 400 px panel on the right, background `#F8FAFC`, left border `#DDE1E7`.

### 5.13 Content placeholder
Border `2px dashed #A3ACB9`, 12 px radius, centered 15 px text (14 px on mobile) in `#4A5361`.

### 5.14 Story card (560 × 900)
White background, border `#DDE1E7`, padding `32px 40px`. Row of chips at the top (US, turn, lane), title in Space Grotesk 28 px, «Como / quiero / para» (as a / I want / so that) block on `#F4F6F9`, 13.5 px acceptance criteria with 13 px uppercase h2, an amber (`#FEF3C7`) hypothesis note and an indigo (`#E0E7FF`) bridge note.

---

## 6. Motion

- Recommendations panel entrance: `translateX(60px) → 0` with opacity, 0.35 s `ease-out`.
- Zone highlight on the diagram: opacity blink 1 → 0.35 → 1, 1.2 s, 3 repetitions.
- Both animations are disabled with `prefers-reduced-motion: reduce`.

---

## 7. Accessibility

- Semantic structure: `<nav aria-label>`, `<header>`, `<main>`, `<aside>`, `<section aria-label>`, `<table>`, `role="tablist"`.
- `aria-current="page"` on the active menu item; `role="status"` on the data status and `role="alert"` on banners.
- Status is never conveyed by color alone: there is always text.
- Decorative icons have `aria-hidden="true"`.
- Touch targets of at least 40–44 px.
- High-contrast text/background pairs for status colors (dark green, amber and red on light tints).

---

## 8. Notes

- The screenshots were generated without access to Google Fonts, so text set in Space Grotesk shows in the Inter fallback. The artifact itself does load Space Grotesk.
- Each screen was captured with its default values (for example, the Despachador role and «En vivo» data). The other editable states are not included.
