"""Anomaly detection rules adhering to Single Responsibility and Open/Closed principles."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

try:
    from models import AlertEvent, AlertType, Severity, TelemetryReading
except ImportError:
    from .models import AlertEvent, AlertType, Severity, TelemetryReading

if TYPE_CHECKING:
    try:
        from window import MeterSlidingWindow
    except ImportError:
        from .window import MeterSlidingWindow

logger = logging.getLogger(__name__)


class AnomalyRule(ABC):
    """Abstract base class / protocol defining a single anomaly detection rule.

    Interface Segregation Principle (ISP) & Single Responsibility Principle (SRP).
    """

    @abstractmethod
    def check(self, reading: TelemetryReading, window: MeterSlidingWindow) -> Optional[AlertEvent]:
        """Evaluate reading against the rule.

        Returns an AlertEvent if an anomaly is detected, or None otherwise.
        """
        pass


class VoltageSagSwellRule(AnomalyRule):
    """Detects voltage sags and swells across 3 phases (EN 50160).

    Sag:
      - Warning: any phase < 207V (nominal 230V - 10%)
      - Critical: any phase < 195V (nominal 230V - 15%)
    Swell:
      - Warning: any phase > 253V (nominal 230V + 10%)
      - Critical: any phase > 265V (nominal 230V + 15%)
    """

    SAG_CRITICAL_THRESHOLD: float = 195.0
    SAG_WARNING_THRESHOLD: float = 207.0
    SWELL_WARNING_THRESHOLD: float = 253.0
    SWELL_CRITICAL_THRESHOLD: float = 265.0

    def check(self, reading: TelemetryReading, window: MeterSlidingWindow) -> Optional[AlertEvent]:
        voltages = [
            ("L1", reading.voltage_l1),
            ("L2", reading.voltage_l2),
            ("L3", reading.voltage_l3),
        ]

        # 1. Check for voltage sag (lowest phase voltage)
        min_phase, min_v = min(voltages, key=lambda x: x[1])
        if min_v < self.SAG_CRITICAL_THRESHOLD:
            return AlertEvent(
                time=reading.timestamp_iso,
                meter_id=reading.meter_id,
                alert_type=AlertType.VOLTAGE_SAG.value,
                severity=Severity.CRITICAL.value,
                value=min_v,
                threshold=self.SAG_CRITICAL_THRESHOLD,
                message=f"Critical voltage sag on phase {min_phase}: {min_v:.1f}V < {self.SAG_CRITICAL_THRESHOLD}V",
            )
        if min_v < self.SAG_WARNING_THRESHOLD:
            return AlertEvent(
                time=reading.timestamp_iso,
                meter_id=reading.meter_id,
                alert_type=AlertType.VOLTAGE_SAG.value,
                severity=Severity.WARNING.value,
                value=min_v,
                threshold=self.SAG_WARNING_THRESHOLD,
                message=f"Voltage sag warning on phase {min_phase}: {min_v:.1f}V < {self.SAG_WARNING_THRESHOLD}V",
            )

        # 2. Check for voltage swell (highest phase voltage)
        max_phase, max_v = max(voltages, key=lambda x: x[1])
        if max_v > self.SWELL_CRITICAL_THRESHOLD:
            return AlertEvent(
                time=reading.timestamp_iso,
                meter_id=reading.meter_id,
                alert_type=AlertType.VOLTAGE_SWELL.value,
                severity=Severity.CRITICAL.value,
                value=max_v,
                threshold=self.SWELL_CRITICAL_THRESHOLD,
                message=f"Critical voltage swell on phase {max_phase}: {max_v:.1f}V > {self.SWELL_CRITICAL_THRESHOLD}V",
            )
        if max_v > self.SWELL_WARNING_THRESHOLD:
            return AlertEvent(
                time=reading.timestamp_iso,
                meter_id=reading.meter_id,
                alert_type=AlertType.VOLTAGE_SWELL.value,
                severity=Severity.WARNING.value,
                value=max_v,
                threshold=self.SWELL_WARNING_THRESHOLD,
                message=f"Voltage swell warning on phase {max_phase}: {max_v:.1f}V > {self.SWELL_WARNING_THRESHOLD}V",
            )

        return None


class DemandSpikeRule(AnomalyRule):
    """Detects active power demand spikes exceeding rolling mu + 3*sigma."""

    def __init__(self, min_samples: int = 3, k_sigma: float = 3.0) -> None:
        self.min_samples = min_samples
        self.k_sigma = k_sigma

    def check(self, reading: TelemetryReading, window: MeterSlidingWindow) -> Optional[AlertEvent]:
        if window.count < self.min_samples:
            return None

        mu = window.mean
        sigma = window.std
        threshold = mu + self.k_sigma * sigma

        # Detect spike if reading exceeds threshold
        if reading.active_power_kw > threshold:
            is_critical = sigma > 0 and reading.active_power_kw > (mu + 5.0 * sigma)
            severity = Severity.CRITICAL.value if is_critical else Severity.WARNING.value
            return AlertEvent(
                time=reading.timestamp_iso,
                meter_id=reading.meter_id,
                alert_type=AlertType.DEMAND_SPIKE.value,
                severity=severity,
                value=reading.active_power_kw,
                threshold=threshold,
                message=(
                    f"Demand spike detected: {reading.active_power_kw:.2f}kW exceeds "
                    f"threshold {threshold:.2f}kW (mu={mu:.2f}, sigma={sigma:.2f})"
                ),
            )
        return None


class PhaseImbalanceRule(AnomalyRule):
    """Detects 3-phase voltage or current asymmetry > 15%."""

    THRESHOLD_PCT: float = 15.0

    def check(self, reading: TelemetryReading, window: MeterSlidingWindow) -> Optional[AlertEvent]:
        # Voltage asymmetry: max deviation from phase mean / phase mean * 100%
        voltages = [reading.voltage_l1, reading.voltage_l2, reading.voltage_l3]
        v_avg = sum(voltages) / 3.0
        v_asym = (max(abs(v - v_avg) for v in voltages) / v_avg * 100.0) if v_avg > 0 else 0.0

        # Current asymmetry
        i_asym = 0.0
        if reading.current_l2 is not None and reading.current_l3 is not None:
            currents = [reading.current_l1, reading.current_l2, reading.current_l3]
            i_avg = sum(currents) / 3.0
            if i_avg > 0.05:  # ignore zero-load float
                i_asym = (max(abs(i - i_avg) for i in currents) / i_avg) * 100.0

        max_asym = max(v_asym, i_asym)
        if max_asym > self.THRESHOLD_PCT:
            severity = Severity.CRITICAL.value if max_asym > 25.0 else Severity.WARNING.value
            target_metric = "voltage" if v_asym >= i_asym else "current"
            return AlertEvent(
                time=reading.timestamp_iso,
                meter_id=reading.meter_id,
                alert_type=AlertType.PHASE_IMBALANCE.value,
                severity=severity,
                value=max_asym,
                threshold=self.THRESHOLD_PCT,
                message=(
                    f"Phase {target_metric} imbalance: asymmetry {max_asym:.1f}% "
                    f"exceeds {self.THRESHOLD_PCT}% threshold"
                ),
            )
        return None


class LowPowerFactorRule(AnomalyRule):
    """Detects poor power factor (PF < 0.85)."""

    THRESHOLD_PF: float = 0.85

    def check(self, reading: TelemetryReading, window: MeterSlidingWindow) -> Optional[AlertEvent]:
        if reading.power_factor < self.THRESHOLD_PF:
            severity = Severity.CRITICAL.value if reading.power_factor < 0.70 else Severity.WARNING.value
            return AlertEvent(
                time=reading.timestamp_iso,
                meter_id=reading.meter_id,
                alert_type=AlertType.LOW_POWER_FACTOR.value,
                severity=severity,
                value=reading.power_factor,
                threshold=self.THRESHOLD_PF,
                message=f"Low power factor detected: {reading.power_factor:.3f} < {self.THRESHOLD_PF} threshold",
            )
        return None


class FrequencyDeviationRule(AnomalyRule):
    """Detects grid frequency excursion outside normal range (< 49.5 Hz or > 50.5 Hz).

    Demonstrates Open/Closed Principle (OCP): added seamlessly without touching AnomalyEngine.
    """

    LOWER_HZ: float = 49.5
    UPPER_HZ: float = 50.5

    def check(self, reading: TelemetryReading, window: MeterSlidingWindow) -> Optional[AlertEvent]:
        if reading.frequency_hz < self.LOWER_HZ:
            severity = Severity.CRITICAL.value if reading.frequency_hz < 49.0 else Severity.WARNING.value
            return AlertEvent(
                time=reading.timestamp_iso,
                meter_id=reading.meter_id,
                alert_type=AlertType.FREQUENCY_DEVIATION.value,
                severity=severity,
                value=reading.frequency_hz,
                threshold=self.LOWER_HZ,
                message=f"Under-frequency event: {reading.frequency_hz:.2f}Hz < {self.LOWER_HZ}Hz",
            )
        if reading.frequency_hz > self.UPPER_HZ:
            severity = Severity.CRITICAL.value if reading.frequency_hz > 51.0 else Severity.WARNING.value
            return AlertEvent(
                time=reading.timestamp_iso,
                meter_id=reading.meter_id,
                alert_type=AlertType.FREQUENCY_DEVIATION.value,
                severity=severity,
                value=reading.frequency_hz,
                threshold=self.UPPER_HZ,
                message=f"Over-frequency event: {reading.frequency_hz:.2f}Hz > {self.UPPER_HZ}Hz",
            )
        return None


__all__ = [
    "AnomalyRule",
    "VoltageSagSwellRule",
    "DemandSpikeRule",
    "PhaseImbalanceRule",
    "LowPowerFactorRule",
    "FrequencyDeviationRule",
]
