use chrono::{DateTime, Utc};
use lru::LruCache;
use std::num::NonZeroUsize;
use std::sync::{Arc, Mutex};

/// Default capacity for the in-memory LRU deduplication cache.
pub const DEFAULT_CACHE_CAPACITY: usize = 50_000;

/// Type alias for the dedup cache key: (meter_id, timestamp).
pub type DedupKey = (String, DateTime<Utc>);
type SharedLruCache = Arc<Mutex<LruCache<DedupKey, ()>>>;

/// Thread-safe in-memory LRU cache for deduplicating incoming telemetry packets.
///
/// Keys are tuples of `(meter_id, timestamp)`. If a packet arrives with the exact same
/// meter identifier and measurement timestamp, it is flagged as a duplicate.
#[derive(Clone, Debug)]
pub struct Deduplicator {
    cache: SharedLruCache,
    capacity: usize,
}

impl Deduplicator {
    /// Creates a new `Deduplicator` with the specified LRU capacity.
    /// If `capacity == 0`, the default capacity (50,000) is used.
    pub fn new(capacity: usize) -> Self {
        let cap = NonZeroUsize::new(capacity)
            .unwrap_or_else(|| NonZeroUsize::new(DEFAULT_CACHE_CAPACITY).unwrap());
        Self {
            cache: Arc::new(Mutex::new(LruCache::new(cap))),
            capacity: cap.get(),
        }
    }

    /// Checks if a `(meter_id, timestamp)` pair is a duplicate.
    ///
    /// If it has already been recorded, returns `true` (duplicate detected).
    /// If not present, records the key and returns `false` (first observation).
    pub fn is_duplicate_or_record(&self, meter_id: &str, timestamp: &DateTime<Utc>) -> bool {
        let mut cache = match self.cache.lock() {
            Ok(guard) => guard,
            Err(poisoned) => poisoned.into_inner(),
        };

        let key = (meter_id.to_string(), *timestamp);
        if cache.get(&key).is_some() {
            true
        } else {
            cache.put(key, ());
            false
        }
    }

    /// Returns the current number of cached entries.
    pub fn len(&self) -> usize {
        let cache = match self.cache.lock() {
            Ok(guard) => guard,
            Err(poisoned) => poisoned.into_inner(),
        };
        cache.len()
    }

    /// Returns true if the cache contains no entries.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Returns the maximum capacity of the cache.
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Clears all entries from the cache.
    pub fn clear(&self) {
        let mut cache = match self.cache.lock() {
            Ok(guard) => guard,
            Err(poisoned) => poisoned.into_inner(),
        };
        cache.clear();
    }
}

impl Default for Deduplicator {
    fn default() -> Self {
        Self::new(DEFAULT_CACHE_CAPACITY)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;
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
        // Capacity of 2 items
        let dedup = Deduplicator::new(2);
        let t1 = Utc.with_ymd_and_hms(2026, 11, 12, 12, 0, 0).unwrap();
        let t2 = Utc.with_ymd_and_hms(2026, 11, 12, 12, 0, 1).unwrap();
        let t3 = Utc.with_ymd_and_hms(2026, 11, 12, 12, 0, 2).unwrap();

        assert!(!dedup.is_duplicate_or_record("MZ-3P-0001", &t1));
        assert!(!dedup.is_duplicate_or_record("MZ-3P-0002", &t2));
        assert_eq!(dedup.len(), 2);

        // Inserting 3rd element evicts the oldest (MZ-3P-0001, t1)
        assert!(!dedup.is_duplicate_or_record("MZ-3P-0003", &t3));
        assert_eq!(dedup.len(), 2);

        // Now (MZ-3P-0001, t1) is evicted, so if it arrives again, it is seen as new
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
}
