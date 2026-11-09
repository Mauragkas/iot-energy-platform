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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_meter_id() {
        let id = MeterId::new("MZ-3P-0042").unwrap();
        assert_eq!(id.as_str(), "MZ-3P-0042");
        assert_eq!(id.to_string(), "MZ-3P-0042");
    }

    #[test]
    fn test_empty_meter_id() {
        assert!(MeterId::new("   ").is_err());
    }

    #[test]
    fn test_invalid_characters() {
        assert!(MeterId::new("MZ-3P-0042; DROP TABLE;").is_err());
        assert!(MeterId::new("MZ 3P 0042").is_err());
    }

    #[test]
    fn test_too_long_meter_id() {
        let long_id = "A".repeat(65);
        assert!(MeterId::new(long_id).is_err());
    }
}
