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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_device_twin_json_roundtrip() {
        let twin = DeviceTwin {
            meter_id: "MZ-3P-0042".to_string(),
            firmware_version: "v2.4.1".to_string(),
            zone: "north".to_string(),
            phase_type: "3P+N".to_string(),
            nominal_voltage: 230.0,
            nominal_frequency: 50.0,
            thresholds: TwinThresholds {
                voltage_min: 207.0,
                voltage_max: 253.0,
                active_power_kw_max: 25.0,
                power_factor_min: 0.85,
            },
            location: TwinLocation {
                lat: 37.9838,
                lon: 23.7275,
            },
            installed_at: Some(Utc::now()),
            status: "ACTIVE".to_string(),
        };

        let json = serde_json::to_string(&twin).unwrap();
        let deserialized: DeviceTwin = serde_json::from_str(&json).unwrap();
        assert_eq!(twin.meter_id, deserialized.meter_id);
        assert_eq!(twin.zone, deserialized.zone);
    }
}
