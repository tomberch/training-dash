"""Integration tests for prune_old_data job (#387)."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from trainingdash.domain.events import EventType
from trainingdash.repositories.postgres.models import CacheStats, Event


def _make_mock_worker_db_session(db_session):
    """Create a mock worker_db_session that yields the test session."""

    @asynccontextmanager
    async def mock_worker_db_session(ctx):
        yield db_session

    return mock_worker_db_session


class TestPruneOldData:
    """Tests for the prune_old_data worker job."""

    @pytest.mark.asyncio
    async def test_deletes_old_events(self, db_session):
        """Events older than 90 days are deleted."""
        now = datetime.now(UTC).replace(tzinfo=None)
        old_date = now - timedelta(days=91)
        recent_date = now - timedelta(days=30)

        # Create old and recent events
        old_event = Event(
            event_type="test.old",
            outcome="info",
            created_at=old_date,
            payload={},
        )
        recent_event = Event(
            event_type="test.recent",
            outcome="info",
            created_at=recent_date,
            payload={},
        )
        db_session.add_all([old_event, recent_event])
        await db_session.commit()

        # Run the actual prune_old_data job
        from trainingdash.worker import prune_old_data

        mock_session = _make_mock_worker_db_session(db_session)
        with patch("trainingdash.worker.worker_db_session", mock_session):
            result = await prune_old_data({})

        assert result["events_deleted"] == 1

        # Verify old event deleted, recent preserved
        events = (await db_session.execute(select(Event))).scalars().all()
        event_types = [e.event_type for e in events]

        assert "test.old" not in event_types
        assert "test.recent" in event_types

    @pytest.mark.asyncio
    async def test_deletes_old_cache_stats(self, db_session):
        """Cache stats older than 90 days are deleted."""
        now = datetime.now(UTC).replace(tzinfo=None)
        old_bucket = now - timedelta(days=91)
        recent_bucket = now - timedelta(days=30)

        # Create old and recent cache stats
        old_stats = CacheStats(
            bucket_start=old_bucket,
            cache_type="tiles_osm",
            hits=100,
            misses=20,
        )
        recent_stats = CacheStats(
            bucket_start=recent_bucket,
            cache_type="tiles_osm",
            hits=50,
            misses=10,
        )
        db_session.add_all([old_stats, recent_stats])
        await db_session.commit()

        # Run the actual prune_old_data job
        from trainingdash.worker import prune_old_data

        mock_session = _make_mock_worker_db_session(db_session)
        with patch("trainingdash.worker.worker_db_session", mock_session):
            result = await prune_old_data({})

        assert result["cache_stats_deleted"] == 1

        # Verify old stats deleted, recent preserved
        stats = (await db_session.execute(select(CacheStats))).scalars().all()
        # Filter out the cache.pruned event that gets created
        stats = [s for s in stats if s.cache_type == "tiles_osm"]

        assert len(stats) == 1
        assert stats[0].bucket_start == recent_bucket

    @pytest.mark.asyncio
    async def test_batch_deletion_for_large_datasets(self, db_session):
        """Events are deleted in batches (job handles many records)."""
        now = datetime.now(UTC).replace(tzinfo=None)
        old_date = now - timedelta(days=100)

        # Create multiple old events
        old_events = [
            Event(
                event_type=f"test.batch.{i}",
                outcome="info",
                created_at=old_date,
                payload={},
            )
            for i in range(50)
        ]
        db_session.add_all(old_events)
        await db_session.commit()

        # Run the actual prune_old_data job
        from trainingdash.worker import prune_old_data

        mock_session = _make_mock_worker_db_session(db_session)
        with patch("trainingdash.worker.worker_db_session", mock_session):
            result = await prune_old_data({})

        assert result["events_deleted"] == 50

        # Verify all old events deleted
        count = (
            await db_session.execute(
                select(func.count()).select_from(Event).where(Event.event_type.like("test.batch.%"))
            )
        ).scalar()
        assert count == 0

    @pytest.mark.asyncio
    async def test_preserves_recent_data(self, db_session):
        """Data within the 90-day window is preserved."""
        now = datetime.now(UTC).replace(tzinfo=None)

        # Create events at various ages within 90 days
        events = [
            Event(
                event_type="test.day1",
                outcome="info",
                created_at=now - timedelta(days=1),
                payload={},
            ),
            Event(
                event_type="test.day30",
                outcome="info",
                created_at=now - timedelta(days=30),
                payload={},
            ),
            Event(
                event_type="test.day89",
                outcome="info",
                created_at=now - timedelta(days=89),
                payload={},
            ),
        ]
        db_session.add_all(events)

        # Create cache stats at various ages within 90 days
        stats = [
            CacheStats(
                bucket_start=now - timedelta(days=1),
                cache_type="test_recent1",
                hits=1,
                misses=0,
            ),
            CacheStats(
                bucket_start=now - timedelta(days=45),
                cache_type="test_recent2",
                hits=2,
                misses=0,
            ),
            CacheStats(
                bucket_start=now - timedelta(days=89),
                cache_type="test_recent3",
                hits=3,
                misses=0,
            ),
        ]
        db_session.add_all(stats)
        await db_session.commit()

        # Run the actual prune_old_data job
        from trainingdash.worker import prune_old_data

        mock_session = _make_mock_worker_db_session(db_session)
        with patch("trainingdash.worker.worker_db_session", mock_session):
            result = await prune_old_data({})

        # Nothing old to delete
        assert result["events_deleted"] == 0
        assert result["cache_stats_deleted"] == 0

        # All data preserved (plus the cache.pruned event)
        event_count = (
            await db_session.execute(select(func.count()).select_from(Event).where(Event.event_type.like("test.day%")))
        ).scalar()
        stats_count = (
            await db_session.execute(
                select(func.count()).select_from(CacheStats).where(CacheStats.cache_type.like("test_recent%"))
            )
        ).scalar()

        assert event_count == 3
        assert stats_count == 3

    @pytest.mark.asyncio
    async def test_idempotent_multiple_runs(self, db_session):
        """Running the job multiple times is safe (idempotent)."""
        now = datetime.now(UTC).replace(tzinfo=None)
        old_date = now - timedelta(days=100)

        # Create old event
        old_event = Event(
            event_type="test.idempotent",
            outcome="info",
            created_at=old_date,
            payload={},
        )
        db_session.add(old_event)
        await db_session.commit()

        from trainingdash.worker import prune_old_data

        mock_session = _make_mock_worker_db_session(db_session)

        # First run - deletes the event
        with patch("trainingdash.worker.worker_db_session", mock_session):
            result1 = await prune_old_data({})
        assert result1["events_deleted"] == 1

        # Second run - nothing to delete (except it creates a cache.pruned event each time)
        with patch("trainingdash.worker.worker_db_session", mock_session):
            result2 = await prune_old_data({})
        assert result2["events_deleted"] == 0

        # Third run - still nothing
        with patch("trainingdash.worker.worker_db_session", mock_session):
            result3 = await prune_old_data({})
        assert result3["events_deleted"] == 0

    @pytest.mark.asyncio
    async def test_emits_pruned_event(self, db_session):
        """A cache.pruned event is emitted after pruning."""
        from trainingdash.repositories.postgres.event_repo import PostgresEventRepo

        now = datetime.now(UTC).replace(tzinfo=None)
        old_date = now - timedelta(days=100)

        # Create old data to delete
        old_event = Event(
            event_type="test.to_delete",
            outcome="info",
            created_at=old_date,
            payload={},
        )
        old_stats = CacheStats(
            bucket_start=old_date,
            cache_type="test_old",
            hits=10,
            misses=5,
        )
        db_session.add_all([old_event, old_stats])
        await db_session.commit()

        # Run the actual prune_old_data job
        from trainingdash.worker import prune_old_data

        mock_session = _make_mock_worker_db_session(db_session)
        with patch("trainingdash.worker.worker_db_session", mock_session):
            result = await prune_old_data({})

        assert result["events_deleted"] == 1
        assert result["cache_stats_deleted"] == 1

        # Verify the pruned event was created
        event_repo = PostgresEventRepo(db_session)
        events = await event_repo.list(event_type=EventType.CACHE_PRUNED.value)
        assert len(events) == 1
        assert events[0].payload["events_deleted"] == 1
        assert events[0].payload["cache_stats_deleted"] == 1
        assert "cutoff" in events[0].payload
