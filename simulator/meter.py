"""Smart Meter Edge Simulator - Meter Model.

Models a 3-phase smart meter (MZ-3P-xxxx) maintaining continuous internal state
(cumulative active energy kWh, voltages, currents, power factor, frequency, radio LQI)
and realistic diurnal consumption load curves.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime
from typing import Any

# Default distribution of geographical zones
DEFAULT_ZONES = ["north", "south", "east", "west"]


def calculate_diurnal_factor(hour: float) -> float:
    """Calculate normalized diurnal load multiplier for a given hour of day (0.0 to 24.0).

    Features:
      - Low night baseline (00:00 - 06:00): ~0.35
      - Morning peak (07:00 - 09:30): up to ~0.85
      - Midday shoulder (10:00 - 16:00): ~0.55
      - Evening peak (18:00 - 22:00): up to ~1.15
      - Late night decline (22:00 - 24:00): tapering off
    """
    baseline = 0.35
    morning_peak = 0.50 * math.exp(-(((hour - 8.0) / 1.8) ** 2))
    evening_peak = 0.80 * math.exp(-(((hour - 19.5) / 2.2) ** 2))
    midday_shoulder = 0.20 * math.exp(-(((hour - 13.5) / 3.0) ** 2))
    return baseline + morning_peak + evening_peak + midday_shoulder


class SmartMeter:
    """Simulates a physical 3-phase smart electricity meter."""

    def __init__(
        self,
        meter_id: str | int,
        zone: str | None = None,
        initial_energy_kwh: float | None = None,
        base_power_kw: float | None = None,
        power_factor_nominal: float = 0.95,
        nominal_voltage: float = 230.0,
        nominal_frequency: float = 50.0,
    ) -> None:
        """Initialize smart meter instance."""
        if isinstance(meter_id, int):
            self.meter_id = f"MZ-3P-{meter_id:04d}"
            idx = meter_id
        else:
            self.meter_id = str(meter_id)
            # Try to extract trailing integer for deterministic seeding
            digits = "".join(filter(str.isdigit, self.meter_id))
            idx = int(digits) if digits else hash(self.meter_id) % 10000

        self.zone = zone if zone else DEFAULT_ZONES[idx % len(DEFAULT_ZONES)]

        # Continuous state
        if initial_energy_kwh is not None:
            self.total_energy_kwh = float(initial_energy_kwh)
        else:
            # Staggered baseline cumulative energy (e.g. 500 to 5000 kWh)
            self.total_energy_kwh = 1000.0 + (idx * 7.7) % 4000.0

        if base_power_kw is not None:
            self.base_power_kw = float(base_power_kw)
        else:
            # Baseline power capacity (1.5 kW to 3.8 kW for residential 3-phase)
            self.base_power_kw = 1.8 + (idx * 0.37) % 2.0

        self.power_factor_nominal = power_factor_nominal
        self.nominal_voltage = nominal_voltage
        self.nominal_frequency = nominal_frequency
        self.last_reading_time: datetime | None = None

    def get_topic(self) -> str:
        """Return MQTT topic for this meter."""
        return f"meazon/grid/{self.zone}/meter/{self.meter_id}/telemetry"

    def generate_reading(
        self,
        timestamp: datetime | None = None,
        override_delta_seconds: float | None = None,
    ) -> dict[str, Any]:
        """Generate a single reading matching docs/schemas/telemetry.json.

        Maintains physical consistency:
          P_total (kW) = (V_L1*I_L1 + V_L2*I_L2 + V_L3*I_L3) * PF / 1000
          total_energy_kwh += P_total * (delta_t / 3600)
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)
        elif timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        # Calculate delta time for continuous cumulative energy integration
        if override_delta_seconds is not None:
            delta_seconds = max(0.001, override_delta_seconds)
        elif self.last_reading_time is not None:
            delta_seconds = max(0.001, (timestamp - self.last_reading_time).total_seconds())
        else:
            delta_seconds = 2.0  # Default initial interval

        # Diurnal load curve factor based on time of day
        hour_of_day = (
            timestamp.hour
            + timestamp.minute / 60.0
            + timestamp.second / 3600.0
            + timestamp.microsecond / 3_600_000_000.0
        )
        diurnal_mult = calculate_diurnal_factor(hour_of_day)

        # Small stochastic noise on load (~ +/- 3%)
        load_jitter = random.uniform(0.97, 1.03)
        target_active_power = self.base_power_kw * diurnal_mult * load_jitter

        # Voltages ~ 230V RMS (EN 50160 nominal 230V +/- 1.5V under normal grid conditions)
        v_l1 = random.gauss(self.nominal_voltage, 1.2)
        v_l2 = random.gauss(self.nominal_voltage, 1.2)
        v_l3 = random.gauss(self.nominal_voltage, 1.2)

        # Clamped to standard safe grid limits under normal conditions
        v_l1 = max(220.0, min(242.0, v_l1))
        v_l2 = max(220.0, min(242.0, v_l2))
        v_l3 = max(220.0, min(242.0, v_l3))

        # Power factor ~ 0.95
        pf = random.gauss(self.power_factor_nominal, 0.008)
        pf = max(0.91, min(0.99, pf))

        # Frequency ~ 50.0 Hz (+/- 0.03 Hz nominal)
        freq = random.gauss(self.nominal_frequency, 0.02)
        freq = max(49.92, min(50.08, freq))

        # Balanced phase current distribution
        # Active power = (V_L1*I_L1 + V_L2*I_L2 + V_L3*I_L3) * PF / 1000
        # Phase power P_phase = target_active_power / 3
        # I_phase = (P_phase * 1000) / (V_phase * PF)
        phase_power_w = (target_active_power * 1000.0) / 3.0
        i_l1 = (phase_power_w / (v_l1 * pf)) * random.uniform(0.98, 1.02)
        i_l2 = (phase_power_w / (v_l2 * pf)) * random.uniform(0.98, 1.02)
        i_l3 = (phase_power_w / (v_l3 * pf)) * random.uniform(0.98, 1.02)

        # Ensure currents are positive
        i_l1 = max(0.01, i_l1)
        i_l2 = max(0.01, i_l2)
        i_l3 = max(0.01, i_l3)

        # Calculate exact total 3-phase active power in kW
        active_power_kw = ((v_l1 * i_l1) + (v_l2 * i_l2) + (v_l3 * i_l3)) * pf / 1000.0

        # Continuous energy integration: kWh = kW * hours
        delta_kwh = active_power_kw * (delta_seconds / 3600.0)
        self.total_energy_kwh += delta_kwh
        self.last_reading_time = timestamp

        # Radio LQI ~ 180-250 (Zigbee mesh link quality)
        zigbee_lqi = int(random.randint(180, 245))

        # Format ISO-8601 UTC timestamp ending in 'Z'
        ts_str = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

        return {
            "meter_id": self.meter_id,
            "timestamp": ts_str,
            "voltage_l1": round(v_l1, 2),
            "voltage_l2": round(v_l2, 2),
            "voltage_l3": round(v_l3, 2),
            "current_l1": round(i_l1, 2),
            "current_l2": round(i_l2, 2),
            "current_l3": round(i_l3, 2),
            "active_power_kw": round(active_power_kw, 3),
            "total_energy_kwh": round(self.total_energy_kwh, 4),
            "power_factor": round(pf, 3),
            "frequency_hz": round(freq, 2),
            "zigbee_lqi": zigbee_lqi,
            "status": "OK",
        }


def create_fleet(
    count: int = 500,
    start_index: int = 1,
    zone: str | None = None,
) -> list[SmartMeter]:
    """Create a fleet of N smart meters with deterministic IDs and zones."""
    meters = []
    for i in range(start_index, start_index + count):
        m_zone = zone if zone else DEFAULT_ZONES[i % len(DEFAULT_ZONES)]
        meter = SmartMeter(meter_id=i, zone=m_zone)
        meters.append(meter)
    return meters
