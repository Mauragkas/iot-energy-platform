"""Data models for telemetry readings and anomaly alerts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class AlertType(str, Enum):
    """Classification code of anomaly matching docs/schemas/alert.json."""

    VOLTAGE_SAG = "VOLTAGE_SAG"
    VOLTAGE_SWELL = "VOLTAGE_SWELL"
    DEMAND_SPIKE = "DEMAND_SPIKE"
    PHASE_IMBALANCE = "PHASE_IMBALANCE"
    LOW_POWER_FACTOR = "LOW_POWER_FACTOR"
    FREQUENCY_DEVIATION = "FREQUENCY_DEVIATION"


class Severity(str, Enum):
    """Alert severity levels matching docs/schemas/alert.json."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class AlertEvent:
    """Grid anomaly alert emitted by real-time streaming detector.

    Strictly matches docs/schemas/alert.json schema.
    """

    time: str
    meter_id: str
    alert_type: str
    severity: str
    value: float
    threshold: float
    message: str
    id: Optional[int | str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert alert event to a JSON-serializable dictionary."""
        d: dict[str, Any] = {
            "time": self.time,
            "meter_id": self.meter_id,
            "alert_type": self.alert_type if isinstance(self.alert_type, str) else self.alert_type.value,
            "severity": self.severity if isinstance(self.severity, str) else self.severity.value,
            "value": round(float(self.value), 4),
            "threshold": round(float(self.threshold), 4),
            "message": self.message,
        }
        if self.id is not None:
            d["id"] = self.id
        return d

    def to_json(self) -> str:
        """Convert alert event to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AlertEvent:
        """Parse dictionary to AlertEvent."""
        return cls(
            time=data["time"],
            meter_id=data["meter_id"],
            alert_type=data["alert_type"],
            severity=data["severity"],
            value=float(data["value"]),
            threshold=float(data["threshold"]),
            message=data["message"],
            id=data.get("id"),
        )


@dataclass(frozen=True)
class TelemetryReading:
    """3-phase smart meter telemetry reading.

    Matches docs/schemas/telemetry.json.
    """

    meter_id: str
    timestamp: datetime
    voltage_l1: float
    voltage_l2: float
    voltage_l3: float
    current_l1: float
    active_power_kw: float
    total_energy_kwh: float
    power_factor: float
    frequency_hz: float
    current_l2: Optional[float] = None
    current_l3: Optional[float] = None
    zigbee_lqi: Optional[int] = None
    status: str = "OK"

    @property
    def timestamp_iso(self) -> str:
        """Return ISO-8601 UTC string."""
        return self.timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryReading:
        """Parse raw telemetry dict into TelemetryReading."""
        ts = data["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)

        return cls(
            meter_id=str(data["meter_id"]),
            timestamp=ts,
            voltage_l1=float(data["voltage_l1"]),
            voltage_l2=float(data["voltage_l2"]),
            voltage_l3=float(data["voltage_l3"]),
            current_l1=float(data["current_l1"]),
            active_power_kw=float(data["active_power_kw"]),
            total_energy_kwh=float(data["total_energy_kwh"]),
            power_factor=float(data["power_factor"]),
            frequency_hz=float(data["frequency_hz"]),
            current_l2=float(data["current_l2"]) if data.get("current_l2") is not None else None,
            current_l3=float(data["current_l3"]) if data.get("current_l3") is not None else None,
            zigbee_lqi=int(data["zigbee_lqi"]) if data.get("zigbee_lqi") is not None else None,
            status=str(data.get("status", "OK")),
        )

    @classmethod
    def from_json(cls, payload: str | bytes) -> TelemetryReading:
        """Parse JSON payload into TelemetryReading."""
        data = json.loads(payload)
        return cls.from_dict(data)
