# AGENTS.md — RITMO / PulsoFlota

> Shared context for **ALL** agents. Concise and stable; always loaded.
> Situational guidance lives in `.kiro/steering/` (loaded by context);
> the supreme governing document is `.specify/memory/constitution.md`.

## Purpose

**PulsoFlota** is the real-time supervisory web console for bus dispatchers and
traffic controllers in Medellín. It enables timely, reliable regulation decisions
from integrated telemetry, regularity algorithms and predictive road alerts. It
tackles two structural problems: operational blindness caused by late or
non-standardized data, and distorted incentives (the "guerra del centavo" — the
penny war — and *bus bunching*) that degrade service regularity. **RITMO**
(Riesgo, Incrementos y Trazabilidad para la Movilidad Operativa — Risk,
Increments and Traceability for Operational Mobility) is the spiral methodology
that governs development.

## Key metric

Service quality is measured as the probability of boarding within *t* minutes or
less, **P(board ≤ t)**, complemented by **EWT** (*Excess Wait Time*), read at the
P85 / P95 percentiles from the rider's real perspective (including bus
occupancy). This metric feeds quality-based payment to operators, so its
integrity is critical (fare-collection anti-fraud).

## Technology stack (hard constraints of the target system)

- **Language:** Python 3.12+.
- **API:** FastAPI or Flask.
- **Dispatcher console:** Streamlit / Dash or HTML5/Jinja2 + WebSockets.
- **Persistence:** PostgreSQL + PostGIS (SQLite for packaged dev/test).
- **Real time / cache:** Redis (Pub/Sub for live telemetry + in-memory state).
- **Containers:** Docker + `docker-compose`, at least 3 services:
  `ingestion-service`, `pulsoflota-web`, `database-redis`.
- **Data validation:** Pydantic V2 / JSON Schema at the ingestion gate.

These are adopted **turn by turn**: check `docs/turns-ritmo.md` for what the
active turn requires and what is deferred.

There is no application code yet; the source layout will follow the service
breakdown above. Build tooling (Node / Python) is already covered in `.gitignore`.

## Repository layout

| Path | What it is |
|------|------------|
| `docs/` | Source-of-truth documentation (OMD, PRD, SRD — in Spanish). |
| `docs/turns-ritmo.md` | **Turn map:** which norms are mandatory in the active turn and which are deferred. |
| `specs/` | Generated per-feature artifacts (spec, plan, tasks, checklists). |
| `.specify/memory/constitution.md` | **Constitution — supreme governing document.** |
| `.kiro/steering/` | Situational guidance (loaded by context, not always). |
| `.kiro/agents/` | Kiro agents (one per Spec Kit workflow phase). |
| `.kiro/prompts/speckit.*.md` | Spec Kit command prompts the agents follow. |
| `.specify/scripts/`, `.specify/templates/` | Spec Kit machinery (bash + templates). |
| `.specify/feature.json`, `.specify/integrations/` | Per-checkout local state (git-ignored). |

## Universal conventions

- **Language:** the repository is written in **English** (agents, steering,
  constitution, specs, code, commits and PRs). The source documents in `docs/`
  (OMD, PRD, SRD) are still in Spanish; domain identifiers defined there (e.g.
  `id_vehiculo`, `p_abordar_t`) are kept as defined until the team decides
  otherwise.
- **RITMO workflow (spiral):** every turn goes Plan → Specify → Build → Verify →
  Review. One story at a time, on an isolated `feature/US-XX` branch.
- **Contract-First:** every data exchange between modules defines and validates a
  contract (Pydantic V2 / OpenAPI) **before** the implementation is written.
- **Isolated ingestion and deterministic real time:** ingestion runs in a
  container isolated from the web; the critical path (≤ 10 s end to end) never
  depends on synchronous calls to generative AI or third parties.
- **Human-in-the-Loop:** every AI recommendation / rule / optimization is only a
  suggestion; no on-road regulation action runs without explicit approval from
  the human dispatcher.
- **Tests and gates:** coverage > 80 % is mandatory; every PR passes the gates
  adopted in the active turn before merging; CI marks the build as failed on any
  principle violation.
- **Security:** RBAC only in the backend (never only in the frontend), no IDOR,
  multi-tenant isolation, secrets from an external manager (never in code or
  `.env`). Detail in `.kiro/steering/security.md`.
- **Commits:** agents never commit/push (blocked in their permissions); review
  and commit yourself. *The source documents do not set a commit-message
  convention; **Conventional Commits** is inferred (`type(scope): description`,
  e.g. `feat(ingestion): validate GPS schema with Pydantic V2`). If the team
  adopts another one, document it here and update the constitution.*

## Governing document

The **constitution** (`.specify/memory/constitution.md`, v1.1.0) is the supreme
governing document: its 5 core principles are NON-NEGOTIABLE and prevail over
any other practice. For situational detail, load the matching steering file
(`.kiro/steering/*.md`).
