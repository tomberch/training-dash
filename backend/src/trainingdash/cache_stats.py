"""
Thread-safe in-memory cache statistics counters.

This module tracks cache hits and misses for tiles (OSM, Carto) and geocoding.
Counters are flushed hourly to the database by a SAQ cron job.

Usage:
    from trainingdash.cache_stats import record_hit, record_miss

    # In tile proxy
    if cache_hit:
        record_hit("tiles_osm")
    else:
        record_miss("tiles_osm")

    # In geocoding service
    if cached_result:
        record_hit("geocoding")
    else:
        record_miss("geocoding")
"""

from dataclasses import dataclass, field
from threading import Lock
from typing import Literal

# Valid cache types
CacheType = Literal["tiles_osm", "tiles_carto", "geocoding"]


@dataclass
class CacheCounters:
    """Container for hit/miss counters per cache type."""

    hits: dict[str, int] = field(default_factory=dict)
    misses: dict[str, int] = field(default_factory=dict)

    def copy(self) -> "CacheCounters":
        """Create a deep copy of the counters."""
        return CacheCounters(
            hits=dict(self.hits),
            misses=dict(self.misses),
        )


class CacheStatsCollector:
    """
    Thread-safe collector for cache hit/miss statistics.

    This is a singleton-style class - use the module-level functions
    (record_hit, record_miss, etc.) rather than instantiating directly.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters = CacheCounters()

    def record_hit(self, cache_type: str) -> None:
        """Increment the hit counter for the given cache type."""
        with self._lock:
            self._counters.hits[cache_type] = self._counters.hits.get(cache_type, 0) + 1

    def record_miss(self, cache_type: str) -> None:
        """Increment the miss counter for the given cache type."""
        with self._lock:
            self._counters.misses[cache_type] = self._counters.misses.get(cache_type, 0) + 1

    def get_current(self) -> CacheCounters:
        """
        Return current counters without resetting.

        Use this for dashboard display (real-time stats).
        """
        with self._lock:
            return self._counters.copy()

    def get_and_reset(self) -> CacheCounters:
        """
        Return current counters and reset to zero.

        Use this for the hourly flush job.
        """
        with self._lock:
            result = self._counters.copy()
            self._counters = CacheCounters()
            return result

    def reset(self) -> None:
        """Reset all counters to zero (for testing)."""
        with self._lock:
            self._counters = CacheCounters()


# Global singleton instance
_collector = CacheStatsCollector()


# Module-level convenience functions
def record_hit(cache_type: CacheType) -> None:
    """Record a cache hit for the given cache type."""
    _collector.record_hit(cache_type)


def record_miss(cache_type: CacheType) -> None:
    """Record a cache miss for the given cache type."""
    _collector.record_miss(cache_type)


def get_current() -> CacheCounters:
    """Get current counters without resetting (for dashboard)."""
    return _collector.get_current()


def get_and_reset() -> CacheCounters:
    """Get current counters and reset (for flush job)."""
    return _collector.get_and_reset()


def reset() -> None:
    """Reset all counters (for testing)."""
    _collector.reset()
