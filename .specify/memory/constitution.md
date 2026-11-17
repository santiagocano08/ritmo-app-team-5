<!--
Sync Impact Report (borrador temporal — eliminar antes de commit)
====================================================================
- Enmienda propuesta 1.0.0 → 1.1.0 (MINOR), 2026-11-17, PR `constitutional-amendment`:
  añade "Adopción por Fases" en Governance y una nota al inicio de "Restricciones
  Técnicas y de Seguridad". Los Principios Core no cambian. Nuevo documento
  referenciado: docs/vueltas-ritmo.md (mapa de vueltas). Motivo: la v1.0.0 exige
  el sistema objetivo completo desde la vuelta 1, y eso es incompatible con una
  espiral guiada por riesgo y con el alcance de la vuelta 1 (taller 2026-11-24).
  Plantillas: sin cambios requeridos. Agentes: create-plan, validate-plan y
  review-code deberían cargar docs/vueltas-ritmo.md en sus resources.
- Cambio de versión inicial: (sin versión previa ratificada) → 1.0.0
  El archivo .specify/memory/constitution.md preexistente era un andamiaje de
  plantilla sin resolver (todos los marcadores [...] intactos, sin versión
  concreta); no existía una constitución ratificada previa. Se adopta la
  versión inicial 1.0.0, alineada con la versión 1.0.0 declarada en los
  documentos fuente (OMD/PRD/SRD).
- Principios modificados: N/A (ratificación inicial). Los 5 principios core
  NON-NEGOTIABLE se incorporan a partir del OMD.
- Secciones añadidas:
  * Core Principles (5 principios NON-NEGOTIABLE)
  * Restricciones Técnicas y de Seguridad (stack, tiempo real firme, OWASP Top 10 2025)
  * Flujo de Desarrollo RITMO y Compuertas de Calidad (5 etapas, 2 carriles, 4 compuertas)
  * Governance (enmiendas, SemVer, cumplimiento)
- Secciones eliminadas: N/A
- TODOs diferidos: ninguno. Ratificación = 2026-11-17 (fecha provista por el
  operador); Last Amended = 2026-11-17 (acto de ratificación inicial).
-->

# RITMO / PulsoFlota Constitution

## Core Principles

### I. Orden Guiado por Riesgo (Risk-First Order) — NON-NEGOTIABLE

- El backlog de desarrollo y la secuencia de vueltas de la espiral RITMO DEBEN
  ordenarse estrictamente por el nivel de riesgo técnico y arquitectónico (ASRs),
  no por prioridad comercial estática.
- NINGUNA nueva funcionalidad del carril adaptativo DEBE iniciarse si existe un
  riesgo de Nivel 1 (seguridad o integridad del dato) no mitigado en la vuelta
  activa.
- **Justificación:** en sistemas de tiempo real firme con control supervisorio,
  ignorar los riesgos de concurrencia o corrupción de datos al inicio conduce al
  colapso de la operación durante picos de demanda.

### II. El Dato Tiene Dueño y Contrato Primero (Contract-First & Data Ownership) — NON-NEGOTIABLE

- Todo intercambio de datos entre módulos o servicios DEBE definir y validar un
  contrato explícito de mensaje (Pydantic V2 / OpenAPI) antes de escribir el
  código de implementación.
- NINGÚN modelo de datos DEBE ser persistido o procesado en el pipeline si carece
  de un propietario de módulo asignado y de un esquema validado en frontera.
- **Justificación:** elimina el acoplamiento implícito y previene que datos
  malformados o no estandarizados procedentes de múltiples operadores
  contaminen los indicadores del cálculo de pago por calidad.

### III. Ingesta Aislada y Tiempo Real Determinista — NON-NEGOTIABLE

- El pipeline de ingesta de telemetría e infraestructura vial DEBE ejecutarse en
  un contenedor de proceso aislado de la interfaz web.
- El camino crítico de ejecución de tiempo real (≤ 10 s de extremo a extremo)
  DEBE ser determinista y NUNCA DEBE depender de llamadas síncronas a agentes de
  IA Generativa o servicios externos de terceros.
- **Justificación:** garantiza la supervivencia de la ingesta y la observabilidad
  de flota en la central incluso si el frontend supervisorio o los servicios
  auxiliares sufren degradación o caídas.

### IV. Compuerta Humana Inquebrantable (Human-in-the-Loop Supervision) — NON-NEGOTIABLE

- Todo agente de IA, algoritmo de optimización o regla automática DEBE operar
  exclusivamente en modo sugerido.
- NINGUNA acción de regulación en vía (modificación de frecuencias, envío de
  mensajes a conductores o redireccionamientos de ruta) DEBE ejecutarse de forma
  autónoma sin la autorización explícita de un despachador humano mediante la
  interfaz web.
- **Justificación:** la responsabilidad operativa y contractual frente a la
  ciudad y los usuarios recae en la central supervisora; la tecnología asiste la
  decisión, pero el humano mantiene el control supervisorio.

### V. Pruebas Obligatorias y Compuertas Automatizadas (Test-First & Automated Gates) — NON-NEGOTIABLE

- Todo Pull Request DEBE incluir pruebas unitarias y de integración que
  garanticen una cobertura superior al 80 %, además de superar automáticamente
  las compuertas de contrato (DataOps) y de integración continua (CI) antes de
  su fusión en la rama principal.
- NINGÚN desarrollador o agente DEBE omitir el paso por las compuertas.
- **Justificación:** previene regresiones en los cálculos de la métrica
  P(abordar ≤ t) y asegura la estabilidad del monolito modular en producción.

## Restricciones Técnicas y de Seguridad

> Estas normas describen el **sistema objetivo**. La sección
> **Adopción por Fases** (en Governance) y `docs/vueltas-ritmo.md` fijan en qué
> vuelta es exigible cada una. Los 5 Principios Core aplican siempre.

**Stack tecnológico obligatorio.**

- Lenguaje: Python 3.12+.
- API: FastAPI o Flask.
- Central del despachador: Streamlit / Dash o HTML5/Jinja2 con WebSockets.
- Persistencia: PostgreSQL con extensión PostGIS (o SQLite para entornos de
  desarrollo/testing empaquetados).
- Tiempo real y caché: Redis (Pub/Sub para eventos de telemetría en vivo y
  gestión de estado en memoria).
- Contenerización: Docker Engine y `docker-compose` con un mínimo de tres
  servicios: `ingestion-service`, `pulsoflota-web` y `database-redis`.

**Rendimiento y tiempo real firme.**

- El sistema se clasifica de tiempo real firme: una recomendación tardía no
  genera fallos catastróficos físicos, pero carece de valor operativo.
- El pipeline de ingesta DEBE procesar hasta 1 000 eventos/segundo con una
  latencia pico P99 ≤ 500 ms.
- El tiempo total desde la detección de una anomalía en vía hasta la
  presentación de la recomendación en la consola del despachador DEBE ser
  ≤ 10 s.
- El recálculo automático de ruta ante un bloqueo vial DEBE ocurrir en ≤ 5 s.
- El mapa interactivo DEBE refrescar la posición de la flota con latencia
  ≤ 2 s.

**Seguridad (alineada con OWASP Top 10 — 2025).** El detalle operativo de cada
criterio de aceptación vive en `.kiro/steering/security.md`; lo siguiente es la
norma de gobierno.

- **Control de acceso:** todo endpoint REST/WebSocket DEBE autenticar al emisor
  y verificar permisos por RBAC en el middleware del backend. Quedan prohibidas
  las referencias directas a objetos inseguras (IDOR): un acceso a recurso ajeno
  DEBE devolver `403 Forbidden` y registrar alerta. Las autorizaciones DEBEN
  evaluarse exclusivamente en el backend; el frontend NO DEBE ser el único
  mecanismo de control. La telemetría de consorcios privados DEBE estar aislada
  lógicamente (multi-tenant).
- **Infraestructura:** los contenedores DEBEN ejecutarse como usuario no root
  (UID 10001). El servidor DEBE emitir las cabeceras de seguridad obligatorias
  (`Content-Security-Policy`, `Strict-Transport-Security`,
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`) y remover las que
  revelan la pila tecnológica. `DEBUG=False` DEBE estar forzado en homologación y
  producción; Swagger/ReDoc NO DEBE exponerse en producción sin autenticación.
- **Cadena de suministro:** el CI/CD DEBE ejecutar análisis de composición de
  software (SCA) en cada PR, bloquear la fusión ante vulnerabilidades de
  severidad Alta o Crítica (CVSS ≥ 7.0) y fijar dependencias con versión exacta
  y hash SHA-256.
- **Criptografía y secretos:** las comunicaciones externas DEBEN usar TLS 1.3
  (mínimo TLS 1.2 con *ciphersuites* PFS); la flota IoT DEBE autenticarse con
  mTLS y certificados x509 por unidad. Las contraseñas DEBEN procesarse con
  Argon2id (o bcrypt con coste ≥ 12). Los secretos DEBEN provenir de un gestor
  externo (Docker Secrets o HashiCorp Vault); NUNCA DEBEN incluirse en código
  fuente ni en archivos `.env` del repositorio.
- **Inyección y validación:** las consultas DEBEN parametrizarse (ORM / SQLAlchemy
  / asyncpg / Pydantic V2). Todo evento de ingesta DEBE validarse contra un
  esquema estricto Pydantic V2; los paquetes inválidos DEBEN rechazarse en el
  acto con código `422 Unprocessable Entity`.
- **Aislamiento de IA generativa:** la ruta de tiempo real determinista DEBE
  aislar completamente los modelos de IA predictivos; ningún modelo o agente
  autónomo DEBE tener escritura directa sobre la base de datos de producción ni
  las APIs de despacho de las unidades a bordo. Toda nueva funcionalidad del
  carril disciplinado DEBE contar con un modelado de amenazas STRIDE documentado
  y priorizado por riesgo.
- **Autenticación y sesiones:** los JWT DEBEN firmarse con `RS256`, expirar en
  ≤ 15 min y transmitirse únicamente en cookies `HttpOnly`, `Secure` y
  `SameSite=Strict`. Administradores y supervisores de cuenca DEBEN usar MFA
  (TOTP). El sistema DEBE bloquear 15 minutos cualquier cuenta o IP con 5
  intentos fallidos consecutivos.
- **Integridad y antifraude de recaudo:** el pipeline de ingesta DEBE registrar
  procedencia, marca de tiempo inmutable y checksum por mensaje, y DEBE detectar
  y descartar datos manipulados (saltos GPS > 120 km/h, validaciones duplicadas,
  inconsistencia entre sensores viales y coordenadas del bus). Los paquetes de
  recaudo DEBEN incluir una firma HMAC basada en el secreto del módulo seguro
  del validador vehicular.
- **Observabilidad SRE:** los logs DEBEN emitirse en JSON estructurado compatible
  con OpenTelemetry y registrar, con marca UTC e identificador de usuario, los
  intentos de autenticación, los cambios de permisos, los desvíos autorizados o
  rechazados y las alteraciones en las fuentes de ingesta. Los logs NUNCA DEBEN
  incluir contraseñas, claves privadas, tokens JWT completos ni PII de
  conductores o pasajeros. Una tasa de rechazo de mensajes IoT > 5 % en 1 min
  DEBE disparar alertas al equipo SRE/DevSecOps.
- **Excepciones y resiliencia:** ninguna respuesta HTTP/WebSocket DEBE exponer
  trazas de pila, rutas de archivos locales ni estructuras internas de
  PostgreSQL; ante un error 500 se DEBE devolver un mensaje genérico con un
  `correlation_id` registrado internamente en los logs. Si la central o la web
  colapsan, la ingesta IoT aislada DEBE seguir registrando eventos en el buffer
  persistente y la consola del despachador DEBE conmutar a un modo de
  contingencia local basado en planes de despacho estáticos prefijados.

## Flujo de Desarrollo RITMO y Compuertas de Calidad

**Ciclo de vida RITMO — 5 etapas por vuelta de espiral.** Todas las vueltas
recorren secuencialmente:

1. **Planear** — selección del riesgo prioritario a mitigar, fecha de cierre de
   la vuelta e hipótesis operativas (responsable: Dueño de Vuelta).
2. **Especificar** — redacción de la historia de usuario como especificación SDD
   (*Specification-Driven Development*) medible y compuerta de contrato si
   existen cambios en esquemas.
3. **Construir** — desarrollo de una historia a la vez en rama aislada
   `feature/US-XX`, incluyendo código de producción, pruebas y reglas del dato.
4. **Verificar** — ejecución del pipeline de CI (linting, pruebas unitarias,
   cobertura > 80 %), pruebas de contrato DataOps e inspección del revisor
   humano.
5. **Revisar (Compuerta de Valor)** — validación de la hipótesis de valor midiendo
   el impacto en P(abordar ≤ t) con el despachador en el entorno de
   pruebas/simulación.

**Dos carriles operativos de desarrollo.**

- **Carril Disciplinado** (Ingesta, Contratos de Mensaje, Pago por Calidad):
  especificación estricta Contract-First / SDD; autonomía de agentes baja (solo
  propuestas validadas en código y compuertas); criticidad máxima; CI estricto y
  pruebas de contrato DataOps.
- **Carril Adaptativo** (Central Web, Visualización, Reglas de Alerta y Desvío):
  iteraciones guiadas por hipótesis de valor validadas con el despachador;
  autonomía de agentes media (desarrollo automatizado en ramas aisladas con
  revisión obligatoria del dueño del módulo).

**Compuertas de calidad (automatizadas y humanas).** Ningún incremento puede ser
promovido de etapa ni desplegado en producción sin superar:

- **Compuerta 1 — Contrato y Análisis Estático** (cada PR): SAST (`Bandit`,
  `ESLint`) y validación de esquemas Pydantic. Aprobación: 0 hallazgos
  Críticos/Altos en SAST y esquema de contrato validado.
- **Compuerta 2 — Integración y Supply Chain** (CI): escaneo SCA (`pip-audit`,
  `Trivy`) y suites de pruebas unitarias/integración. Aprobación: cobertura
  > 80 % y 0 vulnerabilidades conocidas en dependencias.
- **Compuerta 3 — Compuerta del Dato (DataOps)** (en tiempo de ejecución de
  ingesta): pruebas de contrato de mensaje, validación HMAC y detección de
  anomalías. Aprobación: tasa de rechazo de paquetes < 0,1 % y latencia de
  ingesta ≤ 200 ms.
- **Compuerta 4 — Valor y Seguridad Operativa** (cierre de vuelta): validación
  Human-in-the-Loop, auditoría de desvíos y prueba de fallback. Aprobación:
  aprobación explícita del despachador y verificación de no interferencia de la
  IA en el camino de tiempo real.

## Governance

- Esta constitución es el documento de gobierno supremo del proyecto
  RITMO / PulsoFlota; prevalece sobre cualquier otra práctica cuando haya
  conflicto.
- **Enmiendas:** cualquier modificación a los principios core o a este documento
  DEBE proponerse mediante un Pull Request etiquetado `constitutional-amendment`,
  con justificación basada en evidencia de campo o nuevas restricciones del
  dominio de transporte en Medellín. Los cambios a requisitos normativos
  (normas DEBE / DEBERÍA) requieren además un documento de decisión de
  arquitectura (ADR), validación en la compuerta de riesgo del espiral y firma
  unánime del Dueño de Vuelta, el Arquitecto (de Software / de Seguridad) y el
  Representante del Despachador.
- **Versionado (SemVer):** MAJOR (X.0.0) para cambios en los principios core
  NON-NEGOTIABLE o reestructuración de la arquitectura de contenedores/carriles;
  MINOR (1.X.0) para nuevos objetos del modelo de dominio, nuevas historias de
  usuario en la matriz o modificaciones compatibles del stack; PATCH (1.0.X)
  para correcciones de redacción, aclaraciones de reglas o ajustes de métricas
  secundarias.
- **Cumplimiento:** al final de cada vuelta del espiral, el equipo DEBE realizar
  una revisión de cumplimiento de los principios core. Una violación detectada
  (p. ej. código sin pruebas fusionado a la rama principal, o recomendaciones
  emitidas sin compuerta humana) DEBE marcar el build de CI como fallado de
  inmediato.
- **Adopción por Fases:**
  - Los **5 Principios Core NON-NEGOTIABLE** son exigibles desde la primera
    vuelta y en todas las vueltas.
  - Las normas de las secciones *Restricciones Técnicas y de Seguridad* y
    *Compuertas de calidad* se adoptan **de forma incremental, vuelta por
    vuelta**. El orden lo fija el Principio 1: primero los riesgos de Nivel 1.
  - El **mapa de vueltas** (`docs/vueltas-ritmo.md`) es la única fuente que
    declara, para cada vuelta, qué normas son exigibles y cuáles quedan
    diferidas como evolución. Se actualiza en la Etapa 1 — Planear de cada
    vuelta mediante un PR revisado por el equipo. Esa actualización **NO**
    requiere enmienda constitucional, siempre que no contradiga esta
    constitución.
  - Una norma adoptada en una vuelta sigue siendo exigible en todas las vueltas
    posteriores. Una norma diferida **NO DEBE** tratarse como hallazgo
    bloqueante en la vuelta activa; los agentes DEBERÍAN registrarla como
    evolución.
  - La revisión de cumplimiento al cierre de cada vuelta verifica los
    Principios Core y las normas adoptadas **hasta esa vuelta** según el mapa.
- **Guía operativa:** la constitución gobierna; `AGENTS.md` y los archivos
  `.kiro/steering/*.md` la operacionalizan por contexto. Para el detalle de
  seguridad, ver `.kiro/steering/security.md`.

**Version**: 1.1.0 | **Ratified**: 2026-11-17 | **Last Amended**: 2026-11-17
