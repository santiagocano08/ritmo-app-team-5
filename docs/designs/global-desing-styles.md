# PulsoFlota · Estilos globales del mock-up (UXUI-01 a UXUI-12)

Listado de los tokens y patrones que se repiten en las 36 pantallas del lienzo. Los valores salen del código de los artboards. Las capturas están en `escritorio/`, `celular/` y `historias/`.

---

## 1. Formatos de artboard

| Tipo | Tamaño | Uso |
|---|---|---|
| Escritorio | 1280 × 800 px | Pantalla de la historia (interactiva) |
| Celular | 390 × 844 px | Pantalla de la historia (interactiva) |
| Historia | 560 × 900 px | Ficha de la historia de usuario: criterios de aceptación y notas |

Puntos de quiebre indicados en UXUI-03: escritorio desde 1024 px, celular por debajo de 768 px.

---

## 2. Paleta de colores

### 2.1 Neutros y superficies
| Token | Hex | Uso |
|---|---|---|
| Fondo de app | `#F4F6F9` | Fondo general, encabezados de tabla, bloques de cita |
| Superficie | `#FFFFFF` | Tarjetas, encabezados, inputs, ítem activo del menú |
| Superficie suave | `#F8FAFC` | Panel lateral de recomendaciones |
| Chip neutro | `#F1F3F6` | Etiquetas neutras («Datos de ejemplo») |
| Botón secundario suave | `#EEF2F7` | Botón «Mostrar» dentro del input de contraseña |
| Texto principal | `#12161C` | Cuerpo y títulos |
| Texto fuerte secundario | `#3A4250` | Detalles, encabezados de tabla, etiquetas de estación |
| Texto secundario | `#4A5361` | Ayudas, etiquetas, números de orden |
| Borde estándar | `#DDE1E7` | Tarjetas, encabezado, separadores |
| Borde de control | `#A3ACB9` | Inputs, botones secundarios, línea del corredor, placeholders |
| Separador de fila | `#EEF0F3` | Filas de tabla y de listas |

### 2.2 Marca
| Token | Hex | Uso |
|---|---|---|
| Azul marino | `#14213D` | Barra lateral, marcadores de bus, panel de marca del login |
| Azul marino claro | `#2B3A5C` | Divisores y avatar sobre la barra lateral |
| Ámbar de marca | `#FBBF24` | Ícono del logo sobre fondo oscuro (en celular, `#B45309` sobre fondo claro) |
| Azul de acción | `#1D4ED8` | Botón primario, enlaces, controles del prototipo |
| Azul oscuro | `#1E3A8A` | Hover de enlaces, textos sobre fondos azules |
| Texto sobre marino | `#E2E8F0` / `#CBD5E1` / `#94A3B8` | Ítems de menú, rol de usuario, pie del login |

### 2.3 Semánticos (pares fondo / texto)
| Significado | Fondo | Texto |
|---|---|---|
| Éxito · En vivo · Regular | `#DCFCE7` | `#166534` |
| Advertencia · Estimado | `#FEF3C7` | `#78350F` |
| Error · Sin datos · Conflicto | `#FEE2E2` | `#991B1B` |
| Agrupamiento | `#FFEDD5` (borde `#FDBA74`) | `#9A3412` |
| Hueco · Información | `#DBEAFE` (borde `#93C5FD`) | `#1E3A8A` |
| Insignia de historia / puente | `#E0E7FF` | `#1E3A8A` |
| Info secundaria | `#E0F2FE` | `#0C4A6E` |
| Neutro | `#F1F3F6` | `#3A4250` |
| Acción destructiva (botón) | `#991B1B` | `#FFFFFF` |

Bus agrupado en el diagrama: fondo `#C2410C`, texto blanco. Bus con dato estimado: borde discontinuo.

---

## 3. Tipografía

Fuentes de Google Fonts: **Inter** (400, 500, 600, 700) para interfaz y **Space Grotesk** (500, 700) para marca, títulos, cifras y hora.

| Rol | Fuente | Tamaño escritorio | Tamaño celular | Peso |
|---|---|---|---|---|
| Titular del login | Space Grotesk | 44 px | 34 px | 700 |
| Título de pantalla (h1) | Space Grotesk | 24–26 px (30 px en login) | 22 px | 700 |
| Título de ficha de historia | Space Grotesk | 28 px | n/a | 700 |
| Marca «PulsoFlota» | Space Grotesk | 20 px (26 px en login) | n/a | 700 |
| Cifras de KPI | Space Grotesk | 26 px | 22–24 px | 700 |
| Hora actual | Space Grotesk | 22 px | 18 px | 700 |
| Título de sección (h2) | Inter | 15–16 px | 15–17 px | 600–700 |
| Cuerpo | Inter | 14–15 px | 14–15 px | 400 |
| Etiquetas y chips | Inter | 12–13 px | 12 px | 600–700 |
| Ayudas y metadatos | Inter | 12–13 px | 12 px | 400–600 |
| Encabezados de tabla | Inter | 14 px | n/a | 600 |
| Etiquetas en mayúsculas | Inter | 12–13 px, `letter-spacing: .05–.06em` | 11–12 px | 600 |

Escala usada con más frecuencia: 12, 13, 14, 15, 16, 20, 22, 24, 26 px. `line-height`: 1.1–1.15 en titulares, 1.4–1.5 en párrafos.

---

## 4. Espaciado, bordes y forma

- Espaciados habituales: 4, 6, 8, 10, 12, 14, 16, 20, 24, 28 px.
- Padding de contenido: 28 px en escritorio, 16 px en celular.
- Radios: 6 px (chips y botones pequeños), 8 px (botones, inputs, ítems de menú), 10 px (tarjetas y filas), 12 px (placeholders y paneles), 16 px (hoja inferior en celular), 999 px (píldoras y avatares).
- Bordes: `1px solid #DDE1E7` en tarjetas; `1px solid #A3ACB9` en controles; `2px dashed #A3ACB9` en placeholders; `2px dashed #1D4ED8` en controles del prototipo.
- Sombra: se usa una sola, `0 8px 24px rgba(18,22,28,.35)`, para capas flotantes. El resto de la interfaz es plana.
- Iconografía: trazo de 2 px, extremos y uniones redondeados, `stroke: currentColor`; 18–22 px, de 24 px en el logo de login (36 px).

---

## 5. Componentes globales

### 5.1 Navegación
- **Escritorio:** barra lateral de 248 px, fondo `#14213D`, ítems de 44 px, radio 8 px; el activo va en blanco con texto `#14213D`. Pie con avatar de 36 px, rol y «Cerrar sesión».
- **Celular:** barra inferior de 72 px, fondo blanco, borde superior `#DDE1E7`, hasta 4 ítems con ícono de 22 px sobre etiqueta de 12 px; el último es «Más» (perfil y cerrar sesión).

### 5.2 Encabezado superior
- **Escritorio:** 68 px de alto, fondo blanco, borde inferior `#DDE1E7`. Selector de corredor a la izquierda; insignia de estado y hora a la derecha.
- **Celular:** compacto, con corredor, hora y la insignia de estado debajo (`align-self: flex-start`).

### 5.3 Insignia de estado del dato (píldora)
Radio 999 px, padding `6px 12px`, punto de 9–10 px, etiqueta en negrita y detalle. Estados: En vivo, Estimado, Sin datos (colores en 2.3). Siempre lleva texto además del color.

### 5.4 Banner de alerta
`role="alert"`, ancho completo bajo el encabezado, padding `12px 28px` (celular `10px 16px`), mismo par de colores que la insignia.

### 5.5 Botones
| Tipo | Estilo |
|---|---|
| Primario | Fondo `#1D4ED8`, texto blanco, radio 8 px, 600; alto 40 px (acciones secundarias), 48 px (formularios) |
| Secundario | Fondo blanco, borde `1px solid #A3ACB9`, texto `#12161C` |
| Enlace | Texto `#1D4ED8`, 14 px / 600, hover `#1E3A8A` |
| Control de prototipo | Borde `2px dashed #1D4ED8`, texto `#1D4ED8`, fondo transparente |
| Destructivo | Fondo `#991B1B`, texto blanco |
| Acento | Fondo `#FBBF24`, texto `#14213D` |

Alturas táctiles mínimas: 40 px en escritorio y 44 px en celular.

### 5.6 Formularios
Etiqueta de 14 px / 600 sobre el campo con `gap: 6px`. Input de 48 px de alto, padding horizontal 14 px, borde `1px solid #A3ACB9`, radio 8 px, texto de 16 px, fondo blanco. El botón «Mostrar/Ocultar» va dentro del campo (40 px, fondo `#EEF2F7`, texto `#1E3A8A`, radio 6 px).

### 5.7 Tarjetas y KPI
Fondo blanco, `1px solid #DDE1E7`, radio 10 px, padding `12px 16px` a `14px 16px`. Los KPI llevan etiqueta de 13 px y cifra de 26 px; los KPI de alerta cambian al par semántico correspondiente.

### 5.8 Tablas
Contenedor con borde y radio 10 px (`overflow: hidden`). Encabezado en `#F4F6F9`, texto `#3A4250` / 600. Celdas con padding `8–10px 16px`, separador `1px solid #EEF0F3`, estados como chips de 6 px de radio.

### 5.9 Chips y etiquetas
Padding `3px 8px`, radio 6 px, 12 px / 600–700. Variantes semánticas (2.3). Las insignias de ficha usan píldoras de 999 px.

### 5.10 Pestañas
Alto 44 px, texto 15 px / 700, línea inferior de 3 px en la pestaña activa sobre un borde de 2 px `#DDE1E7`; contador en una píldora de 22 px.

### 5.11 Diagrama del corredor
Línea de 4 px `#A3ACB9` con radio 2 px, estaciones de 16 px (blancas, aro de 3 px `#14213D`), etiquetas de 12 px / 600 `#3A4250`, marcadores de bus de 12 px / 700 con radio 6 px (fondo `#14213D`, texto blanco).

### 5.12 Hoja inferior (celular) y paneles laterales (escritorio)
- Celular: hoja con radio superior de 16 px, asa gris, fondo `#F8FAFC`, fondo atenuado detrás.
- Escritorio: panel de 400 px a la derecha, fondo `#F8FAFC`, borde izquierdo `#DDE1E7`.

### 5.13 Placeholder de contenido
Borde `2px dashed #A3ACB9`, radio 12 px, texto centrado de 15 px (14 px en celular) en `#4A5361`.

### 5.14 Ficha de historia (560 × 900)
Fondo blanco, borde `#DDE1E7`, padding `32px 40px`. Fila de chips arriba (US, vuelta, carril), título en Space Grotesk 28 px, bloque «Como / quiero / para» sobre `#F4F6F9`, criterios de aceptación de 13,5 px con h2 en mayúsculas de 13 px, nota ámbar (`#FEF3C7`) de hipótesis y nota índigo (`#E0E7FF`) de puente.

---

## 6. Movimiento

- Entrada de panel de recomendaciones: `translateX(60px) → 0` con opacidad, 0,35 s `ease-out`.
- Resaltado de zona en el diagrama: parpadeo de opacidad 1 → 0,35 → 1, 1,2 s, 3 repeticiones.
- Ambas animaciones se desactivan con `prefers-reduced-motion: reduce`.

---

## 7. Accesibilidad

- Estructura semántica: `<nav aria-label>`, `<header>`, `<main>`, `<aside>`, `<section aria-label>`, `<table>`, `role="tablist"`.
- `aria-current="page"` en el ítem activo del menú; `role="status"` en el estado del dato y `role="alert"` en banners.
- El estado nunca se comunica solo con color: siempre hay texto.
- Íconos decorativos con `aria-hidden="true"`.
- Objetivos táctiles de al menos 40–44 px.
- Pares de color de texto sobre fondo de estado con contraste alto (verde, ámbar y rojo oscuros sobre tonos claros).

---

## 8. Notas

- Las capturas se generaron sin acceso a Google Fonts, así que los textos en Space Grotesk aparecen con Inter de respaldo. En el artefacto sí se carga Space Grotesk.
- Cada pantalla se capturó con sus valores por defecto (por ejemplo, rol Despachador y dato «En vivo»). Los demás estados editables no están incluidos.
