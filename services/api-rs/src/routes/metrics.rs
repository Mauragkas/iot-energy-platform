use actix_web::{HttpResponse, Responder};

use crate::metrics::encode_metrics;

pub async fn metrics_handler() -> impl Responder {
    match encode_metrics() {
        Ok(body) => HttpResponse::Ok()
            .content_type("text/plain; version=0.0.4; charset=utf-8")
            .body(body),
        Err(err) => HttpResponse::InternalServerError().body(err),
    }
}
