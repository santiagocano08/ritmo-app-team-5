---
inclusion: auto
name: realtime-ingestion
description: Al trabajar en el servicio de ingesta aislada, el pipeline de tiempo real determinista, SLOs de latencia, resiliencia, fallback o contingencia de la central.
---

# Ingesta Aislada y Tiempo Real Determinista — PulsoFlota

## Aislamiento (Principio III)

- `ingestion-service` corre en un contenedor de proceso **totalmente aislado**
  del monolito modular `pulsoflota-web`, para que fallos de la interfaz web no
  afecten la captura de datos.

## Determinismo del camino crítico

- El tiempo total desde la detección de una anomalía en vía hasta la presentación
  de la recomendación en la consola del despachador DEBE ser ≤ 10 s.
- El camino crítico de tiempo real DEBE ser determinista y **nunca** depender de
  llamadas síncronas a agentes de IA Generativa ni a servicios externos de
  terceros.
- Ningún modelo de IA o agente autónomo tiene escritura directa sobre la base de
  datos de producción ni las APIs de despacho de las unidades a bordo.

## SLOs de rendimiento

- El pipeline de ingesta procesa hasta 1 000 eventos/segundo con latencia pico
  P99 ≤ 500 ms.
- Latencia de ingesta (compuerta DataOps): ≤ 200 ms.
- Refresco del mapa interactivo: ≤ 2 s.
- Recálculo automático de ruta ante bloqueo vial: ≤ 5 s.

## Clasificación

- Tiempo real **firme**: una recomendación entregada con retraso no genera
  fallos catastróficos físicos, pero carece de valor operativo.

## Fallback y contingencia (A10)

- Si la central de control o la interfaz web colapsan, la ingesta IoT aislada
  sigue registrando eventos en el buffer persistente.
- La consola del despachador conmuta automáticamente a un modo de contingencia
  local basado en planes de despacho estáticos prefijados.

## Referencias

- Validación de eventos en la compuerta de ingesta (esquema, `422`,
  antifraude, HMAC): `data-contracts.md`.
- Observabilidad y alertas (rechazo IoT > 5 % en 1 min → SRE/DevSecOps):
  `security.md`.
