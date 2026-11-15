# Documento de Requisitos de Seguridad (SRD) - RITMO / PulsoFlota

**Proyecto:** PulsoFlota — Central de Control y Despacho Operativo en Tiempo Real (Metodología RITMO)  
**Versión del SRD:** 1.0.0  
**Estándar de Referencia:** OWASP Top 10 (2025) & Modelo de Criticidad RITMO (SWEBOK v4 / ISO/IEC/IEEE 24765)  
**Clasificación del Software:** Aplicación, Dominante en Datos y Control Supervisorio  
**Fecha de Adopción:** 2026-11-14  

---

## 1. Visión General y Alcance de Seguridad del Dominio

El presente **Documento de Requisitos de Seguridad (SRD)** establece las directrices normativas, técnicas y arquitectónicas obligatorias para el desarrollo, despliegue y operación del sistema **PulsoFlota**, bajo la metodología híbrida **RITMO** (Riesgo, Incrementos y Trazabilidad para la Movilidad Operativa) en la ciudad de Medellín.

### 1.1 Contexto de Operación y Riesgos de Dominio
PulsoFlota gestiona la telemetría de flota de buses en tiempo real (GPS, validaciones de pasaje, estado del vehículo) e integra la lectura de la malla vial (velocidad de flujo, congestión y eventos accidentales). Dada su naturaleza de **tiempo real firme (latencia $\le 10\text{ s}$)** y su impacto directo en el cálculo de incentivos económicos ($P(\text{abordar} \le t)$ y *Excess Wait Time* - EWT), la seguridad del sistema abarca tres frentes críticos:
1. **Integridad del Dato y Antifraude de Recaudo:** Evitar la inyección o alteración maliciosa de datos de GPS y tarifa orientados a inflar artificialmente los indicadores de pago por calidad.
2. **Seguridad Operativa y Supervisión Humana:** Garantizar que las recomendaciones automáticas o generadas por IA Generativa (ajustes de frecuencia y redireccionamiento por cierres viales) no modifiquen la operación en vía sin la autorización explícita (*Human-in-the-Loop*) del despachador.
3. **Disponibilidad y Resiliencia Sistémica:** Proteger la ingesta de telemetría IoT aislada para que continúe registrando eventos incluso ante fallos de la interfaz web central o ataques de denegación de servicio (DDoS).

### 1.2 Dualidad de Carriles y Criticidad
* **Carril Disciplinado (Criticidad Alta - Nivel 1):** Ingesta de datos IoT, motor de contratos, cálculo de $P(\text{abordar})$ e indicadores de liquidación contractual. Aplica verificación criptográfica estricta, contratos de mensaje y pruebas automatizadas en CI.
* **Carril Adaptativo (Criticidad Media/Baja - Nivel 2 y 3):** Central web del despachador, paneles de visualización gráfica y reglas predictivas de alerta. Opera mediante iteraciones de hipótesis validadas sin acceso directo al camino de tiempo real determinista.

---

## 2. Requisitos Técnicos de Seguridad (Matriz OWASP Top 10 - 2025 Adaptada)

### 2.1 Control de Acceso (A01:2025 - Broken Access Control)
* **Requisito Técnico:** Todo endpoint de API REST o WebSocket en la aplicación Python (FastAPI/Backend) MUST autenticar la identidad del emisor y verificar explícitamente los permisos asignados mediante Control de Acceso Basado en Roles (*Role-Based Access Control* - RBAC) en la capa de middleware antes de ejecutar cualquier lógica de negocio.
* **Criterios de Aceptación:**
  * **Prohibición de IDOR:** Quedan strictly prohibidas las Referencias Directas a Objetos Inseguros. Si un usuario intenta acceder o modificar un recurso de un operador distinto (ej. consultar `/api/v1/buses/{bus_id}` o alterar rutas de otra cuenca de transporte), el middleware MUST retornar un código `403 Forbidden` y registrar una alerta de seguridad.
  * **Evaluación Centralizada en Backend:** Las autorizaciones MUST ser evaluadas exclusivamente en el servidor central en Python. El cliente web (*frontend*) no MUST tomar decisiones de acceso ni ocultar botones como único mecanismo de control.
  * **Aislamiento Multi-Tenant:** Los datos de telemetría de consorcios privados MUST estar aislados lógicamente, impidiendo que un operador acceda a la telemetría cruda de sus competidores.

### 2.2 Configuración de Seguridad e Infraestructura en Contenedores (A02:2025 - Security Misconfiguration)
* **Requisito Técnico:** Las imágenes de contenedor Docker y los servidores proxy inversos (Nginx/Traefik) MUST estar configurados bajo el principio de mínimo privilegio y fortalecimiento de infraestructura (*hardening*).
* **Criterios de Aceptación:**
  * **Ejecución Non-Root en Docker:** Todos los contenedores de Python (Ingesta y Central) MUST ejecutarse bajo un usuario sin privilegios root (`USER appuser` con UID `10001`).
  * **Cabeceras HTTP de Seguridad:** El servidor web MUST incluir obligatoriamente las siguientes cabeceras en todas las respuestas HTTP:
    * `Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none';`
    * `Strict-Transport-Security: max-age=31536000; includeSubDomains`
    * `X-Content-Type-Options: nosniff`
    * `X-Frame-Options: DENY`
  * **Ocultación de Infraestructura:** El servidor MUST remover las cabeceras descriptivas de pila tecnológica como `Server`, `X-Powered-By` y versiones de Python/FastAPI.
  * **Desactivación de Modos Debug:** El parámetro `DEBUG=False` MUST ser forzado en todos los entornos de homologación y producción. Queda prohibida la exposición de Swagger/ReDoc en producción sin autenticación previa.

### 2.3 Cadena de Suministro de Software y Fábrica de Agentes (A03:2025 - Software Supply Chain Failures)
* **Requisito Técnico:** Se MUST mantener un control estricto de dependencias de terceros (librerías Python, imágenes base de Docker y librerías JavaScript) en el repositorio y en el pipeline de CI/CD.
* **Criterios de Aceptación:**
  * **Escaneo Automatizado de Vulnerabilidades (SCA):** El pipeline de CI/CD MUST ejecutar herramientas de análisis de composición de software (`pip-audit`, `Safety` o `Snyk`) en cada *Pull Request*.
  * **Bloqueo por Severidad CVE:** Si se detectan vulnerabilidades de severidad Alta o Crítica (CVSS $\ge 7.0$) en cualquier paquete Python o imagen Docker base, el pipeline de CI MUST fallar automáticamente e impedir la fusión de código.
  * **Fijación de Versiones (*Pinning*):** Todas las dependencias MUST estar declaradas con su versión exacta y hash de integridad (`poetry.lock` o `requirements.txt` compilado con hashes SHA-256).

### 2.4 Criptografía y Protección de Datos (A04:2025 - Cryptographic Failures)
* **Requisito Técnico:** Todos los datos en tránsito entre las unidades a bordo de los buses, los sensores viales y la central de ingesta, así como los datos en reposo, MUST estar protegidos mediante cifrado robusto.
* **Criterios de Aceptación:**
  * **Cifrado en Tránsito:** Las comunicaciones externas MUST emplear exclusivamente TLS 1.3 (o TLS 1.2 como límite inferior con *ciphersuites* PFS). Las conexiones de la flota vehicular IoT MUST autenticarse mediante mTLS (*Mutual TLS*) con certificados x509 por unidad.
  * **Almacenamiento de Credenciales:** Las contraseñas de despachadores y administradores MUST ser procesadas utilizando **Argon2id** (o `bcrypt` con factor de coste $\ge 12$).
  * **Gestión de Secretos:** Queda estrictamente prohibido incluir contraseñas, tokens JWT, claves de base de datos o API Keys en el código fuente o archivos `.env` del repositorio. Se MUST utilizar un gestor de secretos externo (*Docker Secrets* o *HashiCorp Vault*) inyectado en tiempo de ejecución.

### 2.5 Inyección y Validación de Esquemas IoT (A05:2025 - Injection)
* **Requisito Técnico:** Todo flujo de datos entrante (peticiones REST, mensajes MQTT/WebSockets de telemetría IoT o parámetros de consulta) MUST ser sanitizado y validado formalmente antes de interactuar con la base de datos o el motor de reglas.
* **Criterios de Aceptación:**
  * **Consultas Parametrizadas:** Queda prohibida la concatenación directa de cadenas en sentencias SQL. El sistema MUST utilizar obligatoriamente un ORM parametrizado (SQLAlchemy / asyncpg / Pydantic V2).
  * **Validación Estricta de Esquemas con Pydantic:** Todo evento de ingesta de telemetría GPS o recaudo MUST ser validado contra un esquema estricto Pydantic V2 en la compuerta de ingesta. Si un paquete contiene tipos incorrectos, valores fuera de rango geográfico o campos adicionales no declarados, MUST ser rechazado en el acto con código HTTP `422 Unprocessable Entity`.

### 2.6 Diseño Seguro y Aislamiento de IA Generativa (A06:2025 - Insecure Design)
* **Requisito Técnico:** La arquitectura del sistema MUST aislar completamente la ruta de cómputo en tiempo real determinista de los módulos de inteligencia artificial o algoritmos predictivos adaptativos.
* **Criterios de Aceptación:**
  * **Compuerta Humana (*Human-in-the-Loop*):** Las recomendaciones de regulación de frecuencia o desvíos viales generadas por modelos de IA Generativa MUST presentarse en la consola como sugerencias no vinculantes. La aplicación de cualquier cambio en la operación en vía MUST requerir la aprobación explícita y manual del despachador humano.
  * **Aislamiento del Camino de Tiempo Real:** Ningún modelo de IA o agente autónomo MUST tener permisos de escritura directa sobre la base de datos de producción o las APIs de despacho de las unidades a bordo.
  * **Análisis de Amenazas STRIDE:** Toda nueva funcionalidad o modificación arquitectónica en el carril disciplinado MUST contar con una revisión documentada de modelo de amenazas STRIDE priorizada por riesgo.

### 2.7 Autenticación y Gestión de Sesiones (A07:2025 - Authentication Failures)
* **Requisito Técnico:** La central de control y despacho MUST contar con mecanismos de autenticación robustos resistentes a ataques de fuerza bruta, suplantación de identidad y secuestro de sesión.
* **Criterios de Aceptación:**
  * **Tokens de Sesión JWT Seguros:** Los tokens de sesión JWT MUST ser firmados con el algoritmo `RS256` (clave pública/privada), poseer una expiración máxima de 15 minutos y transmitirse únicamente en cookies con atributos `HttpOnly`, `Secure` y `SameSite=Strict`.
  * **Autenticación Multifactor (MFA):** El acceso de administradores de sistema y supervisores de cuenca MUST exigir obligatoriamente MFA (TOTP).
  * **Protección Anti-Fuerza Bruta:** El sistema MUST bloquear temporalmente (durante 15 minutos) cualquier cuenta o dirección IP que registre 5 intentos fallidos consecutivos de inicio de sesión.

### 2.8 Integridad de Software, Datos y Antifraude de Recaudo (A08:2025 - Data & Software Integrity Failures)
* **Requisito Técnico:** Se MUST garantizar la integridad no manipulable de los eventos de telemetría y recaudo que alimentan el cálculo de las métricas de servicio $P(\text{abordar} \le t)$ y la posterior liquidación de pagos por calidad a los operadores.
* **Criterios de Aceptación:**
  * **Auditoría de Linaje de Datos con DataOps:** Todo pipeline de datos de ingesta MUST registrar la procedencia, marca de tiempo inmutable y checksum del mensaje.
  * **Detección de Anomalías y Datos Adulterados:** El sistema MUST contar con reglas automatizadas para detectar y descartar datos manipulados (ej. saltos de ubicación GPS con velocidades superiores a $120\text{ km/h}$, duplicación de secuencias de pasaje o incongruencia entre sensores viales y coordenadas del bus).
  * **Firma Digital de Eventos:** Los paquetes de datos transmitidos por las validadoras de recaudo MUST incluir una firma HMAC basada en un token secreto almacenado en el módulo seguro del validador vehicular.

### 2.9 Registro, Auditoría y Observabilidad SRE (A09:2025 - Security Logging and Alerting Failures)
* **Requisito Técnico:** El sistema MUST generar un registro inmutable y estructurado de auditoría para todas las acciones sensibles de seguridad y decisiones operativas.
* **Criterios de Aceptación:**
  * **Logs Estructurados JSON:** Todos los eventos de registro MUST emitirse en formato JSON estructurado compatible con estándares OpenTelemetry.
  * **Eventos Auditables Obligatorios:** Se MUST registrar con marca de tiempo UTC e identificador de usuario:
    1. Intentos de autenticación (éxito/fallo).
    2. Cambios de permisos o modificación de usuarios.
    3. Desvíos viales o ajustes de despacho autorizados o rechazados por el despachador.
    4. Alteraciones o caídas en las fuentes de datos de ingesta.
  * **Protección de PII y Datos Sensibles:** Los registros de auditoría y los logs de aplicación no MUST incluir jamás contraseñas en texto plano, claves privadas, tokens JWT completos ni datos de identificación personal de conductores o pasajeros.
  * **Alertas en Tiempo Real:** Las anomalías de seguridad o picos de rechazo de mensajes IoT (>5% de fallos en 1 minuto) MUST disparar alertas inmediatas al equipo SRE/DevSecOps via PagerDuty/Slack.

### 2.10 Gestión de Excepciones y Resiliencia en Tiempo Real (A10:2025 - Exceptional Conditions Handling)
* **Requisito Técnico:** El backend en Python y la ingesta aislada MUST manejar las excepciones de manera defensiva, garantizando la continuidad de la operación y evitando la fuga de detalles de infraestructura.
* **Criterios de Aceptación:**
  * **Sanitización de Trazas de Error:** Ninguna respuesta de API HTTP o WebSocket hacia el cliente MUST exponer trazas de pila (*stack traces*), rutas de archivos locales `/workspace/...` ni estructuras internas de la base de datos PostgreSQL.
  * **Correlation ID Unificado:** Ante un error no controlado (HTTP 500), la aplicación MUST retornar un mensaje genérico estandarizado acompañado de un identificador único de seguimiento (`correlation_id`) grabado internamente en los logs.
  * **Fallback Operativo ante Fallo de la Central:** Si la central de control o la interfaz web colapsan, el servicio de ingesta IoT aislada MUST continuar registrando eventos en el buffer persistente, y la consola del despachador MUST conmutar automáticamente a un modo de contingencia local basado en planes de despacho estáticos prefijados.

---

## 3. Matriz de Compuertas de Calidad de Seguridad (Security Quality Gates)

En alineación con las vueltas del espiral RITMO, ningún incremento de software puede ser promovido de etapa ni desplegado en producción sin superar las siguientes compuertas de seguridad:

| Compuerta de Calidad | Etapa RITMO | Frecuencia / Momento | Pruebas y Controles Exigidos | Criterio de Aprobación Obligatorio | Responsable |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Compuerta 1: Contrato y Análisis Estático** | 2. Especificar / 3. Construir | Cada *Pull Request* | Análisis SAST (`Bandit`, `ESLint`) y validación de esquemas Pydantic. | 0 hallazgos Críticos/Altos en SAST; esquema de contrato validado. | Agente de Desarrollo / Revisor |
| **Compuerta 2: Integración y Supply Chain** | 4. Verificar | En integración continua (CI) | Escaneo SCA (`pip-audit`, `Trivy`) y suites de pruebas unitarias/integración. | Cobertura de pruebas $>80\%$; 0 vulnerabilidades conocidas en dependencias. | Agente de Pruebas / DevSecOps |
| **Compuerta 3: Compuerta del Dato (DataOps)** | 4. Verificar | En tiempo de ejecución (Ingesta) | Pruebas de contrato de mensaje, validación HMAC y detección de anomalías. | Tasa de rechazo de paquetes $<0.1\%$; latencia de ingesta $\le 200\text{ ms}$. | DataOps Lead / Ingesta |
| **Compuerta 4: Compuerta de Valor y Seguridad Operativa** | 5. Revisar | Cierre de Vuelta del Espiral | Validación *Human-in-the-Loop*, auditoría de desvíos y prueba de fallback. | Aprobación explícita del despachador; verificación de no interferencia de IA en tiempo real. | Despachador / Dueño de Vuelta |

---

## 4. Gobernanza y Procedimiento de Enmiendas

1. **Política de Versionado:** El presente SRD se rige por versionado semántico (`MAJOR.MINOR.PATCH`). Un incremento en `MAJOR` representa cambios en los requerimientos de seguridad por actualización de normativas o reestructuración arquitectónica; `MINOR` refleja la adición de nuevos criterios de aceptación; `PATCH` aplica para correcciones de redacción o aclaraciones técnicas.
2. **Procedimiento de Enmienda:** Cualquier modificación a los requisitos normativos (normas MUST / SHOULD) requiere la presentación de un documento de decisión de arquitectura (ADR), la validación en la compuerta de riesgo del espiral y la firma unánime del Dueño de Vuelta, el Arquitecto de Seguridad y el Representante del Despachador.
3. **Auditoría de Cumplimiento:** Se realizará una revisión automatizada de cumplimiento de este SRD al finalizar cada vuelta del espiral RITMO mediante la ejecución del pipeline de auditoría de seguridad y DataOps.
