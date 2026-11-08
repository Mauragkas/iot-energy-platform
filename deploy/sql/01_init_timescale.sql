-- 01_init_timescale.sql: TimescaleDB schema initialization for IoT Energy Platform

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 1. Base telemetry hypertable
CREATE TABLE IF NOT EXISTS meter_readings (
    time                TIMESTAMPTZ       NOT NULL,
    meter_id            VARCHAR(64)       NOT NULL,
    voltage_l1          DOUBLE PRECISION  NOT NULL,
    voltage_l2          DOUBLE PRECISION  NOT NULL,
    voltage_l3          DOUBLE PRECISION  NOT NULL,
    current_l1          DOUBLE PRECISION  NOT NULL,
    current_l2          DOUBLE PRECISION  NOT NULL,
    current_l3          DOUBLE PRECISION  NOT NULL,
    active_power_kw     DOUBLE PRECISION  NOT NULL,
    energy_kwh          DOUBLE PRECISION  NOT NULL,
    power_factor        DOUBLE PRECISION  NOT NULL,
    frequency_hz        DOUBLE PRECISION  NOT NULL,
    CONSTRAINT pk_meter_readings PRIMARY KEY (meter_id, time)
);

-- Partition into 1-day chunks
SELECT create_hypertable(
    'meter_readings',
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Compound index for fast per-meter time-series retrieval
CREATE INDEX IF NOT EXISTS idx_meter_readings_meter_time 
    ON meter_readings (meter_id, time DESC);

-- 2. Continuous Aggregate: 1-Minute Rollup
CREATE MATERIALIZED VIEW IF NOT EXISTS one_minute_consumption_rollup
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time)   AS bucket,
    meter_id,
    AVG(active_power_kw)            AS avg_active_power_kw,
    MAX(active_power_kw)            AS max_active_power_kw,
    MIN(active_power_kw)            AS min_active_power_kw,
    AVG(power_factor)               AS avg_power_factor,
    AVG(voltage_l1)                 AS avg_voltage_l1,
    COUNT(*)                        AS reading_count
FROM meter_readings
GROUP BY bucket, meter_id
WITH NO DATA;

-- 3. Continuous Aggregate: 1-Hour Rollup (with delta energy kWh)
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_consumption_rollup
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time)     AS bucket,
    meter_id,
    AVG(active_power_kw)            AS avg_active_power_kw,
    MAX(active_power_kw)            AS max_active_power_kw,
    MIN(active_power_kw)            AS min_active_power_kw,
    MAX(energy_kwh) - MIN(energy_kwh) AS delta_energy_kwh,
    AVG(power_factor)               AS avg_power_factor,
    AVG(voltage_l1)                 AS avg_voltage_l1,
    COUNT(*)                        AS reading_count
FROM meter_readings
GROUP BY bucket, meter_id
WITH NO DATA;

-- 4. Continuous Aggregate: 1-Day Rollup
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_consumption_rollup
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time)      AS bucket,
    meter_id,
    AVG(active_power_kw)            AS avg_active_power_kw,
    MAX(active_power_kw)            AS max_active_power_kw,
    MAX(energy_kwh) - MIN(energy_kwh) AS delta_energy_kwh,
    AVG(power_factor)               AS avg_power_factor,
    COUNT(*)                        AS reading_count
FROM meter_readings
GROUP BY bucket, meter_id
WITH NO DATA;

-- 5. Continuous Aggregate Refresh Policies
SELECT add_continuous_aggregate_policy('one_minute_consumption_rollup',
    start_offset => INTERVAL '2 hours',
    end_offset   => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('hourly_consumption_rollup',
    start_offset => INTERVAL '3 days',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '10 minutes',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('daily_consumption_rollup',
    start_offset => INTERVAL '30 days',
    end_offset   => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

-- 6. Columnar Compression Policy (compress chunks older than 7 days)
ALTER TABLE meter_readings SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'meter_id',
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('meter_readings', INTERVAL '7 days', if_not_exists => TRUE);

-- 7. Data Retention Policy (drop chunks older than 90 days)
SELECT add_retention_policy('meter_readings', INTERVAL '90 days', if_not_exists => TRUE);

-- 8. Anomaly Alerts Table (with unique constraint for idempotent writes)
CREATE TABLE IF NOT EXISTS meter_alerts (
    id                  BIGSERIAL,
    time                TIMESTAMPTZ       NOT NULL,
    meter_id            VARCHAR(64)       NOT NULL,
    alert_type          VARCHAR(64)       NOT NULL,
    severity            VARCHAR(32)       NOT NULL,
    value               DOUBLE PRECISION  NOT NULL,
    threshold           DOUBLE PRECISION  NOT NULL,
    message             TEXT,
    created_at          TIMESTAMPTZ       DEFAULT NOW(),
    CONSTRAINT uq_meter_alert UNIQUE (meter_id, alert_type, time)
);

CREATE INDEX IF NOT EXISTS idx_meter_alerts_lookup 
    ON meter_alerts (severity, time DESC);

CREATE INDEX IF NOT EXISTS idx_meter_alerts_meter_time 
    ON meter_alerts (meter_id, time DESC);
