"""Tests for historical NP stats domain functions."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from trainingdash.domain.historical_np import (
    HistoricalNpStats,
    find_route_for_course,
    get_historical_np_stats,
    get_course_historical_np,
    HAUSDORFF_THRESHOLD_M,
)


class TestFindRouteForCourse:
    """Tests for find_route_for_course function."""

    @pytest.mark.asyncio
    async def test_returns_route_id_when_match_within_threshold(self):
        """Should return route ID when Hausdorff distance is within threshold."""
        db = AsyncMock()
        # Mock result: route_id=42, distance within threshold
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock(id=42, distance=0.001)  # ~111m at equator
        db.execute.return_value = mock_result

        result = await find_route_for_course(db, user_id=1, course_id=10)

        assert result == 42
        db.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_routes_exist(self):
        """Should return None when no routes exist for user."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        db.execute.return_value = mock_result

        result = await find_route_for_course(db, user_id=1, course_id=10)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_distance_exceeds_threshold(self):
        """Should return None when closest route is beyond threshold."""
        db = AsyncMock()
        # Mock result: distance well beyond threshold (~10km)
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock(id=42, distance=0.1)  # ~11km
        db.execute.return_value = mock_result

        result = await find_route_for_course(db, user_id=1, course_id=10)

        assert result is None


class TestGetHistoricalNpStats:
    """Tests for get_historical_np_stats function."""

    @pytest.mark.asyncio
    async def test_returns_stats_when_activities_exist(self):
        """Should return NP stats when activities with power exist on route."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock(
            ride_count=5,
            avg_np_w=245.0,
            min_np_w=220.0,
            max_np_w=280.0,
            avg_power_w=210.0,
        )
        db.execute.return_value = mock_result

        result = await get_historical_np_stats(db, user_id=1, route_id=42)

        assert result is not None
        assert result.ride_count == 5
        assert result.avg_np_w == 245.0
        assert result.min_np_w == 220.0
        assert result.max_np_w == 280.0
        assert result.avg_power_w == 210.0

    @pytest.mark.asyncio
    async def test_returns_none_when_no_activities_with_np(self):
        """Should return None when no activities have NP data."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = MagicMock(ride_count=0)
        db.execute.return_value = mock_result

        result = await get_historical_np_stats(db, user_id=1, route_id=42)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_query_returns_none(self):
        """Should return None when query returns no row."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        db.execute.return_value = mock_result

        result = await get_historical_np_stats(db, user_id=1, route_id=42)

        assert result is None


class TestGetCourseHistoricalNp:
    """Tests for get_course_historical_np convenience function."""

    @pytest.mark.asyncio
    async def test_returns_stats_when_route_matches(self):
        """Should return stats when course matches a route with rides."""
        db = AsyncMock()

        # First call: find_route_for_course returns route_id
        # Second call: get_historical_np_stats returns stats
        call_count = 0

        def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                # Route match query
                mock_result.first.return_value = MagicMock(id=42, distance=0.001)
            else:
                # Stats query
                mock_result.first.return_value = MagicMock(
                    ride_count=3,
                    avg_np_w=230.0,
                    min_np_w=215.0,
                    max_np_w=250.0,
                    avg_power_w=195.0,
                )
            return mock_result

        db.execute.side_effect = mock_execute

        result = await get_course_historical_np(db, user_id=1, course_id=10)

        assert result is not None
        assert result.ride_count == 3
        assert result.avg_np_w == 230.0

    @pytest.mark.asyncio
    async def test_returns_none_when_no_route_matches(self):
        """Should return None when no route matches the course."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        db.execute.return_value = mock_result

        result = await get_course_historical_np(db, user_id=1, course_id=10)

        assert result is None


class TestHistoricalNpStatsDataclass:
    """Tests for HistoricalNpStats dataclass."""

    def test_dataclass_fields(self):
        """Should have all expected fields."""
        stats = HistoricalNpStats(
            ride_count=5,
            avg_np_w=245.0,
            min_np_w=220.0,
            max_np_w=280.0,
            avg_power_w=210.0,
        )

        assert stats.ride_count == 5
        assert stats.avg_np_w == 245.0
        assert stats.min_np_w == 220.0
        assert stats.max_np_w == 280.0
        assert stats.avg_power_w == 210.0
