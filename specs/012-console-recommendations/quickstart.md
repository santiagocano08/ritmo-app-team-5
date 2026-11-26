# Quickstart: validation guide

Prerequisites: development Postgres running; `.env` loaded (never print it). Run only the files this story creates or changes.

**Backend**
```bash
set -a; . ./.env; set +a; export DATABASE_URL="postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:${POSTGRES_PORT:-5432}/$POSTGRES_DB"
uv run --frozen --extra dev pytest <new recommendation test files> -q --no-cov -p no:cacheprovider
```
Expect: `ok` with at most 3 items ordered by rank, only `proposed`; `stale` at age > 15 s with `[]`; `no_data` with no snapshot or another corridor; no write statements.

**Frontend** (Node container, no `-e TZ`)
```bash
docker run --rm -v "$PWD":/repo -w /repo/src/frontend node:22.11.0-alpine sh -c './node_modules/.bin/vitest run tests/recommendations && ./node_modules/.bin/eslint src tests --ext .ts,.tsx --max-warnings 0 && ./node_modules/.bin/tsc --noEmit'
```
Expect: one card per item with the FR-007 fields; each of the 5 action labels; «En conflicto»; «Vence HH:MM» under the pinned zone; markup reason shown literally; empty, stale and no-data messages; no button in the panel; 5 s refetch.

**Manual (mock mode)**: open *Central en vivo*; the panel sits right of the fleet list (about 400 px) and shows the c1_bunching fixture card.
