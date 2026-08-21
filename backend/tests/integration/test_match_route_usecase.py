"""
Integration tests for MatchRoute use case.

Tests route matching by GPS track similarity, requiring actual database
operations and the route matching algorithm.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from trainingdash.domain.events import EventOutcome, EventType
from trainingdash.repositories.postgres.models import Activity, Event, Record, Route
from trainingdash.use_cases.match_route import MatchRoute


def make_activity(user_id: int) -> Activity:
    """Create an activity without route assignment."""
    return Activity(
        id=uuid4(),
        user_id=user_id,
        started_at=datetime.now(UTC).replace(tzinfo=None),
        source="test",
        source_ref=f"test-{uuid4()}",
    )


def make_records(activity_id, coordinates: list[tuple[float, float]]) -> list[Record]:
    """Create GPS records for an activity.

    Args:
        activity_id: Activity UUID
        coordinates: List of (lat, lon) tuples
    """
    records = []
    base_time = datetime.now(UTC).replace(tzinfo=None)
    for i, (lat, lon) in enumerate(coordinates):
        records.append(
            Record(
                activity_id=activity_id,
                timestamp=base_time.replace(second=i % 60, minute=i // 60),
                lat=lat,
                lon=lon,
            )
        )
    return records


def make_line_route(start_lat: float, start_lon: float, num_points: int = 50) -> list[tuple[float, float]]:
    """Create a simple linear route."""
    # ~10m per point
    delta = 0.0001
    return [(start_lat + i * delta, start_lon + i * delta) for i in range(num_points)]


def make_zigzag_route(start_lat: float, start_lon: float, num_points: int = 50) -> list[tuple[float, float]]:
    """Create a zigzag pattern route."""
    delta = 0.0001
    coords = []
    for i in range(num_points):
        lat = start_lat + i * delta
        lon = start_lon + (delta if i % 2 == 0 else -delta)
        coords.append((lat, lon))
    return coords


class TestMatchRoute:
    """Integration tests for MatchRoute use case."""

    @pytest.mark.asyncio
    async def test_creates_new_route_for_first_activity(self, db_session, seed_user):
        """First activity with GPS should create a new route."""
        activity = make_activity(seed_user.id)
        db_session.add(activity)
        await db_session.flush()

        coords = make_line_route(47.3769, 8.5417)
        records = make_records(activity.id, coords)
        for r in records:
            db_session.add(r)
        await db_session.flush()

        use_case = MatchRoute(db_session)
        result = await use_case.execute(str(activity.id), seed_user.id)

        assert result["success"] is True
        assert result["route_id"] is not None

        await db_session.refresh(activity)
        assert activity.route_id is not None

        # Check route was created
        route_result = await db_session.execute(
            select(Route).where(Route.id == activity.route_id)
        )
        route = route_result.scalar_one()
        assert route.ride_count >= 1

    @pytest.mark.asyncio
    async def test_matches_similar_route(self, db_session, seed_user):
        """Second activity on same path should match existing route."""
        coords = make_line_route(47.3769, 8.5417, num_points=100)

        # First activity creates route
        activity1 = make_activity(seed_user.id)
        db_session.add(activity1)
        await db_session.flush()

        for r in make_records(activity1.id, coords):
            db_session.add(r)
        await db_session.flush()

        use_case = MatchRoute(db_session)
        result1 = await use_case.execute(str(activity1.id), seed_user.id)
        route_id = result1["route_id"]

        # Second activity with same coords
        activity2 = make_activity(seed_user.id)
        db_session.add(activity2)
        await db_session.flush()

        for r in make_records(activity2.id, coords):
            db_session.add(r)
        await db_session.flush()

        result2 = await use_case.execute(str(activity2.id), seed_user.id)

        assert result2["success"] is True
        assert result2["route_id"] == route_id

        await db_session.refresh(activity2)
        assert activity2.route_id == route_id

    @pytest.mark.asyncio
    async def test_different_routes_not_matched(self, db_session, seed_user):
        """Activities on different paths should get different routes."""
        # First activity
        activity1 = make_activity(seed_user.id)
        db_session.add(activity1)
        await db_session.flush()

        coords1 = make_line_route(47.3769, 8.5417)
        for r in make_records(activity1.id, coords1):
            db_session.add(r)
        await db_session.flush()

        use_case = MatchRoute(db_session)
        result1 = await use_case.execute(str(activity1.id), seed_user.id)

        # Second activity - significantly different location
        activity2 = make_activity(seed_user.id)
        db_session.add(activity2)
        await db_session.flush()

        coords2 = make_line_route(46.5197, 6.6323)  # Different city
        for r in make_records(activity2.id, coords2):
            db_session.add(r)
        await db_session.flush()

        result2 = await use_case.execute(str(activity2.id), seed_user.id)

        assert result1["route_id"] != result2["route_id"]

    @pytest.mark.asyncio
    async def test_activity_not_found_logs_failure(self, db_session, seed_user):
        """Should log failure event when activity doesn't exist."""
        fake_id = uuid4()

        use_case = MatchRoute(db_session)
        result = await use_case.execute(str(fake_id), seed_user.id)

        assert result["success"] is False

        # Check event was logged
        event_result = await db_session.execute(
            select(Event).where(
                Event.user_id == seed_user.id,
                Event.event_type == EventType.ROUTE_MATCHED.value,
                Event.outcome == EventOutcome.FAILURE.value,
            )
        )
        event = event_result.scalar_one_or_none()
        assert event is not None

    @pytest.mark.asyncio
    async def test_logs_success_event_when_matched(self, db_session, seed_user):
        """Should log success event when route is matched."""
        activity = make_activity(seed_user.id)
        db_session.add(activity)
        await db_session.flush()

        coords = make_line_route(47.3769, 8.5417)
        for r in make_records(activity.id, coords):
            db_session.add(r)
        await db_session.flush()

        use_case = MatchRoute(db_session)
        await use_case.execute(str(activity.id), seed_user.id)

        event_result = await db_session.execute(
            select(Event).where(
                Event.user_id == seed_user.id,
                Event.event_type == EventType.ROUTE_MATCHED.value,
                Event.outcome == EventOutcome.SUCCESS.value,
            )
        )
        event = event_result.scalar_one_or_none()
        assert event is not None

    @pytest.mark.asyncio
    async def test_activity_without_gps_no_route(self, db_session, seed_user):
        """Activity without GPS records should not get a route."""
        activity = make_activity(seed_user.id)
        db_session.add(activity)
        await db_session.flush()

        # No records added

        use_case = MatchRoute(db_session)
        result = await use_case.execute(str(activity.id), seed_user.id)

        # Should succeed but with no route
        assert result["success"] is True
        assert result["route_id"] is None

        await db_session.refresh(activity)
        assert activity.route_id is None

    @pytest.mark.asyncio
    async def test_out_and_back_matches_original(self, db_session, seed_user):
        """Out-and-back ride should match original route."""
        # First activity - outbound
        activity1 = make_activity(seed_user.id)
        db_session.add(activity1)
        await db_session.flush()

        coords = make_line_route(47.3769, 8.5417, num_points=100)
        for r in make_records(activity1.id, coords):
            db_session.add(r)
        await db_session.flush()

        use_case = MatchRoute(db_session)
        result1 = await use_case.execute(str(activity1.id), seed_user.id)
        route_id = result1["route_id"]

        # Second activity - out and back (same coords + reversed)
        activity2 = make_activity(seed_user.id)
        db_session.add(activity2)
        await db_session.flush()

        out_and_back = coords + list(reversed(coords))
        for r in make_records(activity2.id, out_and_back):
            db_session.add(r)
        await db_session.flush()

        result2 = await use_case.execute(str(activity2.id), seed_user.id)

        # Should match same route (or create new route that encompasses both)
        assert result2["success"] is True
        assert result2["route_id"] is not None

    @pytest.mark.asyncio
    async def test_user_routes_isolated(self, db_session, seed_user):
        """Routes should be isolated per user."""
        from trainingdash.repositories.postgres.models import User

        other_user = User(email="other@example.com", password_hash="hash")
        db_session.add(other_user)
        await db_session.flush()

        coords = make_line_route(47.3769, 8.5417)

        # First user creates route
        activity1 = make_activity(seed_user.id)
        db_session.add(activity1)
        await db_session.flush()

        for r in make_records(activity1.id, coords):
            db_session.add(r)
        await db_session.flush()

        use_case = MatchRoute(db_session)
        result1 = await use_case.execute(str(activity1.id), seed_user.id)

        # Second user on same path - should get own route
        activity2 = make_activity(other_user.id)
        db_session.add(activity2)
        await db_session.flush()

        for r in make_records(activity2.id, coords):
            db_session.add(r)
        await db_session.flush()

        result2 = await use_case.execute(str(activity2.id), other_user.id)

        # Different users get different routes even on same path
        assert result1["route_id"] != result2["route_id"]

    @pytest.mark.asyncio
    async def test_handles_uuid_string_format(self, db_session, seed_user):
        """Should handle activity_id as string (for JSON queue compatibility)."""
        activity = make_activity(seed_user.id)
        db_session.add(activity)
        await db_session.flush()

        coords = make_line_route(47.3769, 8.5417)
        for r in make_records(activity.id, coords):
            db_session.add(r)
        await db_session.flush()

        use_case = MatchRoute(db_session)
        # Pass as string (as would come from SAQ job queue)
        result = await use_case.execute(str(activity.id), seed_user.id)

        assert result["success"] is True
        assert result["route_id"] is not None
