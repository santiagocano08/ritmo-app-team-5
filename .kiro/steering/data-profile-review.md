---
inclusion: fileMatch
fileMatchPattern: ["contracts/**", "db/**", "docs/adr/**", "**/ingestion/**", "**/reference/**", "**/rules/**", "**/simulator/**", "data/reference/**"]
---

# Data profile — Review

Used by `review-code` when a change touches data code or data design. It complements its general
criteria; it does not replace them.

## Data review checklist

- [ ] **Rules not weakened.** No rule in `rules/` was relaxed (more permissive threshold, removed
      check, new exception) to make CI pass. If it changed, an approved ADR justifies it. If not,
      it is a **CRITICAL** finding.
- [ ] **Contract respected.** The code uses exactly the fields of the approved JSON Schema. A new
      field without an ADR is a **CRITICAL** finding.
- [ ] **Bronze immutable.** No `UPDATE` or `DELETE` on bronze.
- [ ] **Idempotency and deduplication** tested (see `data-profile-testing.md`).
- [ ] **Lineage.** New aggregates record the rules version and their bronze origin.
- [ ] **Privacy.** Logs, fixtures and rejections contain no PII of drivers or riders.
- [ ] **Clean real time.** No call to an LLM or synchronous external service on the ingestion or
      decision path.
- [ ] **Turn scope.** If the change implements something deferred in `docs/turns-ritmo.md`, record
      it as `evolution` (LOW) and ask whether it is really needed.

Changes in `contracts/` and `rules/` also require approval from the data owner (CODEOWNERS), even if
this review passes.
