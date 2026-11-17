---
inclusion: auto
name: testing-quality-gates
description: Al escribir pruebas, configurar CI/CD, o verificar una compuerta de calidad (SAST, SCA, DataOps, cobertura >80 %, Human-in-the-Loop).
---

# Pruebas y Compuertas de Calidad — PulsoFlota

## Test-First (Principio V, NON-NEGOTIABLE)

- Todo PR incluye pruebas unitarias y de integración con cobertura > 80 %.
- Ningún desarrollador o agente omite el paso por las compuertas.

## Compuerta 1 — Contrato y Análisis Estático (cada PR)

- SAST: `Bandit` (Python) y `ESLint` (JavaScript).
- Validación de esquemas Pydantic.
- Aprobación: 0 hallazgos Críticos/Altos en SAST y esquema de contrato validado.

## Compuerta 2 — Integración y Supply Chain (CI)

- SCA: `pip-audit` / `Trivy` (y `Safety`/`Snyk` para Python).
- Suites de pruebas unitarias/integración.
- Aprobación: cobertura > 80 % y 0 vulnerabilidades conocidas en dependencias
  (CVE CVSS ≥ 7.0 bloquea la fusión).

## Compuerta 3 — Compuerta del Dato (DataOps, runtime de ingesta)

- Pruebas de contrato de mensaje, validación HMAC y detección de anomalías.
- Aprobación: tasa de rechazo de paquetes < 0,1 % y latencia de ingesta
  ≤ 200 ms.

## Compuerta 4 — Valor y Seguridad Operativa (cierre de vuelta)

- Validación Human-in-the-Loop, auditoría de desvíos y prueba de fallback.
- Aprobación: aprobación explícita del despachador y verificación de no
  interferencia de la IA en el camino de tiempo real.

## Falla inmediata

- Una violación de principios (p. ej. código sin pruebas fusionado a la rama
  principal, o recomendaciones emitidas sin compuerta humana) marca el build de
  CI como fallado de inmediato.

## Foco de pruebas de integración

- Nuevos contratos de servicio, cambios de contrato, comunicación
  inter-servicios y esquemas compartidos.

## Referencias

- Matriz OWASP Top 10 (2025) y criterios de SAST/SCA: `security.md`.
- Ciclo RITMO, ramas `feature/US-XX` y carriles: `ritmo-workflow.md`.
