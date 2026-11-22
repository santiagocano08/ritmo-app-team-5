# src/data — data code

**Owner:** data team (data owner reviews contracts, rules and data ADRs; see `.github/CODEOWNERS`).

## Layers and modules

| Path | What it holds |
|------|---------------|
| `simulator/` | Turn-1 event simulator (stdout JSON lines). |
| `ingestion/` | Boundary validation and **bronze** inserts (immutable). |
| `db/init/` | `001..005_*.sql`: schemas, **bronze**, **config** (reference tables), **silver**, **gold**. |
| `rules/` | Deterministic quality and metric rules, plus `rules/sql/` (silver/gold SQL). |
| `reference/` | Code that builds the reference CSVs from `data/raw/`. |
| `pipeline/` | Silver rebuild, gold snapshot and the `compute` CLI. |
| `refresh/` | Gold refresh loop and its freshness healthcheck. |
| `tests/` | Data tests (`unit/`, `integration/`, `contract/`, `fixtures/`). |
| `sim_console/` | Local simulation console for the data team (isolated `pfsim` stack, demo presets); see its README. |

Shared code stays in `src/pulsoflota/` (config, DB connection, generated contract models);
the backend is in `src/api/`.

## How to run

```bash
python -m src.data.simulator.main --seed 42 --duration 1800 | python -m src.data.ingestion.run
python -m src.data.pipeline.compute --as-of "<UTC time>"
python -m src.data.refresh.run
make reference        # python -m src.data.reference.build
python -m pytest -m "not slow and not live"        # host; needs DATABASE_URL for integration tests
docker compose --profile tools run --rm tests      # inside the compose stack
```

## Where the CSVs are

Reference data files stay at the repository root: `data/reference/*.csv` (built from `data/raw/`).
They are data, not code, so they are not under `src/`.
