# OMD — Object Model, Architecture Definition & Engineering Constitution: RITMO / PulsoFlota

## Control de Constitución y Arquitectura
* **PROJECT_NAME**: RITMO (Riesgo, Incrementos y Trazabilidad para la Movilidad Operativa)
* **CONSTITUTION_VERSION**: 1.0.0
* **RATIFICATION_DATE**: 2026-11-06
* **LAST_AMENDED_DATE**: 2026-11-14
* **APLICACIÓN OBJETIVO**: Central Web de Despacho Supervisorio y Movilidad Operativa (PulsoFlota)

---

## 1. Principios Core de Ingeniería (Core Principles)

### Principio 1: Orden Guiado por Riesgo (Risk-First Order) — [NON-NEGOTIABLE]
* **Regla**: El backlog de desarrollo y la secuencia de vueltas en la espiral **DEBEN** ser ordenados estrictamente por el nivel de riesgo técnico y arquitectónico (ASRs), y no por prioridad comercial estática. Ninguna nueva funcionalidad del carril adaptativo **DEBE** iniciarse si existe un riesgo de nivel 1 (seguridad o integridad del dato) no mitigado en la vuelta activa.
* **Justificación**: En sistemas de tiempo real firme con control supervisorio, ignorar los riesgos de concurrencia o corrupción de datos al inicio conduce al colapso catastrófico de la operación durante picos de demanda.

### Principio 2: El Dato Tiene Dueño y Contrato Primero (Contract-First & Data Ownership) — [NON-NEGOTIABLE]
* **Regla**: Todo intercambio de datos entre módulos o servicios **DEBE** definir y validar un contrato explícito de mensaje (Pydantic / OpenAPI) antes de escribir código de implementación. Ningún modelo de datos **DEBE** ser persistido o procesado en el pipeline si carece de un propietario de módulo asignado y un esquema validado en frontera.
* **Justificación**: Elimina el acoplamiento implícito y previene que datos malformados o no estandarizados procedentes de múltiples operadores contaminen los indicadores del cálculo de pago por calidad.

### Principio 3: Ingesta Aislada y Tiempo Real Determinista — [NON-NEGOTIABLE]
* **Regla**: El pipeline de ingesta de telemetría e infraestructura vial **DEBE** ejecutarse en un contenedor de proceso aislado de la interfaz web. El camino crítico de ejecución de tiempo real ($\le 10\text{ s}$) **DEBE** ser determinista y **NUNCA DEBE** depender de llamadas síncronas a agentes de IA Generativa o servicios externos de terceros.
* **Justificación**: Garantiza la supervivencia de la ingesta y la observabilidad de flota en la central incluso si el frontend supervisorio o los servicios auxiliares sufren degradación o caídas.

### Principio 4: Compuerta Humana Inquebrantable (Human-in-the-Loop Supervision) — [NON-NEGOTIABLE]
* **Regla**: Todo agente de IA, algoritmo de optimización o regla automática **DEBE** operar exclusivamente en modo sugerido. Ninguna acción de regulación en vía (modificación de frecuencias, envío de mensajes a conductores o redireccionamientos de ruta) **DEBE** ejecutarse de forma autónoma sin la autorización explícita de un despachador humano mediante la interfaz web.
* **Justificación**: La responsabilidad operativa y contractual frente a la ciudad y los usuarios recae en la central supervisora; la tecnología asiste la decisión, pero el humano mantiene el control supervisorio.

### Principio 5: Pruebas Obligatorias y Compuertas Automatizadas (Test-First & Automated Gates) — [NON-NEGOTIABLE]
* **Regla**: Todo Pull Request (PR) **DEBE** incluir pruebas unitarias y de integración que garanticen una cobertura superior al $80\%$, además de superar automáticamente las compuertas de contrato (DataOps) y de integración continua (CI) antes de su fusión en la rama principal. Ningún desarrollador o agente **DEBE** omitir el paso por compuertas.
* **Justificación**: Previene regresiones en los cálculos de la métrica $P(\text{abordar} \le t)$ y asegura la estabilidad del monolito modular en producción.

---

## 2. Definición de Arquitectura, Modelo de Objetos y Stack Tecnológico

### 2.1 Stack Tecnológico y Contenedores

El sistema separa **frontend** y **backend** en servicios y carpetas independientes
dentro de `src/`. El backend concentra toda la lógica de negocio, la ingesta y la
evaluación de autorización (Principio IV y A01); el frontend es un cliente web que
consume la API REST/WebSocket y nunca decide control de acceso por sí mismo.

* **Lenguaje de Programación (backend)**: Python 3.12+
* **Framework Web & API (backend)**: FastAPI con Pydantic V2 para servicios API REST y
  WebSocket. El acceso a base de datos usa psycopg 3 con SQL parametrizado únicamente (sin
  ORM, sin SQLAlchemy, sin Alembic).
* **Frontend (central del despachador)**: React 19 + TypeScript + Vite + Tailwind CSS,
  compilado a estáticos y servido tras el proxy inverso (Nginx/Traefik). Consume la API
  del backend por REST/WebSocket.
* **Base de Datos Persistente**: PostgreSQL (con extensión PostGIS para datos geoespaciales)
  o SQLite para entornos de desarrollo/testing empaquetados.
* **Capa de Tiempo Real & Caching**: Redis (Pub/Sub para eventos de telemetría en vivo y
  gestión de estado en memoria).
* **Contenerización**: Docker Engine y `docker-compose`. Estructura de repositorio:

  ```
  src/
  ├── backend/          # FastAPI + Pydantic V2, psycopg 3 / SQL parametrizado (API, ingesta, métricas)
  ├── frontend/         # Vite + React 19 + TypeScript + Tailwind CSS
  └── docker-compose.yml
  ```

  Servicios mínimos definidos en `docker-compose`:
  1. `ingestion-service`: Contenedor de ingesta síncrona de telemetría IoT y fuentes de
     tráfico mockeadas (Python). Aislado del resto (Principio III).
  2. `pulsoflota-backend`: API FastAPI, cálculo de métricas y lógica supervisoria.
  3. `pulsoflota-frontend`: Build estático de React servido por Nginx (en desarrollo, el dev
     server de Vite con proxy hacia el backend).
  4. `database-redis`: Infraestructura de persistencia (PostgreSQL) y caché/pub-sub (Redis).

### 2.2 Modelo de Objetos de Dominio (Domain Object Model)

```
+-------------------------------------------------------------------+
|                            Vehiculo                               |
+-------------------------------------------------------------------+
| - id_vehiculo: str (UUID)                                         |
| - placa: str                                                      |
| - id_operador: str                                                |
| - capacidad_pasajeros: int                                        |
| - estado_operativo: Enum (EN_RUTA, EN_ESTACION, EN_DESVIO, FUERA) |
+-------------------------------------------------------------------+
                                 | 1
                                 | 1..*
+-------------------------------------------------------------------+
|                        EventoTelemetria                           |
+-------------------------------------------------------------------+
| - timestamp: datetime (UTC)                                       |
| - latitud: float                                                  |
| - longitud: float                                                 |
| - velocidad_kmh: float                                            |
| - nivel_ocupacion: float (0.0 - 1.0)                              |
+-------------------------------------------------------------------+

+-------------------------------------------------------------------+
|                           RutaEstandar                            |
+-------------------------------------------------------------------+
| - id_ruta: str                                                    |
| - nombre_corredor: str                                            |
| - estaciones_ordenadas: List[Estacion]                            |
| - headway_objetivo_segundos: int                                  |
+-------------------------------------------------------------------+
                                 | 1
                                 | 1..*
+-------------------------------------------------------------------+
|                            TramoVial                              |
+-------------------------------------------------------------------+
| - id_tramo: str                                                   |
| - coordenada_inicio: GeoPoint                                     |
| - coordenada_fin: GeoPoint                                        |
| - nivel_congestion: Enum (VERDE, AMARILLO, ROJO)                  |
| - velocidad_promedio_actual: float                               |
+-------------------------------------------------------------------+

+-------------------------------------------------------------------+
|                         MetricaServicio                           |
+-------------------------------------------------------------------+
| - ventana_tiempo: TimeWindow                                      |
| - id_estacion: str                                                |
| - p_abordar_t: float (Probabilidad <= t min)                      |
| - ewt_segundos: float (Excess Wait Time)                          |
| - percentil_evaluado: int (85, 95)                                |
+-------------------------------------------------------------------+

+-------------------------------------------------------------------+
|                       PropuestaRegulacion                         |
+-------------------------------------------------------------------+
| - id_propuesta: str                                               |
| - tipo_accion: Enum (DESPACHO_ANTICIPADO, RETENCION, DESVIO_RUTA) |
| - vehiculo_objetivo: Vehiculo                                     |
| - ruta_sugerida: List[TramoVial]                                  |
| - tiempo_respuesta_calculado: float                               |
| - estado_aprobacion: Enum (PENDIENTE, APROBADA, RECHAZADA)        |
| - autorisado_por: Optional[UsuarioDespachador]                    |
+-------------------------------------------------------------------+
```

### 2.3 Dos Carriles Operativos de Desarrollo
1. **Carril Disciplinado (Ingesta, Contratos de Mensaje, Pago por Calidad)**:
   - *Rigor*: Especificación estricta en primera instancia (Contract-First / SDD).
   - *Autonomía de Agentes*: Baja (el agente solo genera propuestas que deben ser validadas en código y compuertas).
   - *Criticidad*: Máxima. Se aplica integración continua estricta y pruebas de contrato DataOps.
2. **Carril Adaptativo (Frontend React, Visualización, Reglas de Alerta y Desvío)**:
   - *Rigor*: Iteraciones guiadas por hipótesis de valor validadas con el despachador.
   - *Autonomía de Agentes*: Media (desarrollo automatizado en ramas aisladas con revisión obligatoria por el dueño del módulo).
   - *Alcance*: El frontend React 19 + TypeScript + Vite + Tailwind vive en `src/frontend/`
     y es el cliente de la central del despachador; consume la API del backend y no toma
     decisiones de autorización (A01).

---

## 3. Flujo de Desarrollo, Proceso de Revisión y Compuertas de Calidad

### 3.1 Ciclo de Vida RITMO (Las 5 Etapas por Vuelta de Espiral)
Todas las vueltas de la espiral recorren secuencialmente cinco etapas estructuradas:
1. **Etapa 1 — Planear**: Selección del riesgo prioritario a mitigar, fecha de cierre de la vuelta e hipótesis operativas. (Responsable: Dueño de Vuelta).
2. **Etapa 2 — Especificar**: Redacción de la historia de usuario como especificación SDD (*Specification-Driven Development*) medible y compuerta de contrato si existen cambios en esquemas.
3. **Etapa 3 — Construir**: Desarrollo de una historia a la vez en rama aislada (`feature/US-XX`), incluyendo código de producción, pruebas y reglas del dato.
4. **Etapa 4 — Verificar**: Ejecución del pipeline de CI (linting, tests unitarios, cobertura $>80\%$), pruebas de contrato DataOps e inspección del revisor humano.
5. **Etapa 5 — Revisar (Compuerta de Valor)**: Validación final de la hipótesis de valor midiendo impacto en $P(\text{abordar} \le t)$ con el despachador en el entorno de pruebas/simulación.

### 3.2 Las Tres Compuertas de Calidad Automatizadas y Humanas
* **Compuerta 1: Compuerta de Contrato (DataOps)**: Verifica que no existan rupturas en los esquemas JSON/Pydantic y que los simuladores de datos sigan la especificación del contrato.
* **Compuerta 2: Compuerta del Dato y CI (DevOps/SRE)**: Valida que la latencia de ingesta sea $\le 500$ ms, sin huecos temporales y con cobertura de pruebas aprobada.
* **Compuerta 3: Compuerta de Valor y Humana (Despachador)**: Cierre formal de cada vuelta del espiral mediante la aprobación del despachador y el gestor del sistema.

### 3.3 Prácticas DevOps y SRE

Las compuertas de calidad definen *qué* se exige; esta sección define *cómo* se
operan a través del ciclo de vida. Su adopción es incremental por vuelta según
`docs/turns-ritmo.md`.

* **Pipeline CI/CD (GitHub Actions)**: El repositorio usa GitHub Actions
  (`.github/workflows/`). Hay dos pipelines por la separación frontend/backend:
  - `backend-ci`: lint (`ruff`), tipos (`mypy`), SAST (`Bandit`), pruebas y cobertura
    (`pytest` > 80 %), SCA (`pip-audit`), build de imagen y escaneo de imagen (`Trivy`).
  - `frontend-ci`: lint (`ESLint`), tipos (`tsc --noEmit`), pruebas (`Vitest`), build de
    Vite y SCA de dependencias JS (`npm audit` / `Trivy`).
  Ambos pipelines se disparan en cada *Pull Request* y bloquean la fusión si falla
  cualquier compuerta (Principio V). El `docker-compose` se valida en CI.
* **Entornos y despliegue**: Tres entornos lógicos — `development` (local con
  `docker-compose`), `staging` (homologación) y `production`. `DEBUG=False` forzado en
  staging y producción. Releases por imágenes versionadas (tag inmutable + SHA); rollback
  por redeploy de la imagen anterior. Cambios de esquema de base de datos aplicados con
  scripts SQL idempotentes versionados (sin Alembic), de forma controlada y con respaldo previo.
* **SLIs y SLOs**: Indicadores derivados de los RNF — latencia de ingesta P99 ≤ 500 ms,
  latencia de refresco de mapa ≤ 2 s, latencia detección→recomendación ≤ 10 s, tasa de
  rechazo de paquetes < 0.1 % y disponibilidad de la ingesta aislada. Cada SLO tiene un
  presupuesto de error; su agotamiento congela despliegues de features hasta recuperar
  margen.
* **Observabilidad (tres señales)**:
  - **Logs**: JSON estructurado compatible con OpenTelemetry, sin PII (ver SRD A09).
  - **Métricas**: exportadas en formato Prometheus (contadores de eventos, latencias,
    tasa de rechazo, estado de buses), visualizadas en Grafana.
  - **Trazas**: trazado distribuido con OpenTelemetry por el camino ingesta → cálculo →
    recomendación, correlacionado con `correlation_id`.
* **Alertas e incidentes**: Alertas al equipo SRE/DevSecOps (PagerDuty/Slack) ante rechazo
  de mensajes IoT > 5 % en 1 min o agotamiento de presupuesto de error. Toda incidencia de
  severidad alta requiere *runbook* y postmortem sin culpa.
* **Healthchecks y resiliencia**: Cada servicio de `docker-compose` define `healthcheck`
  (liveness/readiness) y dependencias con `depends_on: condition: service_healthy`. La
  ingesta aislada sobrevive a la caída del frontend/backend (Principio III) y mantiene el
  buffer persistente (A10).
* **Respaldo y recuperación (DR)**: Respaldo periódico de PostgreSQL con objetivos
  explícitos de RPO y RTO; restauración probada. Bronze es inmutable; silver y gold se
  recalculan desde bronze, lo que acota el impacto de una pérdida.

---

## 4. Gobernanza y Enmiendas del Documento

### 4.1 Procedimiento de Enmienda
* Cualquier modificación a este documento OMD o a sus principios core **DEBE** ser propuesta mediante un Pull Request etiquetado como `constitutional-amendment`.
* El PR de enmienda **DEBE** incluir la justificación basada en evidencia de campo o nuevas restricciones del dominio de transporte en Medellín.
* Requiere la aprobación unánime de los integrantes del equipo (Dueño de Vuelta, Arquitecto de Software y Representante del Despachador).

### 4.2 Política de Versionado (SemVer)
* **MAJOR (X.0.0)**: Cambios en los Principios Core NON-NEGOTIABLE o reestructuración de la arquitectura de contenedores/carriles.
* **MINOR (1.X.0)**: Incorporación de nuevos objetos al modelo de dominio, nuevas historias de usuario en la matriz o modificaciones en el stack tecnológico compatible.
* **PATCH (1.0.X)**: Correcciones menores de texto, clarificación de reglas o ajustes en métricas secundarias.

### 4.3 Auditoría de Cumplimiento
* Al final de cada vuelta del espiral, el equipo **DEBE** realizar una revisión de cumplimiento de los 5 Principios Core.
* Si se detecta una violación a los principios (ej. código sin prueba fogueado en la rama principal o recomendaciones emitidas sin compuerta humana), el build en CI **DEBE** ser marcado como fallido inmediatamente.
