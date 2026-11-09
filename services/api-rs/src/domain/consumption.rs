use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// Aggregated consumption response over an optional time window.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ConsumptionResponse {
    pub meter_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub from: Option<DateTime<Utc>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub to: Option<DateTime<Utc>>,
    pub total_consumption_kwh: f64,
    pub reading_count: i64,
}
