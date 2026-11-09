use actix_web::{web, HttpResponse, Responder, ResponseError};
use chrono::{DateTime, Utc};
use serde::Deserialize;

use crate::domain::time_range::{flexible_datetime, flexible_datetime_opt};
use crate::service::MeterService;

#[derive(Debug, Deserialize)]
pub struct ListMetersQuery {
    pub zone: Option<String>,
    pub limit: Option<usize>,
}

#[derive(Debug, Deserialize)]
pub struct TimeseriesQuery {
    #[serde(deserialize_with = "flexible_datetime::deserialize")]
    pub from: DateTime<Utc>,
    #[serde(deserialize_with = "flexible_datetime::deserialize")]
    pub to: DateTime<Utc>,
    #[serde(default = "default_bucket")]
    pub bucket: String,
}

fn default_bucket() -> String {
    "1h".to_string()
}

#[derive(Debug, Deserialize)]
pub struct ConsumptionQuery {
    #[serde(default, deserialize_with = "flexible_datetime_opt::deserialize")]
    pub from: Option<DateTime<Utc>>,
    #[serde(default, deserialize_with = "flexible_datetime_opt::deserialize")]
    pub to: Option<DateTime<Utc>>,
}

pub async fn list_meters(
    meter_service: web::Data<MeterService>,
    query: web::Query<ListMetersQuery>,
) -> impl Responder {
    match meter_service
        .list_meters(query.zone.as_deref(), query.limit)
        .await
    {
        Ok(twins) => HttpResponse::Ok().json(twins),
        Err(err) => err.error_response(),
    }
}

pub async fn get_meter(
    meter_service: web::Data<MeterService>,
    id: web::Path<String>,
) -> impl Responder {
    match meter_service.get_meter(&id).await {
        Ok(twin) => HttpResponse::Ok().json(twin),
        Err(err) => err.error_response(),
    }
}

pub async fn query_timeseries(
    meter_service: web::Data<MeterService>,
    id: web::Path<String>,
    query: web::Query<TimeseriesQuery>,
) -> impl Responder {
    match meter_service
        .query_timeseries(&id, query.from, query.to, &query.bucket)
        .await
    {
        Ok(points) => HttpResponse::Ok().json(points),
        Err(err) => err.error_response(),
    }
}

pub async fn query_consumption(
    meter_service: web::Data<MeterService>,
    id: web::Path<String>,
    query: web::Query<ConsumptionQuery>,
) -> impl Responder {
    match meter_service
        .query_consumption(&id, query.from, query.to)
        .await
    {
        Ok(consumption) => HttpResponse::Ok().json(consumption),
        Err(err) => err.error_response(),
    }
}
