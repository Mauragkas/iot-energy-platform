use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use lazy_static::lazy_static;
use prometheus::{
    register_histogram, register_int_counter, Encoder, Histogram, IntCounter, TextEncoder,
};
use tracing::{error, info};

use crate::db::{self, DbPool};

lazy_static! {
    pub static ref TELEMETRY_PERSISTED_RECORDS: IntCounter = register_int_counter!(
        "telemetry_persisted_records_total",
        "Total number of telemetry records successfully persisted into TimescaleDB"
    )
    .expect("failed to register telemetry_persisted_records_total");

    pub static ref TELEMETRY_PERSIST_BATCH_DURATION: Histogram = register_histogram!(
        "telemetry_persist_batch_duration_seconds",
        "Duration of batch insert operations into TimescaleDB in seconds",
        vec![0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
    )
    .expect("failed to register telemetry_persist_batch_duration_seconds");

    pub static ref TELEMETRY_PERSIST_BATCHES: IntCounter = register_int_counter!(
        "telemetry_persist_batches_total",
        "Total number of batch insertions attempted"
    )
    .expect("failed to register telemetry_persist_batches_total");

    pub static ref TELEMETRY_PERSIST_ERRORS: IntCounter = register_int_counter!(
        "telemetry_persist_errors_total",
        "Total number of persister errors (e.g. deserialization, database write failure)"
    )
    .expect("failed to register telemetry_persist_errors_total");
}

pub async fn metrics_handler() -> impl Responder {
    let encoder = TextEncoder::new();
    let metric_families = prometheus::gather();
    let mut buffer = Vec::new();
    if let Err(e) = encoder.encode(&metric_families, &mut buffer) {
        error!("Failed to encode prometheus metrics: {e}");
        return HttpResponse::InternalServerError().body(e.to_string());
    }

    HttpResponse::Ok()
        .content_type(encoder.format_type())
        .body(buffer)
}

pub async fn healthz_handler(pool: web::Data<DbPool>) -> impl Responder {
    match db::ping(&pool).await {
        Ok(_) => HttpResponse::Ok().body("OK"),
        Err(e) => {
            error!("Healthcheck failed: DB ping error: {e}");
            HttpResponse::ServiceUnavailable().body(format!("DB unavailable: {e}"))
        }
    }
}

pub fn start_metrics_server(
    pool: DbPool,
    host: &str,
    port: u16,
) -> Result<actix_web::dev::Server, std::io::Error> {
    let pool_data = web::Data::new(pool);
    let server = HttpServer::new(move || {
        App::new()
            .app_data(pool_data.clone())
            .route("/metrics", web::get().to(metrics_handler))
            .route("/healthz", web::get().to(healthz_handler))
    })
    .bind((host, port))?
    .workers(2)
    .run();

    info!(host, port, "Metrics and health HTTP server configured on {host}:{port}");
    Ok(server)
}

#[cfg(test)]
mod tests {
    use super::*;

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
}
