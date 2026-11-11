use actix_web::HttpServer;
use std::sync::Arc;
use tracing::info;
use tracing_subscriber::EnvFilter;

use api_rs::build_app;
use api_rs::config::Config;
use api_rs::repository::{
    DatabaseHealthRepository, MongoTwinRepository, TimescaleAlertRepository,
    TimescaleTimeseriesRepository,
};
use api_rs::service::{AlertService, HealthService, MeterService};

#[actix_web::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let config = Config::from_env();

    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new(&config.log_level)),
        )
        .init();

    info!(
        host = %config.host,
        port = config.port,
        "Starting IoT Energy Platform REST API (api-rs)"
    );

    let pg_pool = config.create_postgres_pool()?;
    let mongo_client = config.create_mongo_client().await?;
    let mongo_db = mongo_client.database(&config.mongo_db);

    let timeseries_repo = Arc::new(TimescaleTimeseriesRepository::new(pg_pool.clone()));
    let alert_repo = Arc::new(TimescaleAlertRepository::new(pg_pool.clone()));
    let twin_repo = Arc::new(MongoTwinRepository::new(&mongo_db));
    let health_repo = Arc::new(DatabaseHealthRepository::new(pg_pool, mongo_db));

    let meter_service = Arc::new(MeterService::new(twin_repo, timeseries_repo));
    let alert_service = Arc::new(AlertService::new(alert_repo));
    let health_service = Arc::new(HealthService::new(health_repo));

    let bind_addr = (config.host.as_str(), config.port);
    info!("Binding HTTP server to {}:{}", bind_addr.0, bind_addr.1);

    HttpServer::new(move || {
        build_app(
            meter_service.clone(),
            alert_service.clone(),
            health_service.clone(),
        )
    })
    .bind(bind_addr)?
    .run()
    .await?;

    Ok(())
}
