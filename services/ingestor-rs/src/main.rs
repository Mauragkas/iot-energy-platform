use ingestor_rs::dedup::{Deduplicator, DEFAULT_CACHE_CAPACITY};
use ingestor_rs::kafka::KafkaPublisher;
use ingestor_rs::metrics::create_metrics_server;
use ingestor_rs::mqtt::{run_mqtt_subscriber, MqttConfig};
use std::sync::Arc;
use tracing::{error, info};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    // 1. Initialize structured logging
    let filter = EnvFilter::try_from_default_env()
        .or_else(|_| {
            let log_level = std::env::var("LOG_LEVEL").unwrap_or_else(|_| "info".to_string());
            EnvFilter::try_new(format!("ingestor_rs={log_level},info"))
        })
        .unwrap_or_else(|_| EnvFilter::new("info"));

    tracing_subscriber::registry()
        .with(filter)
        .with(tracing_subscriber::fmt::layer())
        .init();

    info!("Starting IoT Smart-Energy Ingestion Bridge (ingestor-rs)...");

    // 2. Read configuration
    let metrics_port: u16 = std::env::var("METRICS_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8081);

    let dedup_capacity: usize = std::env::var("DEDUP_CACHE_CAPACITY")
        .ok()
        .and_then(|c| c.parse().ok())
        .unwrap_or(DEFAULT_CACHE_CAPACITY);

    let kafka_brokers =
        std::env::var("KAFKA_BROKERS").unwrap_or_else(|_| "localhost:9092".to_string());
    let kafka_topic =
        std::env::var("KAFKA_TELEMETRY_TOPIC").unwrap_or_else(|_| "iot.telemetry.raw".to_string());

    let mqtt_config = MqttConfig::from_env();

    info!(
        "Config: metrics_port={}, dedup_capacity={}, kafka_brokers={}, kafka_topic={}, mqtt_broker={}:{}, mqtt_share={}",
        metrics_port,
        dedup_capacity,
        kafka_brokers,
        kafka_topic,
        mqtt_config.broker_host,
        mqtt_config.broker_port,
        mqtt_config.subscription_topic()
    );

    // 3. Initialize Deduplication cache
    let dedup = Deduplicator::new(dedup_capacity);

    // 4. Initialize Kafka Producer
    let publisher = match KafkaPublisher::new(&kafka_brokers, &kafka_topic) {
        Ok(p) => Arc::new(p),
        Err(e) => {
            error!("Failed to create Kafka producer: {}", e);
            return Err(e.into());
        }
    };

    // 5. Start Actix-web server (/metrics and /healthz)
    let metrics_server = create_metrics_server(metrics_port)?;
    let server_handle = metrics_server.handle();
    let metrics_task = tokio::spawn(metrics_server);
    info!(
        "Metrics server running on http://0.0.0.0:{}/metrics and /healthz",
        metrics_port
    );

    // 6. Shutdown coordination channels
    let (shutdown_tx, shutdown_rx) = tokio::sync::watch::channel(false);

    // 7. Spawn MQTT subscriber task
    let mqtt_handle = tokio::spawn(run_mqtt_subscriber(
        mqtt_config,
        dedup,
        publisher,
        shutdown_rx,
    ));

    // 8. Wait for OS termination signal (SIGINT or SIGTERM)
    wait_for_shutdown_signal().await;

    info!("Initiating graceful shutdown sequence...");

    // Notify MQTT task to stop and drain in-flight messages
    let _ = shutdown_tx.send(true);

    // Wait for MQTT worker to complete clean exit & Kafka flush
    if let Err(e) = mqtt_handle.await {
        error!("MQTT worker encountered error on join: {:?}", e);
    }

    // Stop metrics server
    server_handle.stop(true).await;
    let _ = metrics_task.await;

    info!("Ingestor service shut down successfully.");
    Ok(())
}

/// Waits for either SIGINT (Ctrl+C) or SIGTERM (Kubernetes pod termination).
async fn wait_for_shutdown_signal() {
    #[cfg(unix)]
    {
        use tokio::signal::unix::{signal, SignalKind};
        let mut sigterm =
            signal(SignalKind::terminate()).expect("Failed to register SIGTERM handler");
        tokio::select! {
            _ = tokio::signal::ctrl_c() => {
                info!("Received SIGINT (Ctrl+C)");
            }
            _ = sigterm.recv() => {
                info!("Received SIGTERM (Kubernetes termination signal)");
            }
        }
    }

    #[cfg(not(unix))]
    {
        tokio::signal::ctrl_c()
            .await
            .expect("Failed to listen for Ctrl+C");
        info!("Received Ctrl+C");
    }
}
