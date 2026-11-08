use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Telemetry reading deserialized from Kafka topic `iot.telemetry.raw`.
///
/// Supports standard fields matching the TimescaleDB `meter_readings` table,
/// with serde aliases for flexibility across different meter simulator conventions
/// (`timestamp` -> `time`, `total_energy_kwh` -> `energy_kwh`).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TelemetryReading {
    #[serde(alias = "timestamp")]
    pub time: DateTime<Utc>,

    pub meter_id: String,

    pub voltage_l1: f64,

    #[serde(default)]
    pub voltage_l2: f64,

    #[serde(default)]
    pub voltage_l3: f64,

    pub current_l1: f64,

    #[serde(default)]
    pub current_l2: f64,

    #[serde(default)]
    pub current_l3: f64,

    pub active_power_kw: f64,

    #[serde(alias = "total_energy_kwh")]
    pub energy_kwh: f64,

    pub power_factor: f64,

    pub frequency_hz: f64,
}

impl TelemetryReading {
    /// Deserialize a TelemetryReading from raw JSON bytes.
    pub fn from_json_slice(slice: &[u8]) -> Result<Self, serde_json::Error> {
        serde_json::from_slice(slice)
    }

    /// Deserialize a TelemetryReading from a JSON string slice.
    pub fn from_json_str(s: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(s)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_standard_payload() {
        let json = r#"{
            "time": "2026-11-12T15:04:05Z",
            "meter_id": "meter_001",
            "voltage_l1": 230.1,
            "voltage_l2": 229.9,
            "voltage_l3": 230.5,
            "current_l1": 10.5,
            "current_l2": 11.0,
            "current_l3": 10.8,
            "active_power_kw": 7.25,
            "energy_kwh": 12500.5,
            "power_factor": 0.98,
            "frequency_hz": 50.02
        }"#;

        let reading: TelemetryReading = TelemetryReading::from_json_str(json).expect("should parse");
        assert_eq!(reading.meter_id, "meter_001");
        assert_eq!(reading.voltage_l1, 230.1);
        assert_eq!(reading.energy_kwh, 12500.5);
        assert_eq!(reading.frequency_hz, 50.02);
    }

    #[test]
    fn test_deserialize_aliased_payload_with_extra_fields() {
        let json = r#"{
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

        let reading = TelemetryReading::from_json_str(json).expect("should parse with aliases");
        assert_eq!(reading.meter_id, "MZ-3P-0042");
        assert_eq!(reading.energy_kwh, 1452.3);
        assert_eq!(reading.current_l2, 0.0);
        assert_eq!(reading.current_l3, 0.0);
    }

    #[test]
    fn test_deserialize_invalid_json() {
        let json = r#"{"meter_id": "invalid"}"#;
        assert!(TelemetryReading::from_json_str(json).is_err());
    }
}
