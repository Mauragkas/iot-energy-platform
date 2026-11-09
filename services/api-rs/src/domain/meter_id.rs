use std::fmt;
use serde::{Deserialize, Serialize};

use super::error::DomainError;

/// MeterId strongly-typed value object representing a validated meter identifier.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
#[serde(transparent)]
pub struct MeterId(String);

impl MeterId {
    pub fn new(id: impl Into<String>) -> Result<Self, DomainError> {
        let trimmed = id.into().trim().to_string();
        if trimmed.is_empty() {
            return Err(DomainError::InvalidMeterId(
                "Meter ID cannot be empty".to_string(),
            ));
        }
        if trimmed.len() > 64 {
            return Err(DomainError::InvalidMeterId(
                "Meter ID exceeds maximum allowed length of 64 characters".to_string(),
            ));
        }
        if !trimmed.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_' || c == '.') {
            return Err(DomainError::InvalidMeterId(
                "Meter ID contains invalid characters; only alphanumeric, '-', '_', '.' are permitted".to_string(),
            ));
        }
        Ok(Self(trimmed))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl AsRef<str> for MeterId {
    fn as_ref(&self) -> &str {
        &self.0
    }
}

impl fmt::Display for MeterId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}
