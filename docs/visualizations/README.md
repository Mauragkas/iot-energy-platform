# IoT Smart-Energy Platform — Verified Visualizations & Benchmarks

> Designed strictly in accordance with the **Periodic Table of Visualization Methods (PTVM)** and styled with the **IBM Carbon Design System** (*"Engineered Precision"*).
>
> **Data Integrity Guarantee**: Contains only empirical benchmarks measured by [`scripts/run_benchmarks.py`](../../scripts/run_benchmarks.py) and verified in [`docs/benchmarks.md`](../benchmarks.md). Zero synthetic mock-ups.

---

## 1. Visual Method Selection Matrix

| Figure / Asset | PTVM ID | Method Name | Communication Purpose | Core Takeaway / Visual Insight | Format |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **System Topology** | **HSA-5** | **Architecture Diagram** | Hierarchy & Structure (*clarify structure*) | Cloud-native flow from 500 edge smart meters through MQTT v5, Kafka KRaft, TimescaleDB, and Envoy L7 | Mermaid / Markdown |
| **Ingestion Protocol** | **FPS-2** | **Swimlane / Sequence** | Flow, Process & Systems (*explain process*) | MQTT v5 shared subscription consumer groups and in-memory LRU burst-replay deduplication | Mermaid / Markdown |
| **Figure 1** | **QC-6 / QC-4**| **Bullet Chart & Dot Plot** | Quantitative Comparison (*compare*) | Sub-1.55 ms REST p95 latencies beat 50 ms SLA target by over 97.6% across all 5 endpoints | Matplotlib (PNG / SVG) |
| **Figure 2** | **QC-3** | **Lollipop Chart** | Quantitative Comparison (*compare*) | 214.8 msg/s sustained ingestion with 100% gateway duplicate packet suppression (16 filtered) | Matplotlib (PNG / SVG) |

---

## 2. System Architecture & Ingestion Flow

### 2.1 Microservice Architecture Topology (`HSA-5`)

```mermaid
flowchart TD
    subgraph Edge["Edge Layer (Industrial Fleet)"]
        M1["Virtual Meter 0001<br/>(3-Phase MZ-3P)"]
        M2["Virtual Meter 0002<br/>(3-Phase MZ-3P)"]
        Mn["Virtual Meter 0500+<br/>(3-Phase MZ-3P)"]
    end

    subgraph Ingestion["Ingestion Tier (MQTT v5 & Deduplication)"]
        MOSQ["Eclipse Mosquitto Broker<br/>(MQTT v5 QoS 1)"]
        ING1["ingestor-rs Replica 1<br/>(Tokio + Shared Sub)"]
        ING2["ingestor-rs Replica 2<br/>(100k LRU Dedup Cache)"]
    end

    subgraph Streaming["Streaming Backbone (Apache Kafka KRaft)"]
        KAFKA["Apache Kafka (KRaft Mode)<br/>• iot.telemetry.raw (3 Partitions)<br/>• iot.alerts (3 Partitions)"]
    end

    subgraph Processing["Processing & Storage Tier"]
        PERS["persister-rs (Rust)<br/>• Micro-Batch Buffer (100 msgs / 200ms)<br/>• Transacted Offsets"]
        ANOM["anomaly-worker-py (Python)<br/>• Sliding-Window Grid Analytics<br/>• Idempotent Alert Writer"]
        TSDB[("TimescaleDB (PostgreSQL 16)<br/>• meter_readings Hypertable (1d chunks)<br/>• 1m, 1h, 1d Continuous Aggregates<br/>• 7-day Columnar Compression")]
        MONGO[("MongoDB 7.0<br/>• Digital Device Twins<br/>• Asset Metadata & Specs")]
    end

    subgraph Serving["Serving & Observability Tier"]
        API["api-rs (Actix-web)<br/>• Clean Layered Architecture<br/>• Sub-1.55ms Query Engine"]
        ENVOY["Envoy L7 Proxy<br/>• STRICT_DNS Headless Discovery<br/>• Round-Robin HTTP/2 Balancer"]
        GRAF["Grafana Dashboards<br/>• Grid Telemetry, Pipeline, Anomalies"]
        PROM["Prometheus 2.x<br/>• /metrics Scrape (8080/8085)"]
    end

    M1 -->|MQTT Publish| MOSQ
    M2 -->|MQTT Publish| MOSQ
    Mn -->|MQTT Publish| MOSQ

    MOSQ -->|"$share/ingestors/iot/telemetry/+"| ING1
    MOSQ -->|"$share/ingestors/iot/telemetry/+"| ING2

    ING1 -->|Keyed by meter_id| KAFKA
    ING2 -->|Keyed by meter_id| KAFKA

    KAFKA -->|Consume iot.telemetry.raw| PERS
    KAFKA -->|Consume iot.telemetry.raw| ANOM

    PERS -->|Batch COPY / INSERT| TSDB
    ANOM -->|Idempotent Alert INSERT| TSDB
    ANOM -->|Publish iot.alerts| KAFKA

    TSDB -->|Continuous Aggregates| API
    MONGO -->|Device Twin Queries| API

    API -->|Prometheus Metrics| PROM
    ING1 -->|Prometheus Metrics| PROM
    PERS -->|Prometheus Metrics| PROM
    PROM -->|Datasource| GRAF
    TSDB -->|SQL Datasource| GRAF

    CLIENTS["REST & gRPC Clients"] --> ENVOY
    ENVOY -->|Load Balanced HTTP/2| API
```

---

### 2.2 Shared Subscription & Deduplication Protocol (`FPS-2`)

```mermaid
sequenceDiagram
    autonumber
    participant Meter as Smart Meter (Gateway)
    participant Broker as Mosquitto (MQTT v5)
    participant Ingestor as ingestor-rs (Shared Sub)
    participant LRU as Memory LRU Cache
    participant Kafka as Kafka (iot.telemetry.raw)

    Meter->>Broker: MQTT PUBLISH (QoS 1, packet_id: 1042)
    Note over Broker,Ingestor: $share/ingestors/iot/telemetry/+
    Broker->>Ingestor: Deliver to available replica
    Ingestor->>LRU: Check key (meter_id, timestamp)
    alt Cache Miss (Fresh Reading)
        LRU-->>Ingestor: Not Found -> Cache Key
        Ingestor->>Kafka: Produce keyed record (meter_id)
        Ingestor->>Broker: MQTT PUBACK
    else Cache Hit (Replay Burst)
        LRU-->>Ingestor: Duplicate Detected
        Note over Ingestor: Drop duplicate in-memory (0ms)
        Ingestor->>Broker: MQTT PUBACK (Suppress downstream write)
    end
```

---

## 3. High-Precision Verified Benchmark Visualizations

### Figure 1: REST API Latency Profile against SLA (`QC-6` / `QC-4`)

> **PTVM Takeaway**: All 5 core endpoints sustain sub-1.55 ms p95 response times, outperforming the 50.0 ms SLA ceiling by 97.6% under Actix-web and TimescaleDB continuous aggregates.

![Figure 1: REST API Latency Profile](figures/fig1_rest_api_latency.png)

- **Detailed Zoom**: p50 (charcoal square), p95 (IBM Blue diamond), and p99 (magenta circle).
- **Macro View**: Clear visual demonstration of the 50 ms SLA compliance margin.
- **Source Data**: [`docs/benchmarks.md`](../benchmarks.md#2-rest-api-latency-profile-actix-web)
- **Vector Source**: [`figures/fig1_rest_api_latency.svg`](figures/fig1_rest_api_latency.svg)

---

### Figure 2: End-to-End Ingestion Pipeline Integrity (`QC-3`)

> **PTVM Takeaway**: The Tokio-based `ingestor-rs` layer sustains 214.8 msg/sec ingestion across 500 active smart meters, processing 3,251 records with 100% duplicate suppression (16 gateway replay packets filtered).

![Figure 2: Ingestion Pipeline Integrity](figures/fig2_ingestion_integrity.png)

- **Design Execution**: High-contrast horizontal lollipop representation highlighting the primary ingestion throughput metric against capacity and alert counts.
- **Source Data**: [`docs/benchmarks.md`](../benchmarks.md#1-end-to-end-pipeline-throughput)
- **Vector Source**: [`figures/fig2_ingestion_integrity.svg`](figures/fig2_ingestion_integrity.svg)

---

## 4. Reproducibility

To re-generate the verified visualization assets (both 300 DPI PNG and vector SVG formats):

```bash
python3 scripts/generate_ptvm_visualizations.py
```
