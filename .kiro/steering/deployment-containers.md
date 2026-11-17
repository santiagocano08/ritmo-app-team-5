---
inclusion: fileMatch
fileMatchPattern: ["**/Dockerfile", "**/Dockerfile.*", "**/docker-compose*.yml", "**/docker-compose*.yaml", "**/.dockerignore"]
---

# Despliegue y Contenedores — PulsoFlota

## Servicios de `docker-compose`

Mínimo tres servicios:

1. **`ingestion-service`** — ingesta síncrona de telemetría IoT y fuentes de
   tráfico mockeadas.
2. **`pulsoflota-web`** — monolito modular: central supervisora, cálculo de
   métricas y mapa interactivo.
3. **`database-redis`** — infraestructura de persistencia y caché/pub-sub de
   eventos.

## Aislamiento

- `ingestion-service` se ejecuta en un contenedor **totalmente aislado** del
  monolito `pulsoflota-web`, para que fallos de la interfaz no afecten la
  captura de datos.

## Hardening (A02)

- Ejecución **non-root**: `USER appuser` con UID `10001` en todos los
  contenedores Python (Ingesta y Central). Mínimo privilegio.
- Proxy inverso (Nginx/Traefik) endurecido bajo mínimo privilegio.
- Cabeceras HTTP de seguridad obligatorias (valores exactos en `security.md`):
  CSP, HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`.
- Remover cabeceras que revelan la pila (`Server`, `X-Powered-By`, versiones).
- `DEBUG=False` forzado en homologación/producción; Swagger/ReDoc no expuestos
  en producción sin autenticación.

## Datos

- Persistencia: PostgreSQL con extensión PostGIS (SQLite para entornos de
  desarrollo/testing empaquetados).
- Tiempo real/caché: Redis (Pub/Sub para telemetría en vivo + estado en
  memoria).

## Secretos (A04)

- Inyectados en runtime vía Docker Secrets o HashiCorp Vault.
- Nunca en imágenes, código fuente ni `.env` del repositorio (`.env` está
  git-ignored).

## Dependencias de imagen (A03)

- Fijar versión exacta + hash SHA-256.
- Escaneo SCA (`Trivy` para imágenes) en CI; bloquear CVE con CVSS ≥ 7.0.

## Referencias

- Matriz OWASP Top 10 (2025): `security.md`.
- Compuertas de SCA/CI: `testing-quality-gates.md`.
