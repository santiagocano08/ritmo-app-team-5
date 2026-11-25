# Quickstart: Effect Result Rule

Prerequisite: development Postgres running; `.env` present (not needed by the rule itself, but the test harness loads it).

```bash
set -a; . ./.env; set +a; export DATABASE_URL="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:${POSTGRES_PORT:-5432}/$POSTGRES_DB"
uv run --frozen --extra dev pytest src/data/tests/unit/test_effect_result.py -q --no-cov -p no:cacheprovider
```

Expected: all cases pass (50 % boundary, saving ≤ 0 with and without headway gain, coverage 0.89 vs 0.90, null inputs, expected saving ≤ 0, configurable ratio/coverage/planned headway).

Coverage of the module alone (SC-002):
`uv run --frozen --extra dev pytest src/data/tests/unit/test_effect_result.py -q -p no:cacheprovider --cov=src/data/rules/effect_result --cov-report=term-missing --cov-fail-under=100`

Check `git status`: only the two new files under `src/` appear.
