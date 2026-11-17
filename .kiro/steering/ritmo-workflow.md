---
inclusion: auto
name: ritmo-workflow
description: Al planear o ejecutar una vuelta del espiral RITMO, una historia de usuario (US-XX), ramas por característica, o decidir el carril (Disciplinado/Adaptativo).
---

# Flujo RITMO, Carriles y Ramas — PulsoFlota

## Orden guiado por riesgo (Principio I)

- El backlog y la secuencia de vueltas se ordenan por riesgo técnico y
  arquitectónico (ASRs), no por prioridad comercial estática.
- Ninguna funcionalidad del carril adaptativo inicia si existe un riesgo de
  Nivel 1 (seguridad o integridad del dato) no mitigado en la vuelta activa.

## 5 etapas por vuelta de espiral

1. **Planear** — Dueño de Vuelta: riesgo prioritario, fecha de cierre de la
   vuelta e hipótesis operativas.
2. **Especificar** — historia de usuario como especificación SDD medible +
   compuerta de contrato si cambia el esquema.
3. **Construir** — una historia a la vez en rama aislada `feature/US-XX`
   (código de producción + pruebas + reglas del dato).
4. **Verificar** — CI (linting, pruebas unitarias, cobertura > 80 %), pruebas
   de contrato DataOps e inspección del revisor humano.
5. **Revisar (Compuerta de Valor)** — medir el impacto en P(abordar ≤ t) con el
   despachador en el entorno de pruebas/simulación.

## Ramas

- Una historia a la vez en rama aislada `feature/US-XX`.
- Convención de mensajes de commit: ver `AGENTS.md` (Conventional Commits
  inferido).

## Dos carriles operativos

- **Carril Disciplinado** (Ingesta, Contratos de Mensaje, Pago por Calidad):
  Contract-First / SDD estricto; autonomía de agentes baja (solo propuestas
  validadas en código y compuertas); criticidad máxima; CI estricto y pruebas
  de contrato DataOps.
- **Carril Adaptativo** (Central Web, Visualización, Reglas de Alerta y
  Desvío): iteraciones guiadas por hipótesis de valor con el despachador;
  autonomía media; revisión obligatoria del dueño del módulo.

## Cumplimiento

- Al cerrar cada vuelta, revisar el cumplimiento de los 5 principios core.
- Una violación detectada marca el build de CI como fallado de inmediato.

## Enmiendas a la constitución

- PR etiquetado `constitutional-amendment` + ADR + firma unánime del Dueño de
  Vuelta, el Arquitecto (de Software / de Seguridad) y el Representante del
  Despachador. Ver constitución § Governance.
