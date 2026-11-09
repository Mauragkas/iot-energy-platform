use api_rs::domain::alert::AlertSeverity;
use api_rs::domain::meter_id::MeterId;
use api_rs::domain::time_range::TimeRange;
use api_rs::domain::timeseries::RollupBucket;
use api_rs::domain::twin::{DeviceTwin, TwinLocation, TwinThresholds};
use chrono::{DateTime, Utc};

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

#[test]
fn test_bucket_parsing() {
    assert_eq!(
        "1m".parse::<RollupBucket>().unwrap(),
        RollupBucket::OneMinute
    );
    assert_eq!("1h".parse::<RollupBucket>().unwrap(), RollupBucket::Hourly);
    assert_eq!("1d".parse::<RollupBucket>().unwrap(), RollupBucket::Daily);
    assert!("10m".parse::<RollupBucket>().is_err());
}

#[test]
fn test_alert_severity_parsing() {
    assert_eq!(
        "CRITICAL".parse::<AlertSeverity>().unwrap(),
        AlertSeverity::Critical
    );
    assert_eq!(
        "critical".parse::<AlertSeverity>().unwrap(),
        AlertSeverity::Critical
    );
    assert_eq!(
        "WARNING".parse::<AlertSeverity>().unwrap(),
        AlertSeverity::Warning
    );
    assert_eq!("info".parse::<AlertSeverity>().unwrap(), AlertSeverity::Info);
    assert!("UNKNOWN".parse::<AlertSeverity>().is_err());
}

#[test]
fn test_device_twin_json_roundtrip() {
    let twin = DeviceTwin {
        meter_id: "MZ-3P-0042".to_string(),
        firmware_version: "v2.4.1".to_string(),
        zone: "north".to_string(),
        phase_type: "3P+N".to_string(),
        nominal_voltage: 230.0,
        nominal_frequency: 50.0,
        thresholds: TwinThresholds {
            voltage_min: 207.0,
            voltage_max: 253.0,
            active_power_kw_max: 25.0,
            power_factor_min: 0.85,
        },
        location: TwinLocation {
            lat: 37.9838,
            lon: 23.7275,
        },
        installed_at: Some(Utc::now()),
        status: "ACTIVE".to_string(),
    };

    let json = serde_json::to_string(&twin).unwrap();
    let deserialized: DeviceTwin = serde_json::from_str(&json).unwrap();
    assert_eq!(twin.meter_id, deserialized.meter_id);
    assert_eq!(twin.zone, deserialized.zone);
}
