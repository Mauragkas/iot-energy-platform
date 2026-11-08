"""Smart Meter Edge Simulator - Fault Injection and Replay Buffer.

Implements fault injection for:
  - Voltage sag (V < 207V)
  - Voltage swell (V > 253V)
  - Demand spike (active_power_kw > mu + 3*sigma, e.g. 35kW)
  - Phase imbalance (e.g. L1=238V, L2=212V, L3=230V)
  - Low power factor (PF < 0.8)
  - Frequency excursion (Hz < 49.5 or > 50.5)

Implements offline gateway disconnect replay buffer:
  - Simulates gateway network drop by holding packets for a duration (e.g. 30s)
  - Bursts packets out-of-order upon reconnection
  - Injects intentional duplicate packets with identical (meter_id, timestamp)
"""

from __future__ import annotations

import random
from enum import Enum
from typing import Any


class FaultType(str, Enum):
    """Enumeration of grid and meter anomaly types."""

    VOLTAGE_SAG = "voltage_sag"
    VOLTAGE_SWELL = "voltage_swell"
    DEMAND_SPIKE = "demand_spike"
    PHASE_IMBALANCE = "phase_imbalance"
    LOW_POWER_FACTOR = "low_power_factor"
    FREQUENCY_EXCURSION = "frequency_excursion"


def inject_voltage_sag(reading: dict[str, Any], voltage_v: float = 195.0) -> dict[str, Any]:
    """Inject a voltage sag below EN 50160 lower limit (V < 207V)."""
    reading = dict(reading)
    # Target under 207V (nominal 230V - 10%)
    target_v = float(voltage_v) if voltage_v < 207.0 else 195.0
    reading["voltage_l1"] = round(target_v, 2)
    reading["status"] = "WARNING"
    # Recalculate active power based on new voltage
    pf = reading["power_factor"]
    v_l1 = reading["voltage_l1"]
    v_l2 = reading["voltage_l2"]
    v_l3 = reading["voltage_l3"]
    i_l1 = reading["current_l1"]
    i_l2 = reading.get("current_l2", i_l1)
    i_l3 = reading.get("current_l3", i_l1)
    reading["active_power_kw"] = round(((v_l1 * i_l1) + (v_l2 * i_l2) + (v_l3 * i_l3)) * pf / 1000.0, 3)
    return reading


def inject_voltage_swell(reading: dict[str, Any], voltage_v: float = 265.0) -> dict[str, Any]:
    """Inject a voltage swell above EN 50160 upper limit (V > 253V)."""
    reading = dict(reading)
    # Target above 253V (nominal 230V + 10%)
    target_v = float(voltage_v) if voltage_v > 253.0 else 265.0
    reading["voltage_l1"] = round(target_v, 2)
    reading["status"] = "WARNING"
    pf = reading["power_factor"]
    v_l1 = reading["voltage_l1"]
    v_l2 = reading["voltage_l2"]
    v_l3 = reading["voltage_l3"]
    i_l1 = reading["current_l1"]
    i_l2 = reading.get("current_l2", i_l1)
    i_l3 = reading.get("current_l3", i_l1)
    reading["active_power_kw"] = round(((v_l1 * i_l1) + (v_l2 * i_l2) + (v_l3 * i_l3)) * pf / 1000.0, 3)
    return reading


def inject_demand_spike(reading: dict[str, Any], spike_kw: float = 35.0) -> dict[str, Any]:
    """Inject a demand spike exceeding normal 3-sigma thresholds (e.g. 35kW)."""
    reading = dict(reading)
    target_kw = float(spike_kw) if spike_kw > 25.0 else 35.0
    reading["active_power_kw"] = round(target_kw, 3)
    reading["status"] = "WARNING"

    # Scale phase currents to match demand spike physically
    v_avg = (reading["voltage_l1"] + reading["voltage_l2"] + reading["voltage_l3"]) / 3.0
    pf = max(0.1, reading["power_factor"])
    i_phase = (target_kw * 1000.0) / (3.0 * v_avg * pf)
    reading["current_l1"] = round(i_phase * random.uniform(0.98, 1.02), 2)
    reading["current_l2"] = round(i_phase * random.uniform(0.98, 1.02), 2)
    reading["current_l3"] = round(i_phase * random.uniform(0.98, 1.02), 2)
    return reading


def inject_phase_imbalance(
    reading: dict[str, Any],
    v_l1: float = 238.0,
    v_l2: float = 212.0,
    v_l3: float = 230.0,
) -> dict[str, Any]:
    """Inject significant 3-phase voltage and current imbalance."""
    reading = dict(reading)
    reading["voltage_l1"] = round(v_l1, 2)
    reading["voltage_l2"] = round(v_l2, 2)
    reading["voltage_l3"] = round(v_l3, 2)

    # Imbalance in current draw
    base_i = reading["current_l1"]
    reading["current_l1"] = round(base_i * 2.2, 2)
    reading["current_l2"] = round(max(0.1, base_i * 0.35), 2)
    reading["current_l3"] = round(base_i * 0.9, 2)

    pf = reading["power_factor"]
    reading["active_power_kw"] = round(
        ((reading["voltage_l1"] * reading["current_l1"])
         + (reading["voltage_l2"] * reading["current_l2"])
         + (reading["voltage_l3"] * reading["current_l3"]))
        * pf
        / 1000.0,
        3,
    )
    reading["status"] = "WARNING"
    return reading


def inject_low_power_factor(reading: dict[str, Any], pf: float = 0.65) -> dict[str, Any]:
    """Inject poor power factor (PF < 0.8) representing inductive motor load."""
    reading = dict(reading)
    target_pf = float(pf) if pf < 0.8 else 0.65
    reading["power_factor"] = round(target_pf, 3)
    reading["status"] = "WARNING"

    # Maintain active power by proportionally increasing apparent current draw
    # P = V * I * PF / 1000 => I increases when PF drops
    scale = 0.95 / max(0.2, target_pf)
    reading["current_l1"] = round(reading["current_l1"] * scale, 2)
    reading["current_l2"] = round(reading.get("current_l2", reading["current_l1"]) * scale, 2)
    reading["current_l3"] = round(reading.get("current_l3", reading["current_l1"]) * scale, 2)
    return reading


def inject_frequency_excursion(
    reading: dict[str, Any],
    freq_hz: float | None = None,
) -> dict[str, Any]:
    """Inject frequency excursion outside EN 50160 grid limits (< 49.5 Hz or > 50.5 Hz)."""
    reading = dict(reading)
    if freq_hz is not None:
        target_hz = float(freq_hz)
    else:
        # Choose low excursion or high excursion
        target_hz = 49.20 if random.random() < 0.5 else 50.85

    reading["frequency_hz"] = round(target_hz, 2)
    reading["status"] = "WARNING"
    return reading


def apply_fault(reading: dict[str, Any], fault_type: FaultType | str) -> dict[str, Any]:
    """Apply designated fault type to reading dictionary."""
    f_type = FaultType(fault_type) if isinstance(fault_type, str) else fault_type

    if f_type == FaultType.VOLTAGE_SAG:
        return inject_voltage_sag(reading)
    elif f_type == FaultType.VOLTAGE_SWELL:
        return inject_voltage_swell(reading)
    elif f_type == FaultType.DEMAND_SPIKE:
        return inject_demand_spike(reading)
    elif f_type == FaultType.PHASE_IMBALANCE:
        return inject_phase_imbalance(reading)
    elif f_type == FaultType.LOW_POWER_FACTOR:
        return inject_low_power_factor(reading)
    elif f_type == FaultType.FREQUENCY_EXCURSION:
        return inject_frequency_excursion(reading)
    else:
        return reading


class FaultInjector:
    """Manages stochastic fault injection for a fleet of smart meters."""

    def __init__(self, fault_probability: float = 0.05) -> None:
        """Initialize fault injector with injection probability."""
        self.fault_probability = max(0.0, min(1.0, fault_probability))
        self.available_faults = list(FaultType)

    def maybe_inject(self, reading: dict[str, Any]) -> tuple[dict[str, Any], FaultType | None]:
        """Inject an anomaly if stochastic threshold is met."""
        if random.random() < self.fault_probability:
            fault = random.choice(self.available_faults)
            return apply_fault(reading, fault), fault
        return reading, None


class ReplayBuffer:
    """Simulates an edge gateway offline disconnect buffer.

    Holds telemetry packets for an offline duration (e.g. 30 seconds), then
    bursts them out-of-order upon gateway reconnection and injects duplicate
    packets with identical (meter_id, timestamp) tuples.
    """

    def __init__(
        self,
        buffer_duration_seconds: float = 30.0,
        duplicate_ratio: float = 0.20,
    ) -> None:
        """Initialize replay buffer with buffer duration and duplicate ratio."""
        self.buffer_duration_seconds = buffer_duration_seconds
        self.duplicate_ratio = max(0.0, min(1.0, duplicate_ratio))
        self.buffer: list[dict[str, Any]] = []
        self.first_packet_time: float | None = None
        self.is_offline: bool = True

    def add(self, reading: dict[str, Any], current_time: float | None = None) -> None:
        """Add a telemetry reading to the offline buffer."""
        import time

        now = current_time if current_time is not None else time.time()
        if self.first_packet_time is None:
            self.first_packet_time = now
        self.buffer.append(dict(reading))

    def should_flush(self, current_time: float | None = None) -> bool:
        """Check if buffer has accumulated enough readings or elapsed duration."""
        import time

        if not self.buffer:
            return False
        now = current_time if current_time is not None else time.time()
        if self.first_packet_time is None:
            return False
        elapsed = now - self.first_packet_time
        return elapsed >= self.buffer_duration_seconds

    def flush_burst(self) -> list[dict[str, Any]]:
        """Flush buffered packets out-of-order with duplicate packets injected.

        Returns:
            list[dict[str, Any]]: Out-of-order burst including intentional duplicate packets.
        """
        if not self.buffer:
            return []

        packets = list(self.buffer)
        self.buffer.clear()
        self.first_packet_time = None

        if len(packets) <= 1:
            return packets

        # 1. Inject duplicate packets with identical (meter_id, timestamp)
        num_duplicates = max(1, int(len(packets) * self.duplicate_ratio))
        duplicate_candidates = random.sample(packets, min(num_duplicates, len(packets)))
        duplicates = [dict(p) for p in duplicate_candidates]

        # 2. Combine and shuffle out-of-order
        burst = packets + duplicates
        # Shuffle to guarantee out-of-order event-time arrival
        random.shuffle(burst)

        return burst

    def __len__(self) -> int:
        """Return count of currently buffered packets."""
        return len(self.buffer)
