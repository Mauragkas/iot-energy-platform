"""Prometheus metrics server and collectors on port 8083."""

from __future__ import annotations

import logging

from prometheus_client import Counter, Histogram, start_http_server

logger = logging.getLogger(__name__)

# Core Prometheus metrics required by specifications
ALERTS_EMITTED_TOTAL = Counter(
    "alerts_emitted_total",
    "Total alerts emitted by anomaly worker",
    ["alert_type", "severity"],
)

PROCESSING_LAG_SECONDS = Histogram(
    "processing_lag_seconds",
    "End-to-end processing lag from reading timestamp to alert detection in seconds",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

READINGS_PROCESSED_TOTAL = Counter(
    "readings_processed_total",
    "Total telemetry readings processed by anomaly worker",
)

WINDOW_RESETS_TOTAL = Counter(
    "window_resets_total",
    "Total sliding window resets due to rebalance or error",
)

_server_started = False


def record_alert_emitted(alert_type: str, severity: str) -> None:
    """Increment alerts emitted counter with labels."""
    ALERTS_EMITTED_TOTAL.labels(alert_type=alert_type, severity=severity).inc()


def record_processing_lag(seconds: float) -> None:
    """Record processing latency in histogram."""
    if seconds >= 0.0:
        PROCESSING_LAG_SECONDS.observe(seconds)


def record_reading_processed() -> None:
    """Increment processed reading counter."""
    READINGS_PROCESSED_TOTAL.inc()


def record_window_reset() -> None:
    """Increment window resets counter."""
    WINDOW_RESETS_TOTAL.inc()


def start_metrics_server(port: int = 8083) -> None:
    """Start Prometheus HTTP server on specified port."""
    global _server_started
    if not _server_started:
        try:
            start_http_server(port)
            _server_started = True
            logger.info("Prometheus metrics server started on port %d", port)
        except OSError as e:
            logger.warning("Could not start metrics server on port %d (already bound?): %s", port, e)
