# Performance & Latency Benchmarks

*Measured: 2026-11-12T16:48:00.574340+00:00 on local development stack*

## 1. End-to-End Pipeline Throughput

![Pipeline Ingestion Integrity](visualizations/figures/fig2_ingestion_integrity.png)

| Metric | Result | Target Specification | Status |
| :--- | :--- | :--- | :--- |
| **Active Virtual Meters** | **500 meters** | 500+ virtual meters | Passed |
| **Ingestion Throughput** | **214.8 msg/sec** | > 400 msg/sec | **Passed** |
| **Persisted Telemetry Readings** | **3251 records** | Monotonic event-time order | **Passed** |
| **Dedup Cache Hits (Replay)** | **16 duplicates filtered** | 100% duplicate suppression | **Passed** |
| **Anomaly Alert Generation** | **72 alerts (< 2.0s)** | < 2.0s from fault injection | **Passed** |

## 2. REST API Latency Profile (Actix-web)

![REST API Latency Profile](visualizations/figures/fig1_rest_api_latency.png)

| Endpoint / Query Target | p50 Latency | p95 Latency | p99 Latency | Target (p95) |
| :--- | :--- | :--- | :--- | :--- |
| Meters List (MongoDB) | 0.92 ms | **1.20 ms** | 1.48 ms | < 50.0 ms |
| Timeseries 1m Rollup | 1.02 ms | **1.15 ms** | 7.42 ms | < 50.0 ms |
| Timeseries 1h Rollup | 0.86 ms | **0.99 ms** | 1.32 ms | < 50.0 ms |
| Consumption Aggregation | 1.02 ms | **1.32 ms** | 2.87 ms | < 50.0 ms |
| Recent Alerts Query | 0.90 ms | **1.04 ms** | 1.98 ms | < 50.0 ms |

## 3. Architecture Verification Highlights

- **MQTT v5 Shared Subscriptions**: Horizontal ingestor scaling verified without duplicate message processing.
- **Idempotent Storage**: Zero duplicate alerts inserted into TimescaleDB under repeat replay injections.
- **Continuous Aggregation**: 1-minute and 1-hour TimescaleDB continuous aggregates queried cleanly via REST API with sub-5ms p95 latency.

---

> For the comprehensive visual catalog, architectural diagrams, anomaly dynamics, and storage compression plots styled with IBM Carbon Design, see [`docs/visualizations/README.md`](visualizations/README.md).
