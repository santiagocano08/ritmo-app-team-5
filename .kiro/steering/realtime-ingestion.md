---
inclusion: auto
name: realtime-ingestion
description: When working on the isolated ingestion service, the deterministic real-time pipeline, latency SLOs, resilience, fallback or control-center contingency.
---

# Isolated Ingestion and Deterministic Real Time — PulsoFlota

> These are norms of the **target system**. For what the active turn requires,
> check `docs/turns-ritmo.md`; `data-profile-development.md` narrows it down.

## Isolation (Principle III)

- `ingestion-service` runs in a process container **fully isolated** from the
  `pulsoflota-web` modular monolith, so web failures do not affect data capture.

## Critical-path determinism

- The total time from detecting an on-road anomaly to showing the
  recommendation on the dispatcher console MUST be ≤ 10 s.
- The real-time critical path MUST be deterministic and **never** depend on
  synchronous calls to generative-AI agents or external third-party services.
- No AI model or autonomous agent has direct write access to the production
  database or to the dispatch APIs of on-board units.

## Performance SLOs

- The ingestion pipeline processes up to 1,000 events/second with peak P99
  latency ≤ 500 ms.
- Ingestion latency (DataOps gate): ≤ 200 ms.
- Interactive map refresh: ≤ 2 s.
- Automatic route recalculation after a road blockage: ≤ 5 s.

## Classification

- **Firm** real time: a late recommendation causes no catastrophic physical
  failure, but has no operational value.

## Fallback and contingency (A10)

- If the control center or the web interface fails, the isolated IoT ingestion
  keeps recording events in the persistent buffer.
- The dispatcher console automatically switches to a local contingency mode
  based on predefined static dispatch plans.

## References

- Event validation at the ingestion gate (schema, `422`, anti-fraud, HMAC):
  `data-contracts.md`.
- Observability and alerts (IoT rejection > 5 % in 1 min → SRE/DevSecOps):
  `security.md`.
