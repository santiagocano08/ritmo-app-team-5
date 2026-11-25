# Quickstart: validate the Spanish reasons

Prerequisites: the development Postgres is running; `.env` present (never print it).

```bash
set -a; . ./.env; set +a; export DATABASE_URL="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:${POSTGRES_PORT:-5432}/$POSTGRES_DB"
uv run --frozen --extra dev pytest src/data/tests/unit/test_mpc_ranking.py src/data/tests/unit/test_mpc_lifecycle.py -q --no-cov -p no:cacheprovider
```

Expected: both pass; `test_mpc_ranking.py` asserts the five templates from [data-model.md](data-model.md) (hold `retener B-103 60 s en P-888 ahorra 22 s por pasajero`).

Fixtures (SC-002): run the existing contract/fixture validation test over `contracts/read/fixtures/*/recommendation.json` (locate it with `grep -rl "fixtures" src/data/tests/unit`); all six validate and their reasons are Spanish.

Fast area check: `src/data/tests/unit`.

Docs check: `docs/data-contract.md` §4.5 contains the one-line statement about `reason`.
