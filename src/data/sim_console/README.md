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

Then press one of the **one-click demo** buttons (rehearsed parameters) or open
*Parámetros avanzados* for a custom run. The UI text is in Spanish, like the dispatcher console.

| Demo button | Scenario | What you see (pace 1 = 5× real time) |
|---|---|---|
| Operación normal | `none` | Healthy fleet, one departure every 10 simulated minutes |
| Apelotonamiento y recomendación | `c1_bunching` | B-102 delayed 400 s → gap; B-103 bunched; first recommendation after ~3 real minutes |
| Bus varado | `c5_breakdown` | B-102 breaks down for 4 min around 17:20 simulated time |

All presets: demand scale 3, seed 42, 2700 s, holds and decision model on.

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
- `.pfsim.env` (secrets) and `runs/` (run history) are git-ignored.
- Excluded from coverage (`pyproject.toml`): it drives Docker and a browser UI.
