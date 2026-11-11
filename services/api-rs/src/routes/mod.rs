pub mod alerts;
pub mod health;
pub mod meters;
pub mod metrics;

use crate::service::ErrorResponse;
use actix_web::{web, HttpResponse};

pub fn configure_routes(cfg: &mut web::ServiceConfig) {
    let query_config = web::QueryConfig::default().error_handler(|err, _req| {
        actix_web::error::InternalError::from_response(
            err.to_string(),
            HttpResponse::BadRequest().json(ErrorResponse {
                error: "BAD_REQUEST",
                message: format!("Invalid query parameters: {err}"),
            }),
        )
        .into()
    });

    let path_config = web::PathConfig::default().error_handler(|err, _req| {
        actix_web::error::InternalError::from_response(
            err.to_string(),
            HttpResponse::BadRequest().json(ErrorResponse {
                error: "BAD_REQUEST",
                message: format!("Invalid path parameter: {err}"),
            }),
        )
        .into()
    });

    cfg.app_data(query_config)
        .app_data(path_config)
        .route("/healthz", web::get().to(health::liveness_handler))
        .route("/readyz", web::get().to(health::readiness_handler))
        .route("/metrics", web::get().to(metrics::metrics_handler))
        .service(
            web::scope("/api/v1")
                .route("/meters", web::get().to(meters::list_meters))
                .route("/meters/{id}", web::get().to(meters::get_meter))
                .route(
                    "/meters/{id}/timeseries",
                    web::get().to(meters::query_timeseries),
                )
                .route(
                    "/meters/{id}/consumption",
                    web::get().to(meters::query_consumption),
                )
                .route("/alerts", web::get().to(alerts::list_alerts)),
        );
}
