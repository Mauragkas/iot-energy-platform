"""Core anomaly detection engine coordinating sliding windows and rules."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

try:
    from detector import AnomalyRule
    from metrics import (
        record_alert_emitted,
        record_processing_lag,
        record_reading_processed,
        record_window_reset,
    )
    from models import AlertEvent, TelemetryReading
    from publisher import AlertPublisher
    from repository import AlertRepository
    from window import MeterSlidingWindow
except ImportError:
    from .detector import AnomalyRule
    from .metrics import (
        record_alert_emitted,
        record_processing_lag,
        record_reading_processed,
        record_window_reset,
    )
    from .models import AlertEvent, TelemetryReading
    from .publisher import AlertPublisher
    from .repository import AlertRepository
    from .window import MeterSlidingWindow

logger = logging.getLogger(__name__)


class AnomalyEngine:
    """Core anomaly detection coordinator adhering to DIP, OCP, and SRP.

    - Dependency Inversion Principle (DIP): Injected AlertRepository, AlertPublisher, and AnomalyRule list.
    - Open/Closed Principle (OCP): New rules are added by supplying them to the constructor without engine changes.
    - Single Responsibility Principle (SRP): Coordinates telemetry flow across windows, rules, storage, and publishing.
    """

    def __init__(
        self,
        repository: AlertRepository,
        publisher: AlertPublisher,
        rules: list[AnomalyRule],
        window_capacity: int = 60,
    ) -> None:
        self.repository = repository
        self.publisher = publisher
        self.rules = list(rules)
        self.window_capacity = window_capacity
        self.windows: dict[str, MeterSlidingWindow] = {}

    def get_or_create_window(self, meter_id: str) -> MeterSlidingWindow:
        """Retrieve existing sliding window or create a new bounded one."""
        if meter_id not in self.windows:
            self.windows[meter_id] = MeterSlidingWindow(capacity=self.window_capacity)
        return self.windows[meter_id]

    def process_reading(self, reading: TelemetryReading) -> list[AlertEvent]:
        """Process an incoming telemetry reading through all configured anomaly rules."""
        window = self.get_or_create_window(reading.meter_id)
        emitted: list[AlertEvent] = []

        for rule in self.rules:
            try:
                alert = rule.check(reading, window)
                if alert is not None:
                    # 1. Idempotent save to repository
                    saved = self.repository.save_alert(alert)
                    # 2. Publish to Kafka topic iot.alerts
                    self.publisher.publish_alert(alert)
                    # 3. Prometheus metrics
                    record_alert_emitted(alert.alert_type, alert.severity)
                    emitted.append(alert)
                    logger.info(
                        "Anomaly detected for %s: %s (%s) - %s [saved_to_db=%s]",
                        alert.meter_id,
                        alert.alert_type,
                        alert.severity,
                        alert.message,
                        saved,
                    )
            except Exception as e:
                logger.error("Error evaluating rule %s on meter %s: %s", type(rule).__name__, reading.meter_id, e)

        # Update sliding window with current reading
        window.add(reading)

        # Observability metrics
        record_reading_processed()
        now = datetime.now(timezone.utc)
        lag = (now - reading.timestamp).total_seconds()
        record_processing_lag(lag)

        return emitted

    def reset_window(self, meter_id: str) -> None:
        """Reset the sliding window for a specific meter (partition rebalance safety)."""
        if meter_id in self.windows:
            self.windows[meter_id].reset()
            record_window_reset()
            logger.info("Sliding window reset for meter %s", meter_id)

    def clear_windows(self) -> None:
        """Clear all in-memory meter windows (partition revocation safety)."""
        self.windows.clear()
        record_window_reset()
        logger.info("All sliding windows cleared on partition rebalance")
