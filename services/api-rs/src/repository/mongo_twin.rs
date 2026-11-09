use async_trait::async_trait;
use futures::TryStreamExt;
use mongodb::bson::doc;
use mongodb::options::FindOptions;
use mongodb::{Collection, Database};

use crate::domain::DeviceTwin;
use super::error::RepositoryError;
use super::twin::TwinRepository;

pub struct MongoTwinRepository {
    collection: Collection<DeviceTwin>,
}

impl MongoTwinRepository {
    pub const COLLECTION_NAME: &'static str = "device_twins";

    pub fn new(database: &Database) -> Self {
        let collection = database.collection::<DeviceTwin>(Self::COLLECTION_NAME);
        Self { collection }
    }
}

#[async_trait]
impl TwinRepository for MongoTwinRepository {
    async fn list_twins(
        &self,
        zone: Option<&str>,
        limit: usize,
    ) -> Result<Vec<DeviceTwin>, RepositoryError> {
        let filter = if let Some(z) = zone {
            doc! { "zone": z }
        } else {
            doc! {}
        };

        let options = FindOptions::builder()
            .limit(limit as i64)
            .sort(doc! { "meter_id": 1 })
            .build();

        let mut cursor = self
            .collection
            .find(filter, options)
            .await
            .map_err(|e| RepositoryError::Database(e.to_string()))?;

        let mut twins = Vec::new();
        while let Some(twin) = cursor
            .try_next()
            .await
            .map_err(|e| RepositoryError::Database(e.to_string()))?
        {
            twins.push(twin);
        }

        Ok(twins)
    }

    async fn get_twin(
        &self,
        meter_id: &str,
    ) -> Result<Option<DeviceTwin>, RepositoryError> {
        let filter = doc! { "meter_id": meter_id };
        self.collection
            .find_one(filter, None)
            .await
            .map_err(|e| RepositoryError::Database(e.to_string()))
    }
}
