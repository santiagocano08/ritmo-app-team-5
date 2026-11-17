# Contract: API Health Endpoint

**Authority**: this feature (FR-011). The API service is minimal and health-only
in turn 1.

## Service

`api` container: FastAPI + uvicorn. Versioned base path `/api/v1` is reserved
but unused. No other routes exist in this story.

## Endpoint

```
GET /healthz
```

### Request
- No parameters, no body, no authentication (turn 1; auth is turn-2 evolution).

### Response
- **200 OK**
- Body: `{"status": "healthy"}`
- Content-Type: `application/json`

### Semantics
- Reports that the API **process** is up and serving. It does **not** depend on
  the database: the health check answers even while bronze is briefly
  unreachable. Bronze growth is verified separately (US-2 independent test).
- No stack traces or internal paths are ever exposed (no-cost security
  baseline). A 500 returns a generic message.

## Non-goals (this story)

- No metrics, no DB-readiness probe, no WebSocket, no other REST resources.
- No RBAC / JWT / security headers (turn 2, evolution).
- The API is **not** on the capture path: stopping it must not stop ingestion
  (Principle III, US-2 acceptance scenario 2).
