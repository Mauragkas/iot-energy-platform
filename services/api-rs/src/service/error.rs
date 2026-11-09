use actix_web::http::StatusCode;
use actix_web::{HttpResponse, ResponseError};
use serde::Serialize;
use thiserror::Error;

use crate::domain::DomainError;
use crate::repository::RepositoryError;

#[derive(Debug, Error)]
pub enum ServiceError {
    #[error("Validation error: {0}")]
    Validation(String),

    #[error("Not found: {0}")]
    NotFound(String),

    #[error("Repository error: {0}")]
    Repository(#[from] RepositoryError),

    #[error("Service unavailable: {0}")]
    Unavailable(String),
}

impl From<DomainError> for ServiceError {
    fn from(err: DomainError) -> Self {
        ServiceError::Validation(err.to_string())
    }
}

#[derive(Debug, Serialize)]
pub struct ErrorResponse {
    pub error: &'static str,
    pub message: String,
}

impl ResponseError for ServiceError {
    fn status_code(&self) -> StatusCode {
        match self {
            ServiceError::Validation(_) => StatusCode::BAD_REQUEST,
            ServiceError::NotFound(_) => StatusCode::NOT_FOUND,
            ServiceError::Repository(RepositoryError::NotFound(_)) => StatusCode::NOT_FOUND,
            ServiceError::Repository(RepositoryError::InvalidInput(_)) => StatusCode::BAD_REQUEST,
            ServiceError::Unavailable(_) | ServiceError::Repository(RepositoryError::Connection(_)) => {
                StatusCode::SERVICE_UNAVAILABLE
            }
            ServiceError::Repository(RepositoryError::Database(_)) => {
                StatusCode::INTERNAL_SERVER_ERROR
            }
        }
    }

    fn error_response(&self) -> HttpResponse {
        let error_code = match self {
            ServiceError::Validation(_) => "BAD_REQUEST",
            ServiceError::NotFound(_) | ServiceError::Repository(RepositoryError::NotFound(_)) => {
                "NOT_FOUND"
            }
            ServiceError::Repository(RepositoryError::InvalidInput(_)) => "BAD_REQUEST",
            ServiceError::Unavailable(_) | ServiceError::Repository(RepositoryError::Connection(_)) => {
                "SERVICE_UNAVAILABLE"
            }
            ServiceError::Repository(RepositoryError::Database(_)) => "INTERNAL_SERVER_ERROR",
        };

        HttpResponse::build(self.status_code()).json(ErrorResponse {
            error: error_code,
            message: self.to_string(),
        })
    }
}
