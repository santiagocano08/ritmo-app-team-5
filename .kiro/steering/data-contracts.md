---
inclusion: auto
name: data-contracts
description: Al definir o modificar el modelo de dominio, contratos de mensaje de telemetría/ingesta, esquemas Pydantic V2, validación en frontera, antifraude de recaudo o linaje de datos (DataOps).
---

# Contratos de Datos y Modelo de Dominio — PulsoFlota

## Contract-First & Data Ownership (Principio II)

- Todo intercambio de datos entre módulos o servicios define y valida un
  contrato explícito de mensaje (Pydantic V2 / OpenAPI) **antes** de escribir la
  implementación.
- Ningún modelo de datos se persiste ni procesa en el pipeline sin un
  propietario de módulo asignado y un esquema validado en frontera.

## Modelo de objetos de dominio (OMD)

- **Vehiculo** — `id_vehiculo: str (UUID)`, `placa: str`, `id_operador: str`,
  `capacidad_pasajeros: int`, `estado_operativo: Enum (EN_RUTA, EN_ESTACION,
  EN_DESVIO, FUERA)`.
- **EventoTelemetria** — `timestamp: datetime (UTC)`, `latitud: float`,
  `longitud: float`, `velocidad_kmh: float`, `nivel_ocupacion: float (0.0-1.0)`.
- **RutaEstandar** — `id_ruta: str`, `nombre_corredor: str`,
  `estaciones_ordenadas: List[Estacion]`, `headway_objetivo_segundos: int`.
- **TramoVial** — `id_tramo: str`, `coordenada_inicio: GeoPoint`,
  `coordenada_fin: GeoPoint`, `nivel_congestion: Enum (VERDE, AMARILLO, ROJO)`,
  `velocidad_promedio_actual: float`.
- **MetricaServicio** — `ventana_tiempo: TimeWindow`, `id_estacion: str`,
  `p_abordar_t: float`, `ewt_segundos: float`, `percentil_evaluado: int (85, 95)`.
- **PropuestaRegulacion** — `id_propuesta: str`, `tipo_accion: Enum
  (DESPACHO_ANTICIPADO, RETENCION, DESVIO_RUTA)`, `vehiculo_objetivo: Vehiculo`,
  `ruta_sugerida: List[TramoVial]`, `tiempo_respuesta_calculado: float`,
  `estado_aprobacion: Enum (PENDIENTE, APROBADA, RECHAZADA)`,
  `autorizado_por: Optional[UsuarioDespachador]`.

## Compuerta de ingesta (validación en frontera)

- Todo evento de telemetría GPS o recaudo se valida contra un esquema estricto
  Pydantic V2. Tipos incorrectos, valores fuera de rango geográfico o campos no
  declarados → rechazo `422 Unprocessable Entity`.
- Tasa de rechazo de paquetes objetivo: < 0,1 %.

## Antifraude y detección de anomalías (A08)

- Descartar datos manipulados: saltos de ubicación GPS con velocidad
  > 120 km/h, duplicación de secuencias de pasaje, inconsistencia entre sensores
  viales y coordenadas del bus.

## Integridad y linaje de datos (DataOps)

- Firma HMAC en los paquetes de recaudo, basada en un secreto del módulo seguro
  del validador vehicular.
- Registrar procedencia, marca de tiempo inmutable y checksum por mensaje.

## Headway y regularidad

- Visualizar el intervalo de paso entre vehículos consecutivos; resaltar
  desviaciones > ±15 % respecto al plan de marcha.

## Referencias

- SLOs de latencia/rendimiento de la ingesta (≤ 200 ms, 1 000 eventos/s) y
  aislamiento del contenedor: `realtime-ingestion.md`.
- RBAC sobre endpoints y aislamiento multi-tenant: `security.md`.
