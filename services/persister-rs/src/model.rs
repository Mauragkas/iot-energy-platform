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
