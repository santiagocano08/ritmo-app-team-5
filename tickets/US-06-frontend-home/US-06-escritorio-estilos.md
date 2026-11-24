# PulsoFlota · UXUI-03 Navegación principal por rol y estado del dato
## Especificación de estilos · Vista de escritorio (1280 × 800 px)

Imagen de referencia: `mockup-base-escritorio.png` (rol Despachador, estado «En vivo»; exportada a 2x, 2560 × 1600 px).

---

## 1. Lienzo y estructura general

| Elemento | Valor |
|---|---|
| Tamaño del artboard | 1280 × 800 px, ancho fijo |
| Fondo general | `#F4F6F9` |
| Color de texto base | `#12161C` |
| Fuente base | Inter, sans-serif |
| Distribución | `display: flex` horizontal: barra lateral (248 px) + columna de contenido (`flex: 1`) |

La columna de contenido es vertical: encabezado (68 px) → banner de alerta (opcional) → área principal (`flex: 1`).

---

## 2. Paleta de colores

### Base
| Uso | Hex |
|---|---|
| Fondo de la aplicación | `#F4F6F9` |
| Superficie (encabezado) | `#FFFFFF` |
| Texto principal | `#12161C` |
| Texto secundario | `#4A5361` |
| Borde / separador | `#DDE1E7` |
| Borde del placeholder | `#A3ACB9` |
| Enlace | `#1D4ED8` (hover `#1E3A8A`) |

### Barra lateral
| Uso | Hex |
|---|---|
| Fondo | `#14213D` |
| Texto de ítem inactivo | `#E2E8F0` |
| Fondo / texto de ítem activo | `#FFFFFF` / `#14213D` |
| Acento del logo (ícono) | `#FBBF24` |
| Línea divisoria del pie y avatar | `#2B3A5C` |
| Rol del usuario (texto) | `#CBD5E1` |

### Estados del dato (insignia del encabezado y banner)
| Estado | Fondo | Texto / punto |
|---|---|---|
| En vivo | `#DCFCE7` | `#166534` |
| Estimado | `#FEF3C7` | `#78350F` |
| Sin datos | `#FEE2E2` | `#991B1B` |

---

## 3. Tipografía

| Rol | Fuente | Tamaño | Peso | Otros |
|---|---|---|---|---|
| Nombre de marca «PulsoFlota» | Space Grotesk | 20 px | 700 | |
| Título de sección (h1) | Space Grotesk | 26 px | 700 (por defecto del h1) | margen 0 |
| Hora actual | Space Grotesk | 22 px | 700 | `aria-label="Hora actual"` |
| Ítems del menú | Inter | 15 px | 600 | |
| Etiqueta «Corredor» | Inter | 12 px | 600 | mayúsculas, `letter-spacing: .05em`, color `#4A5361` |
| Nombre del corredor | Inter | 16 px | 700 | |
| Etiqueta del estado | Inter | 14 px | 700 | |
| Detalle del estado | Inter | 13 px | 400 | |
| Nombre de usuario | Inter | 14 px | 600 | |
| Rol de usuario | Inter | 13 px | 400 | color `#CBD5E1` |
| «Cerrar sesión» | Inter | 14 px | 600 | |
| Texto del banner | Inter | 14 px | 400 | `line-height: 1.4` |
| Texto del placeholder | Inter | 15 px | 400 | centrado |

Fuentes cargadas desde Google Fonts: Inter (400, 500, 600, 700) y Space Grotesk (500, 700).

> Nota: la imagen PNG se generó sin acceso a Google Fonts, por lo que los títulos con Space Grotesk aparecen con Inter como respaldo. En el artefacto sí se usa Space Grotesk.

---

## 4. Barra lateral de navegación

- Elemento `<nav aria-label="Secciones">`.
- Ancho 248 px, alto completo, `box-sizing: border-box`, padding `20px 14px`.
- Fondo `#14213D`, texto blanco.
- Disposición en columna con `gap: 6px`.

### 4.1 Logo
- Fila con `gap: 10px`, padding `4px 10px 22px`.
- Ícono de pulso (trazo `M2 12h4l3-8 4 16 3-8h6`) de 26 × 26 px, color `#FBBF24`, trazo 2, extremos y uniones redondeados.
- Texto «PulsoFlota» en Space Grotesk 20 px / 700.

### 4.2 Ítems de menú
- Alto 44 px, padding horizontal 12 px, `gap: 12px`, radio 8 px, sin subrayado.
- Ícono de 20 × 20 px, trazo 2, `stroke: currentColor`.
- Texto Inter 15 px / 600.
- **Inactivo:** fondo transparente, texto `#E2E8F0`.
- **Activo (primer ítem, `aria-current="page"`):** fondo `#FFFFFF`, texto `#14213D`.
- Íconos: Central en vivo (pulso), Alertas (campana), Plan del día (calendario), Indicadores de calidad (barras).

### 4.3 Pie de la barra (anclado abajo con `margin-top: auto`)
- Padding 12 px, borde superior `1px solid #2B3A5C`, columna con `gap: 10px`.
- **Usuario:** avatar circular de 36 × 36 px (fondo `#2B3A5C`, iniciales «UD» en 13 px / 700) + nombre «Usuario demo» (14 px / 600) y rol (13 px, `#CBD5E1`).
- **Cerrar sesión:** enlace de 40 px de alto, padding horizontal 4 px, `gap: 10px`, ícono de salida de 18 × 18 px, texto 14 px / 600, color `#E2E8F0`. Enlaza a UXUI-01 (escritorio).

---

## 5. Encabezado superior

- Elemento `<header>`: alto 68 px, padding horizontal 28 px, `gap: 20px`, fondo `#FFFFFF`, borde inferior `1px solid #DDE1E7`.
- **Izquierda:** selector de corredor, en columna.
  - Etiqueta «CORREDOR» (12 px / 600, mayúsculas, `#4A5361`).
  - Botón sin fondo ni borde con el texto «[Corredor piloto] · Estación → casa» (16 px / 700) y un chevron hacia abajo de 16 × 16 px, `gap: 6px`.
- **Derecha** (`margin-left: auto`, `gap: 16px`):
  - **Insignia de estado** (`role="status"`): píldora (radio 999 px), padding `6px 12px`, `gap: 10px`. Contiene un punto de 10 × 10 px del color del texto, la etiqueta (14 px / 700) y el detalle (13 px). Colores según el estado (ver sección 2).
  - **Hora:** «17:42» en Space Grotesk 22 px / 700.

---

## 6. Banner de alerta (solo estados «Estimado» y «Sin datos»)

- `role="alert"`, ancho completo bajo el encabezado.
- Padding `12px 28px`, `line-height: 1.4`, texto 14 px, borde inferior `1px solid #DDE1E7`.
- Usa el mismo fondo y color de texto de la insignia del estado.
- Textos:
  - **Estimado:** «Parte de los datos son estimados porque la fuente de un operador no responde. Las recomendaciones basadas en ellos se marcan como estimadas.»
  - **Sin datos:** «No llegan eventos del corredor desde hace más de 2 min. No hay recomendaciones nuevas; decide con el plan del día.»
- En el estado «En vivo» no se muestra.

---

## 7. Área principal

- Elemento `<main>`: `flex: 1`, padding 28 px, columna con `gap: 16px`.
- Título h1 con el nombre de la sección activa (Space Grotesk 26 px).
- **Placeholder de contenido:** ocupa el resto del alto (`flex: 1`), borde `2px dashed #A3ACB9`, radio 12 px, padding 24 px, contenido centrado en ambos ejes, texto `#4A5361` 15 px: «Contenido de la sección: se define en las próximas historias.»

---

## 8. Variantes por rol y estado del dato

Propiedades editables del artboard: `rol` (despachador | gestor) y `dato` (vivo | estimado | sindatos).

### Por rol
| Rol | Ítems del menú (el primero queda activo) | Rol en el pie | Título h1 |
|---|---|---|---|
| Despachador | Central en vivo · Alertas · Plan del día | «Despachador» | «Central en vivo» |
| Gestor | Indicadores de calidad · Plan del día | «Gestor del sistema» | «Indicadores de calidad» |

### Por estado del dato
| Estado | Insignia | Detalle | Banner |
|---|---|---|---|
| En vivo | «En vivo» | «Último evento 17:42:08» | No |
| Estimado | «Estimado» | «Una fuente no responde desde 17:39» | Sí |
| Sin datos | «Sin datos» | «Sin eventos desde 17:39» | Sí |

---

## 9. Radios, espaciados y tamaños clave

- Radios: 8 px (ítems de menú), 12 px (placeholder), 999 px (insignia y avatar).
- Espaciados frecuentes: 6, 10, 12, 16, 20, 28 px.
- Alturas fijas: encabezado 68 px, ítem de menú 44 px, «Cerrar sesión» 40 px.
- Ancho fijo de la barra lateral: 248 px.

---

## 10. Accesibilidad aplicada

- `<nav aria-label="Secciones">`, `aria-current="page"` en el ítem activo.
- Íconos decorativos con `aria-hidden="true"`.
- La insignia usa `role="status"` y el banner `role="alert"`.
- El estado se comunica con texto, no solo con color.
- Contrastes de texto sobre fondos de estado: verde `#166534` sobre `#DCFCE7`, ámbar `#78350F` sobre `#FEF3C7`, rojo `#991B1B` sobre `#FEE2E2`.
- Enlaces y botones reales (`<a>`, `<button>`), con alturas de 40–44 px.
