---
inclusion: auto
name: backend-api
description: Al trabajar en la API/backend Python de PulsoFlota (FastAPI/Flask): endpoints REST/WebSocket, middleware RBAC, autenticación JWT, manejo de errores, correlation_id y validación con Pydantic.
---

# Backend API — PulsoFlota

Guía para la API/backend Python de la central (`pulsoflota-web`): FastAPI o Flask.

## Estructura y enrutado

- Monolito modular `pulsoflota-web` (central supervisora, cálculo de métricas,
  mapa interactivo). Exponer endpoints REST + WebSocket.
- Versionar la API bajo `/api/v1/...`.

## Control de acceso (A01) — en el backend, siempre

- Autenticar la identidad del emisor y verificar permisos por RBAC en el
  middleware **antes** de ejecutar lógica de negocio.
- Prohibido IDOR: acceder/modificar un recurso ajeno (p. ej.
  `/api/v1/buses/{bus_id}` de otra cuenca) DEBE devolver `403 Forbidden` y
  registrar una alerta de seguridad.
- Las autorizaciones se evalúan **exclusivamente en el backend**. El frontend no
  decide acceso ni se limita a ocultar botones como único mecanismo.
- Aislamiento multi-tenant: la telemetría de consorcios privados se aísla
  lógicamente; un operador no accede a la telemetría cruda de competidores.

## Autenticación y sesiones (A07)

- JWT firmado con `RS256`, expiración ≤ 15 min, transmitido únicamente en
  cookies `HttpOnly`, `Secure`, `SameSite=Strict`.
- MFA (TOTP) obligatorio para administradores y supervisores de cuenca.
- Anti-fuerza-bruta: bloquear 15 min cualquier cuenta o IP con 5 intentos
  fallidos consecutivos.

## Validación y datos

- Request/response validados con Pydantic V2; los inválidos se rechazan con
  `422 Unprocessable Entity`. La definición de esquemas y contratos
  inter-módulo vive en `data-contracts.md`.
- Consultas parametrizadas (ORM / SQLAlchemy / asyncpg / Pydantic V2); prohibida
  la concatenación de SQL.

## Errores y excepciones (A10)

- Nunca exponer trazas de pila, rutas locales (`/workspace/...`) ni estructuras
  internas de PostgreSQL.
- HTTP 500 → mensaje genérico estandarizado + `correlation_id` registrado en los
  logs. Errores de validación → `422`.

## Configuración

- `DEBUG=False` forzado en homologación/producción; Swagger/ReDoc no expuestos en
  producción sin autenticación previa.

## Referencias

- Matriz OWASP Top 10 (2025) completa (cabeceras HTTP, criptografía, secretos,
  supply chain, STRIDE, logs/PII): `security.md`.
- Esquemas y validación de telemetría: `data-contracts.md`.
