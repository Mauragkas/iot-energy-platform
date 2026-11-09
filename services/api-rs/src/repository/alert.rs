use async_trait::async_trait;
use chrono::{DateTime, Utc};

use crate::domain::AlertRecord;
use super::error::RepositoryError;

#[async_trait]
pub trait AlertRepository: Send + Sync {
    /// Lists alerts filtered by optional severity and timestamp threshold.
    async fn list_alerts(
        &self,
        severity: Option<&str>,
        since: Option<DateTime<Utc>>,
        limit: usize,
    ) -> Result<Vec<AlertRecord>, RepositoryError>;
}
