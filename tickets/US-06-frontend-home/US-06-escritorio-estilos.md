# PulsoFlota · UXUI-03 Main navigation by role and data state (*Navegación principal por rol y estado del dato*)
## Style specification · Desktop view (1280 × 800 px)

Reference image: `mockup-base-escritorio.png` (Despachador role, «En vivo» state; exported at 2x, 2560 × 1600 px).

On-screen copy and accessible names (`aria-label`) are in Spanish, as the app shows them, and are kept verbatim in «quotes».

---

## 1. Canvas and overall structure

| Element | Value |
|---|---|
| Artboard size | 1280 × 800 px, fixed width |
| General background | `#F4F6F9` |
| Base text color | `#12161C` |
| Base font | Inter, sans-serif |
| Layout | horizontal `display: flex`: sidebar (248 px) + content column (`flex: 1`) |

The content column is vertical: header (68 px) → alert banner (optional) → main area (`flex: 1`).

---

## 2. Color palette

### Base
| Use | Hex |
|---|---|
| Application background | `#F4F6F9` |
| Surface (header) | `#FFFFFF` |
| Primary text | `#12161C` |
| Secondary text | `#4A5361` |
| Border / divider | `#DDE1E7` |
| Placeholder border | `#A3ACB9` |
| Link | `#1D4ED8` (hover `#1E3A8A`) |

### Sidebar
| Use | Hex |
|---|---|
| Background | `#14213D` |
| Inactive item text | `#E2E8F0` |
| Active item background / text | `#FFFFFF` / `#14213D` |
| Logo accent (icon) | `#FBBF24` |
| Footer divider and avatar | `#2B3A5C` |
| User role (text) | `#CBD5E1` |

### Data states (header badge and banner)
| State | Background | Text / dot |
|---|---|---|
| En vivo | `#DCFCE7` | `#166534` |
| Estimado | `#FEF3C7` | `#78350F` |
| Sin datos | `#FEE2E2` | `#991B1B` |

---

## 3. Typography

| Role | Font | Size | Weight | Other |
|---|---|---|---|---|
| Brand name «PulsoFlota» | Space Grotesk | 20 px | 700 | |
| Section title (h1) | Space Grotesk | 26 px | 700 (h1 default) | margin 0 |
| Current time | Space Grotesk | 22 px | 700 | `aria-label="Hora actual"` |
| Menu items | Inter | 15 px | 600 | |
| «Corredor» label | Inter | 12 px | 600 | uppercase, `letter-spacing: .05em`, color `#4A5361` |
| Corridor name | Inter | 16 px | 700 | |
| Status label | Inter | 14 px | 700 | |
| Status detail | Inter | 13 px | 400 | |
| User name | Inter | 14 px | 600 | |
| User role | Inter | 13 px | 400 | color `#CBD5E1` |
| «Cerrar sesión» | Inter | 14 px | 600 | |
| Banner text | Inter | 14 px | 400 | `line-height: 1.4` |
| Placeholder text | Inter | 15 px | 400 | centered |

Fonts loaded from Google Fonts: Inter (400, 500, 600, 700) and Space Grotesk (500, 700).

> Note: the PNG image was generated without access to Google Fonts, so the Space Grotesk titles show in the Inter fallback. The artifact itself does use Space Grotesk.

---

## 4. Navigation sidebar

- Element `<nav aria-label="Secciones">`.
- Width 248 px, full height, `box-sizing: border-box`, padding `20px 14px`.
- Background `#14213D`, white text.
- Column layout with `gap: 6px`.

### 4.1 Logo
- Row with `gap: 10px`, padding `4px 10px 22px`.
- Pulse icon (path `M2 12h4l3-8 4 16 3-8h6`), 26 × 26 px, color `#FBBF24`, stroke 2, rounded caps and joins.
- Text «PulsoFlota» in Space Grotesk 20 px / 700.

### 4.2 Menu items
- 44 px tall, 12 px horizontal padding, `gap: 12px`, 8 px radius, no underline.
- 20 × 20 px icon, stroke 2, `stroke: currentColor`.
- Text Inter 15 px / 600.
- **Inactive:** transparent background, text `#E2E8F0`.
- **Active (first item, `aria-current="page"`):** background `#FFFFFF`, text `#14213D`.
- Icons: «Central en vivo» (pulse), «Alertas» (bell), «Plan del día» (calendar), «Indicadores de calidad» (bars).

### 4.3 Sidebar footer (pinned to the bottom with `margin-top: auto`)
- 12 px padding, top border `1px solid #2B3A5C`, column with `gap: 10px`.
- **User:** 36 × 36 px round avatar (background `#2B3A5C`, initials «UD» at 13 px / 700) + name «Usuario demo» (14 px / 600) and role (13 px, `#CBD5E1`).
- **Cerrar sesión (sign out):** 40 px tall link, 4 px horizontal padding, `gap: 10px`, 18 × 18 px exit icon, 14 px / 600 text, color `#E2E8F0`. Links to UXUI-01 (desktop).

---

## 5. Top header

- Element `<header>`: 68 px tall, 28 px horizontal padding, `gap: 20px`, background `#FFFFFF`, bottom border `1px solid #DDE1E7`.
- **Left:** corridor selector, in a column.
  - Label «CORREDOR» (12 px / 600, uppercase, `#4A5361`).
  - Button with no background or border, with the text «[Corredor piloto] · Estación → casa» (16 px / 700) and a 16 × 16 px down chevron, `gap: 6px`.
- **Right** (`margin-left: auto`, `gap: 16px`):
  - **Status badge** (`role="status"`): pill (999 px radius), padding `6px 12px`, `gap: 10px`. It holds a 10 × 10 px dot in the text color, the label (14 px / 700) and the detail (13 px). Colors by state (see section 2).
  - **Time:** «17:42» in Space Grotesk 22 px / 700.

---

## 6. Alert banner («Estimado» and «Sin datos» states only)

- `role="alert"`, full width below the header.
- Padding `12px 28px`, `line-height: 1.4`, 14 px text, bottom border `1px solid #DDE1E7`.
- Uses the same background and text color as the status badge.
- Copy:
  - **Estimado:** «Parte de los datos son estimados porque la fuente de un operador no responde. Las recomendaciones basadas en ellos se marcan como estimadas.»
  - **Sin datos:** «No llegan eventos del corredor desde hace más de 2 min. No hay recomendaciones nuevas; decide con el plan del día.»
- It is not shown in the «En vivo» state.

---

## 7. Main area

- Element `<main>`: `flex: 1`, 28 px padding, column with `gap: 16px`.
- h1 title with the name of the active section (Space Grotesk 26 px).
- **Content placeholder:** fills the remaining height (`flex: 1`), border `2px dashed #A3ACB9`, 12 px radius, 24 px padding, content centered on both axes, text `#4A5361` 15 px: «Contenido de la sección: se define en las próximas historias.»

---

## 8. Variants by role and data state

Editable artboard properties: `rol` (despachador | gestor) and `dato` (vivo | estimado | sindatos).

### By role
| Role | Menu items (the first one is active) | Role in the footer | h1 title |
|---|---|---|---|
| Dispatcher | Central en vivo · Alertas · Plan del día | «Despachador» | «Central en vivo» |
| Manager | Indicadores de calidad · Plan del día | «Gestor del sistema» | «Indicadores de calidad» |

### By data state
| State | Badge | Detail | Banner |
|---|---|---|---|
| En vivo | «En vivo» | «Último evento 17:42:08» | No |
| Estimado | «Estimado» | «Una fuente no responde desde 17:39» | Yes |
| Sin datos | «Sin datos» | «Sin eventos desde 17:39» | Yes |

---

## 9. Key radii, spacing and sizes

- Radii: 8 px (menu items), 12 px (placeholder), 999 px (badge and avatar).
- Frequent spacing: 6, 10, 12, 16, 20, 28 px.
- Fixed heights: header 68 px, menu item 44 px, «Cerrar sesión» 40 px.
- Fixed sidebar width: 248 px.

---

## 10. Accessibility applied

- `<nav aria-label="Secciones">`, `aria-current="page"` on the active item.
- Decorative icons with `aria-hidden="true"`.
- The badge uses `role="status"` and the banner `role="alert"`.
- State is conveyed with text, not color alone.
- Text contrast on status backgrounds: green `#166534` on `#DCFCE7`, amber `#78350F` on `#FEF3C7`, red `#991B1B` on `#FEE2E2`.
- Real links and buttons (`<a>`, `<button>`), 40–44 px tall.
