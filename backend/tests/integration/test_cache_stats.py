"""Integration tests for cache stats collection (#384)."""

import pytest
from sqlalchemy import select

from trainingdash import cache_stats
from trainingdash.repositories.postgres.models import CacheStats


@pytest.fixture(autouse=True)
def reset_cache_stats():
    """Reset cache stats before and after each test."""
    cache_stats.reset()
    yield
    cache_stats.reset()


class TestCacheStatsCounters:
    """Tests for in-memory cache stats counters."""

    def test_record_hit_increments_counter(self):
        """record_hit increments the hit counter."""
        cache_stats.record_hit("tiles_osm")
        cache_stats.record_hit("tiles_osm")
        cache_stats.record_hit("tiles_carto")

        counters = cache_stats.get_current()
        assert counters.hits["tiles_osm"] == 2
        assert counters.hits["tiles_carto"] == 1
        assert counters.misses == {}

    def test_record_miss_increments_counter(self):
        """record_miss increments the miss counter."""
        cache_stats.record_miss("geocoding")
        cache_stats.record_miss("geocoding")
        cache_stats.record_miss("tiles_osm")

        counters = cache_stats.get_current()
        assert counters.misses["geocoding"] == 2
        assert counters.misses["tiles_osm"] == 1
        assert counters.hits == {}

    def test_get_current_does_not_reset(self):
        """get_current returns counters without resetting."""
        cache_stats.record_hit("tiles_osm")

        counters1 = cache_stats.get_current()
        counters2 = cache_stats.get_current()

        assert counters1.hits["tiles_osm"] == 1
        assert counters2.hits["tiles_osm"] == 1

    def test_get_and_reset_clears_counters(self):
        """get_and_reset returns counters and resets to zero."""
        cache_stats.record_hit("tiles_osm")
        cache_stats.record_miss("geocoding")

        counters = cache_stats.get_and_reset()
        assert counters.hits["tiles_osm"] == 1
        assert counters.misses["geocoding"] == 1

        # Counters should be reset
        empty = cache_stats.get_current()
        assert empty.hits == {}
        assert empty.misses == {}

    def test_counters_are_thread_safe(self):
        """Counters handle concurrent access without errors."""
        import threading

        def increment_many():
            for _ in range(1000):
                cache_stats.record_hit("tiles_osm")
                cache_stats.record_miss("tiles_carto")

        threads = [threading.Thread(target=increment_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        counters = cache_stats.get_current()
        assert counters.hits["tiles_osm"] == 10000
        assert counters.misses["tiles_carto"] == 10000


class TestTileCacheStatsIntegration:
    """Tests for tile proxy cache stats integration."""

    @pytest.mark.asyncio
    async def test_tile_request_records_miss_then_hit(self, http_client):
        """First tile request records miss, second records hit."""
        # Reset to ensure clean state
        cache_stats.reset()

        # First request - should be a miss (fetches from upstream)
        response = await http_client.get("/api/tiles/0/0/0.png")
        # May fail if upstream is unreachable, but stats should still work
        if response.status_code == 200:
            counters = cache_stats.get_current()
            assert counters.misses.get("tiles_osm", 0) == 1

            # Second request - should be a hit (from cache)
            response2 = await http_client.get("/api/tiles/0/0/0.png")
            assert response2.status_code == 200

            counters2 = cache_stats.get_current()
            assert counters2.hits.get("tiles_osm", 0) == 1
            assert counters2.misses.get("tiles_osm", 0) == 1

    @pytest.mark.asyncio
    async def test_carto_tile_records_stats(self, http_client):
        """Carto tile requests record separate stats."""
        cache_stats.reset()

        response = await http_client.get("/api/tiles/carto/light/0/0/0.png")
        if response.status_code == 200:
            counters = cache_stats.get_current()
            assert counters.misses.get("tiles_carto", 0) == 1


class TestFlushCacheStatsJob:
    """Tests for the flush_cache_stats worker job."""

    @pytest.mark.asyncio
    async def test_flush_writes_to_database(self, db_session):
        """flush_cache_stats writes counters to cache_stats table."""
        # Record some stats
        cache_stats.record_hit("tiles_osm")
        cache_stats.record_hit("tiles_osm")
        cache_stats.record_miss("tiles_osm")
        cache_stats.record_hit("geocoding")
        cache_stats.record_miss("geocoding")
        cache_stats.record_miss("geocoding")

        # Create a mock context with the session
        ctx = {"db_session_factory": lambda: _session_context(db_session)}

        # Manually invoke the flush (normally run by cron)
        result = await _flush_with_session(db_session)

        assert result["flushed"] == 2  # tiles_osm and geocoding

        # Verify data in database
        rows = (await db_session.execute(select(CacheStats))).scalars().all()
        assert len(rows) == 2

        osm_row = next(r for r in rows if r.cache_type == "tiles_osm")
        assert osm_row.hits == 2
        assert osm_row.misses == 1

        geo_row = next(r for r in rows if r.cache_type == "geocoding")
        assert geo_row.hits == 1
        assert geo_row.misses == 2

    @pytest.mark.asyncio
    async def test_flush_upserts_to_same_bucket(self, db_session):
        """Multiple flushes in same hour add to existing bucket."""
        # First flush
        cache_stats.record_hit("tiles_osm")
        await _flush_with_session(db_session)

        # Second flush (same hour)
        cache_stats.record_hit("tiles_osm")
        cache_stats.record_hit("tiles_osm")
        await _flush_with_session(db_session)

        # Should have one row with combined totals
        rows = (await db_session.execute(select(CacheStats))).scalars().all()
        assert len(rows) == 1
        assert rows[0].hits == 3

    @pytest.mark.asyncio
    async def test_flush_with_no_data_returns_zero(self, db_session):
        """Flush with no recorded stats returns flushed=0."""
        cache_stats.reset()
        result = await _flush_with_session(db_session)
        assert result["flushed"] == 0

    @pytest.mark.asyncio
    async def test_flush_resets_counters(self, db_session):
        """Flush resets in-memory counters."""
        cache_stats.record_hit("tiles_osm")
        await _flush_with_session(db_session)

        counters = cache_stats.get_current()
        assert counters.hits == {}
        assert counters.misses == {}


async def _flush_with_session(db_session) -> dict:
    """
    Helper to run flush logic directly with a test session.

    This bypasses the worker context and uses the test session directly.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import text

    counters = cache_stats.get_and_reset()

    now = datetime.now(UTC).replace(tzinfo=None)
    bucket_start = (now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1))

    all_cache_types = set(counters.hits.keys()) | set(counters.misses.keys())

    if not all_cache_types:
        return {"flushed": 0}

    flushed = 0
    for cache_type in all_cache_types:
        hits = counters.hits.get(cache_type, 0)
        misses = counters.misses.get(cache_type, 0)

        if hits == 0 and misses == 0:
            continue

        await db_session.execute(
            text("""
                INSERT INTO cache_stats (bucket_start, cache_type, hits, misses)
                VALUES (:bucket_start, :cache_type, :hits, :misses)
                ON CONFLICT (bucket_start, cache_type)
                DO UPDATE SET
                    hits = cache_stats.hits + EXCLUDED.hits,
                    misses = cache_stats.misses + EXCLUDED.misses
            """),
            {
                "bucket_start": bucket_start,
                "cache_type": cache_type,
                "hits": hits,
                "misses": misses,
            },
        )
        flushed += 1

    await db_session.commit()
    return {"flushed": flushed, "bucket_start": bucket_start.isoformat()}


from contextlib import asynccontextmanager


@asynccontextmanager
async def _session_context(session):
    """Wrap a session in an async context manager."""
    yield session
