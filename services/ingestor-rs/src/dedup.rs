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
