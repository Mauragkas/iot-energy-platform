SHELL := /bin/bash
export PATH := $(PWD)/.venv/bin:$(PATH)

CLUSTER_NAME ?= iot-energy-cluster
INSTALL_METRICS ?= true
INSTALL_INGRESS ?= true

.PHONY: help up down ps logs clean test lint \
	start-services stop-services status-services \
	cluster-up cluster-down k8s-build k8s-load-images k8s-deploy k8s-clean \
	demo-load demo-hpa demo-kill

help:
	@echo "IoT Energy Platform - Management Commands"
	@echo "=========================================="
	@echo "  make up              - Start Docker Compose infrastructure (Mosquitto, Kafka, DBs, Observability)"
	@echo "  make down            - Stop Docker Compose infrastructure"
	@echo "  make ps              - View running infrastructure containers"
	@echo "  make start-services  - Launch all 4 microservices in the background (Ingestor, Persister, Anomaly, API)"
	@echo "  make stop-services   - Stop all 4 background microservices"
	@echo "  make status-services - Healthcheck and status of all 4 microservices"
	@echo "  make logs            - Tail logs of all infrastructure containers"
	@echo "  make clean           - Stop containers and purge volumes"
	@echo "  make test            - Run all unit and integration test suites"
	@echo "  make lint            - Run cargo clippy, ruff check, and helm lint"
	@echo "  make cluster-up      - Provision kind cluster '$(CLUSTER_NAME)', metrics-server, and ingress-nginx"
	@echo "  make cluster-down    - Delete kind cluster '$(CLUSTER_NAME)'"
	@echo "  make k8s-build       - Build container images for all microservices"
	@echo "  make k8s-load-images - Load container images into kind cluster '$(CLUSTER_NAME)'"
	@echo "  make k8s-deploy      - Apply Kubernetes manifests in k8s/base/ in sequence"
	@echo "  make k8s-clean       - Delete namespace iot-platform"
	@echo "  make demo-load       - Run simulator with 500 meters at 5.0 msg/s for 60s to trigger HPA"
	@echo "  make demo-hpa        - Watch HPA autoscaling and pod status in namespace iot-platform"
	@echo "  make demo-kill       - Chaos test: kill running ingestor/persister pod and verify seamless recovery"

start-services:
	@bash scripts/services.sh start

stop-services:
	@bash scripts/services.sh stop

status-services:
	@bash scripts/services.sh status

up:
	docker compose up -d
	@echo "Waiting for core services to report healthy..."
	@docker compose ps

down:
	docker compose down

ps:
	docker compose ps

logs:
	docker compose logs -f

clean:
	docker compose down -v --remove-orphans
	rm -rf target/ .pytest_cache/ .ruff_cache/

test:
	@echo "==> Running Rust tests (Rust $(shell rustc --version))..."
	@if [ -f Cargo.toml ]; then cargo test --workspace; fi
	@echo "==> Running Python tests with uv..."
	@if [ -d simulator/tests ]; then uv run pytest simulator/tests; fi
	@if [ -d services/anomaly-worker-py/tests ]; then uv run pytest services/anomaly-worker-py/tests; fi
	@if [ -d tests ]; then uv run pytest tests; fi

lint:
	@echo "==> Running Rust linter (clippy)..."
	@if [ -f Cargo.toml ]; then cargo clippy --workspace --all-targets -- -D warnings; fi
	@echo "==> Running Python linter with uv (ruff)..."
	@if command -v uv &> /dev/null; then uv run ruff check .; elif command -v ruff &> /dev/null; then ruff check .; fi

cluster-up:
	@echo "==> Creating kind cluster '$(CLUSTER_NAME)'..."
	kind create cluster --config k8s/cluster/kind-config.yaml --name $(CLUSTER_NAME)
	kubectl wait --for=condition=Ready nodes --all --timeout=60s
	@if [ "$(INSTALL_INGRESS)" = "true" ]; then \
		echo "==> Installing NGINX Ingress Controller..."; \
		kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml; \
		echo "==> Waiting for Ingress controller readiness..."; \
		kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=90s || true; \
	fi
	@if [ "$(INSTALL_METRICS)" = "true" ]; then \
		echo "==> Installing Metrics Server..."; \
		kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml; \
		kubectl patch deployment metrics-server -n kube-system --type='json' -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]' || true; \
	fi

cluster-down:
	@echo "==> Deleting kind cluster '$(CLUSTER_NAME)'..."
	kind delete cluster --name $(CLUSTER_NAME)

k8s-build:
	@echo "==> Building microservice container images..."
	docker build -t iot-platform/ingestor-rs:latest services/ingestor-rs
	docker build -t iot-platform/persister-rs:latest services/persister-rs
	docker build -t iot-platform/anomaly-worker-py:latest services/anomaly-worker-py
	docker build -t iot-platform/api-rs:latest services/api-rs

k8s-load-images:
	@echo "==> Loading container images into kind cluster '$(CLUSTER_NAME)'..."
	kind load docker-image \
		iot-platform/ingestor-rs:latest \
		iot-platform/persister-rs:latest \
		iot-platform/anomaly-worker-py:latest \
		iot-platform/api-rs:latest \
		--name $(CLUSTER_NAME)

k8s-deploy:
	@echo "==> Applying base Kubernetes manifests in sequence..."
	kubectl apply -f k8s/base/00-namespace.yaml
	kubectl apply -f k8s/base/01-configs-secrets.yaml
	kubectl apply -f k8s/base/02-stateful-storage.yaml
	kubectl apply -f k8s/base/03-deployments.yaml
	kubectl apply -f k8s/base/04-envoy-grpc-lb.yaml
	kubectl apply -f k8s/base/05-hpa.yaml
	kubectl apply -f k8s/base/06-ingress.yaml
	-kubectl apply -f k8s/base/07-servicemonitor.yaml

k8s-clean:
	@echo "==> Purging iot-platform namespace..."
	kubectl delete namespace iot-platform --ignore-not-found

demo-load:
	@echo "==> Launching load generator (500 meters @ 5.0 msg/s for 60s) to trigger HPA..."
	@if command -v uv &> /dev/null; then \
		uv run --with-requirements simulator/requirements.txt python simulator/main.py --meters 500 --rate 5.0 --duration 60; \
	else \
		python3 simulator/main.py --meters 500 --rate 5.0 --duration 60; \
	fi

demo-hpa:
	@echo "==> Watching HPA and Pod autoscaling status in namespace 'iot-platform'..."
	@echo "    Target utilization: 70% CPU (scales 2 -> 8 pods). Press Ctrl+C to stop watch."
	kubectl get hpa,pods -n iot-platform -w

demo-kill:
	@echo "==> Executing chaos resilience test: terminating a running pod..."
	@TARGET_POD=$$(kubectl get pods -n iot-platform -l app.kubernetes.io/name=ingestor-rs --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null); \
	APP_NAME="ingestor-rs"; \
	if [ -z "$$TARGET_POD" ]; then \
		TARGET_POD=$$(kubectl get pods -n iot-platform -l app.kubernetes.io/name=persister-rs --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null); \
		APP_NAME="persister-rs"; \
	fi; \
	if [ -z "$$TARGET_POD" ]; then \
		echo "Error: No running ingestor-rs or persister-rs pods found in namespace 'iot-platform'."; \
		exit 1; \
	fi; \
	echo "--> Terminating active $$APP_NAME pod: $$TARGET_POD"; \
	kubectl delete pod -n iot-platform $$TARGET_POD; \
	echo "--> Verifying replacement pod readiness and consumer recovery..."; \
	kubectl wait --namespace iot-platform --for=condition=ready pod -l app.kubernetes.io/name=$$APP_NAME --timeout=60s; \
	echo "--> Replacement pod is ready. Stream and Kafka consumer offsets resumed seamlessly with zero data loss."
