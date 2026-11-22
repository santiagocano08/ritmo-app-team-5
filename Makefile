.PHONY: generate generate-read reference up down test lint clean network up-split down-split

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

# --- One compose project per service (data, generator, backend, frontend) -----
# Same services as docker-compose.yml, split into four independent stacks joined
# by the external network pulsoflota-net. Start order: data -> generator/backend -> frontend.
#
# The split stacks publish the SAME host ports as the all-in-one stack (db, api,
# frontend), so the two layouts cannot run at the same time; split-guard refuses to
# start a split stack while the all-in-one project is running.
#
# The split data stack keeps its database in its own volume (pulsoflota-data_db_data),
# never in the all-in-one volume: two Postgres servers on one data directory corrupt it.
# To carry the existing data over once, stop both layouts and run `make migrate-db-volume`.
SPLIT_STACKS := data generator backend frontend
# All-in-one compose project name: compose derives it from the folder name.
MONO_PROJECT ?= $(shell basename "$(CURDIR)" | tr '[:upper:]' '[:lower:]')
DB_VOLUME_SRC ?= $(MONO_PROJECT)_db_data
DB_VOLUME_DST ?= pulsoflota-data_db_data
MIGRATE_IMAGE := alpine:3.21.3

.PHONY: network split-guard up-split down-split migrate-db-volume

network:
	docker network inspect pulsoflota-net >/dev/null 2>&1 || docker network create pulsoflota-net

split-guard:
	@if [ -n "$$(docker ps -q --filter label=com.docker.compose.project=$(MONO_PROJECT))" ]; then \
	  echo "ERROR: the all-in-one stack '$(MONO_PROJECT)' is running and publishes the same host ports"; \
	  echo "       (db, api, frontend) as the split stacks. Stop it first with 'make down' (its data volume is kept)."; \
	  exit 1; \
	fi

up-split: split-guard network
	for s in $(SPLIT_STACKS); do docker compose -f compose.$$s.yml up --build -d || exit 1; done

down-split:
	for s in frontend backend generator data; do docker compose -f compose.$$s.yml down; done

up-%: split-guard network
	docker compose -f compose.$*.yml up --build -d

down-%:
	docker compose -f compose.$*.yml down

# One-time copy of the all-in-one database volume into the split data volume.
# Both Postgres servers must be stopped (file-level copy of a cleanly shut down
# cluster; both stacks use postgres:16.11). The source volume is mounted read-only.
# Refuses a destination that already holds data: nothing is ever overwritten.
migrate-db-volume:
	@docker volume inspect $(DB_VOLUME_SRC) >/dev/null 2>&1 || { echo "ERROR: source volume $(DB_VOLUME_SRC) not found"; exit 1; }
	@for v in $(DB_VOLUME_SRC) $(DB_VOLUME_DST); do \
	  if [ -n "$$(docker ps -q --filter volume=$$v)" ]; then \
	    echo "ERROR: volume $$v is in use by a running container. Stop both layouts first ('make down' and 'make down-split')."; \
	    exit 1; \
	  fi; \
	done
	@docker run --rm -v $(DB_VOLUME_SRC):/from:ro $(MIGRATE_IMAGE) test -f /from/PG_VERSION || \
	  { echo "ERROR: $(DB_VOLUME_SRC) holds no Postgres cluster (no PG_VERSION); nothing to migrate."; exit 1; }
	@docker volume inspect $(DB_VOLUME_DST) >/dev/null 2>&1 || \
	  docker volume create --label com.docker.compose.project=pulsoflota-data \
	    --label com.docker.compose.volume=db_data $(DB_VOLUME_DST) >/dev/null
	@if [ -n "$$(docker run --rm -v $(DB_VOLUME_DST):/to $(MIGRATE_IMAGE) ls -A /to)" ]; then \
	  echo "ERROR: $(DB_VOLUME_DST) already holds data; nothing was copied."; \
	  echo "       To replace it, remove it yourself after checking it is disposable: docker volume rm $(DB_VOLUME_DST)"; \
	  exit 1; \
	fi
	docker run --rm -v $(DB_VOLUME_SRC):/from:ro -v $(DB_VOLUME_DST):/to $(MIGRATE_IMAGE) cp -a /from/. /to/
	@docker run --rm -v $(DB_VOLUME_SRC):/from:ro -v $(DB_VOLUME_DST):/to $(MIGRATE_IMAGE) sh -c \
	  'a=$$(find /from | wc -l); b=$$(find /to | wc -l); echo "copied $$b of $$a entries; PG_VERSION $$(cat /to/PG_VERSION 2>/dev/null || echo missing)"; [ "$$a" = "$$b" ]'
