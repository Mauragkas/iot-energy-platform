"""Worker configuration via environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerConfig:
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka_input_topic: str = os.getenv("KAFKA_INPUT_TOPIC", "iot.telemetry.raw")
    kafka_alert_topic: str = os.getenv("KAFKA_ALERT_TOPIC", "iot.alerts")
    kafka_group_id: str = os.getenv("KAFKA_GROUP_ID", "iot-anomaly-group")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/iot_energy",
    )
    metrics_port: int = int(os.getenv("METRICS_PORT", "8083"))
    window_capacity: int = int(os.getenv("WINDOW_CAPACITY", "60"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
