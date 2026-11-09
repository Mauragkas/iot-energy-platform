use chrono::{DateTime, TimeZone, Utc};
use ingestor_rs::dedup::Deduplicator;
use std::thread;

#[test]
fn test_dedup_detects_duplicates() {
    let dedup = Deduplicator::new(100);
    let time1 = Utc.with_ymd_and_hms(2026, 11, 12, 12, 0, 0).unwrap();
    let time2 = Utc.with_ymd_and_hms(2026, 11, 12, 12, 0, 1).unwrap();

    // First packet: not duplicate
    assert!(!dedup.is_duplicate_or_record("MZ-3P-0001", &time1));
    assert_eq!(dedup.len(), 1);

    // Same packet repeated: duplicate!
    assert!(dedup.is_duplicate_or_record("MZ-3P-0001", &time1));
    assert_eq!(dedup.len(), 1);

    // Different meter at same timestamp: not duplicate
    assert!(!dedup.is_duplicate_or_record("MZ-3P-0002", &time1));
    assert_eq!(dedup.len(), 2);

    // Same meter at different timestamp: not duplicate
    assert!(!dedup.is_duplicate_or_record("MZ-3P-0001", &time2));
    assert_eq!(dedup.len(), 3);
}

#[test]
fn test_lru_eviction() {
    let dedup = Deduplicator::new(2);
    let t1 = Utc.with_ymd_and_hms(2026, 11, 12, 12, 0, 0).unwrap();
    let t2 = Utc.with_ymd_and_hms(2026, 11, 12, 12, 0, 1).unwrap();
    let t3 = Utc.with_ymd_and_hms(2026, 11, 12, 12, 0, 2).unwrap();

    assert!(!dedup.is_duplicate_or_record("MZ-3P-0001", &t1));
    assert!(!dedup.is_duplicate_or_record("MZ-3P-0002", &t2));
    assert_eq!(dedup.len(), 2);

    // Inserting 3rd element evicts oldest (MZ-3P-0001, t1)
    assert!(!dedup.is_duplicate_or_record("MZ-3P-0003", &t3));
    assert_eq!(dedup.len(), 2);

    // Now (MZ-3P-0001, t1) is evicted, seen as new
    assert!(!dedup.is_duplicate_or_record("MZ-3P-0001", &t1));
}

#[test]
fn test_thread_safety_concurrent_access() {
    let dedup = Deduplicator::new(10_000);
    let mut handles = Vec::new();

    for i in 0..10 {
        let dedup_clone = dedup.clone();
        let handle = thread::spawn(move || {
            for j in 0..100 {
                let timestamp = DateTime::from_timestamp(1762950000 + j, 0).unwrap();
                let meter_id = format!("MZ-3P-{:04}", i);
                let _ = dedup_clone.is_duplicate_or_record(&meter_id, &timestamp);
            }
        });
        handles.push(handle);
    }

    for h in handles {
        h.join().unwrap();
    }

    assert_eq!(dedup.len(), 1000);
}
