use std::collections::HashMap;
use std::time::{Duration, Instant};
use rdkafka::config::ClientConfig;
use rdkafka::consumer::{CommitMode, Consumer, StreamConsumer};
use rdkafka::message::Message;
use rdkafka::topic_partition_list::{Offset, TopicPartitionList};
use tokio::sync::watch;
use tracing::{error, info, warn};

use crate::config::Config;
use crate::db::{self, DbPool};
use crate::metrics::{
    TELEMETRY_PERSISTED_RECORDS, TELEMETRY_PERSIST_BATCHES,
    TELEMETRY_PERSIST_BATCH_DURATION, TELEMETRY_PERSIST_ERRORS,
};
use crate::model::TelemetryReading;

/// Micro-batch buffer tracking collected telemetry readings and high-watermark offsets.
#[derive(Debug, Default)]
pub struct BatchBuffer {
    pub readings: Vec<TelemetryReading>,
    pub offsets: HashMap<(String, i32), i64>,
}

impl BatchBuffer {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn push_reading(&mut self, reading: TelemetryReading, topic: &str, partition: i32, offset: i64) {
        self.readings.push(reading);
        self.track_offset(topic, partition, offset);
    }

    pub fn track_offset(&mut self, topic: &str, partition: i32, offset: i64) {
        self.offsets
            .entry((topic.to_string(), partition))
            .and_modify(|o| *o = (*o).max(offset))
            .or_insert(offset);
    }

    pub fn len(&self) -> usize {
        self.readings.len()
    }

    pub fn is_empty(&self) -> bool {
        self.readings.is_empty() && self.offsets.is_empty()
    }

    pub fn clear(&mut self) {
        self.readings.clear();
        self.offsets.clear();
    }
}

/// Flushes buffered telemetry readings to TimescaleDB and commits Kafka offsets on success.
pub async fn flush_batch(
    pool: &DbPool,
    consumer: &StreamConsumer,
    buffer: &mut BatchBuffer,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    if buffer.is_empty() {
        return Ok(());
    }

    if !buffer.readings.is_empty() {
        let start = Instant::now();
        let count = buffer.readings.len();

        let mut attempts = 0;
        let max_attempts = 3;
        loop {
            attempts += 1;
            match db::batch_insert(pool, &buffer.readings).await {
                Ok(rows) => {
                    let duration = start.elapsed().as_secs_f64();
                    TELEMETRY_PERSIST_BATCH_DURATION.observe(duration);
                    TELEMETRY_PERSIST_BATCHES.inc();
                    TELEMETRY_PERSISTED_RECORDS.inc_by(rows);
                    info!(
                        persisted = rows,
                        readings = count,
                        duration_secs = duration,
                        "Persisted telemetry batch to TimescaleDB"
                    );
                    break;
                }
                Err(err) => {
                    TELEMETRY_PERSIST_ERRORS.inc();
                    error!(
                        attempt = attempts,
                        max_attempts,
                        error = %err,
                        "Failed to execute batch insert into TimescaleDB"
                    );
                    if attempts >= max_attempts {
                        return Err(err);
                    }
                    tokio::time::sleep(Duration::from_millis(100 * attempts)).await;
                }
            }
        }
    }

    // Commit Kafka offsets only after successful DB write
    if !buffer.offsets.is_empty() {
        let mut tpl = TopicPartitionList::new();
        for ((topic, partition), max_offset) in &buffer.offsets {
            tpl.add_partition_offset(topic, *partition, Offset::Offset(*max_offset + 1))?;
        }
        consumer.commit(&tpl, CommitMode::Sync)?;
    }

    buffer.clear();
    Ok(())
}

/// Consumes telemetry from Kafka in micro-batches and persists them into TimescaleDB.
pub async fn run_consumer(
    config: Config,
    pool: DbPool,
    mut shutdown_rx: watch::Receiver<bool>,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let mut consumer_config = ClientConfig::new();
    consumer_config
        .set("bootstrap.servers", &config.kafka_brokers)
        .set("group.id", &config.kafka_group_id)
        .set("enable.auto.commit", "false")
        .set("auto.offset.reset", "earliest")
        .set("session.timeout.ms", "45000")
        .set("max.poll.interval.ms", "300000")
        .set("enable.partition.eof", "false");

    info!(
        brokers = %config.kafka_brokers,
        topic = %config.kafka_topic,
        group = %config.kafka_group_id,
        batch_size = config.batch_size,
        flush_interval_ms = config.flush_interval_ms,
        "Initializing Kafka StreamConsumer"
    );

    let consumer: StreamConsumer = consumer_config.create()?;
    consumer.subscribe(&[&config.kafka_topic])?;

    let mut buffer = BatchBuffer::new();
    let flush_duration = Duration::from_millis(config.flush_interval_ms);
    let mut interval = tokio::time::interval(flush_duration);
    interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);

    info!("Starting persister consumer loop");

    loop {
        tokio::select! {
            _ = shutdown_rx.changed() => {
                if *shutdown_rx.borrow() {
                    info!("Shutdown signal received, draining buffer before exit...");
                    if let Err(e) = flush_batch(&pool, &consumer, &mut buffer).await {
                        error!("Error during shutdown flush: {e}");
                    }
                    info!("Buffer drained. Persister consumer loop ended.");
                    break;
                }
            }
            _ = interval.tick() => {
                if !buffer.is_empty() {
                    if let Err(e) = flush_batch(&pool, &consumer, &mut buffer).await {
                        error!("Interval flush error: {e}");
                    }
                }
            }
            msg_res = consumer.recv() => {
                match msg_res {
                    Ok(msg) => {
                        let topic = msg.topic();
                        let partition = msg.partition();
                        let offset = msg.offset();

                        match msg.payload() {
                            Some(payload) => {
                                match TelemetryReading::from_json_slice(payload) {
                                    Ok(reading) => {
                                        buffer.push_reading(reading, topic, partition, offset);
                                        if buffer.len() >= config.batch_size {
                                            if let Err(e) = flush_batch(&pool, &consumer, &mut buffer).await {
                                                error!("Batch size threshold flush error: {e}");
                                            }
                                        }
                                    }
                                    Err(e) => {
                                        TELEMETRY_PERSIST_ERRORS.inc();
                                        warn!(
                                            topic, partition, offset,
                                            error = %e,
                                            "Failed to deserialize telemetry reading; advancing offset to avoid poison pill"
                                        );
                                        buffer.track_offset(topic, partition, offset);
                                    }
                                }
                            }
                            None => {
                                TELEMETRY_PERSIST_ERRORS.inc();
                                warn!(topic, partition, offset, "Received message with empty payload");
                                buffer.track_offset(topic, partition, offset);
                            }
                        }
                    }
                    Err(e) => {
                        warn!("Kafka receive error: {e}");
                    }
                }
            }
        }
    }

    Ok(())
}
