# src/data/test_lab — data flow viewer

A **read-only console that shows the data and the decisions flowing through the platform**, from
the simulator's raw events to the dispatcher's answer. It runs in its own container on port
**8085**. It is a data-team harness, not product code: it starts nothing and never writes (every
query is a `SELECT` in a read-only transaction).

## The seven stages (live, every 5 s)

| # | Stage | Where it lives |
|---|---|---|
| 1 | Raw | simulator events as they land (`bronze.events`, `source = simulator`) |
| 2 | Bronze | immutable landing table, idempotent on `(source, event_id)`, `bronze.rejections` |
| 3 | Silver | `bus_current_state`, `stop_visits`, `incidents` |
| 4 | Gold · analytics | the snapshot: `corridor_now`, `service_metric` (EWT), `source_status` |
| 5 | Decision | `gold.decision_inputs`, the candidates in `gold.mpc_evaluation`, `gold.recommendation` |
| 6 | Front | what the api serves the dispatcher console (`/api/v1/corridor/{id}/now`, `source-status`) and the open recommendation documents |
| 7 | Response | the `decision` event the dispatcher writes through the command door (`bronze.events`), the status it moves the recommendation to, and `gold.instruction_status` |

Click a stage to see its rows. **Trazar una recomendación** follows one `rec_id` end to end: the
bronze cut it was computed from, the silver visits, the snapshot and inputs it used (the "why"),
the document the front shows, and the answer that came back.

## What-if tab: the decision model with your variables (`whatif.py`)

Loads the inputs of the **newest snapshot** exactly as the refresh does (`pipeline.recommend.load_inputs`), applies
your edits and runs the **same pure model** the cycle runs (`generate_candidates` → `evaluate_candidates` →
`rank_candidates`). The result is shown next to the unchanged run; nothing is written.

Editable: per in-service bus its position, occupancy, data quality, a breakdown in minutes and its `bus_state`
(set by hand: in the cycle it comes from the headway classification of `corridor_now`, which needs position
history); reserve availability; drivers free; a demand multiplier (queues, arrival rates, train batches); and the
model parameters `threshold_s_per_rider`, `reserve_cost_s`, `reserve_ready_s`, `top_n`, `queue_trigger_riders`,
`hold_options_s`. Rest keys are left empty (what would the model propose from scratch).

Needs migration 009 on the stack (`config.decision_model`); today only `pfsim` has it.

## Run

```bash
docker compose -f docker-compose.yml -f src/data/test_lab/compose.lab.yml up -d --build test-lab
# open http://localhost:8085
```

## Targets

- `pfsim` (optional, listed first): the sim-console stack (`src/data/sim_console`), read through
  its host ports (56432, 58100). Enable it with `PFSIM_DSN` in `.env`:
  `PFSIM_DSN=postgresql://<user>:<password>@host.docker.internal:56432/<db>`.
- `principal`: the default stack, read through the compose network (`db:5432`, `api:8000`).

To see the loop move, start a run in the sim console (`Demo completa`) and approve a
recommendation there or in the dispatcher console: it shows up in stage 7 within one cycle.

## Data contract

No contract change: it reads `bronze`, `silver`, `gold` and `config` and writes nothing.
Excluded from coverage (`pyproject.toml`), like `sim_console`.
