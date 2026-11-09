# iot-energy-platform

End-to-end IoT smart-energy telemetry platform: MQTT → Kafka → TimescaleDB/MongoDB → Rust API,
with a Python anomaly-detection worker, plus a Kubernetes/Helm productionization of the same stack.

Full specification: [docs/PROJECT.md](docs/PROJECT.md)

## Status

| Milestone | State |
| :--- | :--- |
| M1 Compose skeleton + simulator | completed |
| M2 `ingestor-rs` | completed |
| M3 TimescaleDB schema + persister | completed |
| M4 `anomaly-worker-py` | completed |
| M5 `api-rs` | completed |
| M6 Grafana dashboards | completed |
| M7 kind cluster | in progress |
| M8 Helm chart | not started |
| M9 HPA demo | not started |
| M10 Resilience / pod-kill demo | not started |
| M11 CI green | not started |

## Layout

```
simulator/      virtual 3-phase meters, fault injection, load generator
services/       ingestor-rs, anomaly-worker-py, api-rs
deploy/         sql, grafana provisioning, mongo seed
k8s/            cluster (kind), base manifests, Helm chart
docs/           PROJECT.md, benchmarks, demo script
scripts/
```

## Quickstart

TODO after M1.

```bash
docker compose up -d
make demo-load
```

## Kubernetes

```bash
make cluster-up
helm install iot-stack ./k8s/charts/platform -f k8s/charts/platform/values-dev.yaml -n iot-platform
```

Demo: see `docs/demo.md` (autoscaling 2 → 8 pods, pod kill with zero data loss).

## Benchmarks

TODO — see `docs/benchmarks.md`.
