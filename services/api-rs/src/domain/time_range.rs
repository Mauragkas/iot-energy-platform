use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};

use super::error::DomainError;

/// TimeRange value object for bounded query windows.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct TimeRange {
    pub from: DateTime<Utc>,
    pub to: DateTime<Utc>,
}

impl TimeRange {
    pub fn new(from: DateTime<Utc>, to: DateTime<Utc>) -> Result<Self, DomainError> {
        if to < from {
            return Err(DomainError::InvalidTimeRange(format!(
                "'to' ({}) cannot be before 'from' ({})",
                to.to_rfc3339(),
                from.to_rfc3339()
            )));
        }
        Ok(Self { from, to })
    }

    /// Enforces maximum allowed time window (e.g. 30 days) to prevent unbounded full-table scans.
    pub fn validate_max_window(&self, max_days: i64) -> Result<(), DomainError> {
        let max_duration = Duration::days(max_days);
        let actual_duration = self.to - self.from;
        if actual_duration > max_duration {
            return Err(DomainError::InvalidTimeRange(format!(
                "Time window duration of {} days exceeds the maximum allowed limit of {} days",
                actual_duration.num_days(),
                max_days
            )));
        }
        Ok(())
    }
}

pub mod flexible_datetime {
    use super::*;
    use serde::{self, Deserializer};

    pub fn deserialize<'de, D>(deserializer: D) -> Result<DateTime<Utc>, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        let s = s.trim().replace(' ', "+");
        DateTime::parse_from_rfc3339(&s)
            .map(|dt| dt.with_timezone(&Utc))
            .map_err(serde::de::Error::custom)
    }
}

pub mod flexible_datetime_opt {
    use super::*;
    use serde::{self, Deserializer};

    pub fn deserialize<'de, D>(deserializer: D) -> Result<Option<DateTime<Utc>>, D::Error>
    where
        D: Deserializer<'de>,
    {
        let opt = Option::<String>::deserialize(deserializer)?;
        match opt {
            Some(s) if !s.trim().is_empty() => {
                let s = s.trim().replace(' ', "+");
                DateTime::parse_from_rfc3339(&s)
                    .map(|dt| Some(dt.with_timezone(&Utc)))
                    .map_err(serde::de::Error::custom)
            }
            _ => Ok(None),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_valid_time_range() {
        let from = "2026-11-01T00:00:00Z".parse::<DateTime<Utc>>().unwrap();
        let to = "2026-11-05T00:00:00Z".parse::<DateTime<Utc>>().unwrap();
        let range = TimeRange::new(from, to).unwrap();
        assert!(range.validate_max_window(30).is_ok());
    }

    #[test]
    fn test_to_before_from() {
        let from = "2026-11-05T00:00:00Z".parse::<DateTime<Utc>>().unwrap();
        let to = "2026-11-01T00:00:00Z".parse::<DateTime<Utc>>().unwrap();
        assert!(TimeRange::new(from, to).is_err());
    }

    #[test]
    fn test_window_exceeds_maximum() {
        let from = "2026-10-01T00:00:00Z".parse::<DateTime<Utc>>().unwrap();
        let to = "2026-11-15T00:00:00Z".parse::<DateTime<Utc>>().unwrap();
        let range = TimeRange::new(from, to).unwrap();
        assert!(range.validate_max_window(30).is_err());
    }
}
