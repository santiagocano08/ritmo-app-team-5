# src/data/sim_console — data simulation console

A **local test harness for the data team**, not product code and not the dispatcher console
(that one is `src/frontend/`). Its **Simulación** tab starts, stops and deletes simulator runs on an isolated
compose project (`pfsim`) and shows only the run itself: demo buttons, start hour, countdown to the scenario's
events, simulated time, data age, source and services. Everything else lives in the other tabs (see *One app on
8090*): the data flow, the decision model, the decisions (the only place to approve or discard) and the results,
including how well the model's projection matched what happened.

It is what we use to demo the decision loop: the simulator causes bunching, the dispatcher
console (`src/frontend/`, served by the `pfsim` stack on port 58080) shows it, and approving a
recommendation here closes the loop.

## One app on 8090

The console is the single entry point for the demo: **Simulación** (this page: launch, stop, countdown, status)
and, mounted at `/lab/`, the data flow viewer of `src/data/test_lab` with its tabs **Flujo**, **¿Qué pasa si…?**,
**Decisiones** (the only place to approve or discard) and **Resultados** (fleet, waits, P(board), effect of each
decision, A/B of saved runs). They read this console's `pfsim` stack. The 8085 container of the viewer is optional
and only needed to look at the principal stack.

## Run

```bash
cp src/data/sim_console/.pfsim.env.example src/data/sim_console/.pfsim.env   # once; set POSTGRES_PASSWORD
uv run --frozen python -m src.data.sim_console.app                           # http://127.0.0.1:8090
```

Then press one of the **one-click demo** buttons (rehearsed parameters; each one resets `pfsim` and starts a new run, because scenarios are loaded at start so a seed always replays the same stream) or open
*Parámetros avanzados* for a custom run. The UI text is in Spanish, like the dispatcher console.

| Demo button | Scenario | What you see (pace 1 = 5× real time) |
|---|---|---|
| Demo completa (una sola corrida, 30 min: 3600 simulated s at pace 2.5, since 2026-11-23; was 12 min at pace 1) | `demo_full` | No restart; incidents in the first ~7 real minutes, then normal operation: 0:50 B-101 goes silent («Estimated» ~1:15, back at 1:50); 2:20 B-102 delayed 400 s; ~3:30 first recommendations; ~4:50 B-103 bunched; 6:36 B-104 breaks down for 4 simulated minutes; 7:24 normal until 12:00 |
| Operación normal | `none` | Healthy fleet, one departure every 10 simulated minutes |
| Apelotonamiento y recomendación | `c1_bunching` | B-102 delayed 400 s → gap; B-103 bunched; first recommendation after ~3 real minutes |
| Bus varado | `c5_breakdown` | B-102 breaks down for 4 min around 17:20 simulated time |

All presets: demand scale 5 (3 until 2026-11-23), seed 42, holds and decision model on; 2700 s at pace 1 (Demo completa: 3600 s at pace 2.5 = 30 real minutes).

**Warm-up.** *Demo completa* (scenario `demo_live`) starts with `SIM_WARMUP_S=1500`: the first 25 simulated minutes
are written without the pace (in a few seconds), so the paced demo opens with the corridor full of buses, the metric
windows filled and recommendations to decide from the first minute (rehearsal 2026-11-23: first two recommendations
16 real seconds after *running*). Its incidents sit around the end of the warm-up (B-103 delayed at P-887 during it,
B-101 silent at +1 min, B-104 breaks down at +10 min). Duration 5100 s = warm-up + 60 paced minutes at pace 2.5 =
30 real minutes. The *Calentamiento* field of the custom run sets it for any scenario. After a console restart, the
running run is picked up from `runs/history.jsonl` so the countdown survives.

**Start hour.** The *Hora de inicio simulada* selector above the buttons (default 17:00, the rehearsed evening peak) sets the local hour the simulated day starts at (`SIM_START_HOUR`, 0–23) for the buttons and for the custom run. Congestion, street demand and metro trains follow that hour; incidents keep their offsets. The rehearsed "visible" times were measured at 17:00, so at another hour the dispatcher console can show them sooner or later. 00:00–03:00 and 23:00 have no metro and no reference demand. The console shows a **countdown to the next event** of the running scenario (real time = Δsimulated × pace / 5).

**What approving does.** An approved recommendation becomes `applied` through the command door. The simulator executes **holds** (story 004) and **reserve dispatches** (006 phase 3c): a reserve bus (B-108..B-111 since contract v0.5; B-106 in the rehearsal below) starts reporting at P-883 about 120 simulated seconds after the approval and shows in the dispatcher console once it leaves P-883 (rehearsal 2026-11-22: approved 17:17:05, first event 17:19:20, on screen 17:21:10, 51 real seconds after the click at pace 1). `adjust_departure` and `skip_stop` stay `applied` without execution; `slow_down` comes with phase 3b (#30). See `docs/data-contract.md` §4.5.

**Saved runs.** Each run's recommendations and decisions are saved to `runs/archive/<run_key>/`
(`report.json` with everything, `recommendations.csv` one row per recommendation) **before every reset**
(a new run or *Borrar stack*), on *Detener simulador* and when the run ends; `POST /api/archive` saves on demand,
`GET /api/runs` lists them. Every recommendation gets its outcome: applied, discarded or expired (time, bus passed
the stop, or **run ended**: the simulated clock stops with the simulator, so a proposal still open then is closed
in the report at the last simulated time). The decision buttons refuse a recommendation whose `expires_ts` is past
in simulated time or whose run is over. The data flow viewer (8085, *Decisiones* tab) shows the same report.

## Ports (`pfsim` never touches the default stack or its `db_data` volume)

| Service | Host port |
|---|---|
| Dispatcher console (`frontend`) | 58080 |
| API | 58100 (listens on 8000 inside the network: the frontend's Nginx proxies to `api:8000`) |
| PostgreSQL | 56432 |
| This console | 8090 (`SIM_CONSOLE_PORT` to change) |

## Data contract

No contract change. Approve/discard writes a `decision` event to `bronze.events` through the
command door (`docs/data-contract.md` §4.2), validated against
`contracts/read/command_event.schema.json` — the same message the backend writes. It does so only
on the isolated `pfsim` database.

## Safety

- Binds to `127.0.0.1` only.
- Runs fixed `docker compose` argument lists on project `pfsim` (no shell, no free text).
- Every run parameter is validated against an allow-list or a numeric range.
- `IMAGE_TAG=pfsim` in `.pfsim.env`: the compose images are named `pulsoflota/<service>:${IMAGE_TAG}`, so a pfsim build never replaces the default stack images (`:dev`).
- `.pfsim.env` (secrets) and `runs/` (run history) are git-ignored.
- Excluded from coverage (`pyproject.toml`): it drives Docker and a browser UI.
