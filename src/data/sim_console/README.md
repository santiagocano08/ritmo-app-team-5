# src/data/sim_console — data simulation console

A **local test harness for the data team**, not product code and not the dispatcher console
(that one is `src/frontend/`). It starts simulator runs on an **isolated compose project
(`pfsim`)**, shows what the data platform produces (snapshots, corridor state, EWT,
recommendations, holds, projection accuracy) and lets you approve or discard a recommendation.

It is what we use to demo the decision loop: the simulator causes bunching, the dispatcher
console (`src/frontend/`, served by the `pfsim` stack on port 58080) shows it, and approving a
recommendation here closes the loop.

## Run

```bash
cp src/data/sim_console/.pfsim.env.example src/data/sim_console/.pfsim.env   # once; set POSTGRES_PASSWORD
uv run --frozen python -m src.data.sim_console.app                           # http://127.0.0.1:8090
```

Then press one of the **one-click demo** buttons (rehearsed parameters; each one resets `pfsim` and starts a new run, because scenarios are loaded at start so a seed always replays the same stream) or open
*Parámetros avanzados* for a custom run. The UI text is in Spanish, like the dispatcher console.

| Demo button | Scenario | What you see (pace 1 = 5× real time) |
|---|---|---|
| Demo completa (una sola corrida, 12 min) | `demo_full` | No restart; incidents in the first ~7 real minutes, then normal operation: 0:50 B-101 goes silent («Estimated» ~1:15, back at 1:50); 2:20 B-102 delayed 400 s; ~3:30 first recommendations; ~4:50 B-103 bunched; 6:36 B-104 breaks down for 4 simulated minutes; 7:24 normal until 12:00 |
| Operación normal | `none` | Healthy fleet, one departure every 10 simulated minutes |
| Apelotonamiento y recomendación | `c1_bunching` | B-102 delayed 400 s → gap; B-103 bunched; first recommendation after ~3 real minutes |
| Bus varado | `c5_breakdown` | B-102 breaks down for 4 min around 17:20 simulated time |

All presets: demand scale 3, seed 42, holds and decision model on; 2700 s (Demo completa: 3600 s). The console shows a **countdown to the next event** of the running scenario (real time = Δsimulated × pace / 5).

**What approving does.** An approved recommendation becomes `applied` through the command door. The simulator executes **holds** (story 004) and **reserve dispatches** (006 phase 3c): the reserve bus B-106 starts reporting at P-883 about 120 simulated seconds after the approval and shows in the dispatcher console once it leaves P-883 (rehearsal 2026-11-22: approved 17:17:05, first event 17:19:20, on screen 17:21:10, 51 real seconds after the click at pace 1). `adjust_departure` and `skip_stop` stay `applied` without execution; `slow_down` comes with phase 3b (#30). See `docs/data-contract.md` §4.5.

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
