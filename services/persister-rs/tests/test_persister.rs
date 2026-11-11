use chrono::{TimeZone, Utc};
use persister_rs::config::Config;
use persister_rs::consumer::BatchBuffer;
use persister_rs::db::build_batch_insert_query;
use persister_rs::metrics::{
    TELEMETRY_PERSISTED_RECORDS, TELEMETRY_PERSIST_BATCHES, TELEMETRY_PERSIST_BATCH_DURATION,
    TELEMETRY_PERSIST_ERRORS,
};
use persister_rs::model::TelemetryReading;

#[test]
fn test_config_defaults() {
    let config = Config::from_env();
    assert_eq!(config.kafka_brokers, "localhost:9092");
    assert_eq!(config.kafka_topic, "iot.telemetry.raw");
    assert_eq!(config.kafka_group_id, "iot-persister-group");
    assert_eq!(config.db_host, "localhost");
    assert_eq!(config.db_port, 5432);
    assert_eq!(config.db_user, "postgres");
    assert_eq!(config.db_password, "postgres");
    assert_eq!(config.db_name, "iot_energy");
    assert_eq!(config.metrics_host, "0.0.0.0");
    assert_eq!(config.metrics_port, 8082);
    assert_eq!(config.batch_size, 500);
    assert_eq!(config.flush_interval_ms, 500);
}

#[test]
fn test_query_generator_large_batch() {
    let query_500 = build_batch_insert_query(500);
    assert!(query_500.starts_with("INSERT INTO meter_readings"));
    assert!(query_500.contains("($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)"));
    // 500 rows * 12 cols = 6000 params, last param is $6000
    assert!(query_500.contains("$6000"));
    assert!(query_500.ends_with("ON CONFLICT (meter_id, time) DO NOTHING;"));
}

#[test]
fn test_payload_deserialization_edge_cases() {
    // Missing optional phases default to 0.0
    let json_minimal = r#"{
        "meter_id": "meter_single_phase",
        "timestamp": "2026-11-12T15:00:00Z",
        "voltage_l1": 230.5,
        "current_l1": 15.0,
        "active_power_kw": 3.45,
        "total_energy_kwh": 100.5,
        "power_factor": 0.99,
        "frequency_hz": 50.0
    }"#;

    let parsed =
        TelemetryReading::from_json_str(json_minimal).expect("should parse minimal payload");
    assert_eq!(parsed.meter_id, "meter_single_phase");
    assert_eq!(
        parsed.time,
        Utc.with_ymd_and_hms(2026, 11, 12, 15, 0, 0).unwrap()
    );
    assert_eq!(parsed.voltage_l2, 0.0);
    assert_eq!(parsed.voltage_l3, 0.0);
    assert_eq!(parsed.current_l2, 0.0);
    assert_eq!(parsed.current_l3, 0.0);
    assert_eq!(parsed.energy_kwh, 100.5);
}

#[test]
fn test_micro_batch_buffer_partition_tracking() {
    let mut buffer = BatchBuffer::new();

    let reading1 = TelemetryReading {
        time: Utc::now(),
        meter_id: "m1".to_string(),
        voltage_l1: 230.0,
        voltage_l2: 230.0,
        voltage_l3: 230.0,
        current_l1: 10.0,
        current_l2: 10.0,
        current_l3: 10.0,
        active_power_kw: 6.9,
        energy_kwh: 50.0,
        power_factor: 1.0,
        frequency_hz: 50.0,
    };

    let reading2 = TelemetryReading {
        meter_id: "m2".to_string(),
        ..reading1.clone()
    };

    // Partition 0 received offset 10, then 11
    buffer.push_reading(reading1, "iot.telemetry.raw", 0, 10);
    buffer.push_reading(reading2, "iot.telemetry.raw", 0, 11);

    // Partition 1 received offset 40
    buffer.track_offset("iot.telemetry.raw", 1, 40);

    assert_eq!(buffer.len(), 2);
    assert_eq!(
        *buffer
            .offsets
            .get(&("iot.telemetry.raw".to_string(), 0))
            .unwrap(),
        11
    );
    assert_eq!(
        *buffer
            .offsets
            .get(&("iot.telemetry.raw".to_string(), 1))
            .unwrap(),
        40
    );
}

#[test]
fn test_metrics_instrumentation_counters() {
    let initial_persisted = TELEMETRY_PERSISTED_RECORDS.get();
    let initial_batches = TELEMETRY_PERSIST_BATCHES.get();
    let initial_errors = TELEMETRY_PERSIST_ERRORS.get();

    TELEMETRY_PERSISTED_RECORDS.inc_by(100);
    TELEMETRY_PERSIST_BATCHES.inc();
    TELEMETRY_PERSIST_ERRORS.inc();
    TELEMETRY_PERSIST_BATCH_DURATION.observe(0.045);

    assert_eq!(TELEMETRY_PERSISTED_RECORDS.get(), initial_persisted + 100);
    assert_eq!(TELEMETRY_PERSIST_BATCHES.get(), initial_batches + 1);
    assert_eq!(TELEMETRY_PERSIST_ERRORS.get(), initial_errors + 1);
}
