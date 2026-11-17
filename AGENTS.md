# AGENTS.md — RITMO / PulsoFlota

> Contexto compartido para **TODOS** los agentes. Conciso y estable; se carga siempre.
> La guía situacional vive en `.kiro/steering/` (se carga según contexto);
> el gobierno supremo es `.specify/memory/constitution.md`.

## Propósito

**PulsoFlota** es la central web supervisora en tiempo real para despachadores de
buses y controladores de tráfico de Medellín. Habilita decisiones de regulación
oportunas y confiables a partir de telemetría integrada, algoritmos de
regularidad y alertas viales predictivas. Combate dos problemas estructurales:
la ceguera operativa por datos tardíos o no estandarizados, y los incentivos
distorsionados ("guerra del centavo" y *bus bunching*) que degradan la
regularidad del servicio. **RITMO** (Riesgo, Incrementos y Trazabilidad para la
Movilidad Operativa) es la metodología de espiral que gobierna el desarrollo.

## Métrica eje

La calidad de servicio se mide como la probabilidad de abordar en *t* minutos o
menos, **P(abordar ≤ t)**, complementada por el **EWT** (*Excess Wait Time*),
leídas en percentiles P85 / P95 desde la perspectiva real del usuario (incluida
la ocupación de buses). Esta métrica alimenta el pago por calidad a los
operadores, de modo que su integridad es crítica (antifraude de recaudo).

## Stack tecnológico (restricciones duras)

- **Lenguaje:** Python 3.12+.
- **API:** FastAPI o Flask.
- **Central del despachador:** Streamlit / Dash o HTML5/Jinja2 + WebSockets.
- **Persistencia:** PostgreSQL + PostGIS (SQLite para dev/test empaquetados).
- **Tiempo real / caché:** Redis (Pub/Sub para telemetría en vivo + estado en
  memoria).
- **Contenedores:** Docker + `docker-compose`, mínimo 3 servicios:
  `ingestion-service`, `pulsoflota-web`, `database-redis`.
- **Validación de datos:** Pydantic V2 / JSON Schema en la compuerta de ingesta.

No hay código de aplicación todavía; el layout de fuentes seguirá la
descomposición de servicios anterior. Las herramientas de build (Node / Python)
ya están preparadas en `.gitignore`.

## Layout del repositorio

| Ruta | Qué es |
|------|--------|
| `docs/` | Documentación fuente de verdad (OMD, PRD, SRD — en español). |
| `docs/vueltas-ritmo.md` | **Mapa de vueltas:** qué normas son exigibles en la vuelta activa y cuáles quedan diferidas. |
| `specs/` | Artefactos generados por característica (spec, plan, tasks, checklists). |
| `.specify/memory/constitution.md` | **Constitución — documento de gobierno supremo.** |
| `.kiro/steering/` | Guía situacional (se carga según contexto, no siempre). |
| `.kiro/agents/` | Agentes de Kiro (uno por fase del flujo Spec Kit). |
| `.kiro/prompts/speckit.*.md` | Prompts de Spec Kit que siguen los agentes. |
| `.specify/scripts/`, `.specify/templates/` | Maquinaria Spec Kit (bash + plantillas). |
| `.specify/feature.json`, `.specify/integrations/` | Estado local por checkout (git-ignored). |

## Convenciones universales

- **Flujo RITMO (espiral):** cada vuelta recorre Planear → Especificar →
  Construir → Verificar → Revisar. Una historia a la vez, en rama aislada
  `feature/US-XX`.
- **Contract-First:** todo intercambio de datos entre módulos define y valida un
  contrato (Pydantic V2 / OpenAPI) **antes** de escribir la implementación.
- **Ingesta aislada y tiempo real determinista:** la ingesta corre en un
  contenedor aislado de la web; el camino crítico (≤ 10 s de extremo a extremo)
  nunca depende de llamadas síncronas a IA generativa ni a terceros.
- **Human-in-the-Loop:** toda recomendación de IA / regla / optimización es solo
  una sugerencia; ninguna acción de regulación en vía se ejecuta sin aprobación
  explícita del despachador humano.
- **Pruebas y compuertas:** cobertura > 80 % obligatoria; cada PR supera SAST,
  SCA y DataOps antes de fusionarse; el CI marca el build como fallado ante
  cualquier violación de principios.
- **Seguridad:** RBAC solo en el backend (nunca solo en el frontend), sin IDOR,
  aislamiento multi-tenant, secretos vía gestor externo (nunca en código ni
  `.env`). Detalle en `.kiro/steering/security.md`.
- **Commits:** los agentes no hacen commit/push (bloqueado en permisos); revisa
  y confirma tú. *Los documentos fuente no fijan convención de mensajes; se
  infiere **Conventional Commits** (`tipo(alcance): descripción`, p. ej.
  `feat(ingestion): valida esquema GPS con Pydantic V2`). Si el equipo adopta
  otra, documéntala aquí y actualiza la constitución.*

## Documento de gobierno

La **constitución** (`.specify/memory/constitution.md`, v1.1.0) es el documento
de gobierno supremo: sus 5 principios core son NON-NEGOTIABLE y prevalecen sobre
cualquier otra práctica. Para detalle situacional, carga el steering file
correspondiente (`.kiro/steering/*.md`).
