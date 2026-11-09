use chrono::Utc;
use persister_rs::consumer::BatchBuffer;
use persister_rs::model::TelemetryReading;

#[test]
fn test_batch_buffer_accumulation_and_clearing() {
    let mut buffer = BatchBuffer::new();
    assert!(buffer.is_empty());

    let reading = TelemetryReading {
        time: Utc::now(),
        meter_id: "test_meter".to_string(),
        voltage_l1: 230.0,
        voltage_l2: 230.0,
        voltage_l3: 230.0,
        current_l1: 5.0,
        current_l2: 5.0,
        current_l3: 5.0,
        active_power_kw: 3.45,
        energy_kwh: 100.0,
        power_factor: 0.95,
        frequency_hz: 50.0,
    };

    buffer.push_reading(reading, "iot.telemetry.raw", 0, 100);
    buffer.track_offset("iot.telemetry.raw", 0, 101);
    buffer.track_offset("iot.telemetry.raw", 1, 50);

    assert_eq!(buffer.len(), 1);
    assert!(!buffer.is_empty());
    assert_eq!(
        buffer.offsets.get(&("iot.telemetry.raw".to_string(), 0)),
        Some(&101)
    );
    assert_eq!(
        buffer.offsets.get(&("iot.telemetry.raw".to_string(), 1)),
        Some(&50)
    );

    buffer.clear();
    assert!(buffer.is_empty());
    assert_eq!(buffer.len(), 0);
}
