use actix_web::{web, HttpResponse, Responder, ResponseError};

use crate::service::HealthService;

pub async fn liveness_handler(health_service: web::Data<HealthService>) -> impl Responder {
    let res = health_service.check_liveness();
    HttpResponse::Ok().json(res)
}

pub async fn readiness_handler(health_service: web::Data<HealthService>) -> impl Responder {
    match health_service.check_readiness().await {
        Ok(report) => HttpResponse::Ok().json(report),
        Err(err) => err.error_response(),
    }
}
