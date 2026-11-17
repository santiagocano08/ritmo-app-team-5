---
inclusion: auto
name: frontend-web
description: Al trabajar en la central web del despachador (Streamlit/Dash/HTML5+WebSockets): mapa interactivo, visualización de headway y congestión, UI de Human-in-the-Loop y modo de contingencia.
---

# Central Web del Despachador — PulsoFlota

## Stack

- Streamlit / Dash o HTML5/Jinja2 con WebSockets.
- Monolito modular `pulsoflota-web`: central supervisora, cálculo de métricas y
  mapa interactivo. Pertenece al **Carril Adaptativo** (ver `ritmo-workflow.md`).

## Mapa interactivo en tiempo real

- Posición geoespacial actualizada de todos los buses activos del corredor.
- Refresco de posición con latencia ≤ 2 s (validar con 100 buses simulados).

## Headway y regularidad

- Calcular y visualizar el intervalo de paso (*headway*) entre vehículos
  consecutivos en cada ruta estándar.
- Resaltar desviaciones > ±15 % respecto al plan de marcha.

## Congestión vial

- Ingerir la velocidad de flujo vehicular por tramo y clasificar la congestión
  con codificación por colores:
  - **Verde:** fluido.
  - **Amarillo:** moderado.
  - **Rojo:** congestionado.

## Human-in-the-Loop (Principio IV, NON-NEGOTIABLE)

- Alertas tempranas de desincronización de flota con ≥ 3 min de anticipación
  antes de consolidar *bunching* o *gap*.
- Las recomendaciones de regulación (retención, salida anticipada, inyección de
  reserva, desvío) se presentan como **sugerencias no vinculantes**.
- Ningún comando se transmite a la flota sin un **clic de confirmación humana**
  explícito del despachador.
- Llevar registro de auditoría de los desvíos autorizados (para compensaciones y
  cumplimiento de contrato con operadores).

## Desvíos por contingencias

- Presentar la recomendación de desvío en el mapa con la ruta sugerida, la
  distancia adicional y la variación proyectada en el indicador de servicio.

## Contingencia

- Si la central o la web colapsan, la consola conmuta a un modo de contingencia
  local basado en planes de despacho estáticos prefijados.

## Control de acceso

- El frontend **no** debe ser el único mecanismo de control de acceso; las
  autorizaciones se evalúan en el backend. Ver `security.md` (A01) y
  `backend-api.md`.
