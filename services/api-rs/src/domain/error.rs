use thiserror::Error;

#[derive(Debug, Error, PartialEq, Eq)]
pub enum DomainError {
    #[error("Invalid meter ID: {0}")]
    InvalidMeterId(String),

    #[error("Invalid time range: {0}")]
    InvalidTimeRange(String),

    #[error("Invalid bucket: {0}")]
    InvalidBucket(String),

    #[error("Invalid alert severity: {0}")]
    InvalidSeverity(String),
}
