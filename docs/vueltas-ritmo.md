# Mapa de Vueltas — RITMO / PulsoFlota

## Control del Documento
* **PROJECT_NAME**: RITMO (Riesgo, Incrementos y Trazabilidad para la Movilidad Operativa) / PulsoFlota
* **VERSIÓN DEL MAPA**: 0.1.0 (borrador para revisión del equipo)
* **FECHA**: 2026-11-17
* **ESTADO**: Propuesta. Requiere aprobación del equipo
* **GOBIERNA**: Constitución v1.1.0, sección "Adopción por Fases"

---

## 1. Propósito y Cómo se Usa

Este documento dice **en qué vuelta de la espiral se adopta cada norma** de la constitución, del PRD y del SRD. Las normas técnicas describen el sistema terminado; este mapa dice cuáles se exigen en cada vuelta.

Se planifica **en ola**:
* La **vuelta activa** está en detalle.
* Las **vueltas futuras** están a alto nivel: riesgo, alcance y normas que adoptan.
* En la **Etapa 1 — Planear** de cada vuelta, el Dueño de Vuelta detalla la vuelta siguiente y actualiza este mapa. Esa actualización no requiere enmienda constitucional.

**Reglas que no cambian con la vuelta:**
* Los **5 Principios Core NON-NEGOTIABLE** aplican en **todas** las vueltas, desde la primera.
* Una norma marcada como adoptada en una vuelta **sigue siendo obligatoria** en todas las vueltas siguientes.
* Una norma **diferida** no se exige en la vuelta activa. Los agentes (`create-plan`, `validate-plan`, `review-code`) **NO DEBEN** marcarla como hallazgo bloqueante. Sí pueden registrarla como "evolución".

---

## 2. Orden de las Vueltas

El orden lo fija el **Principio 1 (Orden Guiado por Riesgo)**: ninguna funcionalidad del carril adaptativo inicia mientras haya un riesgo de Nivel 1 (seguridad o integridad del dato) sin mitigar. Por eso las dos vueltas de Nivel 1 van primero.

| Vuelta | Nombre | Riesgo que mitiga | Nivel | Carril | Estado |
|---|---|---|---|---|---|
| **1** | Dato y lazo mínimo | Integridad del dato: un dato malformado, duplicado o ausente contamina la métrica y las recomendaciones | **1** | Disciplinado | **Activa**: se construye para el taller (2026-11-24) |
| **2** | Seguridad de la operación | Acceso indebido, suplantación de unidades y fraude en el recaudo | **1** | Disciplinado | Diseño |
| **3** | Tiempo real y aislamiento | Concurrencia y latencia en hora pico; caída de la web que arrastra la ingesta | 2 | Disciplinado | Diseño |
| **4** | Carril adaptativo | Valor: que las recomendaciones mejoren de verdad P(abordar ≤ t) | 2 | Adaptativo | Diseño |

---

## 3. Vuelta 1 — Dato y Lazo Mínimo (activa)

**Hipótesis operativa:** con un contrato de mensaje validado en frontera y un lazo cerrado mínimo (detectar → recomendar → aprobar → ejecutar → medir), el despachador recibe recomendaciones confiables. Un dato caído o duplicado no dispara alertas falsas.

**Corredor:** estación Prado (línea A del Metro), ruta alimentadora C6-008, solo el sentido estación → barrio. Flota base de 5 buses + 2 de reserva.

### 3.1 Alcance
* **Contrato del mensaje** con Pydantic V2. Los eventos inválidos se rechazan con `422` y quedan registrados con su motivo.
* **Simulador** con bucle simple en Python y paso de 5 s. Publica 5 eventos: posición del bus, llegada y salida de parada, llegada de persona, confirmación del conductor y novedad.
* **Persistencia en PostgreSQL** con esquemas bronce, plata y oro. La posición se guarda como avance en metros, sin geometría.
* **Fallas del dato (D1):** duplicados y fuente caída. Un bus sin dato pasa a estado "Estimado" y no dispara alertas.
* **Métricas:** headway, espera media y EWT.
* **Escenarios:** agrupamiento, hueco, oleada en el transbordo, accidente en un tramo, bus varado y falla del dato.
* **Modelos:** líneas base para el tiempo de recorrido por tramo y para la demanda en Prado. El ML predice, las reglas deciden y la persona aprueba.
* **Recomendaciones:** retener, ajustar la salida y refuerzo desde la reserva, **siempre con aprobación del despachador** (RF-2.3).
* **Historias del PRD que cubre:** US-01 parcial (headway y estado de la flota, sin mapa geográfico) y US-02.

### 3.2 Normas que adopta
* Los 5 Principios Core.
* RNF-3.3.1: validación en frontera y rechazo del 100 % de los paquetes sin esquema válido.
* RF-2.1, RF-2.2 y RF-2.3.
* Compuerta 1: solo la validación de esquemas Pydantic.
* Compuerta 2: pruebas unitarias y de integración con cobertura > 80 %.
* Compuerta 4: aprobación explícita del despachador.
* De seguridad, solo lo que no cuesta implementar aparte: consultas parametrizadas, ningún secreto en el repositorio, respuestas de error sin trazas de pila.

### 3.3 Normas diferidas (evolución)
Redis, PostGIS, contenedor de ingesta separado, 1.000 eventos/s, mapa geográfico ≤ 2 s, SAST/SCA, RBAC/JWT/MFA, mTLS, HMAC, gestor de secretos y desvío de rutas (US-03).

---

## 4. Vuelta 2 — Seguridad de la Operación (diseño)

* **Alcance:**
  * RBAC en el backend y aislamiento multi-tenant.
  * JWT RS256 en cookies seguras, MFA para administradores y supervisores, bloqueo tras 5 intentos fallidos.
  * mTLS con certificado x509 por bus y firma HMAC del recaudo.
  * Docker Secrets o Vault.
  * Cabeceras de seguridad y logs JSON compatibles con OpenTelemetry, sin PII.
  * Modelado de amenazas STRIDE.
  * Antifraude: saltos de GPS > 120 km/h, validaciones duplicadas e incoherencia entre sensores.
* **Normas que adopta:** la sección de seguridad (OWASP Top 10 — 2025) completa, la Compuerta 1 completa (SAST: Bandit) y la parte SCA de la Compuerta 2 (`pip-audit`, Trivy).

## 5. Vuelta 3 — Tiempo Real y Aislamiento (diseño)

* **Alcance:**
  * `ingestion-service` en su propio contenedor, con `docker-compose` de 3 servicios.
  * Redis Pub/Sub (o un broker con API Kafka).
  * PostGIS y TimescaleDB.
  * Mapa interactivo con refresco ≤ 2 s.
  * Las 5 fallas del dato: duplicados, fuera de orden, posición imposible, fuente caída y ráfagas.
  * Buffer persistente y modo de contingencia local.
* **Normas que adopta:** RNF-3.1.2 (1.000 eventos/s, P99 ≤ 500 ms), RNF-3.2.2, RNF-3.2.3, RF-1.1, RF-1.3 y la Compuerta 3 (DataOps: rechazo < 0,1 %, ingesta ≤ 200 ms).

## 6. Vuelta 4 — Carril Adaptativo (diseño)

* **Alcance:**
  * US-03 completa: detección de bloqueos, recálculo de ruta ≤ 5 s, recomendación de desvío y auditoría de desvíos.
  * Los dos sentidos del corredor, con recorte de vuelta.
  * Simulación de eventos discretos.
  * Modelos completos de tiempo de recorrido y demanda, detección de anomalías y registro de experimentos.
  * Afluencia del Metro (RF-1.4).
  * Priorización por P(abordar ≤ t) (RF-2.4).
* **Normas que adopta:** RF-3.1 a RF-3.4, RF-1.4, RF-2.4 y la Compuerta 4 completa (auditoría de desvíos y prueba de fallback).

---

## 7. Mantenimiento del Mapa
* El mapa se actualiza en la Etapa 1 — Planear de cada vuelta, con un PR revisado por el equipo.
* Mover una norma a una vuelta **posterior** a la que ya estaba asignada requiere justificación escrita en el PR.
* Al cerrar cada vuelta (Etapa 5), la revisión de cumplimiento comprueba los 5 Principios Core y las normas adoptadas **hasta esa vuelta**.
