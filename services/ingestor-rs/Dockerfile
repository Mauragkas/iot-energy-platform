# ==============================================================================
# Multi-stage Dockerfile for IoT Smart-Energy Ingestion Bridge (ingestor-rs)
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder
# ------------------------------------------------------------------------------
FROM rust:1.80-slim-bookworm AS builder

# Install build dependencies for cmake and rdkafka C-bindings
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    build-essential \
    pkg-config \
    libssl-dev \
    zlib1g-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/ingestor-rs

# Copy manifests and source code
COPY Cargo.toml Cargo.lock* ./
COPY src ./src
COPY tests ./tests

# Build optimized release binary
RUN cargo build --release --bin ingestor-rs

# ------------------------------------------------------------------------------
# Stage 2: Runtime
# ------------------------------------------------------------------------------
FROM debian:bookworm-slim AS runtime

# Install runtime shared libraries and certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Run as non-root user for container security
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser

WORKDIR /app

# Copy binary from builder
COPY --from=builder /usr/src/ingestor-rs/target/release/ingestor-rs /app/ingestor-rs

USER appuser

# Expose Prometheus metrics and healthcheck port
EXPOSE 8081

ENV RUST_LOG=info \
    METRICS_PORT=8081

ENTRYPOINT ["/app/ingestor-rs"]
