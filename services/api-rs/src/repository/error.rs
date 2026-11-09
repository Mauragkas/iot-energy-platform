use thiserror::Error;

#[derive(Debug, Error)]
pub enum RepositoryError {
    #[error("Database error: {0}")]
    Database(String),

    #[error("Item not found: {0}")]
    NotFound(String),

    #[error("Invalid parameter: {0}")]
    InvalidInput(String),

    #[error("Connection error: {0}")]
    Connection(String),
}
