use async_trait::async_trait;
use chrono::{DateTime, Utc};
use deadpool_postgres::Pool;

use super::error::RepositoryError;
use super::timeseries::TimeseriesRepository;
use crate::domain::{ConsumptionResponse, RollupBucket, TimeseriesPoint};

pub struct TimescaleTimeseriesRepository {
    pool: Pool,
}

impl TimescaleTimeseriesRepository {
    pub fn new(pool: Pool) -> Self {
        Self { pool }
    }
}

#[async_trait]
impl TimeseriesRepository for TimescaleTimeseriesRepository {
    async fn query_timeseries(
        &self,
        meter_id: &str,
        from: DateTime<Utc>,
        to: DateTime<Utc>,
        bucket_str: &str,
    ) -> Result<Vec<TimeseriesPoint>, RepositoryError> {
        let bucket: RollupBucket = bucket_str
            .parse()
            .map_err(|e| RepositoryError::InvalidInput(format!("{e}")))?;

        let client = self
            .pool
            .get()
            .await
            .map_err(|e| RepositoryError::Connection(e.to_string()))?;

        let query = match bucket {
            RollupBucket::OneMinute => {
                "SELECT bucket, avg_active_power_kw, max_active_power_kw, min_active_power_kw, \
                        NULL::double precision AS delta_energy_kwh, avg_power_factor, avg_voltage_l1, reading_count \
                 FROM one_minute_consumption_rollup \
                 WHERE meter_id = $1 AND bucket >= $2 AND bucket <= $3 \
                 ORDER BY bucket ASC"
            }
            RollupBucket::Hourly => {
                "SELECT bucket, avg_active_power_kw, max_active_power_kw, min_active_power_kw, \
                        delta_energy_kwh, avg_power_factor, avg_voltage_l1, reading_count \
                 FROM hourly_consumption_rollup \
                 WHERE meter_id = $1 AND bucket >= $2 AND bucket <= $3 \
                 ORDER BY bucket ASC"
            }
            RollupBucket::Daily => {
                "SELECT bucket, avg_active_power_kw, max_active_power_kw, NULL::double precision AS min_active_power_kw, \
                        delta_energy_kwh, avg_power_factor, NULL::double precision AS avg_voltage_l1, reading_count \
                 FROM daily_consumption_rollup \
                 WHERE meter_id = $1 AND bucket >= $2 AND bucket <= $3 \
                 ORDER BY bucket ASC"
            }
        };

        let rows = client
            .query(query, &[&meter_id, &from, &to])
            .await
            .map_err(|e| RepositoryError::Database(e.to_string()))?;

        let mut points = Vec::with_capacity(rows.len());
        for row in rows {
            points.push(TimeseriesPoint {
                bucket: row.get("bucket"),
                avg_active_power_kw: row.get("avg_active_power_kw"),
                max_active_power_kw: row.get("max_active_power_kw"),
                min_active_power_kw: row.get("min_active_power_kw"),
                delta_energy_kwh: row.get("delta_energy_kwh"),
                avg_power_factor: row.get("avg_power_factor"),
                avg_voltage_l1: row.get("avg_voltage_l1"),
                reading_count: row.get("reading_count"),
            });
        }

        Ok(points)
    }

    async fn query_consumption(
        &self,
        meter_id: &str,
        from: Option<DateTime<Utc>>,
        to: Option<DateTime<Utc>>,
    ) -> Result<ConsumptionResponse, RepositoryError> {
        let client = self
            .pool
            .get()
            .await
            .map_err(|e| RepositoryError::Connection(e.to_string()))?;

        let query = "SELECT \
                COALESCE(MAX(energy_kwh) - MIN(energy_kwh), 0.0) AS total_consumption_kwh, \
                COUNT(*)::bigint AS reading_count \
             FROM meter_readings \
             WHERE meter_id = $1 \
               AND ($2::timestamptz IS NULL OR time >= $2) \
               AND ($3::timestamptz IS NULL OR time <= $3)";

        let row = client
            .query_one(query, &[&meter_id, &from, &to])
            .await
            .map_err(|e| RepositoryError::Database(e.to_string()))?;

        let total_consumption_kwh: f64 = row.get("total_consumption_kwh");
        let reading_count: i64 = row.get("reading_count");

        Ok(ConsumptionResponse {
            meter_id: meter_id.to_string(),
            from,
            to,
            total_consumption_kwh,
            reading_count,
        })
    }
}
