use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::str::FromStr;

use super::error::DomainError;

/// Continuous aggregate rollup bucket resolution.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RollupBucket {
    OneMinute,
    Hourly,
    Daily,
}

impl RollupBucket {
    pub fn as_str(&self) -> &'static str {
        match self {
            RollupBucket::OneMinute => "1m",
            RollupBucket::Hourly => "1h",
            RollupBucket::Daily => "1d",
        }
    }

    pub fn table_name(&self) -> &'static str {
        match self {
            RollupBucket::OneMinute => "one_minute_consumption_rollup",
            RollupBucket::Hourly => "hourly_consumption_rollup",
            RollupBucket::Daily => "daily_consumption_rollup",
        }
    }
}

impl FromStr for RollupBucket {
    type Err = DomainError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.trim().to_lowercase().as_str() {
            "1m" | "1min" | "1minute" => Ok(RollupBucket::OneMinute),
            "1h" | "1hour" | "hourly" => Ok(RollupBucket::Hourly),
            "1d" | "1day" | "daily" => Ok(RollupBucket::Daily),
            other => Err(DomainError::InvalidBucket(format!(
                "Unsupported bucket '{}'. Supported values are: '1m', '1h', '1d'",
                other
            ))),
        }
    }
}

/// Timeseries point from rollup materialized views.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TimeseriesPoint {
    pub bucket: DateTime<Utc>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub avg_active_power_kw: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_active_power_kw: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub min_active_power_kw: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub delta_energy_kwh: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub avg_power_factor: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub avg_voltage_l1: Option<f64>,
    pub reading_count: i64,
}
