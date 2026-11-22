---
inclusion: auto
name: data-contracts
description: When defining or changing the domain model, telemetry/ingestion message contracts, Pydantic V2 schemas, boundary validation, fare-collection anti-fraud, data lineage (DataOps), silver/gold tables and views, service metrics (EWT, P(board ≤ t), M1, M2), the decision model, or anything the backend reads or writes (docs/data-contract.md).
---

# Data Contracts and Domain Model — PulsoFlota

> These are norms of the **target system**. For what the active turn requires,
> check `docs/turns-ritmo.md`; the data profiles (`data-profile-*.md`) narrow it down.

## Data contract review on every data change (data owner rule, 2026-11-21)

Every change to data MUST include a review of the data contract. The data contract is:
- `docs/data-contract.md` (how the backend reads gold and writes command events);
- the JSON Schemas under `contracts/read/` and `contracts/turn1-events/`;
- the ADRs that back them (0001–0003, 0006, 0007).

A data change is any change to a silver or gold table or view, a metric (EWT, P(board ≤ t), M1, M2), a rule (bus states, freshness, effect), the decision model, a command event, the reference data, or the simulator when it changes what gets published.

- **Specs and plans** MUST list the contract sections they affect, or state "no contract impact" with the reason.
- **Verification** MUST check that the contract's queries, example outputs and versions still hold after the change.
- **When there is an impact**, the contract is updated in the same PR or the very next one, never "later". A change of meaning in a published field requires a version bump (ADR-0002/0003 versioning rule).
- Changes to `docs/data-contract.md`, `contracts/` and data ADRs need the data owner's review (`.github/CODEOWNERS`).

## Contract-First and Data Ownership (Principle II)

- Every data exchange between modules or services defines and validates an
  explicit message contract (Pydantic V2 / OpenAPI) **before** the
  implementation is written.
- No data model is persisted or processed in the pipeline without an assigned
  owning module and a schema validated at the boundary.

## Domain object model (OMD)

Identifiers are kept exactly as defined in the OMD (`docs/omd-ritmo.md`).

- **Vehiculo** (vehicle) — `id_vehiculo: str (UUID)`, `placa: str`,
  `id_operador: str`, `capacidad_pasajeros: int`, `estado_operativo: Enum
  (EN_RUTA, EN_ESTACION, EN_DESVIO, FUERA)`.
- **EventoTelemetria** (telemetry event) — `timestamp: datetime (UTC)`,
  `latitud: float`, `longitud: float`, `velocidad_kmh: float`,
  `nivel_ocupacion: float (0.0-1.0)`.
- **RutaEstandar** (standard route) — `id_ruta: str`, `nombre_corredor: str`,
  `estaciones_ordenadas: List[Estacion]`, `headway_objetivo_segundos: int`.
- **TramoVial** (road segment) — `id_tramo: str`, `coordenada_inicio: GeoPoint`,
  `coordenada_fin: GeoPoint`, `nivel_congestion: Enum (VERDE, AMARILLO, ROJO)`,
  `velocidad_promedio_actual: float`.
- **MetricaServicio** (service metric) — `ventana_tiempo: TimeWindow`,
  `id_estacion: str`, `p_abordar_t: float`, `ewt_segundos: float`,
  `percentil_evaluado: int (85, 95)`.
- **PropuestaRegulacion** (regulation proposal) — `id_propuesta: str`,
  `tipo_accion: Enum (DESPACHO_ANTICIPADO, RETENCION, DESVIO_RUTA)`,
  `vehiculo_objetivo: Vehiculo`, `ruta_sugerida: List[TramoVial]`,
  `tiempo_respuesta_calculado: float`, `estado_aprobacion: Enum (PENDIENTE,
  APROBADA, RECHAZADA)`, `autorizado_por: Optional[UsuarioDespachador]`.

## Ingestion gate (boundary validation)

- Every GPS telemetry or fare-collection event is validated against a strict
  Pydantic V2 schema. Wrong types, values outside the geographic range or
  undeclared fields → `422 Unprocessable Entity` rejection.
- Target packet rejection rate: < 0.1 %.

## Anti-fraud and anomaly detection (A08)

- Discard tampered data: GPS jumps implying speed > 120 km/h, duplicated fare
  sequences, inconsistency between road sensors and bus coordinates.

## Data integrity and lineage (DataOps)

- HMAC signature on fare-collection packets, based on a secret of the on-board
  validator's secure module.
- Record provenance, an immutable timestamp and a checksum per message.
- Immutable lineage for anti-fraud: every gold aggregate records its
  `rules_version` and its bronze origin, so each settlement metric
  (P(board ≤ t), EWT) is reproducible and traceable to the rules version that
  produced it. Quality rules are deterministic, tested code (never an LLM
  decision), which prevents retroactively altering payment indicators.

## Headway and regularity

- Show the headway between consecutive vehicles; highlight deviations > ±15 %
  from the schedule.

## References

- Ingestion latency/throughput SLOs (≤ 200 ms, 1,000 events/s) and container
  isolation: `realtime-ingestion.md`.
- Endpoint RBAC and multi-tenant isolation: `security.md`.
