use async_trait::async_trait;
use chrono::{DateTime, Utc};
use deadpool_postgres::Pool;

use crate::domain::AlertRecord;
use super::alert::AlertRepository;
use super::error::RepositoryError;

pub struct TimescaleAlertRepository {
    pool: Pool,
}

impl TimescaleAlertRepository {
    pub fn new(pool: Pool) -> Self {
        Self { pool }
    }
}

#[async_trait]
impl AlertRepository for TimescaleAlertRepository {
    async fn list_alerts(
        &self,
        severity: Option<&str>,
        since: Option<DateTime<Utc>>,
        limit: usize,
    ) -> Result<Vec<AlertRecord>, RepositoryError> {
        let client = self
            .pool
            .get()
            .await
            .map_err(|e| RepositoryError::Connection(e.to_string()))?;

        let limit_i64 = limit as i64;
        let query = "SELECT id, time, meter_id, alert_type, severity, value, threshold, message, created_at \
                     FROM meter_alerts \
                     WHERE ($1::text IS NULL OR severity = $1) \
                       AND ($2::timestamptz IS NULL OR time >= $2) \
                     ORDER BY time DESC \
                     LIMIT $3";

        let rows = client
            .query(query, &[&severity, &since, &limit_i64])
            .await
            .map_err(|e| RepositoryError::Database(e.to_string()))?;

        let mut alerts = Vec::with_capacity(rows.len());
        for row in rows {
            alerts.push(AlertRecord {
                id: row.get("id"),
                time: row.get("time"),
                meter_id: row.get("meter_id"),
                alert_type: row.get("alert_type"),
                severity: row.get("severity"),
                value: row.get("value"),
                threshold: row.get("threshold"),
                message: row.get("message"),
                created_at: row.get("created_at"),
            });
        }

        Ok(alerts)
    }
}
