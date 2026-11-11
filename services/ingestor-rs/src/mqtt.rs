use crate::dedup::Deduplicator;
use crate::kafka::TelemetryPublisher;
use crate::metrics::{
    TELEMETRY_MESSAGES_DEDUPLICATED_TOTAL, TELEMETRY_MESSAGES_PUBLISHED_TOTAL,
    TELEMETRY_MESSAGES_RECEIVED_TOTAL, TELEMETRY_MESSAGES_REJECTED_TOTAL,
    TELEMETRY_PUBLISH_DURATION_SECONDS,
};
use crate::model::SmartMeterTelemetry;
use rumqttc::{AsyncClient, Event, MqttOptions, Packet, QoS};
use std::sync::Arc;
use std::time::Duration;
use tracing::{debug, error, info, warn};

/// Configuration for the MQTT subscriber connection.
#[derive(Debug, Clone)]
pub struct MqttConfig {
    pub broker_host: String,
    pub broker_port: u16,
    pub client_id: String,
    pub share_group: String,
    pub topic_filter: String,
}

impl MqttConfig {
    /// Loads MQTT configuration from environment variables or sensible defaults.
    pub fn from_env() -> Self {
        let broker_host =
            std::env::var("MQTT_BROKER_HOST").unwrap_or_else(|_| "localhost".to_string());
        let broker_port = std::env::var("MQTT_BROKER_PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(1883);
        let share_group =
            std::env::var("MQTT_SHARE_GROUP").unwrap_or_else(|_| "ingest".to_string());
        let topic_filter = std::env::var("MQTT_TOPIC_FILTER")
            .unwrap_or_else(|_| "meazon/grid/+/meter/+/telemetry".to_string());

        let client_id = std::env::var("MQTT_CLIENT_ID").unwrap_or_else(|_| {
            let pid = std::process::id();
            let timestamp = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis();
            format!("ingestor-{}-{}", pid, timestamp % 100_000)
        });

        Self {
            broker_host,
            broker_port,
            client_id,
            share_group,
            topic_filter,
        }
    }

    /// Formats the MQTT v5 shared subscription topic.
    ///
    /// E.g. `$share/ingest/meazon/grid/+/meter/+/telemetry`
    pub fn subscription_topic(&self) -> String {
        format!("$share/{}/{}", self.share_group, self.topic_filter)
    }
}

/// Outcome of processing a single incoming telemetry message.
#[derive(Debug, PartialEq, Eq)]
pub enum ProcessOutcome {
    Published(String),
    Duplicate(String),
    Rejected(String),
}

/// Core ingestion processing logic:
/// 1. Metric counter increment (`telemetry_messages_received_total`)
/// 2. JSON Deserialization -> `SmartMeterTelemetry`
/// 3. Electrical unit & schema validation
/// 4. Deduplication cache check `(meter_id, timestamp)`
/// 5. Publish to Kafka with key = `meter_id`
/// 6. Metric counters & histogram updates
pub async fn process_message<P: TelemetryPublisher + ?Sized>(
    payload: &[u8],
    dedup: &Deduplicator,
    publisher: &P,
) -> ProcessOutcome {
    TELEMETRY_MESSAGES_RECEIVED_TOTAL.inc();

    // 1. JSON parsing
    let telemetry: SmartMeterTelemetry = match serde_json::from_slice(payload) {
        Ok(t) => t,
        Err(e) => {
            TELEMETRY_MESSAGES_REJECTED_TOTAL.inc();
            warn!("Failed to deserialize telemetry JSON: {}", e);
            return ProcessOutcome::Rejected(format!("Deserialization error: {}", e));
        }
    };

    // 2. Semantic validation
    if let Err(e) = telemetry.validate() {
        TELEMETRY_MESSAGES_REJECTED_TOTAL.inc();
        warn!(
            "Telemetry validation failed for meter '{}': {}",
            telemetry.meter_id, e
        );
        return ProcessOutcome::Rejected(format!("Validation error: {}", e));
    }

    // 3. Deduplication check
    if dedup.is_duplicate_or_record(&telemetry.meter_id, &telemetry.timestamp) {
        TELEMETRY_MESSAGES_DEDUPLICATED_TOTAL.inc();
        debug!(
            "Deduplicated repeated packet for meter '{}' at timestamp '{}'",
            telemetry.meter_id, telemetry.timestamp
        );
        return ProcessOutcome::Duplicate(telemetry.meter_id);
    }

    // 4. Re-serialize normalized JSON payload (guarantees UTC formatting and valid fields)
    let payload_str = match serde_json::to_string(&telemetry) {
        Ok(s) => s,
        Err(e) => {
            TELEMETRY_MESSAGES_REJECTED_TOTAL.inc();
            error!("Failed to re-serialize validated telemetry: {}", e);
            return ProcessOutcome::Rejected(format!("Serialization error: {}", e));
        }
    };

    // 5. Publish to Kafka
    let timer = TELEMETRY_PUBLISH_DURATION_SECONDS.start_timer();
    match publisher.publish(&telemetry.meter_id, &payload_str).await {
        Ok(_) => {
            timer.observe_duration();
            TELEMETRY_MESSAGES_PUBLISHED_TOTAL.inc();
            debug!(
                "Successfully published telemetry for meter '{}'",
                telemetry.meter_id
            );
            ProcessOutcome::Published(telemetry.meter_id)
        }
        Err(e) => {
            error!(
                "Failed to publish to Kafka for meter '{}': {}",
                telemetry.meter_id, e
            );
            ProcessOutcome::Rejected(format!("Kafka publish error: {}", e))
        }
    }
}

/// Runs the MQTT subscriber loop connecting to Mosquitto and routing messages.
/// Listens to `shutdown_rx` for graceful termination.
pub async fn run_mqtt_subscriber<P: TelemetryPublisher + 'static>(
    config: MqttConfig,
    dedup: Deduplicator,
    publisher: Arc<P>,
    mut shutdown_rx: tokio::sync::watch::Receiver<bool>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let mut mqttoptions =
        MqttOptions::new(&config.client_id, &config.broker_host, config.broker_port);
    mqttoptions.set_keep_alive(Duration::from_secs(30));
    mqttoptions.set_clean_session(true);

    let sub_topic = config.subscription_topic();
    info!(
        "Connecting to MQTT broker at {}:{} as client '{}'",
        config.broker_host, config.broker_port, config.client_id
    );

    let (client, mut eventloop) = AsyncClient::new(mqttoptions, 200);

    // Initial subscription request
    info!("Subscribing to shared topic: {}", sub_topic);
    client.subscribe(&sub_topic, QoS::AtLeastOnce).await?;

    let mut subscribed = true;

    loop {
        tokio::select! {
            _ = shutdown_rx.changed() => {
                if *shutdown_rx.borrow() {
                    info!("Shutdown signal received in MQTT subscriber. Draining in-flight messages...");
                    // Try to unsubscribe to avoid pulling new messages from Mosquitto
                    let _ = client.unsubscribe(&sub_topic).await;
                    break;
                }
            }
            event_result = eventloop.poll() => {
                match event_result {
                    Ok(Event::Incoming(Packet::Publish(publish))) => {
                        let payload = publish.payload;
                        let dedup_clone = dedup.clone();
                        let pub_clone = publisher.clone();

                        // Process message
                        process_message(&payload, &dedup_clone, pub_clone.as_ref()).await;
                    }
                    Ok(Event::Incoming(Packet::ConnAck(_))) => {
                        info!("Connected to MQTT broker successfully.");
                        if !subscribed {
                            let _ = client.subscribe(&sub_topic, QoS::AtLeastOnce).await;
                            subscribed = true;
                        }
                    }
                    Ok(Event::Incoming(Packet::Disconnect)) => {
                        warn!("Received disconnect from MQTT broker.");
                        subscribed = false;
                    }
                    Ok(_) => {
                        // Other packets (PingResp, SubAck, etc.)
                    }
                    Err(e) => {
                        warn!("MQTT connection error: {}. Retrying in 500ms...", e);
                        subscribed = false;
                        tokio::time::sleep(Duration::from_millis(500)).await;
                    }
                }
            }
        }
    }

    info!("MQTT event loop stopped. Flushing Kafka producer...");
    if let Err(e) = publisher.flush(Duration::from_secs(5)) {
        warn!("Error flushing Kafka producer on shutdown: {}", e);
    } else {
        info!("Kafka producer flushed successfully.");
    }

    Ok(())
}
