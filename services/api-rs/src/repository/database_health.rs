use async_trait::async_trait;
use deadpool_postgres::Pool;
use mongodb::bson::doc;
use mongodb::Database;

use super::error::RepositoryError;
use super::health::HealthRepository;

pub struct DatabaseHealthRepository {
    pg_pool: Pool,
    mongo_db: Database,
}

impl DatabaseHealthRepository {
    pub fn new(pg_pool: Pool, mongo_db: Database) -> Self {
        Self { pg_pool, mongo_db }
    }
}

#[async_trait]
impl HealthRepository for DatabaseHealthRepository {
    async fn check_timescale(&self) -> Result<(), RepositoryError> {
        let client = self
            .pg_pool
            .get()
            .await
            .map_err(|e| RepositoryError::Connection(format!("TimescaleDB pool checkout failed: {e}")))?;

        client
            .simple_query("SELECT 1;")
            .await
            .map_err(|e| RepositoryError::Database(format!("TimescaleDB ping query failed: {e}")))?;

        Ok(())
    }

    async fn check_mongodb(&self) -> Result<(), RepositoryError> {
        self.mongo_db
            .run_command(doc! { "ping": 1 }, None)
            .await
            .map_err(|e| RepositoryError::Database(format!("MongoDB ping command failed: {e}")))?;

        Ok(())
    }
}
