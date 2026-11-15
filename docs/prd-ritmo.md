# PRD — Product Requirement Definition: RITMO / PulsoFlota

## Control del Documento
* **PROJECT_NAME**: RITMO (Riesgo, Incrementos y Trazabilidad para la Movilidad Operativa) / PulsoFlota
* **CONSTITUTION_VERSION**: 1.0.0
* **RATIFICATION_DATE**: 2026-11-06
* **LAST_AMENDED_DATE**: 2026-11-14
* **ESTADO**: Ratificado / En Producción Inicial

---

## 1. Visión General del Producto y Problemática de Dominio

### 1.1 Contexto de Operación (Medellín)
La ciudad de Medellín enfrenta elevados niveles de congestión vehicular derivados de la ineficiencia y falta de confiabilidad en el sistema de transporte público de buses. La operación actual padece dos causas estructurales principales:
1. **Deficiencia de Información y Visibilidad Vial**: El despacho de flota se realiza con datos tardíos, manuales o inexistentes. Los operadores capturan posicionamiento GPS y validaciones de tarifa sin un estándar unificado de datos, existiendo una ceguera operativa respecto al estado de congestión en tiempo real de los tramos de la red vial estándar.
2. **Incentivos Operativos Distorsionados**: El modelo de pago por pasajero transportado incentiva la "guerra del centavo", provocando la competencia desleal, el agrupamiento de buses (*bus bunching*) y la degradación sistemática de la regularidad en el servicio.

### 1.2 Propósito de PulsoFlota
PulsoFlota es la central web supervisor en tiempo real diseñada para los despachadores de buses y controladores de tráfico. Habilita una toma de decisiones de regulación oportuna y confiable basada en telemetría integrada, algoritmos de regularidad y alertas viales predictivas.

### 1.3 Alcance del Sistema
* **Corredor de Pruebas**: Corredor masivo de buses con estaciones cerradas, rutas estándar predefinidas y punto de transbordo multimodal con el Metro de Medellín.
* **Entorno de Datos**: Telemetría e ingesta alimentadas por un generador de datos sintéticos calibrado con los microdatos abiertos del Metro de Medellín y sensores viales mockeados.
* **Métrica Eje de Calidad**: Probabilidad de abordar en $t$ minutos o menos al llegar a la estación, $P(\text{abordar} \le t)$, complementada por el Tiempo de Espera Excesivo ($EWT$ - *Excess Wait Time*). Mide el servicio desde la perspectiva real del usuario (incluyendo ocupación de buses) procesado como series de tiempo leídas en percentiles ($P_{85}$, $P_{95}$).

---

## 2. Requerimientos Funcionales (RF)

### US-01: Visor del Estado de la Flota y Monitoreo Vial en Tiempo Real
* **RF-1.1 (MUST)**: El sistema **DEBE** desplegar un mapa interactivo en tiempo real que muestre la posición geoespacial actualizada de todos los buses activos en el corredor con una latencia de refresco $\le 2$ segundos.
* **RF-1.2 (MUST)**: El sistema **DEBE** calcular y visualizar el intervalo de paso (*headway*) actual entre vehículos consecutivos en cada ruta estándar, resaltando desviaciones superiores al $\pm 15\%$ respecto al plan de marcha.
* **RF-1.3 (MUST)**: El sistema **DEBE** ingerir la velocidad de flujo vehicular por tramo y clasificar los niveles de congestión en la malla vial utilizando un esquema de codificación visual por colores (Verde: Fluido, Amarillo: Moderado, Rojo: Congestionado).
* **RF-1.4 (SHOULD)**: El sistema **DEBERÍA** integrar los datos de afluencia de pasajeros en las estaciones del Metro asociadas al punto de transbordo para prever picos de demanda.

### US-02: Motor de Alertas y Recomendaciones de Despacho Dinámico
* **RF-2.1 (MUST)**: El sistema **DEBE** emitir alertas tempranas de desincronización de flota con al menos $\ge 3$ minutos de anticipación antes de que se consolide un evento de agrupamiento (*bunching*) o hueco de frecuencia (*gap*).
* **RF-2.2 (MUST)**: El sistema **DEBE** generar recomendaciones de regulación (ej. retención en estación, salida anticipada, inyección de flota de reserva) en un tiempo de cómputo y respuesta $\le 10$ segundos.
* **RF-2.3 (MUST)**: El sistema **DEBE** requerir la aprobación manual del despachador humano antes de enviar cualquier orden de regulación a las unidades a bordo.
* **RF-2.4 (SHOULD)**: El sistema **DEBERÍA** priorizar las recomendaciones que maximicen el indicador $P(\text{abordar} \le t)$ en la franja horaria activa.

### US-03: Redireccionamiento Dinámico de Rutas por Contingencias Viales
* **RF-3.1 (MUST)**: El sistema **DEBE** detectar bloqueos o accidentes viales en las rutas estándar mediante la ingestión de eventos del flujo de datos de tráfico mockeado.
* **RF-3.2 (MUST)**: El sistema **DEBE** calcular automáticamente rutas alternativas para la flota afectada, evaluando el impacto estimado en el tiempo de recorrido y la frecuencia del corredor.
* **RF-3.3 (MUST)**: El sistema **DEBE** presentar la recomendación de desvío al despachador en el visor de mapa con la ruta sugerida, distancia adicional y variación proyectada en el indicador de servicio.
* **RF-3.4 (SHOULD)**: El sistema **DEBERÍA** llevar un registro de auditoría de los desvíos autorizados por el despachador para el cálculo de compensaciones y cumplimiento de contrato con los operadores.

---

## 3. Requerimientos No Funcionales (RNF)

### 3.1 Rendimiento y Tiempo Real Firme
* **RNF-3.1.1 (MUST)**: El sistema **DEBE** clasificarse como de *Tiempo Real Firme*. Una recomendación entregada con retraso no genera fallos catastróficos físicos, pero carece de valor operativo.
* **RNF-3.1.2 (MUST)**: El pipeline de procesamiento de eventos de ingesta **DEBE** procesar hasta 1,000 eventos de telemetría/segundo con una latencia pico $P_{99} \le 500$ ms.
* **RNF-3.1.3 (MUST)**: El tiempo total desde la detección de una anomalía en vía hasta la presentación de la recomendación en la consola del despachador **DEBE** ser $\le 10$ segundos.

### 3.2 Arquitectura y Despliegue en Contenedores
* **RNF-3.2.1 (MUST)**: La aplicación web **DEBE** ser desarrollada en Python (FastAPI/Flask/Streamlit) y empaquetada mediante Docker y `docker-compose`.
* **RNF-3.2.2 (MUST)**: El servicio de ingesta de telemetría en tiempo real **DEBE** ejecutarse en un contenedor totalmente aislado del monolito modular de la central web para prevenir que fallos en la interfaz afecten la captura de datos.
* **RNF-3.2.3 (MUST)**: El sistema **DEBE** incluir una base de datos persistente (PostgreSQL / SQLite) y una capa de almacenamiento/pub-sub en memoria (Redis) para la gestión de datos de tiempo real mockeados.

### 3.3 Calidad de Datos, Seguridad e Integridad
* **RNF-3.3.1 (MUST)**: Toda ingesta de telemetría **DEBE** ser validada en frontera mediante contratos de mensaje (Pydantic / JSON Schema). Los datos corruptos o desfasados en el tiempo **DEBEN** ser rechazados y registrados en el log de DataOps.
* **RNF-3.3.2 (MUST)**: El sistema **DEBE** implementar mecanismos de detección de datos manipulados (ej. saltos incoherentes de GPS o validaciones duplicadas) para proteger el cálculo de pago por calidad.
* **RNF-3.3.3 (SHOULD)**: El sistema **DEBERÍA** proveer tolerancia a fallos mediante un simulador de datos sintéticos que reemplace fuentes de telemetría caídas sin interrumpir la operación del despachador.

---

## 4. Matriz de Criterios de Aceptación y Validación

| ID Requisito | Criterio de Aceptación | Método de Validación | Paso/Fallo |
| :--- | :--- | :--- | :--- |
| **RF-1.1** | Latencia de mapa $\le 2\text{ s}$ en refresco de posición. | Prueba de rendimiento frontend con 100 buses simulados. | Requerido |
| **RF-2.2** | Cómputo de recomendación en $\le 10\text{ s}$. | Prueba de carga de motor algorítmico en CI/CD. | Requerido |
| **RF-2.3** | Ningún comando se transmite a la flota sin clic de confirmación humana. | Inspección de código y pruebas de integración de API. | Requerido |
| **RF-3.2** | Recálculo automático de ruta ante evento de bloqueo vial en $\le 5\text{ s}$. | Inyección automatizada de eventos de accidente sintéticos. | Requerido |
| **RNF-3.3.1** | Rechazo del $100\%$ de paquetes de telemetría sin esquema válido. | Compuerta de calidad de datos automatizada en DataOps. | Requerido |
