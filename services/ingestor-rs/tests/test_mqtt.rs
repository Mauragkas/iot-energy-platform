use ingestor_rs::dedup::Deduplicator;
use ingestor_rs::kafka::MockPublisher;
use ingestor_rs::mqtt::{process_message, ProcessOutcome};

fn sample_json(meter_id: &str, timestamp: &str, voltage: f64) -> String {
    format!(
        r#"{{
            "meter_id": "{}",
            "timestamp": "{}",
            "voltage_l1": {},
            "voltage_l2": 230.0,
            "voltage_l3": 230.0,
            "current_l1": 10.0,
            "active_power_kw": 2.3,
            "total_energy_kwh": 500.0,
            "power_factor": 0.95,
            "frequency_hz": 50.0,
            "zigbee_lqi": 200,
            "status": "OK"
        }}"#,
        meter_id, timestamp, voltage
    )
}

#[tokio::test]
async fn test_process_valid_message() {
    let dedup = Deduplicator::new(100);
    let mock_pub = MockPublisher::new();

    let json = sample_json("MZ-3P-0042", "2026-11-12T15:00:00Z", 230.0);
    let outcome = process_message(json.as_bytes(), &dedup, &mock_pub).await;

    assert_eq!(outcome, ProcessOutcome::Published("MZ-3P-0042".to_string()));
    let sent = mock_pub.messages.lock().unwrap();
    assert_eq!(sent.len(), 1);
    assert_eq!(sent[0].0, "MZ-3P-0042");
}

#[tokio::test]
async fn test_process_duplicate_message() {
    let dedup = Deduplicator::new(100);
    let mock_pub = MockPublisher::new();

    let json = sample_json("MZ-3P-0042", "2026-11-12T15:00:00Z", 230.0);
    let outcome1 = process_message(json.as_bytes(), &dedup, &mock_pub).await;
    assert_eq!(
        outcome1,
        ProcessOutcome::Published("MZ-3P-0042".to_string())
    );

    let outcome2 = process_message(json.as_bytes(), &dedup, &mock_pub).await;
    assert_eq!(
        outcome2,
        ProcessOutcome::Duplicate("MZ-3P-0042".to_string())
    );

    // Published messages count should still be 1
    let sent = mock_pub.messages.lock().unwrap();
    assert_eq!(sent.len(), 1);
}

#[tokio::test]
async fn test_process_invalid_json() {
    let dedup = Deduplicator::new(100);
    let mock_pub = MockPublisher::new();

    let outcome = process_message(b"not json", &dedup, &mock_pub).await;
    match outcome {
        ProcessOutcome::Rejected(msg) => assert!(msg.contains("Deserialization error")),
        _ => panic!("Expected Rejected outcome"),
    }
}

#[tokio::test]
async fn test_process_validation_error() {
    let dedup = Deduplicator::new(100);
    let mock_pub = MockPublisher::new();

    // Voltage 600V is out of 0..500 bounds
    let json = sample_json("MZ-3P-0042", "2026-11-12T15:00:00Z", 600.0);
    let outcome = process_message(json.as_bytes(), &dedup, &mock_pub).await;
    match outcome {
        ProcessOutcome::Rejected(msg) => assert!(msg.contains("Validation error")),
        _ => panic!("Expected Rejected outcome"),
    }
}
