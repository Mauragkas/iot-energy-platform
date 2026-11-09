"""Kafka consumer loop consuming from `iot.telemetry.raw` with partition rebalance safety."""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from engine import AnomalyEngine
    from models import TelemetryReading
except ImportError:
    from .engine import AnomalyEngine
    from .models import TelemetryReading

logger = logging.getLogger(__name__)


class TelemetryConsumer:
    """Kafka consumer loop consuming from `iot.telemetry.raw` in group `iot-anomaly-group`."""

    def __init__(
        self,
        bootstrap_servers: str,
        engine: AnomalyEngine,
        topic: str = "iot.telemetry.raw",
        group_id: str = "iot-anomaly-group",
        consumer_config: Optional[dict[str, Any]] = None,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.engine = engine
        self.topic = topic
        self.group_id = group_id
        self.consumer_config = consumer_config or {}
        self.running: bool = False
        self._consumer = None

    def _init_consumer(self):
        from confluent_kafka import Consumer

        config = {
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": self.group_id,
            "auto.offset.reset": "latest",
            "enable.auto.commit": True,
            "session.timeout.ms": 10000,
            "max.poll.interval.ms": 300000,
        }
        config.update(self.consumer_config)

        consumer = Consumer(config)

        def _on_assign(c, partitions):
            logger.info("Consumer assigned partitions: %s", [p.partition for p in partitions])
            c.assign(partitions)

        def _on_revoke(c, partitions):
            logger.warning(
                "Consumer partitions revoked: %s. Clearing in-memory windows for rebalance safety.",
                [p.partition for p in partitions],
            )
            # Partition rebalance safety: clear windows so we don't retain stale state
            self.engine.clear_windows()
            c.unassign()

        consumer.subscribe([self.topic], on_assign=_on_assign, on_revoke=_on_revoke)
        return consumer

    def run(self, max_messages: Optional[int] = None) -> int:
        """Run consumer loop until stopped or max_messages reached."""
        self._consumer = self._init_consumer()
        self.running = True
        processed = 0

        logger.info("Kafka consumer loop started for topic '%s' in group '%s'", self.topic, self.group_id)

        try:
            while self.running:
                msg = self._consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    logger.error("Consumer error: %s", msg.error())
                    continue

                try:
                    payload = msg.value().decode("utf-8")
                    reading = TelemetryReading.from_json(payload)
                    self.engine.process_reading(reading)
                    processed += 1
                except Exception as e:
                    logger.error("Failed to process message offset %d: %s", msg.offset(), e)

                if max_messages is not None and processed >= max_messages:
                    break
        finally:
            self.close()

        return processed

    def stop(self) -> None:
        """Signal consumer loop to terminate."""
        self.running = False

    def close(self) -> None:
        """Close Kafka consumer."""
        if self._consumer:
            try:
                self._consumer.close()
            except Exception as e:
                logger.error("Error closing Kafka consumer: %s", e)
            self._consumer = None
