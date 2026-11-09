use async_trait::async_trait;

use super::error::RepositoryError;

#[async_trait]
pub trait HealthRepository: Send + Sync {
    /// Pings the TimescaleDB / PostgreSQL database.
    async fn check_timescale(&self) -> Result<(), RepositoryError>;

    /// Pings the MongoDB database.
    async fn check_mongodb(&self) -> Result<(), RepositoryError>;
}
