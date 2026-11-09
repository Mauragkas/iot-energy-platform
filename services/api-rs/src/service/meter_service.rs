use std::sync::Arc;
use chrono::{DateTime, Utc};

use crate::domain::{
    ConsumptionResponse, DeviceTwin, MeterId, RollupBucket, TimeRange, TimeseriesPoint,
};
use crate::repository::{TimeseriesRepository, TwinRepository};
use super::error::ServiceError;

pub const MAX_PAGINATION_LIMIT: usize = 2000;
pub const DEFAULT_PAGINATION_LIMIT: usize = 100;
pub const MAX_QUERY_WINDOW_DAYS: i64 = 30;

pub struct MeterService {
    twin_repo: Arc<dyn TwinRepository>,
    timeseries_repo: Arc<dyn TimeseriesRepository>,
}

impl MeterService {
    pub fn new(
        twin_repo: Arc<dyn TwinRepository>,
        timeseries_repo: Arc<dyn TimeseriesRepository>,
    ) -> Self {
        Self {
            twin_repo,
            timeseries_repo,
        }
    }

    /// Lists device twins with optional zone filter, enforcing maximum pagination bounds.
    pub async fn list_meters(
        &self,
        zone: Option<&str>,
        limit: Option<usize>,
    ) -> Result<Vec<DeviceTwin>, ServiceError> {
        let capped_limit = limit
            .unwrap_or(DEFAULT_PAGINATION_LIMIT)
            .clamp(1, MAX_PAGINATION_LIMIT);

        let twins = self.twin_repo.list_twins(zone, capped_limit).await?;
        Ok(twins)
    }

    /// Fetches a single device twin by meter_id.
    pub async fn get_meter(&self, id: &str) -> Result<DeviceTwin, ServiceError> {
        let valid_id = MeterId::new(id)?;
        let maybe_twin = self.twin_repo.get_twin(valid_id.as_str()).await?;
        maybe_twin.ok_or_else(|| ServiceError::NotFound(format!("Meter '{}' not found", id)))
    }

    /// Queries timeseries rollup points over a bounded time window (max 30 days).
    pub async fn query_timeseries(
        &self,
        id: &str,
        from: DateTime<Utc>,
        to: DateTime<Utc>,
        bucket_str: &str,
    ) -> Result<Vec<TimeseriesPoint>, ServiceError> {
        let valid_id = MeterId::new(id)?;
        let time_range = TimeRange::new(from, to)?;
        time_range.validate_max_window(MAX_QUERY_WINDOW_DAYS)?;

        let bucket: RollupBucket = bucket_str.parse()?;

        let points = self
            .timeseries_repo
            .query_timeseries(valid_id.as_str(), from, to, bucket.as_str())
            .await?;

        Ok(points)
    }

    /// Queries consumption delta over an optional time window, validating window bounds if supplied.
    pub async fn query_consumption(
        &self,
        id: &str,
        from: Option<DateTime<Utc>>,
        to: Option<DateTime<Utc>>,
    ) -> Result<ConsumptionResponse, ServiceError> {
        let valid_id = MeterId::new(id)?;

        if let (Some(f), Some(t)) = (from, to) {
            let time_range = TimeRange::new(f, t)?;
            time_range.validate_max_window(MAX_QUERY_WINDOW_DAYS)?;
        }

        let resp = self
            .timeseries_repo
            .query_consumption(valid_id.as_str(), from, to)
            .await?;

        Ok(resp)
    }
}
