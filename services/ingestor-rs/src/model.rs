use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Diagnostic status of the smart meter.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "UPPERCASE")]
pub enum DeviceStatus {
    #[default]
    Ok,
    Warning,
    Error,
}

impl std::fmt::Display for DeviceStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Ok => write!(f, "OK"),
            Self::Warning => write!(f, "WARNING"),
            Self::Error => write!(f, "ERROR"),
        }
    }
}

/// 3-phase smart meter telemetry metric payload.
///
/// Matches the schema defined in `docs/schemas/telemetry.json`.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SmartMeterTelemetry {
    /// Unique identifier of the 3-phase meter (e.g. "MZ-3P-0042")
    pub meter_id: String,

    /// ISO-8601 UTC timestamp of measurement reading
    pub timestamp: DateTime<Utc>,

    /// Phase 1 RMS Voltage in Volts (nominal 230V, range 0..500V)
    pub voltage_l1: f64,

    /// Phase 2 RMS Voltage in Volts (nominal 230V, range 0..500V)
    pub voltage_l2: f64,

    /// Phase 3 RMS Voltage in Volts (nominal 230V, range 0..500V)
    pub voltage_l3: f64,

    /// Phase 1 RMS Current in Amperes (range 0..200A)
    pub current_l1: f64,

    /// Phase 2 RMS Current in Amperes (range 0..200A)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub current_l2: Option<f64>,

    /// Phase 3 RMS Current in Amperes (range 0..200A)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub current_l3: Option<f64>,

    /// Total 3-phase active real power in Kilowatts (range -100..200 kW)
    pub active_power_kw: f64,

    /// Cumulative forward active energy in Kilowatt-hours (>= 0.0 kWh)
    pub total_energy_kwh: f64,

    /// Total power factor cos phi (range -1.0..1.0)
    pub power_factor: f64,

    /// AC mains frequency in Hertz (nominal 50.0 Hz, range 40..65 Hz)
    pub frequency_hz: f64,

    /// Zigbee / Mesh radio Link Quality Indicator (0..255)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub zigbee_lqi: Option<u16>,

    /// Internal hardware self-diagnostic status
    #[serde(default)]
    pub status: DeviceStatus,
}

#[derive(Debug, Error, PartialEq)]
pub enum ValidationError {
    #[error("Invalid meter_id format '{0}': expected pattern '^MZ-3P-[0-9]{{4}}$'")]
    InvalidMeterId(String),

    #[error("Invalid voltage_l1: {0}V (expected 0.0..=500.0)")]
    InvalidVoltageL1(f64),

    #[error("Invalid voltage_l2: {0}V (expected 0.0..=500.0)")]
    InvalidVoltageL2(f64),

    #[error("Invalid voltage_l3: {0}V (expected 0.0..=500.0)")]
    InvalidVoltageL3(f64),

    #[error("Invalid current_l1: {0}A (expected 0.0..=200.0)")]
    InvalidCurrentL1(f64),

    #[error("Invalid current_l2: {0}A (expected 0.0..=200.0)")]
    InvalidCurrentL2(f64),

    #[error("Invalid current_l3: {0}A (expected 0.0..=200.0)")]
    InvalidCurrentL3(f64),

    #[error("Invalid active_power_kw: {0}kW (expected -100.0..=200.0)")]
    InvalidActivePower(f64),

    #[error("Invalid total_energy_kwh: {0}kWh (expected >= 0.0)")]
    InvalidTotalEnergy(f64),

    #[error("Invalid power_factor: {0} (expected -1.0..=1.0)")]
    InvalidPowerFactor(f64),

    #[error("Invalid frequency_hz: {0}Hz (expected 40.0..=65.0)")]
    InvalidFrequency(f64),

    #[error("Invalid zigbee_lqi: {0} (expected 0..=255)")]
    InvalidZigbeeLqi(u16),
}

/// Checks whether the meter ID matches the required pattern: ^MZ-3P-[0-9]{4}$
pub fn is_valid_meter_id(id: &str) -> bool {
    id.len() == 10
        && id.starts_with("MZ-3P-")
        && id.as_bytes()[6..].iter().all(|b| b.is_ascii_digit())
}

impl SmartMeterTelemetry {
    /// Validates all metric values according to physical electrical bounds
    /// and schema constraints defined in `docs/schemas/telemetry.json`.
    pub fn validate(&self) -> Result<(), ValidationError> {
        if !is_valid_meter_id(&self.meter_id) {
            return Err(ValidationError::InvalidMeterId(self.meter_id.clone()));
        }

        if !self.voltage_l1.is_finite() || !(0.0..=500.0).contains(&self.voltage_l1) {
            return Err(ValidationError::InvalidVoltageL1(self.voltage_l1));
        }

        if !self.voltage_l2.is_finite() || !(0.0..=500.0).contains(&self.voltage_l2) {
            return Err(ValidationError::InvalidVoltageL2(self.voltage_l2));
        }

        if !self.voltage_l3.is_finite() || !(0.0..=500.0).contains(&self.voltage_l3) {
            return Err(ValidationError::InvalidVoltageL3(self.voltage_l3));
        }

        if !self.current_l1.is_finite() || !(0.0..=200.0).contains(&self.current_l1) {
            return Err(ValidationError::InvalidCurrentL1(self.current_l1));
        }

        if let Some(i2) = self.current_l2 {
            if !i2.is_finite() || !(0.0..=200.0).contains(&i2) {
                return Err(ValidationError::InvalidCurrentL2(i2));
            }
        }

        if let Some(i3) = self.current_l3 {
            if !i3.is_finite() || !(0.0..=200.0).contains(&i3) {
                return Err(ValidationError::InvalidCurrentL3(i3));
            }
        }

        if !self.active_power_kw.is_finite() || !(-100.0..=200.0).contains(&self.active_power_kw) {
            return Err(ValidationError::InvalidActivePower(self.active_power_kw));
        }

        if !self.total_energy_kwh.is_finite() || self.total_energy_kwh < 0.0 {
            return Err(ValidationError::InvalidTotalEnergy(self.total_energy_kwh));
        }

        if !self.power_factor.is_finite() || !(-1.0..=1.0).contains(&self.power_factor) {
            return Err(ValidationError::InvalidPowerFactor(self.power_factor));
        }

        if !self.frequency_hz.is_finite() || !(40.0..=65.0).contains(&self.frequency_hz) {
            return Err(ValidationError::InvalidFrequency(self.frequency_hz));
        }

        if let Some(lqi) = self.zigbee_lqi {
            if lqi > 255 {
                return Err(ValidationError::InvalidZigbeeLqi(lqi));
            }
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn sample_valid_telemetry() -> SmartMeterTelemetry {
        SmartMeterTelemetry {
            meter_id: "MZ-3P-0042".to_string(),
            timestamp: Utc.with_ymd_and_hms(2026, 11, 12, 15, 4, 5).unwrap(),
            voltage_l1: 230.4,
            voltage_l2: 229.8,
            voltage_l3: 231.1,
            current_l1: 12.8,
            current_l2: Some(11.5),
            current_l3: Some(13.2),
            active_power_kw: 2.85,
            total_energy_kwh: 1452.3,
            power_factor: 0.96,
            frequency_hz: 50.01,
            zigbee_lqi: Some(187),
            status: DeviceStatus::Ok,
        }
    }

    #[test]
    fn test_valid_telemetry_deserialization() {
        let json_data = r#"{
            "meter_id": "MZ-3P-0042",
            "timestamp": "2026-11-12T15:04:05Z",
            "voltage_l1": 230.4,
            "voltage_l2": 229.8,
            "voltage_l3": 231.1,
            "current_l1": 12.8,
            "active_power_kw": 2.85,
            "total_energy_kwh": 1452.3,
            "power_factor": 0.96,
            "frequency_hz": 50.01,
            "zigbee_lqi": 187,
            "status": "OK"
        }"#;

        let telemetry: SmartMeterTelemetry = serde_json::from_str(json_data).unwrap();
        assert_eq!(telemetry.meter_id, "MZ-3P-0042");
        assert_eq!(telemetry.status, DeviceStatus::Ok);
        assert_eq!(telemetry.zigbee_lqi, Some(187));
        assert!(telemetry.validate().is_ok());
    }

    #[test]
    fn test_default_status_when_missing() {
        let json_data = r#"{
            "meter_id": "MZ-3P-0001",
            "timestamp": "2026-11-12T15:00:00Z",
            "voltage_l1": 230.0,
            "voltage_l2": 230.0,
            "voltage_l3": 230.0,
            "current_l1": 10.0,
            "active_power_kw": 2.3,
            "total_energy_kwh": 100.0,
            "power_factor": 0.98,
            "frequency_hz": 50.0
        }"#;

        let telemetry: SmartMeterTelemetry = serde_json::from_str(json_data).unwrap();
        assert_eq!(telemetry.status, DeviceStatus::Ok);
        assert_eq!(telemetry.current_l2, None);
        assert_eq!(telemetry.current_l3, None);
        assert!(telemetry.validate().is_ok());
    }

    #[test]
    fn test_rejects_unknown_fields() {
        let json_data = r#"{
            "meter_id": "MZ-3P-0042",
            "timestamp": "2026-11-12T15:04:05Z",
            "voltage_l1": 230.4,
            "voltage_l2": 229.8,
            "voltage_l3": 231.1,
            "current_l1": 12.8,
            "active_power_kw": 2.85,
            "total_energy_kwh": 1452.3,
            "power_factor": 0.96,
            "frequency_hz": 50.01,
            "unknown_extra_field": "injected"
        }"#;

        let result: Result<SmartMeterTelemetry, _> = serde_json::from_str(json_data);
        assert!(result.is_err(), "Should deny unknown fields according to schema");
    }

    #[test]
    fn test_invalid_meter_id() {
        let mut telemetry = sample_valid_telemetry();

        telemetry.meter_id = "INVALID_ID".to_string();
        assert_eq!(
            telemetry.validate(),
            Err(ValidationError::InvalidMeterId("INVALID_ID".to_string()))
        );

        telemetry.meter_id = "MZ-3P-004a".to_string();
        assert!(telemetry.validate().is_err());

        telemetry.meter_id = "MZ-1P-0042".to_string();
        assert!(telemetry.validate().is_err());

        telemetry.meter_id = "MZ-3P-00425".to_string();
        assert!(telemetry.validate().is_err());
    }

    #[test]
    fn test_voltage_out_of_bounds() {
        let mut telemetry = sample_valid_telemetry();

        telemetry.voltage_l1 = 500.1;
        assert_eq!(
            telemetry.validate(),
            Err(ValidationError::InvalidVoltageL1(500.1))
        );

        telemetry.voltage_l1 = -1.0;
        assert_eq!(
            telemetry.validate(),
            Err(ValidationError::InvalidVoltageL1(-1.0))
        );

        telemetry.voltage_l1 = f64::NAN;
        assert!(telemetry.validate().is_err());
    }

    #[test]
    fn test_current_out_of_bounds() {
        let mut telemetry = sample_valid_telemetry();

        telemetry.current_l1 = 200.5;
        assert_eq!(
            telemetry.validate(),
            Err(ValidationError::InvalidCurrentL1(200.5))
        );

        telemetry.current_l2 = Some(250.0);
        telemetry.current_l1 = 10.0;
        assert_eq!(
            telemetry.validate(),
            Err(ValidationError::InvalidCurrentL2(250.0))
        );
    }

    #[test]
    fn test_power_factor_bounds() {
        let mut telemetry = sample_valid_telemetry();

        telemetry.power_factor = 1.05;
        assert_eq!(
            telemetry.validate(),
            Err(ValidationError::InvalidPowerFactor(1.05))
        );

        telemetry.power_factor = -1.05;
        assert_eq!(
            telemetry.validate(),
            Err(ValidationError::InvalidPowerFactor(-1.05))
        );

        telemetry.power_factor = -1.0;
        assert!(telemetry.validate().is_ok());

        telemetry.power_factor = 1.0;
        assert!(telemetry.validate().is_ok());
    }

    #[test]
    fn test_frequency_bounds() {
        let mut telemetry = sample_valid_telemetry();

        telemetry.frequency_hz = 39.9;
        assert_eq!(
            telemetry.validate(),
            Err(ValidationError::InvalidFrequency(39.9))
        );

        telemetry.frequency_hz = 65.1;
        assert_eq!(
            telemetry.validate(),
            Err(ValidationError::InvalidFrequency(65.1))
        );
    }

    #[test]
    fn test_total_energy_negative() {
        let mut telemetry = sample_valid_telemetry();
        telemetry.total_energy_kwh = -0.1;
        assert_eq!(
            telemetry.validate(),
            Err(ValidationError::InvalidTotalEnergy(-0.1))
        );
    }

    #[test]
    fn test_zigbee_lqi_bounds() {
        let mut telemetry = sample_valid_telemetry();
        telemetry.zigbee_lqi = Some(300);
        assert_eq!(
            telemetry.validate(),
            Err(ValidationError::InvalidZigbeeLqi(300))
        );
    }
}
