---
inclusion: auto
name: security
description: Al implementar seguridad, autenticación, criptografía, gestión de secretos, hardening de contenedores, cabeceras HTTP, cadena de suministro (SCA) o modelado de amenazas STRIDE. Matriz OWASP Top 10 (2025).
---

# Seguridad — OWASP Top 10 (2025) — PulsoFlota

Matriz completa de criterios de aceptación. La constitución (sección
"Restricciones Técnicas y de Seguridad") fija los MUSTs de gobierno; este
archivo operacionaliza los criterios.

## A01 — Broken Access Control

- RBAC en el middleware del backend; autenticar emisor y verificar permisos antes
  de la lógica de negocio.
- Prohibido IDOR: acceso a recurso ajeno → `403 Forbidden` + alerta de seguridad.
- Autorizaciones solo en el backend; el frontend no decide acceso ni se limita a
  ocultar botones.
- Aislamiento multi-tenant: telemetría de consorcios privados aislada
  lógicamente.

## A02 — Security Misconfiguration

- Contenedores Python (Ingesta y Central) como usuario no root: `USER appuser`
  con UID `10001`.
- Cabeceras HTTP obligatorias en todas las respuestas:
  - `Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none';`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
- Remover `Server`, `X-Powered-By` y versiones de Python/FastAPI.
- `DEBUG=False` forzado en homologación y producción; Swagger/ReDoc no expuestos
  en producción sin autenticación.

## A03 — Software Supply Chain Failures

- SCA en cada PR: `pip-audit`, `Safety` o `Snyk` (Python), `Trivy` (imágenes
  Docker base y librerías JS).
- Bloquear la fusión ante CVE de severidad Alta o Crítica (CVSS ≥ 7.0).
- Fijar dependencias con versión exacta y hash SHA-256 (`poetry.lock` o
  `requirements.txt` con hashes).

## A04 — Cryptographic Failures

- Cifrado en tránsito: TLS 1.3 (mínimo TLS 1.2 con *ciphersuites* PFS); flota IoT
  con mTLS y certificados x509 por unidad.
- Contraseñas con Argon2id (o `bcrypt` con factor de coste ≥ 12).
- Secretos (contraseñas, JWT, claves de BD, API Keys) vía Docker Secrets o
  HashiCorp Vault, inyectados en runtime. Prohibido en código fuente o `.env`
  del repositorio.

## A05 — Injection

- Consultas parametrizadas (SQLAlchemy / asyncpg / Pydantic V2); prohibida la
  concatenación de SQL.
- Validación estricta Pydantic V2 en la ingesta: tipos incorrectos, valores fuera
  de rango geográfico o campos no declarados → `422 Unprocessable Entity`.

## A06 — Insecure Design

- Aislar la ruta de tiempo real determinista de los módulos de IA predictiva.
- Human-in-the-Loop: las recomendaciones de IA se presentan como sugerencias no
  vinculantes; cualquier cambio en la operación en vía requiere aprobación
  manual explícita del despachador.
- Ningún modelo/agente con escritura directa sobre la BD de producción ni las
  APIs de despacho.
- STRIDE documentado y priorizado por riesgo para toda nueva funcionalidad o
  modificación del carril disciplinado.

## A07 — Authentication Failures

- JWT firmado con `RS256`, expiración ≤ 15 min, cookies `HttpOnly` + `Secure` +
  `SameSite=Strict`.
- MFA (TOTP) obligatorio para administradores y supervisores de cuenca.
- Bloqueo 15 min de cuenta o IP con 5 intentos fallidos consecutivos.

## A08 — Data & Software Integrity Failures

- Linaje de datos (DataOps): procedencia, marca de tiempo inmutable y checksum
  por mensaje.
- Detección de anomalías: saltos GPS > 120 km/h, duplicación de pasaje,
  inconsistencia entre sensores viales y coordenadas del bus.
- Firma HMAC en paquetes de recaudo (secreto del módulo seguro del validador).

## A09 — Security Logging and Alerting Failures

- Logs en JSON estructurado compatible con OpenTelemetry.
- Eventos auditables con marca UTC e identificador de usuario: intentos de
  autenticación (éxito/fallo), cambios de permisos/usuarios, desvíos o ajustes
  de despacho autorizados/rechazados, alteraciones o caídas en las fuentes de
  ingesta.
- Prohibido registrar contraseñas en texto plano, claves privadas, tokens JWT
  completos o PII de conductores/pasajeros.
- Alertas en tiempo real al equipo SRE/DevSecOps (PagerDuty/Slack) ante
  anomalías de seguridad o rechazo de mensajes IoT > 5 % en 1 min.

## A10 — Exceptional Conditions Handling

- Sanitizar trazas: ninguna respuesta HTTP/WebSocket expone *stack traces*,
  rutas locales (`/workspace/...`) ni estructuras internas de PostgreSQL.
- HTTP 500 → mensaje genérico + `correlation_id` registrado en los logs.
- Fallback operativo: ingesta IoT aislada sigue en buffer persistente; la
  consola conmuta a planes de despacho estáticos prefijados.

## Referencias

- Flujo de API/auth y manejo de errores: `backend-api.md`.
- Compuertas de SAST/SCA en CI: `testing-quality-gates.md`.
- Hardening de imágenes y `docker-compose`: `deployment-containers.md`.
