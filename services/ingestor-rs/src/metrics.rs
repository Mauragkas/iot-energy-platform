use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use lazy_static::lazy_static;
use prometheus::{
    register_histogram, register_int_counter, Encoder, Histogram, IntCounter, TextEncoder,
};

lazy_static! {
    /// Counter for total incoming MQTT telemetry messages received.
    pub static ref TELEMETRY_MESSAGES_RECEIVED_TOTAL: IntCounter =
        register_int_counter!(
            "telemetry_messages_received_total",
            "Total number of telemetry messages received from MQTT"
        ).expect("failed to register telemetry_messages_received_total");

    /// Counter for total telemetry messages successfully published to Kafka.
    pub static ref TELEMETRY_MESSAGES_PUBLISHED_TOTAL: IntCounter =
        register_int_counter!(
            "telemetry_messages_published_total",
            "Total number of telemetry messages successfully published to Kafka"
        ).expect("failed to register telemetry_messages_published_total");

    /// Counter for duplicate telemetry messages detected and dropped.
    pub static ref TELEMETRY_MESSAGES_DEDUPLICATED_TOTAL: IntCounter =
        register_int_counter!(
            "telemetry_messages_deduplicated_total",
            "Total number of duplicate telemetry messages dropped"
        ).expect("failed to register telemetry_messages_deduplicated_total");

    /// Counter for invalid or unparseable telemetry messages rejected.
    pub static ref TELEMETRY_MESSAGES_REJECTED_TOTAL: IntCounter =
        register_int_counter!(
            "telemetry_messages_rejected_total",
            "Total number of invalid or unparseable telemetry messages rejected"
        ).expect("failed to register telemetry_messages_rejected_total");

    /// Histogram for latency of publishing messages to Kafka in seconds.
    pub static ref TELEMETRY_PUBLISH_DURATION_SECONDS: Histogram =
        register_histogram!(
            "telemetry_publish_duration_seconds",
            "Duration of publishing telemetry messages to Kafka in seconds",
            vec![0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5]
        ).expect("failed to register telemetry_publish_duration_seconds");
}

/// Handler for Prometheus `/metrics` scrape endpoint.
pub async fn metrics_handler() -> impl Responder {
    let encoder = TextEncoder::new();
    let metric_families = prometheus::gather();
    let mut buffer = Vec::new();

    if let Err(e) = encoder.encode(&metric_families, &mut buffer) {
        tracing::error!("Failed to encode prometheus metrics: {}", e);
        return HttpResponse::InternalServerError().body("Metric encoding error");
    }

    HttpResponse::Ok()
        .content_type("text/plain; version=0.0.4; charset=utf-8")
        .body(buffer)
}

/// Handler for `/healthz` liveness probe.
pub async fn healthz_handler() -> impl Responder {
    HttpResponse::Ok().body("OK")
}

/// Configures routes for the Actix web service.
pub fn configure_routes(cfg: &mut web::ServiceConfig) {
    cfg.route("/metrics", web::get().to(metrics_handler))
        .route("/healthz", web::get().to(healthz_handler));
}

/// Spawns the Actix-web server hosting `/metrics` and `/healthz` on the given port.
pub fn create_metrics_server(port: u16) -> Result<actix_web::dev::Server, std::io::Error> {
    let server = HttpServer::new(|| App::new().configure(configure_routes))
        .bind(("0.0.0.0", port))?
        .run();

    Ok(server)
}
