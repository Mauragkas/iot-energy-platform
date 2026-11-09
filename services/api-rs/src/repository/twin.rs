use async_trait::async_trait;

use crate::domain::DeviceTwin;
use super::error::RepositoryError;

#[async_trait]
pub trait TwinRepository: Send + Sync {
    /// Lists device twins with optional zone filter and capped limit.
    async fn list_twins(
        &self,
        zone: Option<&str>,
        limit: usize,
    ) -> Result<Vec<DeviceTwin>, RepositoryError>;

    /// Fetches a single device twin by meter_id.
    async fn get_twin(
        &self,
        meter_id: &str,
    ) -> Result<Option<DeviceTwin>, RepositoryError>;
}
