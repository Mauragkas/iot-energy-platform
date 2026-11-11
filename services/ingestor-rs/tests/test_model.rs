use chrono::{TimeZone, Utc};
use ingestor_rs::model::{DeviceStatus, SmartMeterTelemetry, ValidationError};

fn sample_valid_telemetry() -> SmartMeterTelemetry {
    SmartMeterTelemetry {
        meter_id: "MZ-3P-0042".to_string(),
        timestamp: Utc.with_ymd_and_hms(2026, 11, 12, 15, 4, 5).unwrap(),
        voltage_l1: 230.4,
        voltage_l2: 229.8,
        voltage_l3: 231.1,
        current_l1: 12.8,
        current_l2: Some(11.5),
        current_l3: Some(13.2),
        active_power_kw: 2.85,
        total_energy_kwh: 1452.3,
        power_factor: 0.96,
        frequency_hz: 50.01,
        zigbee_lqi: Some(187),
        status: DeviceStatus::Ok,
    }
}

#[test]
fn test_valid_telemetry_deserialization() {
    let json_data = r#"{
        "meter_id": "MZ-3P-0042",
        "timestamp": "2026-11-12T15:04:05Z",
        "voltage_l1": 230.4,
        "voltage_l2": 229.8,
        "voltage_l3": 231.1,
        "current_l1": 12.8,
        "active_power_kw": 2.85,
        "total_energy_kwh": 1452.3,
        "power_factor": 0.96,
        "frequency_hz": 50.01,
        "zigbee_lqi": 187,
        "status": "OK"
    }"#;

    let telemetry: SmartMeterTelemetry = serde_json::from_str(json_data).unwrap();
    assert_eq!(telemetry.meter_id, "MZ-3P-0042");
    assert_eq!(telemetry.status, DeviceStatus::Ok);
    assert_eq!(telemetry.zigbee_lqi, Some(187));
    assert!(telemetry.validate().is_ok());
}

#[test]
fn test_default_status_when_missing() {
    let json_data = r#"{
        "meter_id": "MZ-3P-0001",
        "timestamp": "2026-11-12T15:00:00Z",
        "voltage_l1": 230.0,
        "voltage_l2": 230.0,
        "voltage_l3": 230.0,
        "current_l1": 10.0,
        "active_power_kw": 2.3,
        "total_energy_kwh": 100.0,
        "power_factor": 0.98,
        "frequency_hz": 50.0
    }"#;

    let telemetry: SmartMeterTelemetry = serde_json::from_str(json_data).unwrap();
    assert_eq!(telemetry.status, DeviceStatus::Ok);
    assert_eq!(telemetry.current_l2, None);
    assert_eq!(telemetry.current_l3, None);
    assert!(telemetry.validate().is_ok());
}

#[test]
fn test_rejects_unknown_fields() {
    let json_data = r#"{
        "meter_id": "MZ-3P-0042",
        "timestamp": "2026-11-12T15:04:05Z",
        "voltage_l1": 230.4,
        "voltage_l2": 229.8,
        "voltage_l3": 231.1,
        "current_l1": 12.8,
        "active_power_kw": 2.85,
        "total_energy_kwh": 1452.3,
        "power_factor": 0.96,
        "frequency_hz": 50.01,
        "unknown_extra_field": "injected"
    }"#;

    let result: Result<SmartMeterTelemetry, _> = serde_json::from_str(json_data);
    assert!(
        result.is_err(),
        "Should deny unknown fields according to schema"
    );
}

#[test]
fn test_invalid_meter_id() {
    let mut telemetry = sample_valid_telemetry();

    telemetry.meter_id = "INVALID_ID".to_string();
    assert_eq!(
        telemetry.validate(),
        Err(ValidationError::InvalidMeterId("INVALID_ID".to_string()))
    );

    telemetry.meter_id = "MZ-3P-004a".to_string();
    assert!(telemetry.validate().is_err());

    telemetry.meter_id = "MZ-1P-0042".to_string();
    assert!(telemetry.validate().is_err());

    telemetry.meter_id = "MZ-3P-00425".to_string();
    assert!(telemetry.validate().is_err());
}

#[test]
fn test_voltage_out_of_bounds() {
    let mut telemetry = sample_valid_telemetry();

    telemetry.voltage_l1 = 500.1;
    assert_eq!(
        telemetry.validate(),
        Err(ValidationError::InvalidVoltageL1(500.1))
    );

    telemetry.voltage_l1 = -1.0;
    assert_eq!(
        telemetry.validate(),
        Err(ValidationError::InvalidVoltageL1(-1.0))
    );

    telemetry.voltage_l1 = f64::NAN;
    assert!(telemetry.validate().is_err());
}

#[test]
fn test_current_out_of_bounds() {
    let mut telemetry = sample_valid_telemetry();

    telemetry.current_l1 = 200.5;
    assert_eq!(
        telemetry.validate(),
        Err(ValidationError::InvalidCurrentL1(200.5))
    );

    telemetry.current_l2 = Some(250.0);
    telemetry.current_l1 = 10.0;
    assert_eq!(
        telemetry.validate(),
        Err(ValidationError::InvalidCurrentL2(250.0))
    );
}

#[test]
fn test_power_factor_bounds() {
    let mut telemetry = sample_valid_telemetry();

    telemetry.power_factor = 1.05;
    assert_eq!(
        telemetry.validate(),
        Err(ValidationError::InvalidPowerFactor(1.05))
    );

    telemetry.power_factor = -1.05;
    assert_eq!(
        telemetry.validate(),
        Err(ValidationError::InvalidPowerFactor(-1.05))
    );

    telemetry.power_factor = -1.0;
    assert!(telemetry.validate().is_ok());

    telemetry.power_factor = 1.0;
    assert!(telemetry.validate().is_ok());
}

#[test]
fn test_frequency_bounds() {
    let mut telemetry = sample_valid_telemetry();

    telemetry.frequency_hz = 39.9;
    assert_eq!(
        telemetry.validate(),
        Err(ValidationError::InvalidFrequency(39.9))
    );

    telemetry.frequency_hz = 65.1;
    assert_eq!(
        telemetry.validate(),
        Err(ValidationError::InvalidFrequency(65.1))
    );
}

#[test]
fn test_total_energy_negative() {
    let mut telemetry = sample_valid_telemetry();
    telemetry.total_energy_kwh = -0.1;
    assert_eq!(
        telemetry.validate(),
        Err(ValidationError::InvalidTotalEnergy(-0.1))
    );
}

#[test]
fn test_zigbee_lqi_bounds() {
    let mut telemetry = sample_valid_telemetry();
    telemetry.zigbee_lqi = Some(300);
    assert_eq!(
        telemetry.validate(),
        Err(ValidationError::InvalidZigbeeLqi(300))
    );
}
