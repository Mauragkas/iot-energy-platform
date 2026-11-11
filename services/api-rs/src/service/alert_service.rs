use chrono::{DateTime, Utc};
use std::sync::Arc;

use super::error::ServiceError;
use super::meter_service::{DEFAULT_PAGINATION_LIMIT, MAX_PAGINATION_LIMIT};
use crate::domain::{AlertRecord, AlertSeverity};
use crate::repository::AlertRepository;

pub struct AlertService {
    alert_repo: Arc<dyn AlertRepository>,
}

impl AlertService {
    pub fn new(alert_repo: Arc<dyn AlertRepository>) -> Self {
        Self { alert_repo }
    }

    /// Lists alerts, validating severity and enforcing pagination bounds.
    pub async fn list_alerts(
        &self,
        severity: Option<&str>,
        since: Option<DateTime<Utc>>,
        limit: Option<usize>,
    ) -> Result<Vec<AlertRecord>, ServiceError> {
        let normalized_severity = if let Some(s) = severity {
            let parsed: AlertSeverity = s.parse()?;
            Some(parsed.as_str())
        } else {
            None
        };

        let capped_limit = limit
            .unwrap_or(DEFAULT_PAGINATION_LIMIT)
            .clamp(1, MAX_PAGINATION_LIMIT);

        let alerts = self
            .alert_repo
            .list_alerts(normalized_severity, since, capped_limit)
            .await?;

        Ok(alerts)
    }
}
