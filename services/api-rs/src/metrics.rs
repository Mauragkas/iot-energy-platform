use lazy_static::lazy_static;
use prometheus::{
    register_histogram_vec, register_int_counter_vec, Encoder, HistogramVec, IntCounterVec,
    TextEncoder,
};

lazy_static! {
    pub static ref HTTP_REQUESTS_TOTAL: IntCounterVec = register_int_counter_vec!(
        "http_requests_total",
        "Total number of HTTP requests processed by api-rs",
        &["method", "endpoint", "status"]
    )
    .expect("failed to register http_requests_total");
    pub static ref HTTP_REQUEST_DURATION_SECONDS: HistogramVec = register_histogram_vec!(
        "http_request_duration_seconds",
        "HTTP request latency in seconds for api-rs",
        &["method", "endpoint"],
        vec![0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
    )
    .expect("failed to register http_request_duration_seconds");
}

pub fn record_http_request(method: &str, endpoint: &str, status: u16, duration_secs: f64) {
    let status_str = status.to_string();
    HTTP_REQUESTS_TOTAL
        .with_label_values(&[method, endpoint, &status_str])
        .inc();
    HTTP_REQUEST_DURATION_SECONDS
        .with_label_values(&[method, endpoint])
        .observe(duration_secs);
}

pub fn encode_metrics() -> Result<String, String> {
    let encoder = TextEncoder::new();
    let metric_families = prometheus::gather();
    let mut buffer = Vec::new();
    encoder
        .encode(&metric_families, &mut buffer)
        .map_err(|e| format!("Failed to encode prometheus metrics: {e}"))?;
    String::from_utf8(buffer).map_err(|e| format!("Invalid UTF-8 metric buffer: {e}"))
}
