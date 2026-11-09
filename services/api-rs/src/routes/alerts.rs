use actix_web::{web, HttpResponse, Responder, ResponseError};
use chrono::{DateTime, Utc};
use serde::Deserialize;

use crate::domain::time_range::flexible_datetime_opt;
use crate::service::AlertService;

#[derive(Debug, Deserialize)]
pub struct ListAlertsQuery {
    pub severity: Option<String>,
    #[serde(default, deserialize_with = "flexible_datetime_opt::deserialize")]
    pub since: Option<DateTime<Utc>>,
    pub limit: Option<usize>,
}

pub async fn list_alerts(
    alert_service: web::Data<AlertService>,
    query: web::Query<ListAlertsQuery>,
) -> impl Responder {
    match alert_service
        .list_alerts(query.severity.as_deref(), query.since, query.limit)
        .await
    {
        Ok(alerts) => HttpResponse::Ok().json(alerts),
        Err(err) => err.error_response(),
    }
}
