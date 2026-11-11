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
    #[serde(
        default,
        skip_serializing_if = "Option::is_none",
        with = "flexible_installed_at"
    )]
    pub installed_at: Option<DateTime<Utc>>,
    pub status: String,
}

pub mod flexible_installed_at {
    use super::*;
    use serde::{Deserializer, Serializer};

    pub fn serialize<S>(val: &Option<DateTime<Utc>>, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        val.serialize(serializer)
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<Option<DateTime<Utc>>, D::Error>
    where
        D: Deserializer<'de>,
    {
        let b = bson::Bson::deserialize(deserializer)?;
        match b {
            bson::Bson::Null => Ok(None),
            bson::Bson::DateTime(dt) => Ok(Some(dt.to_chrono())),
            bson::Bson::String(s) => DateTime::parse_from_rfc3339(&s)
                .map(|dt| Some(dt.with_timezone(&Utc)))
                .map_err(serde::de::Error::custom),
            bson::Bson::Int64(ms) => Ok(DateTime::from_timestamp_millis(ms)),
            bson::Bson::Document(doc) => {
                if let Some(bson::Bson::DateTime(dt)) = doc.get("$date") {
                    Ok(Some(dt.to_chrono()))
                } else if let Some(bson::Bson::Int64(ms)) = doc.get("$date") {
                    Ok(DateTime::from_timestamp_millis(*ms))
                } else {
                    Ok(None)
                }
            }
            _ => Ok(None),
        }
    }
}
