use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Operational thresholds configured on the meter.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TwinThresholds {
    pub voltage_min: f64,
    pub voltage_max: f64,
    pub active_power_kw_max: f64,
    pub power_factor_min: f64,
}

/// Geographic coordinates for the device location.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TwinLocation {
    pub lat: f64,
    pub lon: f64,
}

/// Device twin metadata stored in MongoDB.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DeviceTwin {
    pub meter_id: String,
    pub firmware_version: String,
    pub zone: String,
    pub phase_type: String,
    pub nominal_voltage: f64,
    pub nominal_frequency: f64,
    pub thresholds: TwinThresholds,
    pub location: TwinLocation,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub installed_at: Option<DateTime<Utc>>,
    pub status: String,
}
