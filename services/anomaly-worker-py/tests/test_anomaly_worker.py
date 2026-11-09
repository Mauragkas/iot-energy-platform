"""Comprehensive test suite for Module D — Real-Time Streaming Anomaly Worker.

Tests cover:
  1. Voltage sag (Warning < 207V, Critical < 195V)
  2. Voltage swell (Warning > 253V, Critical > 265V)
  3. Demand spike (active_power_kw > mu + 3*sigma based on window statistics)
  4. Phase imbalance (voltage / current asymmetry > 15%)
  5. Low power factor (PF < 0.85)
  6. Idempotent storage (ON CONFLICT DO NOTHING)
  7. Kafka publication mock
  8. Window statistics (mean, std, EWMA, bounded capacity)
  9. Dependency Inversion Principle (DIP) & Open/Closed Principle (OCP)
  10. Strict JSON schema validation against docs/schemas/alert.json
  11. Consumer partition rebalance safety
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import jsonschema
import pytest

from detector import (
    AnomalyRule,
    DemandSpikeRule,
    FrequencyDeviationRule,
    LowPowerFactorRule,
    PhaseImbalanceRule,
    VoltageSagSwellRule,
)
from engine import AnomalyEngine
from models import AlertEvent, AlertType, Severity, TelemetryReading
from publisher import InMemoryAlertPublisher, KafkaAlertPublisher
from repository import InMemoryAlertRepository, PostgresAlertRepository
from window import MeterSlidingWindow

# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------


def make_reading(
    meter_id: str = "MZ-3P-0042",
    timestamp: datetime | None = None,
    voltage_l1: float = 230.0,
    voltage_l2: float = 230.0,
    voltage_l3: float = 230.0,
    current_l1: float = 10.0,
    current_l2: float | None = 10.0,
    current_l3: float | None = 10.0,
    active_power_kw: float = 6.9,
    total_energy_kwh: float = 100.0,
    power_factor: float = 0.95,
    frequency_hz: float = 50.0,
    status: str = "OK",
) -> TelemetryReading:
    """Helper factory for valid TelemetryReading instances."""
    if timestamp is None:
        timestamp = datetime(2026, 11, 12, 16, 0, 0, tzinfo=timezone.utc)
    return TelemetryReading(
        meter_id=meter_id,
        timestamp=timestamp,
        voltage_l1=voltage_l1,
        voltage_l2=voltage_l2,
        voltage_l3=voltage_l3,
        current_l1=current_l1,
        current_l2=current_l2,
        current_l3=current_l3,
        active_power_kw=active_power_kw,
        total_energy_kwh=total_energy_kwh,
        power_factor=power_factor,
        frequency_hz=frequency_hz,
        status=status,
    )


@pytest.fixture
def alert_schema() -> dict:
    """Load canonical alert schema from docs/schemas/alert.json."""
    # Find repository root containing docs/schemas/alert.json
    cur = Path(__file__).resolve()
    for parent in cur.parents:
        schema_path = parent / "docs" / "schemas" / "alert.json"
        if schema_path.exists():
            with open(schema_path, "r", encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError("docs/schemas/alert.json not found in repository hierarchy")


# ---------------------------------------------------------------------------
# 1. Voltage Sag Tests
# ---------------------------------------------------------------------------


class TestVoltageSagRule:
    def test_nominal_voltage_no_alert(self):
        rule = VoltageSagSwellRule()
        window = MeterSlidingWindow()
        reading = make_reading(voltage_l1=230.0, voltage_l2=230.0, voltage_l3=230.0)
        alert = rule.check(reading, window)
        assert alert is None

    def test_voltage_sag_warning(self):
        rule = VoltageSagSwellRule()
        window = MeterSlidingWindow()
        # 200V is < 207V (Warning) but >= 195V
        reading = make_reading(voltage_l1=200.0, voltage_l2=230.0, voltage_l3=230.0)
        alert = rule.check(reading, window)

        assert alert is not None
        assert alert.alert_type == AlertType.VOLTAGE_SAG.value
        assert alert.severity == Severity.WARNING.value
        assert alert.value == 200.0
        assert alert.threshold == 207.0
        assert "phase L1" in alert.message

    def test_voltage_sag_critical(self):
        rule = VoltageSagSwellRule()
        window = MeterSlidingWindow()
        # 190V is < 195V (Critical)
        reading = make_reading(voltage_l1=230.0, voltage_l2=190.0, voltage_l3=230.0)
        alert = rule.check(reading, window)

        assert alert is not None
        assert alert.alert_type == AlertType.VOLTAGE_SAG.value
        assert alert.severity == Severity.CRITICAL.value
        assert alert.value == 190.0
        assert alert.threshold == 195.0
        assert "phase L2" in alert.message


# ---------------------------------------------------------------------------
# 2. Voltage Swell Tests
# ---------------------------------------------------------------------------


class TestVoltageSwellRule:
    def test_voltage_swell_warning(self):
        rule = VoltageSagSwellRule()
        window = MeterSlidingWindow()
        # 258V is > 253V (Warning) but <= 265V
        reading = make_reading(voltage_l1=230.0, voltage_l2=230.0, voltage_l3=258.0)
        alert = rule.check(reading, window)

        assert alert is not None
        assert alert.alert_type == AlertType.VOLTAGE_SWELL.value
        assert alert.severity == Severity.WARNING.value
        assert alert.value == 258.0
        assert alert.threshold == 253.0
        assert "phase L3" in alert.message

    def test_voltage_swell_critical(self):
        rule = VoltageSagSwellRule()
        window = MeterSlidingWindow()
        # 270V is > 265V (Critical)
        reading = make_reading(voltage_l1=270.0, voltage_l2=230.0, voltage_l3=230.0)
        alert = rule.check(reading, window)

        assert alert is not None
        assert alert.alert_type == AlertType.VOLTAGE_SWELL.value
        assert alert.severity == Severity.CRITICAL.value
        assert alert.value == 270.0
        assert alert.threshold == 265.0
        assert "phase L1" in alert.message


# ---------------------------------------------------------------------------
# 3. Demand Spike Tests
# ---------------------------------------------------------------------------


class TestDemandSpikeRule:
    def test_insufficient_samples_no_spike(self):
        rule = DemandSpikeRule(min_samples=5)
        window = MeterSlidingWindow()
        # Only 2 samples buffered
        window.add(make_reading(active_power_kw=5.0))
        window.add(make_reading(active_power_kw=5.1))

        reading = make_reading(active_power_kw=35.0)
        assert rule.check(reading, window) is None

    def test_demand_spike_detected_beyond_3_sigma(self):
        rule = DemandSpikeRule(min_samples=5, k_sigma=3.0)
        window = MeterSlidingWindow()

        # Seed 10 normal readings around 5 kW with standard deviation ~0.1
        values = [4.9, 5.0, 5.1, 4.95, 5.05, 5.0, 4.9, 5.1, 5.0, 4.95]
        for v in values:
            window.add(make_reading(active_power_kw=v))

        mu = window.mean
        sigma = window.std
        assert 4.9 < mu < 5.1
        assert 0.05 < sigma < 0.15

        # Normal reading: 5.2 kW (within 3 sigma: 5.0 + 3*0.07 ~ 5.21)
        normal = make_reading(active_power_kw=5.15)
        assert rule.check(normal, window) is None

        # Massive demand spike: 35.0 kW
        spike = make_reading(active_power_kw=35.0)
        alert = rule.check(spike, window)

        assert alert is not None
        assert alert.alert_type == AlertType.DEMAND_SPIKE.value
        assert alert.value == 35.0
        assert alert.threshold == pytest.approx(mu + 3.0 * sigma, rel=1e-3)
        assert alert.severity == Severity.CRITICAL.value


# ---------------------------------------------------------------------------
# 4. Phase Imbalance Tests
# ---------------------------------------------------------------------------


class TestPhaseImbalanceRule:
    def test_balanced_phases_no_alert(self):
        rule = PhaseImbalanceRule()
        window = MeterSlidingWindow()
        reading = make_reading(
            voltage_l1=230.0,
            voltage_l2=230.0,
            voltage_l3=230.0,
            current_l1=10.0,
            current_l2=10.0,
            current_l3=10.0,
        )
        assert rule.check(reading, window) is None

    def test_voltage_phase_imbalance(self):
        rule = PhaseImbalanceRule()
        window = MeterSlidingWindow()
        # Imbalance: L1=260V, L2=200V, L3=230V -> avg=230V, max dev=30V -> (30/230)*100 = 13.04%
        # Let's exceed 15%: L1=275V, L2=190V, L3=225V -> avg=230V, dev=45V -> (45/230)*100 = 19.56%
        reading = make_reading(
            voltage_l1=275.0,
            voltage_l2=190.0,
            voltage_l3=225.0,
            current_l1=10.0,
            current_l2=10.0,
            current_l3=10.0,
        )
        alert = rule.check(reading, window)

        assert alert is not None
        assert alert.alert_type == AlertType.PHASE_IMBALANCE.value
        assert alert.threshold == 15.0
        assert alert.value > 15.0
        assert alert.severity == Severity.WARNING.value
        assert "voltage" in alert.message

    def test_current_phase_imbalance(self):
        rule = PhaseImbalanceRule()
        window = MeterSlidingWindow()
        # High current asymmetry: L1=25A, L2=2A, L3=10A -> avg=12.33A, dev=12.67A -> > 100%
        reading = make_reading(
            voltage_l1=230.0,
            voltage_l2=230.0,
            voltage_l3=230.0,
            current_l1=25.0,
            current_l2=2.0,
            current_l3=10.0,
        )
        alert = rule.check(reading, window)

        assert alert is not None
        assert alert.alert_type == AlertType.PHASE_IMBALANCE.value
        assert alert.threshold == 15.0
        assert alert.value > 25.0
        assert alert.severity == Severity.CRITICAL.value
        assert "current" in alert.message


# ---------------------------------------------------------------------------
# 5. Low Power Factor Tests
# ---------------------------------------------------------------------------


class TestLowPowerFactorRule:
    def test_normal_power_factor_no_alert(self):
        rule = LowPowerFactorRule()
        window = MeterSlidingWindow()
        reading = make_reading(power_factor=0.95)
        assert rule.check(reading, window) is None

    def test_low_power_factor_warning(self):
        rule = LowPowerFactorRule()
        window = MeterSlidingWindow()
        reading = make_reading(power_factor=0.78)
        alert = rule.check(reading, window)

        assert alert is not None
        assert alert.alert_type == AlertType.LOW_POWER_FACTOR.value
        assert alert.severity == Severity.WARNING.value
        assert alert.value == 0.78
        assert alert.threshold == 0.85

    def test_low_power_factor_critical(self):
        rule = LowPowerFactorRule()
        window = MeterSlidingWindow()
        reading = make_reading(power_factor=0.62)
        alert = rule.check(reading, window)

        assert alert is not None
        assert alert.alert_type == AlertType.LOW_POWER_FACTOR.value
        assert alert.severity == Severity.CRITICAL.value
        assert alert.value == 0.62


# ---------------------------------------------------------------------------
# 6. Idempotent Storage Tests
# ---------------------------------------------------------------------------


class TestAlertRepository:
    def test_in_memory_repository_idempotency(self):
        repo = InMemoryAlertRepository()
        alert1 = AlertEvent(
            time="2026-11-12T16:00:00Z",
            meter_id="MZ-3P-0042",
            alert_type=AlertType.VOLTAGE_SAG.value,
            severity=Severity.WARNING.value,
            value=202.0,
            threshold=207.0,
            message="Voltage sag warning",
        )
        # First save: should be inserted
        assert repo.save_alert(alert1) is True
        assert len(repo.alerts) == 1
        assert repo.alerts[0].id == 1

        # Duplicate save with same (meter_id, alert_type, time): should be rejected (idempotent)
        assert repo.save_alert(alert1) is False
        assert len(repo.alerts) == 1

        # Different alert_type: should be inserted
        alert2 = AlertEvent(
            time="2026-11-12T16:00:00Z",
            meter_id="MZ-3P-0042",
            alert_type=AlertType.LOW_POWER_FACTOR.value,
            severity=Severity.WARNING.value,
            value=0.72,
            threshold=0.85,
            message="Low PF",
        )
        assert repo.save_alert(alert2) is True
        assert len(repo.alerts) == 2

    def test_postgres_repository_query_structure(self):
        """Verify PostgresAlertRepository matches ON CONFLICT DO NOTHING specification."""
        sql = PostgresAlertRepository.INSERT_SQL.strip()
        assert "ON CONFLICT (meter_id, alert_type, time) DO NOTHING" in sql
        assert "INSERT INTO meter_alerts" in sql
        assert "RETURNING id" in sql

    def test_postgres_repository_mocked_execution(self):
        repo = PostgresAlertRepository(dsn="postgresql://user:pass@localhost:5432/db")

        # Mock psycopg connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (42,)

        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_conn.cursor.return_value = mock_cursor
        repo._conn = mock_conn

        alert = AlertEvent(
            time="2026-11-12T16:00:00Z",
            meter_id="MZ-3P-0042",
            alert_type=AlertType.VOLTAGE_SAG.value,
            severity=Severity.WARNING.value,
            value=202.0,
            threshold=207.0,
            message="Voltage sag",
        )

        # 1. Successful insert returns True
        assert repo.save_alert(alert) is True
        mock_cursor.execute.assert_called_once()

        # 2. Conflict returns None -> save_alert returns False
        mock_cursor.fetchone.return_value = None
        assert repo.save_alert(alert) is False


# ---------------------------------------------------------------------------
# 7. Kafka Publication Mock Tests
# ---------------------------------------------------------------------------


class TestAlertPublisher:
    def test_in_memory_publisher(self):
        pub = InMemoryAlertPublisher()
        alert = AlertEvent(
            time="2026-11-12T16:00:00Z",
            meter_id="MZ-3P-0042",
            alert_type=AlertType.DEMAND_SPIKE.value,
            severity=Severity.WARNING.value,
            value=35.0,
            threshold=18.0,
            message="Demand spike",
        )
        pub.publish_alert(alert)
        assert len(pub.published_alerts) == 1
        assert pub.published_alerts[0] == alert

    def test_kafka_alert_publisher_mocked(self):
        # Instantiate with mocked Producer
        mock_producer = MagicMock()
        publisher = KafkaAlertPublisher(
            bootstrap_servers="localhost:9092",
            topic="iot.alerts",
            producer_config={"client.id": "test-client"},
        )
        publisher.producer = mock_producer

        alert = AlertEvent(
            time="2026-11-12T16:00:00Z",
            meter_id="MZ-3P-0042",
            alert_type=AlertType.VOLTAGE_SWELL.value,
            severity=Severity.CRITICAL.value,
            value=268.0,
            threshold=265.0,
            message="Critical swell",
        )

        publisher.publish_alert(alert)
        mock_producer.produce.assert_called_once()
        call_kwargs = mock_producer.produce.call_args[1]

        assert call_kwargs["topic"] == "iot.alerts"
        assert call_kwargs["key"] == b"MZ-3P-0042"
        # Validate that published payload is valid JSON and contains alert fields
        payload = json.loads(call_kwargs["value"].decode("utf-8"))
        assert payload["meter_id"] == "MZ-3P-0042"
        assert payload["alert_type"] == "VOLTAGE_SWELL"
        assert payload["severity"] == "CRITICAL"
        mock_producer.poll.assert_called_once_with(0)


# ---------------------------------------------------------------------------
# 8. Sliding Window Statistics Tests
# ---------------------------------------------------------------------------


class TestMeterSlidingWindow:
    def test_empty_window_stats(self):
        window = MeterSlidingWindow(capacity=10)
        assert window.count == 0
        assert window.is_empty is True
        assert window.mean == 0.0
        assert window.std == 0.0
        assert window.ewma == 0.0
        assert window.latest is None

    def test_rolling_mean_and_std(self):
        window = MeterSlidingWindow(capacity=5)
        # Add values: 10, 12, 14, 16, 18 -> mean = 14, variance = 10, std = sqrt(10) ~ 3.162277
        for v in [10.0, 12.0, 14.0, 16.0, 18.0]:
            window.add(make_reading(active_power_kw=v))

        assert window.count == 5
        assert window.mean == pytest.approx(14.0)
        assert window.std == pytest.approx(3.162277, rel=1e-4)

    def test_bounded_ring_buffer_eviction(self):
        window = MeterSlidingWindow(capacity=3)
        window.add(make_reading(active_power_kw=10.0))
        window.add(make_reading(active_power_kw=20.0))
        window.add(make_reading(active_power_kw=30.0))
        assert window.count == 3
        assert window.mean == pytest.approx(20.0)

        # 4th reading should evict the 1st reading (10.0)
        window.add(make_reading(active_power_kw=40.0))
        assert window.count == 3
        assert window.mean == pytest.approx(30.0)  # (20 + 30 + 40) / 3 = 30.0

    def test_ewma_calculation(self):
        alpha = 0.5
        window = MeterSlidingWindow(capacity=10, alpha=alpha)

        # 1st point: EWMA = 10.0
        window.add(make_reading(active_power_kw=10.0))
        assert window.ewma == pytest.approx(10.0)

        # 2nd point: EWMA = 0.5 * 20.0 + 0.5 * 10.0 = 15.0
        window.add(make_reading(active_power_kw=20.0))
        assert window.ewma == pytest.approx(15.0)

        # 3rd point: EWMA = 0.5 * 30.0 + 0.5 * 15.0 = 22.5
        window.add(make_reading(active_power_kw=30.0))
        assert window.ewma == pytest.approx(22.5)

    def test_window_reset(self):
        window = MeterSlidingWindow(capacity=10)
        window.add(make_reading(active_power_kw=15.0))
        assert window.count == 1
        window.reset()
        assert window.count == 0
        assert window.is_empty is True
        assert window.mean == 0.0
        assert window.ewma == 0.0


# ---------------------------------------------------------------------------
# 9. Dependency Inversion Principle & Open/Closed Principle
# ---------------------------------------------------------------------------


class CustomNegativePowerRule(AnomalyRule):
    """Custom plug-in rule detecting unexpected power export (active_power_kw < 0).

    Demonstrates Open/Closed Principle (OCP): New rule plugged in without modifying AnomalyEngine.
    """

    def check(self, reading: TelemetryReading, window: MeterSlidingWindow) -> AlertEvent | None:
        if reading.active_power_kw < 0.0:
            return AlertEvent(
                time=reading.timestamp_iso,
                meter_id=reading.meter_id,
                alert_type="FREQUENCY_DEVIATION",  # fits schema enum
                severity=Severity.WARNING.value,
                value=reading.active_power_kw,
                threshold=0.0,
                message=f"Reverse active power detected: {reading.active_power_kw} kW",
            )
        return None


class TestAnomalyEngineDIPAndOCP:
    def test_engine_dependency_injection_and_ocp(self):
        repo = InMemoryAlertRepository()
        pub = InMemoryAlertPublisher()

        # Inject standard rules PLUS the custom plug-in rule (OCP)
        rules: list[AnomalyRule] = [
            VoltageSagSwellRule(),
            LowPowerFactorRule(),
            FrequencyDeviationRule(),
            CustomNegativePowerRule(),
        ]

        engine = AnomalyEngine(
            repository=repo,
            publisher=pub,
            rules=rules,
            window_capacity=50,
        )

        # 1. Normal reading -> 0 alerts
        reading_normal = make_reading(active_power_kw=5.0, voltage_l1=230.0, power_factor=0.95)
        emitted_normal = engine.process_reading(reading_normal)
        assert len(emitted_normal) == 0
        assert len(repo.alerts) == 0
        assert len(pub.published_alerts) == 0

        # 2. Reading triggering both Sag and CustomNegativePowerRule
        reading_faulty = make_reading(
            active_power_kw=-2.5,
            voltage_l1=192.0,  # Critical sag
            power_factor=0.95,
        )
        emitted_faulty = engine.process_reading(reading_faulty)

        # 2 alerts should be generated, saved, and published
        assert len(emitted_faulty) == 2
        assert len(repo.alerts) == 2
        assert len(pub.published_alerts) == 2

        alert_types = {a.alert_type for a in emitted_faulty}
        assert AlertType.VOLTAGE_SAG.value in alert_types
        assert "FREQUENCY_DEVIATION" in alert_types


# ---------------------------------------------------------------------------
# 10. Strict Schema Conformance against docs/schemas/alert.json
# ---------------------------------------------------------------------------


class TestAlertSchemaConformance:
    def test_all_rule_alerts_comply_with_schema(self, alert_schema):
        """Ensure every alert emitted by any rule strictly adheres to alert.json schema."""
        rules = [
            VoltageSagSwellRule(),
            DemandSpikeRule(min_samples=2),
            PhaseImbalanceRule(),
            LowPowerFactorRule(),
            FrequencyDeviationRule(),
        ]

        window = MeterSlidingWindow()
        window.add(make_reading(active_power_kw=5.0))
        window.add(make_reading(active_power_kw=5.0))

        test_readings = [
            # Sag
            make_reading(voltage_l1=192.0),
            # Swell
            make_reading(voltage_l1=268.0),
            # Demand spike
            make_reading(active_power_kw=35.0),
            # Phase imbalance
            make_reading(voltage_l1=280.0, voltage_l2=190.0, voltage_l3=220.0),
            # Low power factor
            make_reading(power_factor=0.65),
            # Under frequency
            make_reading(frequency_hz=49.1),
            # Over frequency
            make_reading(frequency_hz=50.8),
        ]

        alerts_tested = 0
        for reading in test_readings:
            for rule in rules:
                alert = rule.check(reading, window)
                if alert is not None:
                    alert_dict = alert.to_dict()
                    # Validate against docs/schemas/alert.json
                    jsonschema.validate(instance=alert_dict, schema=alert_schema)
                    alerts_tested += 1

        assert alerts_tested >= 7, f"Expected at least 7 alerts tested against schema, got {alerts_tested}"


# ---------------------------------------------------------------------------
# 11. Consumer Partition Rebalance Safety
# ---------------------------------------------------------------------------


class TestRebalanceSafety:
    def test_partition_revocation_clears_windows(self):
        repo = InMemoryAlertRepository()
        pub = InMemoryAlertPublisher()
        engine = AnomalyEngine(repo, pub, [VoltageSagSwellRule()])

        # Populate sliding windows for multiple meters
        engine.process_reading(make_reading(meter_id="MZ-3P-0001"))
        engine.process_reading(make_reading(meter_id="MZ-3P-0002"))

        assert len(engine.windows) == 2
        assert engine.windows["MZ-3P-0001"].count == 1
        assert engine.windows["MZ-3P-0002"].count == 1

        # Simulate partition revocation rebalance event
        engine.clear_windows()

        assert len(engine.windows) == 0

        # Next reading creates fresh window without cross-partition pollution
        engine.process_reading(make_reading(meter_id="MZ-3P-0001"))
        assert len(engine.windows) == 1
        assert engine.windows["MZ-3P-0001"].count == 1
