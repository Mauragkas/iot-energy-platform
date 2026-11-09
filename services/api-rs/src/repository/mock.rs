use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, RwLock};
use async_trait::async_trait;
use chrono::{DateTime, Utc};

use crate::domain::{AlertRecord, ConsumptionResponse, DeviceTwin, TimeseriesPoint};
use super::alert::AlertRepository;
use super::error::RepositoryError;
use super::health::HealthRepository;
use super::timeseries::TimeseriesRepository;
use super::twin::TwinRepository;

/// Mock implementation of TimeseriesRepository for testing.
#[derive(Clone, Default)]
pub struct MockTimeseriesRepository {
    points: Arc<RwLock<Vec<TimeseriesPoint>>>,
    consumption: Arc<RwLock<Option<ConsumptionResponse>>>,
}

impl MockTimeseriesRepository {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_points(self, points: Vec<TimeseriesPoint>) -> Self {
        *self.points.write().unwrap() = points;
        self
    }

    pub fn with_consumption(self, resp: ConsumptionResponse) -> Self {
        *self.consumption.write().unwrap() = Some(resp);
        self
    }
}

#[async_trait]
impl TimeseriesRepository for MockTimeseriesRepository {
    async fn query_timeseries(
        &self,
        _meter_id: &str,
        from: DateTime<Utc>,
        to: DateTime<Utc>,
        _bucket: &str,
    ) -> Result<Vec<TimeseriesPoint>, RepositoryError> {
        let lock = self.points.read().unwrap();
        let filtered = lock
            .iter()
            .filter(|p| p.bucket >= from && p.bucket <= to)
            .cloned()
            .collect();
        Ok(filtered)
    }

    async fn query_consumption(
        &self,
        meter_id: &str,
        from: Option<DateTime<Utc>>,
        to: Option<DateTime<Utc>>,
    ) -> Result<ConsumptionResponse, RepositoryError> {
        let lock = self.consumption.read().unwrap();
        if let Some(ref resp) = *lock {
            return Ok(resp.clone());
        }

        Ok(ConsumptionResponse {
            meter_id: meter_id.to_string(),
            from,
            to,
            total_consumption_kwh: 125.5,
            reading_count: 360,
        })
    }
}

/// Mock implementation of TwinRepository for testing.
#[derive(Clone, Default)]
pub struct MockTwinRepository {
    twins: Arc<RwLock<Vec<DeviceTwin>>>,
}

impl MockTwinRepository {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_twins(self, twins: Vec<DeviceTwin>) -> Self {
        *self.twins.write().unwrap() = twins;
        self
    }
}

#[async_trait]
impl TwinRepository for MockTwinRepository {
    async fn list_twins(
        &self,
        zone: Option<&str>,
        limit: usize,
    ) -> Result<Vec<DeviceTwin>, RepositoryError> {
        let lock = self.twins.read().unwrap();
        let filtered = lock
            .iter()
            .filter(|t| {
                if let Some(z) = zone {
                    t.zone.eq_ignore_ascii_case(z)
                } else {
                    true
                }
            })
            .take(limit)
            .cloned()
            .collect();
        Ok(filtered)
    }

    async fn get_twin(
        &self,
        meter_id: &str,
    ) -> Result<Option<DeviceTwin>, RepositoryError> {
        let lock = self.twins.read().unwrap();
        let found = lock.iter().find(|t| t.meter_id == meter_id).cloned();
        Ok(found)
    }
}

/// Mock implementation of AlertRepository for testing.
#[derive(Clone, Default)]
pub struct MockAlertRepository {
    alerts: Arc<RwLock<Vec<AlertRecord>>>,
}

impl MockAlertRepository {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_alerts(self, alerts: Vec<AlertRecord>) -> Self {
        *self.alerts.write().unwrap() = alerts;
        self
    }
}

#[async_trait]
impl AlertRepository for MockAlertRepository {
    async fn list_alerts(
        &self,
        severity: Option<&str>,
        since: Option<DateTime<Utc>>,
        limit: usize,
    ) -> Result<Vec<AlertRecord>, RepositoryError> {
        let lock = self.alerts.read().unwrap();
        let filtered = lock
            .iter()
            .filter(|a| {
                if let Some(s) = severity {
                    if !a.severity.eq_ignore_ascii_case(s) {
                        return false;
                    }
                }
                if let Some(since_dt) = since {
                    if a.time < since_dt {
                        return false;
                    }
                }
                true
            })
            .take(limit)
            .cloned()
            .collect();
        Ok(filtered)
    }
}

/// Mock implementation of HealthRepository for testing.
pub struct MockHealthRepository {
    pub timescale_healthy: AtomicBool,
    pub mongo_healthy: AtomicBool,
}

impl MockHealthRepository {
    pub fn new(timescale_ok: bool, mongo_ok: bool) -> Self {
        Self {
            timescale_healthy: AtomicBool::new(timescale_ok),
            mongo_healthy: AtomicBool::new(mongo_ok),
        }
    }

    pub fn set_timescale_healthy(&self, ok: bool) {
        self.timescale_healthy.store(ok, Ordering::SeqCst);
    }

    pub fn set_mongo_healthy(&self, ok: bool) {
        self.mongo_healthy.store(ok, Ordering::SeqCst);
    }
}

impl Default for MockHealthRepository {
    fn default() -> Self {
        Self::new(true, true)
    }
}

#[async_trait]
impl HealthRepository for MockHealthRepository {
    async fn check_timescale(&self) -> Result<(), RepositoryError> {
        if self.timescale_healthy.load(Ordering::SeqCst) {
            Ok(())
        } else {
            Err(RepositoryError::Connection("TimescaleDB connection failed".to_string()))
        }
    }

    async fn check_mongodb(&self) -> Result<(), RepositoryError> {
        if self.mongo_healthy.load(Ordering::SeqCst) {
            Ok(())
        } else {
            Err(RepositoryError::Connection("MongoDB ping failed".to_string()))
        }
    }
}
