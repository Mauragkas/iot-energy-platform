SHELL := /bin/bash
export PATH := $(PWD)/.venv/bin:$(PATH)
.PHONY: help up down ps logs clean test lint cluster-up cluster-down k8s-deploy demo-load demo-hpa demo-kill

help:
	@echo "IoT Energy Platform - Management Commands"
	@echo "=========================================="
	@echo "  make up           - Start Docker Compose infrastructure (Mosquitto, Kafka, DBs, Observability)"
	@echo "  make down         - Stop Docker Compose infrastructure"
	@echo "  make ps           - View running infrastructure containers"
	@echo "  make logs         - Tail logs of all infrastructure containers"
	@echo "  make clean        - Stop containers and purge volumes"
	@echo "  make test         - Run all unit and integration test suites"
	@echo "  make lint         - Run cargo clippy, ruff check, and helm lint"
	@echo "  make cluster-up   - Provision kind cluster and ingress infrastructure"
	@echo "  make cluster-down - Delete kind cluster"
	@echo "  make k8s-deploy   - Deploy platform Helm chart to kind"
	@echo "  make demo-load    - Run high-throughput load generator for HPA demo"
	@echo "  make demo-hpa     - Watch HPA autoscaling in action"
	@echo "  make demo-kill    - Chaos pod-kill test during active stream"

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
	@echo "==> Running Rust tests..."
	@if [ -f Cargo.toml ]; then cargo test --all; fi
	@echo "==> Running Python tests..."
	@if [ -d simulator/tests ]; then pytest simulator/tests; fi
	@if [ -d services/anomaly-worker-py/tests ]; then pytest services/anomaly-worker-py/tests; fi

lint:
	@echo "==> Running Rust linter..."
	@if [ -f Cargo.toml ]; then cargo clippy --all-targets -- -D warnings; fi
	@echo "==> Running Python linter..."
	@if command -v ruff &> /dev/null; then ruff check .; fi

cluster-up:
	@echo "==> Creating kind cluster..."
	kind create cluster --config k8s/cluster/kind-config.yaml --name iot-cluster
	kubectl wait --for=condition=Ready nodes --all --timeout=60s
	@echo "==> Installing NGINX Ingress Controller..."
	kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
	kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=90s

cluster-down:
	kind delete cluster --name iot-cluster

k8s-deploy:
	helm upgrade --install iot-stack ./k8s/charts/platform -f ./k8s/charts/platform/values-dev.yaml -n iot-platform --create-namespace

demo-load:
	@echo "==> Launching load generator (2000 virtual meters @ 50 msg/s)..."
	python3 simulator/main.py --mode load --meters 2000 --rate 50

demo-hpa:
	kubectl get hpa,pods -n iot-platform -w

demo-kill:
	@echo "==> Triggering chaos pod deletion..."
	@POD=$$(kubectl get pods -n iot-platform -l app.kubernetes.io/component=ingestor -o jsonpath='{.items[0].metadata.name}'); \
	echo "Deleting ingestor pod: $$POD"; \
	kubectl delete pod -n iot-platform $$POD
