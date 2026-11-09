"""Alert publisher interface and implementations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

try:
    from models import AlertEvent
except ImportError:
    from .models import AlertEvent

logger = logging.getLogger(__name__)


class AlertPublisher(ABC):
    """Abstract publisher for alert events (DIP & ISP)."""

    @abstractmethod
    def publish_alert(self, alert: AlertEvent) -> None:
        """Publish alert event to target destination."""
        pass

    @abstractmethod
    def flush(self, timeout: float = 5.0) -> None:
        """Flush any pending messages."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close producer."""
        pass


class KafkaAlertPublisher(AlertPublisher):
    """Kafka alert publisher producing to `iot.alerts` topic."""

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str = "iot.alerts",
        producer_config: Optional[dict[str, Any]] = None,
    ) -> None:
        from confluent_kafka import Producer

        config = {
            "bootstrap.servers": bootstrap_servers,
            "client.id": "anomaly-worker-publisher",
            "acks": "all",
            "retries": 3,
            "compression.type": "snappy",
        }
        if producer_config:
            config.update(producer_config)

        self.producer = Producer(config)
        self.topic = topic

    def publish_alert(self, alert: AlertEvent) -> None:
        """Publish alert to Kafka topic."""
        key = alert.meter_id.encode("utf-8")
        value = alert.to_json().encode("utf-8")

        def _on_delivery(err: Any, msg: Any) -> None:
            if err is not None:
                logger.error("Failed to deliver alert to Kafka: %s", err)
            else:
                logger.debug("Delivered alert to %s [%d] at offset %d", msg.topic(), msg.partition(), msg.offset())

        self.producer.produce(
            topic=self.topic,
            key=key,
            value=value,
            on_delivery=_on_delivery,
        )
        self.producer.poll(0)

    def flush(self, timeout: float = 5.0) -> None:
        self.producer.flush(timeout)

    def close(self) -> None:
        self.flush()


class InMemoryAlertPublisher(AlertPublisher):
    """In-memory mock publisher for unit and integration testing."""

    def __init__(self) -> None:
        self.published_alerts: list[AlertEvent] = []

    def publish_alert(self, alert: AlertEvent) -> None:
        self.published_alerts.append(alert)

    def flush(self, timeout: float = 5.0) -> None:
        pass

    def close(self) -> None:
        pass
