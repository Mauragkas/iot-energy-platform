# Multi-stage Dockerfile for persister-rs
# Stage 1: Build binary with native C/C++ toolchain for librdkafka cmake-build
FROM rust:1-slim-bookworm AS builder

WORKDIR /usr/src/app

# Install native dependencies required for compiling rdkafka (librdkafka with cmake-build)
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    build-essential \
    pkg-config \
    libssl-dev \
    libcurl4-openssl-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy workspace configuration and sources
COPY Cargo.toml Cargo.lock ./
COPY services/persister-rs ./services/persister-rs

# Create dummy ingestor-rs package to satisfy workspace resolution when building from repo root
RUN mkdir -p services/ingestor-rs/src && \
    echo 'fn main() {}' > services/ingestor-rs/src/main.rs && \
    printf '[package]\nname = "ingestor-rs"\nversion = "0.1.0"\nedition = "2021"\n' > services/ingestor-rs/Cargo.toml

# Build optimized release binary
RUN cargo build --release -p persister-rs

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
COPY --from=builder /usr/src/app/target/release/persister-rs /usr/local/bin/persister-rs

USER persister

EXPOSE 8082

ENV RUST_LOG=info \
    METRICS_PORT=8082 \
    METRICS_HOST=0.0.0.0

ENTRYPOINT ["/usr/local/bin/persister-rs"]
