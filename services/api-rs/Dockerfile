# ==============================================================================
# Multi-stage Dockerfile for IoT REST API Service (api-rs)
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder
# ------------------------------------------------------------------------------
FROM rust:1-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src/api-rs

# Copy manifests and source code
COPY Cargo.toml Cargo.lock* ./
COPY src ./src
COPY tests ./tests

# Build optimized release binary
RUN cargo build --release --bin api-rs

# ------------------------------------------------------------------------------
# Stage 2: Runtime
# ------------------------------------------------------------------------------
FROM debian:bookworm-slim AS runtime

# Install runtime dependencies and certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged service user for security
RUN groupadd -g 10001 apiuser && \
    useradd -u 10001 -g apiuser -s /bin/sh -m apiuser

WORKDIR /app

# Copy compiled binary from builder
COPY --from=builder /usr/src/api-rs/target/release/api-rs /usr/local/bin/api-rs

USER apiuser

# Expose HTTP API port
EXPOSE 8080

ENV RUST_LOG=info \
    PORT=8080 \
    HOST=0.0.0.0

ENTRYPOINT ["/usr/local/bin/api-rs"]
