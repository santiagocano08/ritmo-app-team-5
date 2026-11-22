# Contracts: feature 006 (decision model)

These notes describe the interfaces this feature adds or changes. They are design notes for review; the executable contracts are the JSON Schemas under `contracts/read/` (CODEOWNERS: data owner) and the tests.

| File | Interface | Phase | Cut order (plan.md) |
|---|---|---|---|
| [recommendation-1.1.0.md](recommendation-1.1.0.md) | `contracts/read/recommendation.schema.json` 1.0.0 to 1.1.0 (new action types, optional `action.speed_reduction_pct`), fixtures, generated model | 2 | never |
| [gold-recommendation.md](gold-recommendation.md) | `gold.recommendation`, `gold.mpc_evaluation`, `gold.decision_log`; read queries Q13 and Q11 | 2, 4 | log: second |
| [execution.md](execution.md) | Simulator side: poller read, orders, hooks, not-executed counter | 2, 3 | slow/reserve (3b, 3c): third |
| [command-event-1.1.0.md](command-event-1.1.0.md) | `contracts/read/command_event.schema.json` 1.0.0 to 1.1.0, optional `reason` | 4 | second |

Rules for the whole feature (FR-029, SC-013):

- Cut order if hours run out: phase 5, then phase 4, then 3b and 3c; phases 1, 2 and 3a never. Phase 6 (road trend) is outside the committed scope.
- Simulator environment: `SIM_DEMAND_SCALE` (default `1.0`, range 0.1 to 10) is a demo setting of the simulator, documented in `.env.example`; it is not a contract field and the model never reads it (execution.md).
- Only the two schema files change under `contracts/`, both additive. Every existing fixture still validates unchanged.
- No ADR text and no `docs/data-contract.md` line is written by this feature. The data owner writes the ADR amendments and the contract lines (including the `[006]` markers for the new tables).
- The backend reads `gold.recommendation` (Q13) and writes only `decision` events. It never writes a status or a recommendation.
