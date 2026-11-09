use persister_rs::metrics::{
    TELEMETRY_PERSISTED_RECORDS, TELEMETRY_PERSIST_BATCHES, TELEMETRY_PERSIST_BATCH_DURATION,
    TELEMETRY_PERSIST_ERRORS,
};
use prometheus::{Encoder, TextEncoder};

#[test]
fn test_metrics_registration_and_gathering() {
    TELEMETRY_PERSISTED_RECORDS.inc_by(5);
    TELEMETRY_PERSIST_BATCHES.inc();
    TELEMETRY_PERSIST_ERRORS.inc();
    TELEMETRY_PERSIST_BATCH_DURATION.observe(0.012);

    let encoder = TextEncoder::new();
    let metric_families = prometheus::gather();
    let mut buffer = Vec::new();
    encoder.encode(&metric_families, &mut buffer).unwrap();
    let output = String::from_utf8(buffer).unwrap();

    assert!(output.contains("telemetry_persisted_records_total"));
    assert!(output.contains("telemetry_persist_batches_total"));
    assert!(output.contains("telemetry_persist_errors_total"));
    assert!(output.contains("telemetry_persist_batch_duration_seconds"));
}
