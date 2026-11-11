use persister_rs::config;
use persister_rs::consumer;
use persister_rs::db;
use persister_rs::metrics;
use tokio::sync::watch;
use tracing::{error, info};

async fn wait_for_shutdown() {
    let ctrl_c = async {
        tokio::signal::ctrl_c()
            .await
            .expect("failed to install Ctrl+C handler");
    };

    #[cfg(unix)]
    let terminate = async {
        match tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()) {
            Ok(mut signal) => {
                signal.recv().await;
            }
            Err(e) => {
                error!("Failed to install SIGTERM handler: {e}");
                std::future::pending::<()>().await;
            }
        }
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {
            info!("Received SIGINT (Ctrl+C)");
        }
        _ = terminate => {
            info!("Received SIGTERM");
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    info!("Starting persister-rs (Module C Time-Series Persister)");

    let config = config::Config::from_env();

    let pool = db::create_pool(&config)?;

    let metrics_server =
        metrics::start_metrics_server(pool.clone(), &config.metrics_host, config.metrics_port)?;
    let server_handle = metrics_server.handle();
    let server_task = tokio::spawn(metrics_server);

    let (shutdown_tx, shutdown_rx) = watch::channel(false);

    let sig_tx = shutdown_tx.clone();
    tokio::spawn(async move {
        wait_for_shutdown().await;
        let _ = sig_tx.send(true);
    });

    if let Err(e) = consumer::run_consumer(config, pool, shutdown_rx).await {
        error!("Consumer worker encountered fatal error: {e}");
    }

    info!("Stopping metrics HTTP server...");
    server_handle.stop(true).await;
    let _ = server_task.await;

    info!("persister-rs exited cleanly.");
    Ok(())
}
