# Multi-stage Dockerfile for persister-rs
# Stage 1: Build binary with native C/C++ toolchain for librdkafka cmake-build
FROM rust:1-slim-bookworm AS builder

WORKDIR /usr/src/persister-rs

# Install native dependencies required for compiling rdkafka (librdkafka with cmake-build)
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    build-essential \
    pkg-config \
    libssl-dev \
    libcurl4-openssl-dev \
    zlib1g-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy crate manifests and sources
COPY Cargo.toml Cargo.lock* ./
COPY src ./src
COPY tests ./tests

# Build optimized release binary
RUN cargo build --release --bin persister-rs

# Stage 2: Minimal runtime image
FROM debian:bookworm-slim AS runner

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libssl3 \
    libcurl4 \
    zlib1g \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged service user
RUN useradd -u 10001 -m -s /bin/sh persister

# Copy binary from builder stage
COPY --from=builder /usr/src/persister-rs/target/release/persister-rs /usr/local/bin/persister-rs

USER persister

EXPOSE 8082

ENV RUST_LOG=info \
    METRICS_PORT=8082 \
    METRICS_HOST=0.0.0.0

ENTRYPOINT ["/usr/local/bin/persister-rs"]
