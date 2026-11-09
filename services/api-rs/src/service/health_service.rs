use std::sync::Arc;
use serde::Serialize;

use crate::repository::HealthRepository;
use super::error::ServiceError;

#[derive(Debug, Serialize)]
pub struct LivenessResponse {
    pub status: &'static str,
}

#[derive(Debug, Serialize)]
pub struct ReadinessResponse {
    pub status: &'static str,
    pub postgres: &'static str,
    pub mongodb: &'static str,
}

pub struct HealthService {
    health_repo: Arc<dyn HealthRepository>,
}

impl HealthService {
    pub fn new(health_repo: Arc<dyn HealthRepository>) -> Self {
        Self { health_repo }
    }

    pub fn check_liveness(&self) -> LivenessResponse {
        LivenessResponse { status: "ok" }
    }

    pub async fn check_readiness(&self) -> Result<ReadinessResponse, ServiceError> {
        let pg_res = self.health_repo.check_timescale().await;
        let mongo_res = self.health_repo.check_mongodb().await;

        match (pg_res, mongo_res) {
            (Ok(_), Ok(_)) => Ok(ReadinessResponse {
                status: "ready",
                postgres: "ok",
                mongodb: "ok",
            }),
            (Err(e), Ok(_)) => Err(ServiceError::Unavailable(format!(
                "TimescaleDB readiness check failed: {e}"
            ))),
            (Ok(_), Err(e)) => Err(ServiceError::Unavailable(format!(
                "MongoDB readiness check failed: {e}"
            ))),
            (Err(e1), Err(e2)) => Err(ServiceError::Unavailable(format!(
                "Both TimescaleDB ({e1}) and MongoDB ({e2}) readiness checks failed"
            ))),
        }
    }
}
