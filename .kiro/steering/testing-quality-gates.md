---
inclusion: auto
name: testing-quality-gates
description: When writing tests, configuring CI/CD, or checking a quality gate (SAST, SCA, DataOps, coverage >80 %, Human-in-the-Loop).
---

# Testing and Quality Gates — PulsoFlota

> Each gate applies from the turn in which `docs/turns-ritmo.md` adopts it. In
> turn 1: Gate 1 (schema validation only), Gate 2 (tests and coverage) and the
> human approval of Gate 4.

## Test-First (Principle V, NON-NEGOTIABLE)

- Every PR includes unit and integration tests with coverage > 80 %.
- No developer or agent skips the gates.

## Gate 1 — Contract and Static Analysis (every PR)

- SAST: `Bandit` (Python) and `ESLint` (JavaScript).
- Pydantic schema validation.
- Pass: 0 Critical/High SAST findings and a validated contract schema.

## Gate 2 — Integration and Supply Chain (CI)

- SCA: `pip-audit` / `Trivy` (and `Safety`/`Snyk` for Python); `npm audit`
  for the React console.
- Unit/integration test suites (pytest for Python; Vitest for the React
  console, which counts towards the same > 80 % threshold).
- Pass: coverage > 80 % and 0 known dependency vulnerabilities (a CVE with
  CVSS ≥ 7.0 blocks the merge).

## Gate 3 — Data Gate (DataOps, ingestion runtime)

- Message contract tests, HMAC validation and anomaly detection.
- Pass: packet rejection rate < 0.1 % and ingestion latency ≤ 200 ms.

## Gate 4 — Value and Operational Safety (turn closing)

- Human-in-the-Loop validation, diversion audit and fallback test.
- Pass: explicit dispatcher approval and verification that AI does not interfere
  with the real-time path.

## Immediate failure

- A principle violation (e.g. untested code merged into the main branch, or
  recommendations issued without the human gate) immediately marks the CI build
  as failed.

## Integration test focus

- New service contracts, contract changes, inter-service communication and
  shared schemas.

## References

- OWASP Top 10 (2025) matrix and SAST/SCA criteria: `security.md`.
- RITMO cycle, `feature/US-XX` branches and lanes: `ritmo-workflow.md`.
