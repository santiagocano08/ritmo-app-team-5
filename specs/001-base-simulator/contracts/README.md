# Interface Contracts — Turn-1 Run Environment and Base Simulator

**Feature**: 001-base-simulator | **Turn**: 1 (active) | **Date**: 2026-11-17

This directory documents the **interfaces this feature exposes**. The
authoritative event message contract already exists at the repo root
(`contracts/turn1-events/`, v1.0.0, ADR-0001/ADR-0002); this feature **consumes**
it and does not change it. Per Contract-First (Principle II), the Pydantic V2
validation models are **generated** from those schemas with
`datamodel-code-generator` — never hand-written (R3).

## Interfaces

| File | Interface | Direction |
|---|---|---|
| `ingestion-boundary.md` | The ingestion boundary contract (validates envelopes; valid → bronze, invalid/duplicate → rejections) | inbound |
| `api-health.md` | The API service health-check endpoint (`GET /healthz`) | outbound (HTTP) |
| `reference-data-files.md` | The curated reference-data file formats under `data/reference/` | file contract |
| `simulator-cli.md` | The base-simulator CLI (seed + duration → JSON-lines envelopes on stdout) | CLI contract |

## Authority and change control

- **Event message shape**: `contracts/turn1-events/*` is authoritative. A change
  there (versioned per the contract README) is the only way to change the
  envelope or payload. This directory only references it.
- **Rejection reasons / idempotency**: fixed by the contract and ADR-0001;
  re-stated here for convenience, not redefined.
- **Other interfaces** (API health, reference-data files, simulator CLI): owned
  by this story; changes here are reviewed as part of this feature.
