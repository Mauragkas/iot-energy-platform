use ingestor_rs::kafka::{MockPublisher, TelemetryPublisher};

#[tokio::test]
async fn test_mock_publisher() {
    let publisher = MockPublisher::new();
    publisher
        .publish("MZ-3P-0042", r#"{"meter_id":"MZ-3P-0042"}"#)
        .await
        .unwrap();

    let msgs = publisher.messages.lock().unwrap();
    assert_eq!(msgs.len(), 1);
    assert_eq!(msgs[0].0, "MZ-3P-0042");
    assert_eq!(msgs[0].1, r#"{"meter_id":"MZ-3P-0042"}"#);
}
