"""Alert repository interface and implementations."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Set, Tuple

try:
    from models import AlertEvent
except ImportError:
    from .models import AlertEvent

logger = logging.getLogger(__name__)


class AlertRepository(ABC):
    """Abstract repository for persisting anomaly alerts (DIP & ISP)."""

    @abstractmethod
    def save_alert(self, alert: AlertEvent) -> bool:
        """Save alert idempotently.

        Returns True if inserted, False if ignored due to conflict.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Cleanly close underlying connections."""
        pass


class PostgresAlertRepository(AlertRepository):
    """PostgreSQL / TimescaleDB alert repository with ON CONFLICT DO NOTHING idempotent writes."""

    INSERT_SQL = """
        INSERT INTO meter_alerts (time, meter_id, alert_type, severity, value, threshold, message)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (meter_id, alert_type, time) DO NOTHING
        RETURNING id;
    """

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self._conn = None

    def _get_connection(self):
        import psycopg

        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self.dsn, autocommit=True)
        return self._conn

    def save_alert(self, alert: AlertEvent) -> bool:
        """Insert alert into meter_alerts table idempotently."""
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute(
                    self.INSERT_SQL,
                    (
                        alert.time,
                        alert.meter_id,
                        alert.alert_type,
                        alert.severity,
                        alert.value,
                        alert.threshold,
                        alert.message,
                    ),
                )
                row = cur.fetchone()
                return row is not None
        except Exception as e:
            logger.error("Failed to save alert to PostgreSQL: %s", e)
            self._conn = None
            raise

    def close(self) -> None:
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None


class InMemoryAlertRepository(AlertRepository):
    """In-memory mock repository implementing idempotent writes for testing."""

    def __init__(self) -> None:
        self.alerts: list[AlertEvent] = []
        self._seen_keys: Set[Tuple[str, str, str]] = set()
        self._next_id: int = 1

    def save_alert(self, alert: AlertEvent) -> bool:
        key = (alert.meter_id, alert.alert_type, alert.time)
        if key in self._seen_keys:
            # ON CONFLICT (meter_id, alert_type, time) DO NOTHING
            return False

        self._seen_keys.add(key)
        saved = AlertEvent(
            time=alert.time,
            meter_id=alert.meter_id,
            alert_type=alert.alert_type,
            severity=alert.severity,
            value=alert.value,
            threshold=alert.threshold,
            message=alert.message,
            id=alert.id or self._next_id,
        )
        self._next_id += 1
        self.alerts.append(saved)
        return True

    def close(self) -> None:
        self.alerts.clear()
        self._seen_keys.clear()
