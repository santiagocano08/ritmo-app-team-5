# src/data/test_lab — data flow viewer

A **console that shows the data and the decisions flowing through the platform**, from
the simulator's raw events to the dispatcher's answer. It runs in its own container on port
**8085**. It is a data-team harness, not product code: it starts nothing, and every query is a
`SELECT` in a read-only transaction. The one write is approving or discarding a recommendation in
the *Decisiones* tab, and only on the isolated `pfsim` stack (see below); the principal stack is
never written.

**Where it runs.** Normally inside the sim console, at http://127.0.0.1:8090/lab/ (one app, `pfsim` only; the
console's *Simulación* tab sits next to these tabs). The container on 8085 below is optional, for the principal
stack. All the page's URLs are relative, so the same `index.html` serves both.

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

## Decisiones tab: was a decision taken? (`decisions.py`)

A pre-MVP to show users the decision loop working. For the selected stack:

- **Open now**: each open recommendation with a countdown to `expires_ts` in **simulated time** (and the
  approximate real seconds, from the observed pace), with *Aprobar* / *Descartar* on `pfsim`. The click writes
  the same command-door `decision` event as the backend (`docs/data-contract.md` §4.2), checked against
  `contracts/read/command_event.schema.json` (mounted read-only). It refuses when the simulated time is past
  `expires_ts`, when the run is over, or when the recommendation already has a decision: the pipeline lets the
  first decision win, so a late click must not overturn an expiry.
- **Counts in a window** (last 5/10/15/30/60 simulated minutes or the whole run): proposed, applied, discarded,
  expired (by time, bus passed the stop, run ended), open now, % decided and median time to decide; and a
  table per 5 simulated minutes.
- **Every recommendation of the run** with its outcome, who decided and how long it took.
- **Saved runs**: the archive in `src/data/sim_console/runs/archive/` (mounted; git-ignored), with CSV/JSON
  downloads and a *Guardar esta corrida* button. The sim console saves a run on its own before every reset.

**Expiry.** `gold.recommendation` keeps every recommendation; the pipeline marks it `expired` (with `close_ts`)
when its time-to-live runs out or the bus passes the stop. When a run ends, the simulated clock stops, so an open
proposal would stay `proposed` forever: the report counts it as **expired · run ended** at the last simulated
time (run over = no simulator event for `LAB_RUN_SILENT_S`, 30 s). This is derived in the report
(`src/data/sim_console/report.py`, shared with the sim console); nothing is written to gold.

## Resultados tab: does the corridor work better? (`src/data/sim_console/outcomes.py`)

To show users the model is valid. From gold only:

- **Now**: buses in service (and the run's maximum), free reserves (ids), free drivers, bunched and gaps, mean
  wait vs scheduled wait, EWT, P(board within 5/10/15 min) (`gold.stop_boarding_band`), decisions applied/proposed.
- **Charts over the run** (simulated time): mean and scheduled wait; buses in service and bunched. Decisions are
  vertical marks (applied, discarded, expired) with a hover tooltip.
- **Did the decisions help?** For every closed recommendation: the mean wait at the close and 15 simulated minutes
  later. EWT uses a trailing 15-minute window, so those are two windows that do not overlap. Better = at least
  5 s lower, worse = at least 5 s higher. A run that stops first gives "not measured". Applied vs not applied
  (discarded + expired) are compared as groups. This is **descriptive, not causal**. The official verdict is the
  ADR-0007 effect rule (`rules/effect.py`, #27), which this tab does not implement.
- **Compare runs**: saved runs with average wait, EWT, P(board ≤ 10 min) and % of time bunched. The simulator is
  deterministic, so the strong test is the same seed/scenario/hour run once without deciding and once applying.

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

No contract change: it reads `bronze`, `silver`, `gold` and `config`. The only write is the existing
command-door `decision` event (§4.2, `command_event` 1.0.0) on `pfsim`, the same message the backend
and the sim console write. The "expired · run ended" outcome lives in the report, not in gold.
Excluded from coverage (`pyproject.toml`), like `sim_console`.
