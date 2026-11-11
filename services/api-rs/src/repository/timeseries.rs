use async_trait::async_trait;
use chrono::{DateTime, Utc};

use super::error::RepositoryError;
use crate::domain::{ConsumptionResponse, TimeseriesPoint};

#[async_trait]
pub trait TimeseriesRepository: Send + Sync {
    /// Queries continuous aggregate views: `one_minute_consumption_rollup`, `hourly_consumption_rollup`, or `daily_consumption_rollup`.
    async fn query_timeseries(
        &self,
        meter_id: &str,
        from: DateTime<Utc>,
        to: DateTime<Utc>,
        bucket: &str,
    ) -> Result<Vec<TimeseriesPoint>, RepositoryError>;

    /// Queries aggregated consumption (kWh delta and reading count) over an optional time window.
    async fn query_consumption(
        &self,
        meter_id: &str,
        from: Option<DateTime<Utc>>,
        to: Option<DateTime<Utc>>,
    ) -> Result<ConsumptionResponse, RepositoryError>;
}
