use std::env;

#[derive(Debug, Clone)]
pub struct Config {
    pub kafka_brokers: String,
    pub kafka_topic: String,
    pub kafka_group_id: String,

    pub db_url: Option<String>,
    pub db_host: String,
    pub db_port: u16,
    pub db_user: String,
    pub db_password: String,
    pub db_name: String,
    pub db_pool_max_size: usize,

    pub metrics_host: String,
    pub metrics_port: u16,

    pub batch_size: usize,
    pub flush_interval_ms: u64,
}

impl Config {
    pub fn from_env() -> Self {
        let kafka_brokers = env::var("KAFKA_BROKERS").unwrap_or_else(|_| "localhost:9092".to_string());
        let kafka_topic = env::var("KAFKA_TELEMETRY_TOPIC")
            .or_else(|_| env::var("KAFKA_TOPIC"))
            .unwrap_or_else(|_| "iot.telemetry.raw".to_string());
        let kafka_group_id = env::var("KAFKA_GROUP_ID_PERSISTER")
            .or_else(|_| env::var("KAFKA_GROUP_ID"))
            .unwrap_or_else(|_| "iot-persister-group".to_string());

        let db_url = env::var("DATABASE_URL").ok();
        let db_host = env::var("TIMESCALE_HOST").unwrap_or_else(|_| "localhost".to_string());
        let db_port = env::var("TIMESCALE_PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(5432);
        let db_user = env::var("TIMESCALE_USER").unwrap_or_else(|_| "postgres".to_string());
        let db_password = env::var("TIMESCALE_PASSWORD").unwrap_or_else(|_| "postgres".to_string());
        let db_name = env::var("TIMESCALE_DB").unwrap_or_else(|_| "iot_energy".to_string());
        let db_pool_max_size = env::var("DB_POOL_MAX_SIZE")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(16);

        let metrics_host = env::var("METRICS_HOST").unwrap_or_else(|_| "0.0.0.0".to_string());
        let metrics_port = env::var("METRICS_PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(8082);

        let batch_size = env::var("PERSISTER_BATCH_SIZE")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(500);
        let flush_interval_ms = env::var("PERSISTER_FLUSH_INTERVAL_MS")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(500);

        Self {
            kafka_brokers,
            kafka_topic,
            kafka_group_id,
            db_url,
            db_host,
            db_port,
            db_user,
            db_password,
            db_name,
            db_pool_max_size,
            metrics_host,
            metrics_port,
            batch_size,
            flush_interval_ms,
        }
    }
}
