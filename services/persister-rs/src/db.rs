use deadpool_postgres::{Manager, Pool, Runtime};
use std::fmt::Write;
use std::str::FromStr;
use tokio_postgres::types::ToSql;
use tokio_postgres::NoTls;
use tracing::{debug, info};

use crate::config::Config;
use crate::model::TelemetryReading;

pub type DbPool = Pool;

pub fn create_pool(config: &Config) -> Result<DbPool, Box<dyn std::error::Error + Send + Sync>> {
    let pg_config = if let Some(ref url_str) = config.db_url {
        info!("Configuring TimescaleDB pool from DATABASE_URL");
        tokio_postgres::Config::from_str(url_str)?
    } else {
        info!(
            host = %config.db_host,
            port = config.db_port,
            dbname = %config.db_name,
            user = %config.db_user,
            "Configuring TimescaleDB pool from connection parameters"
        );
        let mut pg_cfg = tokio_postgres::Config::new();
        pg_cfg.host(&config.db_host);
        pg_cfg.port(config.db_port);
        pg_cfg.user(&config.db_user);
        pg_cfg.password(&config.db_password);
        pg_cfg.dbname(&config.db_name);
        pg_cfg
    };

    let manager = Manager::new(pg_config, NoTls);
    let pool = Pool::builder(manager)
        .max_size(config.db_pool_max_size)
        .runtime(Runtime::Tokio1)
        .build()?;

    Ok(pool)
}

/// Perform a health check query `SELECT 1` on the database pool.
pub async fn ping(pool: &DbPool) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let client = pool.get().await?;
    client.simple_query("SELECT 1;").await?;
    Ok(())
}

/// Builds dynamic multi-row VALUES SQL query for batch insertion.
///
/// Columns (12):
/// `(time, meter_id, voltage_l1, voltage_l2, voltage_l3, current_l1, current_l2, current_l3, active_power_kw, energy_kwh, power_factor, frequency_hz)`
pub fn build_batch_insert_query(row_count: usize) -> String {
    if row_count == 0 {
        return String::new();
    }

    let mut query = String::from(
        "INSERT INTO meter_readings (\
            time, meter_id, voltage_l1, voltage_l2, voltage_l3, \
            current_l1, current_l2, current_l3, active_power_kw, \
            energy_kwh, power_factor, frequency_hz\
        ) VALUES ",
    );

    const COLS_PER_ROW: usize = 12;
    for i in 0..row_count {
        if i > 0 {
            query.push_str(", ");
        }
        let base = i * COLS_PER_ROW;
        let _ = write!(
            query,
            "(${}, ${}, ${}, ${}, ${}, ${}, ${}, ${}, ${}, ${}, ${}, ${})",
            base + 1,
            base + 2,
            base + 3,
            base + 4,
            base + 5,
            base + 6,
            base + 7,
            base + 8,
            base + 9,
            base + 10,
            base + 11,
            base + 12
        );
    }

    query.push_str(" ON CONFLICT (meter_id, time) DO NOTHING;");
    query
}

/// Batch insert a slice of telemetry readings into TimescaleDB.
///
/// Returns the number of rows successfully inserted.
pub async fn batch_insert(
    pool: &DbPool,
    readings: &[TelemetryReading],
) -> Result<u64, Box<dyn std::error::Error + Send + Sync>> {
    if readings.is_empty() {
        return Ok(0);
    }

    let sql = build_batch_insert_query(readings.len());
    let mut params: Vec<&(dyn ToSql + Sync)> = Vec::with_capacity(readings.len() * 12);

    for r in readings {
        params.push(&r.time);
        params.push(&r.meter_id);
        params.push(&r.voltage_l1);
        params.push(&r.voltage_l2);
        params.push(&r.voltage_l3);
        params.push(&r.current_l1);
        params.push(&r.current_l2);
        params.push(&r.current_l3);
        params.push(&r.active_power_kw);
        params.push(&r.energy_kwh);
        params.push(&r.power_factor);
        params.push(&r.frequency_hz);
    }

    let client = pool.get().await?;
    let rows_affected = client.execute(&sql, &params[..]).await?;
    debug!(
        rows_affected,
        count = readings.len(),
        "Batch insert executed"
    );

    Ok(rows_affected)
}
