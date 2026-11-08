use chrono::DateTime;
use ingestor_rs::dedup::Deduplicator;
use ingestor_rs::kafka::TelemetryPublisher;
use ingestor_rs::metrics::{
    TELEMETRY_MESSAGES_DEDUPLICATED_TOTAL, TELEMETRY_MESSAGES_PUBLISHED_TOTAL,
    TELEMETRY_MESSAGES_RECEIVED_TOTAL, TELEMETRY_MESSAGES_REJECTED_TOTAL,
};
use ingestor_rs::model::{is_valid_meter_id, DeviceStatus, SmartMeterTelemetry};
use ingestor_rs::mqtt::{process_message, ProcessOutcome};
use std::future::Future;
use std::pin::Pin;
use std::sync::{Arc, Mutex};
use std::time::Duration;

static METRICS_TEST_MUTEX: tokio::sync::Mutex<()> = tokio::sync::Mutex::const_new(());

#[derive(Default, Clone)]
struct TestPublisher {
    published: Arc<Mutex<Vec<(String, String)>>>,
}

impl TelemetryPublisher for TestPublisher {
    fn publish<'a>(
        &'a self,
        key: &'a str,
        payload: &'a str,
    ) -> Pin<Box<dyn Future<Output = Result<(), String>> + Send + 'a>> {
        let k = key.to_string();
        let p = payload.to_string();
        let store = self.published.clone();
        Box::pin(async move {
            store.lock().unwrap().push((k, p));
            Ok(())
        })
    }

    fn flush(&self, _timeout: Duration) -> Result<(), String> {
        Ok(())
    }
}

#[tokio::test]
async fn test_ingestor_pipeline_valid_and_duplicate() {
    let _guard = METRICS_TEST_MUTEX.lock().await;

    let dedup = Deduplicator::new(1000);
    let publisher = TestPublisher::default();

    let initial_received = TELEMETRY_MESSAGES_RECEIVED_TOTAL.get();
    let initial_published = TELEMETRY_MESSAGES_PUBLISHED_TOTAL.get();
    let initial_deduped = TELEMETRY_MESSAGES_DEDUPLICATED_TOTAL.get();

    let payload = r#"{
        "meter_id": "MZ-3P-1234",
        "timestamp": "2026-11-12T16:00:00Z",
        "voltage_l1": 230.0,
        "voltage_l2": 231.0,
        "voltage_l3": 229.0,
        "current_l1": 15.5,
        "current_l2": 14.8,
        "current_l3": 15.1,
        "active_power_kw": 10.2,
        "total_energy_kwh": 3500.0,
        "power_factor": 0.97,
        "frequency_hz": 50.02,
        "zigbee_lqi": 220,
        "status": "OK"
    }"#;

    // 1. Process first packet
    let outcome1 = process_message(payload.as_bytes(), &dedup, &publisher).await;
    assert_eq!(outcome1, ProcessOutcome::Published("MZ-3P-1234".to_string()));

    assert_eq!(TELEMETRY_MESSAGES_RECEIVED_TOTAL.get(), initial_received + 1);
    assert_eq!(TELEMETRY_MESSAGES_PUBLISHED_TOTAL.get(), initial_published + 1);
    assert_eq!(TELEMETRY_MESSAGES_DEDUPLICATED_TOTAL.get(), initial_deduped);

    // 2. Process duplicate packet
    let outcome2 = process_message(payload.as_bytes(), &dedup, &publisher).await;
    assert_eq!(outcome2, ProcessOutcome::Duplicate("MZ-3P-1234".to_string()));

    assert_eq!(TELEMETRY_MESSAGES_RECEIVED_TOTAL.get(), initial_received + 2);
    assert_eq!(TELEMETRY_MESSAGES_PUBLISHED_TOTAL.get(), initial_published + 1);
    assert_eq!(TELEMETRY_MESSAGES_DEDUPLICATED_TOTAL.get(), initial_deduped + 1);

    let messages = publisher.published.lock().unwrap();
    assert_eq!(messages.len(), 1);
    assert_eq!(messages[0].0, "MZ-3P-1234");
}

#[tokio::test]
async fn test_ingestor_pipeline_rejects_corrupt_and_invalid() {
    let _guard = METRICS_TEST_MUTEX.lock().await;

    let dedup = Deduplicator::new(1000);
    let publisher = TestPublisher::default();

    let initial_received = TELEMETRY_MESSAGES_RECEIVED_TOTAL.get();
    let initial_rejected = TELEMETRY_MESSAGES_REJECTED_TOTAL.get();

    // 1. Syntax error
    let outcome1 = process_message(b"malformed json", &dedup, &publisher).await;
    assert!(matches!(outcome1, ProcessOutcome::Rejected(_)));

    // 2. Semantic error: voltage out of range (550V > 500V max)
    let bad_voltage = r#"{
        "meter_id": "MZ-3P-1234",
        "timestamp": "2026-11-12T16:00:00Z",
        "voltage_l1": 550.0,
        "voltage_l2": 230.0,
        "voltage_l3": 230.0,
        "current_l1": 10.0,
        "active_power_kw": 2.3,
        "total_energy_kwh": 100.0,
        "power_factor": 0.95,
        "frequency_hz": 50.0
    }"#;
    let outcome2 = process_message(bad_voltage.as_bytes(), &dedup, &publisher).await;
    assert!(matches!(outcome2, ProcessOutcome::Rejected(_)));

    // 3. Pattern error: invalid meter ID
    let bad_id = r#"{
        "meter_id": "METER_9999",
        "timestamp": "2026-11-12T16:00:00Z",
        "voltage_l1": 230.0,
        "voltage_l2": 230.0,
        "voltage_l3": 230.0,
        "current_l1": 10.0,
        "active_power_kw": 2.3,
        "total_energy_kwh": 100.0,
        "power_factor": 0.95,
        "frequency_hz": 50.0
    }"#;
    let outcome3 = process_message(bad_id.as_bytes(), &dedup, &publisher).await;
    assert!(matches!(outcome3, ProcessOutcome::Rejected(_)));

    assert_eq!(TELEMETRY_MESSAGES_RECEIVED_TOTAL.get(), initial_received + 3);
    assert_eq!(TELEMETRY_MESSAGES_REJECTED_TOTAL.get(), initial_rejected + 3);
}

#[test]
fn test_meter_id_pattern_compliance() {
    assert!(is_valid_meter_id("MZ-3P-0001"));
    assert!(is_valid_meter_id("MZ-3P-9999"));
    assert!(!is_valid_meter_id("MZ-3P-001")); // Too short
    assert!(!is_valid_meter_id("MZ-3P-00001")); // Too long
    assert!(!is_valid_meter_id("MZ-1P-0001")); // 1-phase prefix
    assert!(!is_valid_meter_id("MZ-3P-ABCD")); // Non-numeric
    assert!(!is_valid_meter_id(""));
}

#[test]
fn test_brownout_zero_voltage_is_valid() {
    let telemetry = SmartMeterTelemetry {
        meter_id: "MZ-3P-0042".to_string(),
        timestamp: DateTime::from_timestamp(1762950000, 0).unwrap(),
        voltage_l1: 0.0, // Complete outage / brownout on phase 1
        voltage_l2: 0.0,
        voltage_l3: 0.0,
        current_l1: 0.0,
        current_l2: None,
        current_l3: None,
        active_power_kw: 0.0,
        total_energy_kwh: 120.5,
        power_factor: 0.0,
        frequency_hz: 50.0,
        zigbee_lqi: Some(150),
        status: DeviceStatus::Warning,
    };

    assert!(telemetry.validate().is_ok());
}
