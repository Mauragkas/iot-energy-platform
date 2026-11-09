use actix_web::{http::StatusCode, test, App};
use ingestor_rs::metrics::{
    configure_routes, TELEMETRY_MESSAGES_DEDUPLICATED_TOTAL, TELEMETRY_MESSAGES_PUBLISHED_TOTAL,
    TELEMETRY_MESSAGES_RECEIVED_TOTAL, TELEMETRY_MESSAGES_REJECTED_TOTAL,
    TELEMETRY_PUBLISH_DURATION_SECONDS,
};

#[actix_web::test]
async fn test_healthz_endpoint() {
    let app = test::init_service(App::new().configure(configure_routes)).await;
    let req = test::TestRequest::get().uri("/healthz").to_request();
    let resp = test::call_service(&app, req).await;

    assert_eq!(resp.status(), StatusCode::OK);
    let body = test::read_body(resp).await;
    assert_eq!(body, "OK");
}

#[actix_web::test]
async fn test_metrics_endpoint_and_counters() {
    TELEMETRY_MESSAGES_RECEIVED_TOTAL.inc();
    TELEMETRY_MESSAGES_PUBLISHED_TOTAL.inc();
    TELEMETRY_MESSAGES_DEDUPLICATED_TOTAL.inc();
    TELEMETRY_MESSAGES_REJECTED_TOTAL.inc();
    let timer = TELEMETRY_PUBLISH_DURATION_SECONDS.start_timer();
    timer.observe_duration();

    let app = test::init_service(App::new().configure(configure_routes)).await;
    let req = test::TestRequest::get().uri("/metrics").to_request();
    let resp = test::call_service(&app, req).await;

    assert_eq!(resp.status(), StatusCode::OK);
    let body = test::read_body(resp).await;
    let body_str = std::str::from_utf8(&body).unwrap();

    assert!(body_str.contains("telemetry_messages_received_total"));
    assert!(body_str.contains("telemetry_messages_published_total"));
    assert!(body_str.contains("telemetry_messages_deduplicated_total"));
    assert!(body_str.contains("telemetry_messages_rejected_total"));
    assert!(body_str.contains("telemetry_publish_duration_seconds"));
}
