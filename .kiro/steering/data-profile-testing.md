---
inclusion: fileMatch
fileMatchPattern: ["tests/**/*data*", "tests/**/*ingest*", "tests/**/*contract*", "tests/**/*rules*", "tests/**/*simulat*", "tests/fixtures/**"]
---

# Data profile — Testing

Used by `create-tasks` (when generating test tasks) and `implement-code` (when writing them) in data
stories.

## Mandatory tests in every data story

1. **Contract.** Every valid example in `contracts/` passes validation and every invalid example is
   rejected with the expected reason. If the schema changes version, messages from the previous
   version are still accepted or explicitly rejected, as the ADR states.
2. **Idempotency.** Ingesting the same batch twice leaves bronze, silver and gold unchanged.
3. **Bronze immutability.** No operation updates or deletes bronze rows.
4. **Turn 1 data faults:**
   - *Duplicates:* the duplicate is discarded and recorded as such.
   - *Source outage:* a bus with no reports for more than 2 min becomes "Estimated" and raises no
     alert.
5. **Lineage.** A gold aggregate can be traced to its bronze events and to the rules version.

## Test data

- Small, deterministic fixtures in `tests/fixtures/`, with a fixed seed. No unseeded random data.
- Demo scenarios (bunching, gap, surge, accident, broken-down bus, data fault) are generated with
  the simulator in **forced mode**: fixed time and seed.
- Never use real data with PII. The Helsinki HFP message format is only a template; **its numbers
  are not used**.

## Coverage

Minimum coverage is the constitution's (> 80 %). Quality rules in `rules/` should be close to 100 %,
because they protect the metric.
