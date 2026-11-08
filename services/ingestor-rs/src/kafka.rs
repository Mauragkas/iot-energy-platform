use rdkafka::config::ClientConfig;
use rdkafka::producer::{FutureProducer, FutureRecord, Producer};
use rdkafka::util::Timeout;
use std::future::Future;
use std::pin::Pin;
use std::time::Duration;
use tracing::info;

/// Abstract telemetry publisher trait to allow mocking in unit and integration tests.
pub trait TelemetryPublisher: Send + Sync {
    fn publish<'a>(
        &'a self,
        key: &'a str,
        payload: &'a str,
    ) -> Pin<Box<dyn Future<Output = Result<(), String>> + Send + 'a>>;

    fn flush(&self, timeout: Duration) -> Result<(), String>;
}

/// Kafka publisher wrapping `rdkafka::producer::FutureProducer`.
pub struct KafkaPublisher {
    producer: FutureProducer,
    topic: String,
}

impl KafkaPublisher {
    /// Creates and configures a new `KafkaPublisher` with production-grade settings:
    /// - `acks = all` for strongest persistence guarantees
    /// - `enable.idempotence = true` to prevent duplicate records on retry
    /// - `retries = 5`
    /// - `message.timeout.ms = 5000`
    /// - `max.in.flight.requests.per.connection = 5` (safe with idempotence)
    pub fn new(brokers: &str, topic: &str) -> Result<Self, rdkafka::error::KafkaError> {
        let producer: FutureProducer = ClientConfig::new()
            .set("bootstrap.servers", brokers)
            .set("acks", "all")
            .set("enable.idempotence", "true")
            .set("retries", "5")
            .set("message.timeout.ms", "5000")
            .set("max.in.flight.requests.per.connection", "5")
            .create()?;

        info!(
            "Kafka FutureProducer initialized: brokers={}, topic={}",
            brokers, topic
        );

        Ok(Self {
            producer,
            topic: topic.to_string(),
        })
    }

    pub fn topic(&self) -> &str {
        &self.topic
    }
}

impl TelemetryPublisher for KafkaPublisher {
    fn publish<'a>(
        &'a self,
        key: &'a str,
        payload: &'a str,
    ) -> Pin<Box<dyn Future<Output = Result<(), String>> + Send + 'a>> {
        Box::pin(async move {
            let record = FutureRecord::to(&self.topic)
                .key(key)
                .payload(payload);

            match self.producer.send(record, Timeout::After(Duration::from_secs(5))).await {
                Ok(_) => Ok(()),
                Err((kafka_err, _)) => Err(kafka_err.to_string()),
            }
        })
    }

    fn flush(&self, timeout: Duration) -> Result<(), String> {
        self.producer
            .flush(Timeout::After(timeout))
            .map_err(|e| e.to_string())
    }
}

/// Mock publisher for unit testing ingestion pipeline logic.
#[cfg(test)]
pub struct MockPublisher {
    pub messages: std::sync::Arc<std::sync::Mutex<Vec<(String, String)>>>,
}

#[cfg(test)]
impl Default for MockPublisher {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
impl MockPublisher {
    pub fn new() -> Self {
        Self {
            messages: std::sync::Arc::new(std::sync::Mutex::new(Vec::new())),
        }
    }
}

#[cfg(test)]
impl TelemetryPublisher for MockPublisher {
    fn publish<'a>(
        &'a self,
        key: &'a str,
        payload: &'a str,
    ) -> Pin<Box<dyn Future<Output = Result<(), String>> + Send + 'a>> {
        let k = key.to_string();
        let p = payload.to_string();
        let msgs = self.messages.clone();
        Box::pin(async move {
            msgs.lock().unwrap().push((k, p));
            Ok(())
        })
    }

    fn flush(&self, _timeout: Duration) -> Result<(), String> {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_mock_publisher() {
        let publisher = MockPublisher::new();
        publisher
            .publish("MZ-3P-0042", r#"{"meter_id":"MZ-3P-0042"}"#)
            .await
            .unwrap();

        let msgs = publisher.messages.lock().unwrap();
        assert_eq!(msgs.len(), 1);
        assert_eq!(msgs[0].0, "MZ-3P-0042");
        assert_eq!(msgs[0].1, r#"{"meter_id":"MZ-3P-0042"}"#);
    }
}
