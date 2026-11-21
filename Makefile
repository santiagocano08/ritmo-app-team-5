.PHONY: generate generate-read reference up down test lint clean

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
READ_SCHEMAS := source_status corridor_now decision_inputs
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
	python -m src.reference.build

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

# --- Kubernetes (kind + Helm + Argo CD, ADR-0005). Guide: deploy/README.md ------------
KIND_CLUSTER := pulsoflota
K8S_NS := pulsoflota
CHART := deploy/helm/pulsoflota
ARGOCD_VERSION := v3.6.2

.PHONY: kind-up kind-down kind-load kind-deploy argocd-install sync-db-init

# Create the kind cluster (web on 127.0.0.1:8180, api on 127.0.0.1:8100).
kind-up:
	kind create cluster --config deploy/kind/cluster.yaml

kind-down:
	kind delete cluster --name $(KIND_CLUSTER)

# Build both images locally and load them into kind (no registry needed).
kind-load:
	docker build -t pulsoflota-app:local --target prod .
	docker build -t pulsoflota-web:local web
	kind load docker-image pulsoflota-app:local pulsoflota-web:local --name $(KIND_CLUSTER)

# Install or upgrade the chart with the local images (needs the pulsoflota-db Secret).
kind-deploy:
	helm upgrade --install pf $(CHART) -n $(K8S_NS) -f $(CHART)/values-kind.yaml \
	  --set image.app.repository=pulsoflota-app --set image.app.tag=local \
	  --set image.web.repository=pulsoflota-web --set image.web.tag=local \
	  --set imagePullSecrets=null --wait --timeout 5m

argocd-install:
	kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -n argocd --server-side -f https://raw.githubusercontent.com/argoproj/argo-cd/$(ARGOCD_VERSION)/manifests/install.yaml
	kubectl -n argocd rollout status deploy/argocd-server --timeout=300s

# Copy db/init/*.sql into the chart (Helm cannot read files outside it). CI fails if they differ.
sync-db-init:
	cp db/init/*.sql $(CHART)/files/db-init/

# Remove generated and cached artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage
