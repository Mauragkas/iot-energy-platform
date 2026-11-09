use std::str::FromStr;
use deadpool_postgres::{Manager, Pool, Runtime};
use mongodb::options::ClientOptions;
use mongodb::Client;
use tokio_postgres::NoTls;
use tracing::info;

#[derive(Debug, Clone)]
pub struct Config {
    pub host: String,
    pub port: u16,

    // TimescaleDB / PostgreSQL
    pub database_url: Option<String>,
    pub db_host: String,
    pub db_port: u16,
    pub db_user: String,
    pub db_password: String,
    pub db_name: String,
    pub db_pool_max_size: usize,

    // MongoDB
    pub mongo_uri: Option<String>,
    pub mongo_host: String,
    pub mongo_port: u16,
    pub mongo_user: Option<String>,
    pub mongo_password: Option<String>,
    pub mongo_db: String,

    pub log_level: String,
}

impl Config {
    pub fn from_env() -> Self {
        let host = std::env::var("HOST").unwrap_or_else(|_| "0.0.0.0".to_string());
        let port = std::env::var("API_PORT")
            .or_else(|_| std::env::var("PORT"))
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(8080);

        let database_url = std::env::var("DATABASE_URL").ok();
        let db_host = std::env::var("TIMESCALE_HOST")
            .or_else(|_| std::env::var("POSTGRES_HOST"))
            .unwrap_or_else(|_| "localhost".to_string());
        let db_port = std::env::var("TIMESCALE_PORT")
            .or_else(|_| std::env::var("POSTGRES_PORT"))
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(5432);
        let db_user = std::env::var("TIMESCALE_USER")
            .or_else(|_| std::env::var("POSTGRES_USER"))
            .unwrap_or_else(|_| "postgres".to_string());
        let db_password = std::env::var("TIMESCALE_PASSWORD")
            .or_else(|_| std::env::var("POSTGRES_PASSWORD"))
            .unwrap_or_else(|_| "postgres".to_string());
        let db_name = std::env::var("TIMESCALE_DB")
            .or_else(|_| std::env::var("POSTGRES_DB"))
            .unwrap_or_else(|_| "iot_energy".to_string());
        let db_pool_max_size = std::env::var("DB_POOL_MAX_SIZE")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(16);

        let mongo_uri = std::env::var("MONGO_URI").ok();
        let mongo_host = std::env::var("MONGO_HOST").unwrap_or_else(|_| "localhost".to_string());
        let mongo_port = std::env::var("MONGO_PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(27018);
        let mongo_user = std::env::var("MONGO_USER").ok();
        let mongo_password = std::env::var("MONGO_PASSWORD").ok();
        let mongo_db = std::env::var("MONGO_DB").unwrap_or_else(|_| "iot_twins".to_string());

        let log_level = std::env::var("LOG_LEVEL").unwrap_or_else(|_| "info".to_string());

        Self {
            host,
            port,
            database_url,
            db_host,
            db_port,
            db_user,
            db_password,
            db_name,
            db_pool_max_size,
            mongo_uri,
            mongo_host,
            mongo_port,
            mongo_user,
            mongo_password,
            mongo_db,
            log_level,
        }
    }

    pub fn create_postgres_pool(&self) -> Result<Pool, Box<dyn std::error::Error + Send + Sync>> {
        let pg_config = if let Some(ref url_str) = self.database_url {
            info!("Configuring TimescaleDB pool from DATABASE_URL");
            tokio_postgres::Config::from_str(url_str)?
        } else {
            info!(
                host = %self.db_host,
                port = self.db_port,
                dbname = %self.db_name,
                user = %self.db_user,
                "Configuring TimescaleDB pool from parameters"
            );
            let mut pg_cfg = tokio_postgres::Config::new();
            pg_cfg.host(&self.db_host);
            pg_cfg.port(self.db_port);
            pg_cfg.user(&self.db_user);
            pg_cfg.password(&self.db_password);
            pg_cfg.dbname(&self.db_name);
            pg_cfg
        };

        let manager = Manager::new(pg_config, NoTls);
        let pool = Pool::builder(manager)
            .max_size(self.db_pool_max_size)
            .runtime(Runtime::Tokio1)
            .build()?;

        Ok(pool)
    }

    pub async fn create_mongo_client(&self) -> Result<Client, Box<dyn std::error::Error + Send + Sync>> {
        let uri = if let Some(ref uri) = self.mongo_uri {
            info!("Configuring MongoDB client from MONGO_URI");
            uri.clone()
        } else {
            info!(
                host = %self.mongo_host,
                port = self.mongo_port,
                dbname = %self.mongo_db,
                "Configuring MongoDB client from parameters"
            );
            match (&self.mongo_user, &self.mongo_password) {
                (Some(u), Some(p)) => format!(
                    "mongodb://{u}:{p}@{}:{}/{}?authSource=admin",
                    self.mongo_host, self.mongo_port, self.mongo_db
                ),
                _ => format!(
                    "mongodb://{}:{}/{}",
                    self.mongo_host, self.mongo_port, self.mongo_db
                ),
            }
        };

        let client_options = ClientOptions::parse(&uri).await?;
        let client = Client::with_options(client_options)?;
        Ok(client)
    }
}
