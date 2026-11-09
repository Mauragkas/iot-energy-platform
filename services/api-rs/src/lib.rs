pub mod config;
pub mod domain;
pub mod metrics;
pub mod repository;
pub mod routes;
pub mod service;

use std::sync::Arc;
use actix_web::body::BoxBody;
use actix_web::dev::{Service as _, ServiceFactory, ServiceRequest, ServiceResponse};
use actix_web::{web, App, Error};

use crate::metrics::record_http_request;
use crate::service::{AlertService, HealthService, MeterService};

/// Builds and registers an Actix-web App instance with injected services,
/// JSON error handlers, route hierarchy, and Prometheus observation middleware.
pub fn build_app(
    meter_service: Arc<MeterService>,
    alert_service: Arc<AlertService>,
    health_service: Arc<HealthService>,
) -> App<
    impl ServiceFactory<
        ServiceRequest,
        Config = (),
        Response = ServiceResponse<BoxBody>,
        Error = Error,
        InitError = (),
    >,
> {
    App::new()
        .app_data(web::Data::from(meter_service))
        .app_data(web::Data::from(alert_service))
        .app_data(web::Data::from(health_service))
        .wrap_fn(|req, srv| {
            let start = std::time::Instant::now();
            let method = req.method().to_string();
            let path = req.match_pattern().unwrap_or_else(|| req.path().to_string());
            let fut = srv.call(req);
            async move {
                let res: ServiceResponse<BoxBody> = fut.await?;
                let elapsed = start.elapsed().as_secs_f64();
                let status = res.status().as_u16();
                record_http_request(&method, &path, status, elapsed);
                Ok(res)
            }
        })
        .configure(routes::configure_routes)
}
