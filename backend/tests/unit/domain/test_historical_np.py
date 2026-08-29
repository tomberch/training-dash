"""Tests for historical NP stats domain types and repository."""

import pytest

from tests.fakes.historical_np_repo import FakeHistoricalNpRepo
from trainingdash.domain.historical_np import HistoricalNpStats


class TestHistoricalNpStatsDataclass:
    """Tests for HistoricalNpStats dataclass."""

    def test_dataclass_fields(self):
        """Should have all expected fields."""
        stats = HistoricalNpStats(
            ride_count=5,
            avg_np_w=245.0,
            min_np_w=220.0,
            best_np_w=280.0,
            avg_power_w=210.0,
        )

        assert stats.ride_count == 5
        assert stats.avg_np_w == 245.0
        assert stats.min_np_w == 220.0
        assert stats.best_np_w == 280.0
        assert stats.avg_power_w == 210.0

    def test_dataclass_equality(self):
        """Two stats with same values should be equal."""
        stats1 = HistoricalNpStats(
            ride_count=3,
            avg_np_w=230.0,
            min_np_w=200.0,
            best_np_w=250.0,
            avg_power_w=190.0,
        )
        stats2 = HistoricalNpStats(
            ride_count=3,
            avg_np_w=230.0,
            min_np_w=200.0,
            best_np_w=250.0,
            avg_power_w=190.0,
        )
        assert stats1 == stats2


class TestFakeHistoricalNpRepo:
    """Tests for FakeHistoricalNpRepo (validates test infrastructure)."""

    @pytest.mark.asyncio
    async def test_find_route_for_course_returns_configured_route(self):
        """Should return preconfigured route ID."""
        repo = FakeHistoricalNpRepo()
        repo.set_course_route(user_id=1, course_id=10, route_id=42)

        result = await repo.find_route_for_course(user_id=1, course_id=10)

        assert result == 42

    @pytest.mark.asyncio
    async def test_find_route_for_course_returns_none_when_not_configured(self):
        """Should return None when no route is configured."""
        repo = FakeHistoricalNpRepo()

        result = await repo.find_route_for_course(user_id=1, course_id=10)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_stats_for_route_returns_configured_stats(self):
        """Should return preconfigured stats."""
        repo = FakeHistoricalNpRepo()
        stats = HistoricalNpStats(
            ride_count=5,
            avg_np_w=245.0,
            min_np_w=220.0,
            best_np_w=280.0,
            avg_power_w=210.0,
        )
        repo.set_route_stats(user_id=1, route_id=42, stats=stats)

        result = await repo.get_stats_for_route(user_id=1, route_id=42)

        assert result is not None
        assert result.ride_count == 5
        assert result.avg_np_w == 245.0

    @pytest.mark.asyncio
    async def test_get_stats_for_route_returns_none_when_not_configured(self):
        """Should return None when no stats are configured."""
        repo = FakeHistoricalNpRepo()

        result = await repo.get_stats_for_route(user_id=1, route_id=42)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_for_course_combines_route_and_stats_lookup(self):
        """Should return stats when course matches a route with stats."""
        repo = FakeHistoricalNpRepo()
        repo.set_course_route(user_id=1, course_id=10, route_id=42)
        stats = HistoricalNpStats(
            ride_count=3,
            avg_np_w=230.0,
            min_np_w=215.0,
            best_np_w=250.0,
            avg_power_w=195.0,
        )
        repo.set_route_stats(user_id=1, route_id=42, stats=stats)

        result = await repo.get_for_course(user_id=1, course_id=10)

        assert result is not None
        assert result.ride_count == 3
        assert result.avg_np_w == 230.0

    @pytest.mark.asyncio
    async def test_get_for_course_returns_none_when_no_route_matches(self):
        """Should return None when course doesn't match any route."""
        repo = FakeHistoricalNpRepo()

        result = await repo.get_for_course(user_id=1, course_id=10)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_for_course_returns_none_when_route_has_no_stats(self):
        """Should return None when matched route has no stats."""
        repo = FakeHistoricalNpRepo()
        repo.set_course_route(user_id=1, course_id=10, route_id=42)
        # No stats configured for route 42

        result = await repo.get_for_course(user_id=1, course_id=10)

        assert result is None

    @pytest.mark.asyncio
    async def test_clear_removes_all_data(self):
        """Should clear all configured routes and stats."""
        repo = FakeHistoricalNpRepo()
        repo.set_course_route(user_id=1, course_id=10, route_id=42)
        stats = HistoricalNpStats(
            ride_count=3,
            avg_np_w=230.0,
            min_np_w=215.0,
            best_np_w=250.0,
            avg_power_w=195.0,
        )
        repo.set_route_stats(user_id=1, route_id=42, stats=stats)

        repo.clear()

        assert await repo.find_route_for_course(user_id=1, course_id=10) is None
        assert await repo.get_stats_for_route(user_id=1, route_id=42) is None
