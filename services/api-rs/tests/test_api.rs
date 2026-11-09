use std::sync::Arc;
use actix_web::test::{self, TestRequest};
use chrono::{DateTime, Duration, Utc};
use serde_json::Value;

use api_rs::build_app;
use api_rs::domain::{
    AlertRecord, ConsumptionResponse, DeviceTwin, TimeseriesPoint, TwinLocation, TwinThresholds,
};
use api_rs::repository::{
    MockAlertRepository, MockHealthRepository, MockTimeseriesRepository, MockTwinRepository,
};
use api_rs::service::{
    AlertService, HealthService, MeterService, MAX_PAGINATION_LIMIT,
};

fn sample_twin(id: &str, zone: &str) -> DeviceTwin {
    DeviceTwin {
        meter_id: id.to_string(),
        firmware_version: "v2.4.1".to_string(),
        zone: zone.to_string(),
        phase_type: "3P+N".to_string(),
        nominal_voltage: 230.0,
        nominal_frequency: 50.0,
        thresholds: TwinThresholds {
            voltage_min: 207.0,
            voltage_max: 253.0,
            active_power_kw_max: 25.0,
            power_factor_min: 0.85,
        },
        location: TwinLocation {
            lat: 37.9838,
            lon: 23.7275,
        },
        installed_at: Some("2026-01-01T00:00:00Z".parse::<DateTime<Utc>>().unwrap()),
        status: "ACTIVE".to_string(),
    }
}

fn sample_alert(id: i64, meter_id: &str, severity: &str, time: DateTime<Utc>) -> AlertRecord {
    AlertRecord {
        id,
        time,
        meter_id: meter_id.to_string(),
        alert_type: "VOLTAGE_SAG".to_string(),
        severity: severity.to_string(),
        value: 198.5,
        threshold: 207.0,
        message: Some("Phase L1 voltage dipped below 207V".to_string()),
        created_at: Some(time),
    }
}

struct TestFixture {
    pub timeseries_repo: MockTimeseriesRepository,
    pub twin_repo: MockTwinRepository,
    pub alert_repo: MockAlertRepository,
    pub health_repo: Arc<MockHealthRepository>,
}

impl TestFixture {
    fn new() -> Self {
        Self {
            timeseries_repo: MockTimeseriesRepository::new(),
            twin_repo: MockTwinRepository::new(),
            alert_repo: MockAlertRepository::new(),
            health_repo: Arc::new(MockHealthRepository::new(true, true)),
        }
    }

    fn into_services(
        self,
    ) -> (
        Arc<MeterService>,
        Arc<AlertService>,
        Arc<HealthService>,
        Arc<MockHealthRepository>,
    ) {
        let twin_repo = Arc::new(self.twin_repo);
        let timeseries_repo = Arc::new(self.timeseries_repo);
        let alert_repo = Arc::new(self.alert_repo);
        let health_repo = self.health_repo.clone();

        let meter_service = Arc::new(MeterService::new(twin_repo, timeseries_repo));
        let alert_service = Arc::new(AlertService::new(alert_repo));
        let health_service = Arc::new(HealthService::new(health_repo.clone()));

        (meter_service, alert_service, health_service, health_repo)
    }
}

#[actix_web::test]
async fn test_healthz_liveness() {
    let fixture = TestFixture::new();
    let (m_svc, a_svc, h_svc, _) = fixture.into_services();
    let app = test::init_service(build_app(m_svc, a_svc, h_svc)).await;

    let req = TestRequest::get().uri("/healthz").to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);

    let body: Value = test::read_body_json(resp).await;
    assert_eq!(body["status"], "ok");
}

#[actix_web::test]
async fn test_readyz_healthy_and_unhealthy() {
    let fixture = TestFixture::new();
    let (m_svc, a_svc, h_svc, health_repo) = fixture.into_services();
    let app = test::init_service(build_app(m_svc, a_svc, h_svc)).await;

    // 1. Both healthy -> 200 OK
    let req = TestRequest::get().uri("/readyz").to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);
    let body: Value = test::read_body_json(resp).await;
    assert_eq!(body["status"], "ready");
    assert_eq!(body["postgres"], "ok");
    assert_eq!(body["mongodb"], "ok");

    // 2. TimescaleDB down -> 503 Service Unavailable with structured JSON error
    health_repo.set_timescale_healthy(false);
    let req = TestRequest::get().uri("/readyz").to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 503);
    let body: Value = test::read_body_json(resp).await;
    assert_eq!(body["error"], "SERVICE_UNAVAILABLE");

    // 3. Mongo down -> 503 Service Unavailable
    health_repo.set_timescale_healthy(true);
    health_repo.set_mongo_healthy(false);
    let req = TestRequest::get().uri("/readyz").to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 503);
    let body: Value = test::read_body_json(resp).await;
    assert_eq!(body["error"], "SERVICE_UNAVAILABLE");
}

#[actix_web::test]
async fn test_prometheus_metrics() {
    let fixture = TestFixture::new();
    let (m_svc, a_svc, h_svc, _) = fixture.into_services();
    let app = test::init_service(build_app(m_svc, a_svc, h_svc)).await;

    // Trigger an endpoint to verify counter increments
    let req = TestRequest::get().uri("/healthz").to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);

    let req = TestRequest::get().uri("/metrics").to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);

    let body = test::read_body(resp).await;
    let body_str = String::from_utf8(body.to_vec()).unwrap();
    assert!(body_str.contains("http_requests_total"));
    assert!(body_str.contains("http_request_duration_seconds"));
}

#[actix_web::test]
async fn test_meters_list_and_filter() {
    let mut fixture = TestFixture::new();
    fixture.twin_repo = fixture.twin_repo.with_twins(vec![
        sample_twin("MZ-3P-0001", "north"),
        sample_twin("MZ-3P-0002", "south"),
        sample_twin("MZ-3P-0003", "north"),
    ]);

    let (m_svc, a_svc, h_svc, _) = fixture.into_services();
    let app = test::init_service(build_app(m_svc, a_svc, h_svc)).await;

    // List all
    let req = TestRequest::get().uri("/api/v1/meters").to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);
    let twins: Vec<DeviceTwin> = test::read_body_json(resp).await;
    assert_eq!(twins.len(), 3);

    // Filter by zone
    let req = TestRequest::get()
        .uri("/api/v1/meters?zone=north")
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);
    let north_twins: Vec<DeviceTwin> = test::read_body_json(resp).await;
    assert_eq!(north_twins.len(), 2);
    assert!(north_twins.iter().all(|t| t.zone == "north"));

    // Limit parameter
    let req = TestRequest::get().uri("/api/v1/meters?limit=1").to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);
    let limited: Vec<DeviceTwin> = test::read_body_json(resp).await;
    assert_eq!(limited.len(), 1);
}

#[actix_web::test]
async fn test_meters_pagination_capping() {
    let twins = (1..=50)
        .map(|i| sample_twin(&format!("MZ-3P-{:04}", i), "north"))
        .collect();
    let mut fixture = TestFixture::new();
    fixture.twin_repo = fixture.twin_repo.with_twins(twins);

    let (m_svc, a_svc, h_svc, _) = fixture.into_services();
    let app = test::init_service(build_app(m_svc, a_svc, h_svc)).await;

    // Query with excessive limit (e.g. 5000) should be accepted and capped at MAX_PAGINATION_LIMIT
    let req = TestRequest::get().uri("/api/v1/meters?limit=5000").to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);
    let list: Vec<DeviceTwin> = test::read_body_json(resp).await;
    assert_eq!(list.len(), 50);
    assert!(list.len() <= MAX_PAGINATION_LIMIT);
}

#[actix_web::test]
async fn test_get_meter_by_id_and_not_found() {
    let mut fixture = TestFixture::new();
    fixture.twin_repo = fixture
        .twin_repo
        .with_twins(vec![sample_twin("MZ-3P-0042", "east")]);

    let (m_svc, a_svc, h_svc, _) = fixture.into_services();
    let app = test::init_service(build_app(m_svc, a_svc, h_svc)).await;

    // Valid existing meter
    let req = TestRequest::get()
        .uri("/api/v1/meters/MZ-3P-0042")
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);
    let twin: DeviceTwin = test::read_body_json(resp).await;
    assert_eq!(twin.meter_id, "MZ-3P-0042");
    assert_eq!(twin.zone, "east");

    // Nonexistent meter -> 404 Not Found
    let req = TestRequest::get()
        .uri("/api/v1/meters/MZ-3P-9999")
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 404);
    let body: Value = test::read_body_json(resp).await;
    assert_eq!(body["error"], "NOT_FOUND");

    // Invalid meter ID characters -> 400 Bad Request
    let req = TestRequest::get()
        .uri("/api/v1/meters/INVALID%20ID%20WITH%20SPACES")
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 400);
    let body: Value = test::read_body_json(resp).await;
    assert_eq!(body["error"], "BAD_REQUEST");
}

#[actix_web::test]
async fn test_timeseries_rollups_and_window_validation() {
    let base_time = "2026-11-10T12:00:00Z".parse::<DateTime<Utc>>().unwrap();
    let mut fixture = TestFixture::new();
    fixture.timeseries_repo = fixture.timeseries_repo.with_points(vec![
        TimeseriesPoint {
            bucket: base_time,
            avg_active_power_kw: Some(2.85),
            max_active_power_kw: Some(3.10),
            min_active_power_kw: Some(2.50),
            delta_energy_kwh: Some(2.85),
            avg_power_factor: Some(0.96),
            avg_voltage_l1: Some(230.2),
            reading_count: 60,
        },
        TimeseriesPoint {
            bucket: base_time + Duration::hours(1),
            avg_active_power_kw: Some(3.15),
            max_active_power_kw: Some(3.40),
            min_active_power_kw: Some(2.90),
            delta_energy_kwh: Some(3.15),
            avg_power_factor: Some(0.95),
            avg_voltage_l1: Some(231.0),
            reading_count: 60,
        },
    ]);

    let (m_svc, a_svc, h_svc, _) = fixture.into_services();
    let app = test::init_service(build_app(m_svc, a_svc, h_svc)).await;

    // 1. Valid timeseries query
    let uri = format!(
        "/api/v1/meters/MZ-3P-0042/timeseries?from={}&to={}&bucket=1h",
        base_time.to_rfc3339(),
        (base_time + Duration::hours(2)).to_rfc3339()
    );
    let req = TestRequest::get().uri(&uri).to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);
    let points: Vec<TimeseriesPoint> = test::read_body_json(resp).await;
    assert_eq!(points.len(), 2);

    // 2. Range exceeds max window (30 days) -> 400 Bad Request
    let large_window_uri = format!(
        "/api/v1/meters/MZ-3P-0042/timeseries?from={}&to={}&bucket=1h",
        base_time.to_rfc3339(),
        (base_time + Duration::days(35)).to_rfc3339()
    );
    let req = TestRequest::get().uri(&large_window_uri).to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 400);
    let body: Value = test::read_body_json(resp).await;
    assert_eq!(body["error"], "BAD_REQUEST");
    assert!(body["message"]
        .as_str()
        .unwrap()
        .contains("exceeds the maximum allowed limit of 30 days"));

    // 3. 'to' before 'from' -> 400 Bad Request
    let inverted_uri = format!(
        "/api/v1/meters/MZ-3P-0042/timeseries?from={}&to={}&bucket=1h",
        (base_time + Duration::hours(5)).to_rfc3339(),
        base_time.to_rfc3339()
    );
    let req = TestRequest::get().uri(&inverted_uri).to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 400);

    // 4. Invalid bucket -> 400 Bad Request
    let invalid_bucket_uri = format!(
        "/api/v1/meters/MZ-3P-0042/timeseries?from={}&to={}&bucket=invalid_bucket",
        base_time.to_rfc3339(),
        (base_time + Duration::hours(1)).to_rfc3339()
    );
    let req = TestRequest::get().uri(&invalid_bucket_uri).to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 400);
}

#[actix_web::test]
async fn test_consumption_query_and_validation() {
    let from = "2026-11-01T00:00:00Z".parse::<DateTime<Utc>>().unwrap();
    let to = "2026-11-05T00:00:00Z".parse::<DateTime<Utc>>().unwrap();

    let mut fixture = TestFixture::new();
    fixture.timeseries_repo = fixture.timeseries_repo.with_consumption(ConsumptionResponse {
        meter_id: "MZ-3P-0042".to_string(),
        from: Some(from),
        to: Some(to),
        total_consumption_kwh: 48.6,
        reading_count: 5760,
    });

    let (m_svc, a_svc, h_svc, _) = fixture.into_services();
    let app = test::init_service(build_app(m_svc, a_svc, h_svc)).await;

    // Valid consumption query with from and to
    let uri = format!(
        "/api/v1/meters/MZ-3P-0042/consumption?from={}&to={}",
        from.to_rfc3339(),
        to.to_rfc3339()
    );
    let req = TestRequest::get().uri(&uri).to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);

    let res: ConsumptionResponse = test::read_body_json(resp).await;
    assert_eq!(res.meter_id, "MZ-3P-0042");
    assert_eq!(res.total_consumption_kwh, 48.6);
    assert_eq!(res.reading_count, 5760);

    // Window > 30 days -> 400 Bad Request
    let large_window_uri = format!(
        "/api/v1/meters/MZ-3P-0042/consumption?from={}&to={}",
        from.to_rfc3339(),
        (from + Duration::days(40)).to_rfc3339()
    );
    let req = TestRequest::get().uri(&large_window_uri).to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 400);
}

#[actix_web::test]
async fn test_alerts_listing_and_filtering() {
    let t1 = "2026-11-12T10:00:00Z".parse::<DateTime<Utc>>().unwrap();
    let t2 = "2026-11-12T11:00:00Z".parse::<DateTime<Utc>>().unwrap();
    let t3 = "2026-11-12T12:00:00Z".parse::<DateTime<Utc>>().unwrap();

    let mut fixture = TestFixture::new();
    fixture.alert_repo = fixture.alert_repo.with_alerts(vec![
        sample_alert(1, "MZ-3P-0001", "CRITICAL", t1),
        sample_alert(2, "MZ-3P-0002", "WARNING", t2),
        sample_alert(3, "MZ-3P-0003", "CRITICAL", t3),
    ]);

    let (m_svc, a_svc, h_svc, _) = fixture.into_services();
    let app = test::init_service(build_app(m_svc, a_svc, h_svc)).await;

    // 1. List all alerts
    let req = TestRequest::get().uri("/api/v1/alerts").to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);
    let alerts: Vec<AlertRecord> = test::read_body_json(resp).await;
    assert_eq!(alerts.len(), 3);

    // 2. Filter by severity=CRITICAL
    let req = TestRequest::get()
        .uri("/api/v1/alerts?severity=CRITICAL")
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);
    let crit_alerts: Vec<AlertRecord> = test::read_body_json(resp).await;
    assert_eq!(crit_alerts.len(), 2);
    assert!(crit_alerts.iter().all(|a| a.severity == "CRITICAL"));

    // 3. Filter by since timestamp
    let uri = format!("/api/v1/alerts?since={}", t2.to_rfc3339());
    let req = TestRequest::get().uri(&uri).to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 200);
    let since_alerts: Vec<AlertRecord> = test::read_body_json(resp).await;
    assert_eq!(since_alerts.len(), 2);

    // 4. Invalid severity -> 400 Bad Request
    let req = TestRequest::get()
        .uri("/api/v1/alerts?severity=UNKNOWN_SEVERITY")
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), 400);
    let body: Value = test::read_body_json(resp).await;
    assert_eq!(body["error"], "BAD_REQUEST");
}
