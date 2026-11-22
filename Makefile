.PHONY: generate generate-read reference up down test lint clean \
        up-db up-ingestion up-refresh up-api up-frontend \
        stop-db stop-ingestion stop-refresh stop-api stop-frontend

# Regenerate Pydantic V2 models from the accepted turn-1 contract schemas.
# The generated file is a build artifact — never hand-edited.
# CI asserts the committed file matches a fresh generation.
generate:
	datamodel-codegen \
	  --input contracts/turn1-events \
	  --input-file-type jsonschema \
	  --output src/pulsoflota/models/turn1_events.py \
	  --output-model-type pydantic_v2.BaseModel \
	  --use-annotated \
	  --use-double-quotes \
	  --target-python-version 3.12 \
	  --use-title-as-name \
	  --strict-nullable \
	  --enum-field-as-literal one \
	  --use-field-description \
	  --disable-timestamp

# Regenerate the Pydantic V2 models of the three gold read objects (research R9).
# One module per schema under src/pulsoflota/models/read/. Never hand-edited;
# running it twice must leave `git diff` empty.
READ_SCHEMAS := source_status corridor_now decision_inputs incident recommendation
generate-read:
	mkdir -p src/pulsoflota/models/read
	touch src/pulsoflota/models/read/__init__.py
	for name in $(READ_SCHEMAS); do \
	  datamodel-codegen \
	    --input contracts/read/$$name.schema.json \
	    --input-file-type jsonschema \
	    --output src/pulsoflota/models/read/$$name.py \
	    --output-model-type pydantic_v2.BaseModel \
	    --use-annotated \
	    --use-double-quotes \
	    --target-python-version 3.12 \
	    --use-title-as-name \
	    --strict-nullable \
	    --enum-field-as-literal one \
	    --use-field-description \
	    --disable-timestamp || exit 1; \
	done

# Build curated reference data from data/raw/ -> data/reference/
reference:
	python -m src.data.reference.build

# Start all three containers: db, ingestion, api
up:
	docker compose up --build -d

# Stop and remove all containers
down:
	docker compose down

# Run all tests with coverage (must be > 80 %)
test:
	uv run pytest $(PYTEST_ARGS)

# Lint (placeholder — SAST/SCA deferred to turn 2)
lint:
	@echo "Linting deferred to turn 2 (SAST/SCA not in turn-1 scope)"

# Remove generated and cached artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage

# --- Per-service start / stop (single docker-compose.yml) ----------------------
# One compose project, six services. `docker compose up -d --build <service>`
# rebuilds and recreates only that service's container/image. Start order for a
# cold boot is handled by depends_on (db -> ingestion/refresh/api -> frontend);
# the refresh healthcheck only goes healthy once bronze data exists, which is
# expected for the first ~40s.

up-db:
	docker compose up -d db

up-ingestion:
	docker compose up -d --build ingestion

up-refresh:
	docker compose up -d --build refresh

up-api:
	docker compose up -d --build api

up-frontend:
	docker compose up -d --build frontend

stop-db:
	docker compose stop db

stop-ingestion:
	docker compose stop ingestion

stop-refresh:
	docker compose stop refresh

stop-api:
	docker compose stop api

stop-frontend:
	docker compose stop frontend
