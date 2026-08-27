"""Integration tests for Segment, SegmentEffort, and SegmentSuggestion models."""

from datetime import datetime, timedelta

import pytest
from geoalchemy2.functions import ST_MakePoint, ST_MakePolygon, ST_MakeLine, ST_SetSRID
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from trainingdash.repositories.postgres.models import (
    Activity,
    Segment,
    SegmentEffort,
    SegmentSuggestion,
    User,
)


class TestSegmentModel:
    """Tests for Segment model CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_segment_climb(self, db_session, seed_user):
        """Can create a climb segment with required fields."""
        segment = Segment(
            name="Test Climb",
            type="climb",
            status="suggested",
            climb_category="3",
            polyline="encodedPolylineHere",
            start_point=ST_SetSRID(ST_MakePoint(7.4, 46.9), 4326),
            end_point=ST_SetSRID(ST_MakePoint(7.5, 47.0), 4326),
            bounds=ST_SetSRID(
                ST_MakePolygon(
                    ST_MakeLine(
                        text("ARRAY[ST_MakePoint(7.4, 46.9), ST_MakePoint(7.5, 46.9), "
                             "ST_MakePoint(7.5, 47.0), ST_MakePoint(7.4, 47.0), ST_MakePoint(7.4, 46.9)]")
                    )
                ),
                4326,
            ),
            distance_m=2500.0,
            elevation_gain_m=200.0,
            avg_grade_pct=8.0,
            max_grade_pct=15.0,
            gradient_segments=[{"distance_m": 500, "grade_pct": 6.0}, {"distance_m": 500, "grade_pct": 10.0}],
            created_by=seed_user.id,
        )
        db_session.add(segment)
        await db_session.commit()
        await db_session.refresh(segment)

        assert segment.id is not None
        assert segment.name == "Test Climb"
        assert segment.type == "climb"
        assert segment.status == "suggested"
        assert segment.climb_category == "3"
        assert segment.distance_m == 2500.0
        assert segment.effort_count == 0
        assert segment.athlete_count == 0
        assert segment.deleted_at is None

    @pytest.mark.asyncio
    async def test_create_segment_custom(self, db_session, seed_user):
        """Can create a custom segment without climb_category."""
        segment = Segment(
            name="My Favorite Stretch",
            type="custom",
            status="approved",
            polyline="anotherPolyline",
            start_point=ST_SetSRID(ST_MakePoint(7.4, 46.9), 4326),
            end_point=ST_SetSRID(ST_MakePoint(7.5, 47.0), 4326),
            bounds=ST_SetSRID(
                ST_MakePolygon(
                    ST_MakeLine(
                        text("ARRAY[ST_MakePoint(7.4, 46.9), ST_MakePoint(7.5, 46.9), "
                             "ST_MakePoint(7.5, 47.0), ST_MakePoint(7.4, 47.0), ST_MakePoint(7.4, 46.9)]")
                    )
                ),
                4326,
            ),
            distance_m=1000.0,
            elevation_gain_m=10.0,
            avg_grade_pct=1.0,
            max_grade_pct=3.0,
            gradient_segments=[],
            direction_bearing=45.0,
            created_by=seed_user.id,
        )
        db_session.add(segment)
        await db_session.commit()
        await db_session.refresh(segment)

        assert segment.type == "custom"
        assert segment.status == "approved"
        assert segment.climb_category is None
        assert segment.direction_bearing == 45.0

    @pytest.mark.asyncio
    async def test_segment_invalid_type_rejected(self, db_session, seed_user):
        """Invalid segment type is rejected by database constraint."""
        segment = Segment(
            name="Invalid Type",
            type="descent",  # not a valid type
            polyline="test",
            start_point=ST_SetSRID(ST_MakePoint(7.4, 46.9), 4326),
            end_point=ST_SetSRID(ST_MakePoint(7.5, 47.0), 4326),
            bounds=ST_SetSRID(
                ST_MakePolygon(
                    ST_MakeLine(
                        text("ARRAY[ST_MakePoint(7.4, 46.9), ST_MakePoint(7.5, 46.9), "
                             "ST_MakePoint(7.5, 47.0), ST_MakePoint(7.4, 47.0), ST_MakePoint(7.4, 46.9)]")
                    )
                ),
                4326,
            ),
            distance_m=1000.0,
            elevation_gain_m=100.0,
            avg_grade_pct=10.0,
            max_grade_pct=15.0,
            gradient_segments=[],
        )
        db_session.add(segment)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_segment_invalid_status_rejected(self, db_session, seed_user):
        """Invalid segment status is rejected by database constraint."""
        segment = Segment(
            name="Invalid Status",
            type="climb",
            status="pending",  # not a valid status
            polyline="test",
            start_point=ST_SetSRID(ST_MakePoint(7.4, 46.9), 4326),
            end_point=ST_SetSRID(ST_MakePoint(7.5, 47.0), 4326),
            bounds=ST_SetSRID(
                ST_MakePolygon(
                    ST_MakeLine(
                        text("ARRAY[ST_MakePoint(7.4, 46.9), ST_MakePoint(7.5, 46.9), "
                             "ST_MakePoint(7.5, 47.0), ST_MakePoint(7.4, 47.0), ST_MakePoint(7.4, 46.9)]")
                    )
                ),
                4326,
            ),
            distance_m=1000.0,
            elevation_gain_m=100.0,
            avg_grade_pct=10.0,
            max_grade_pct=15.0,
            gradient_segments=[],
        )
        db_session.add(segment)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_segment_soft_delete(self, db_session, seed_user):
        """Segment can be soft-deleted by setting deleted_at."""
        segment = Segment(
            name="To Delete",
            type="climb",
            polyline="test",
            start_point=ST_SetSRID(ST_MakePoint(7.4, 46.9), 4326),
            end_point=ST_SetSRID(ST_MakePoint(7.5, 47.0), 4326),
            bounds=ST_SetSRID(
                ST_MakePolygon(
                    ST_MakeLine(
                        text("ARRAY[ST_MakePoint(7.4, 46.9), ST_MakePoint(7.5, 46.9), "
                             "ST_MakePoint(7.5, 47.0), ST_MakePoint(7.4, 47.0), ST_MakePoint(7.4, 46.9)]")
                    )
                ),
                4326,
            ),
            distance_m=1000.0,
            elevation_gain_m=100.0,
            avg_grade_pct=10.0,
            max_grade_pct=15.0,
            gradient_segments=[],
        )
        db_session.add(segment)
        await db_session.commit()
        await db_session.refresh(segment)

        # Soft delete
        segment.deleted_at = datetime.now()
        await db_session.commit()
        await db_session.refresh(segment)

        assert segment.deleted_at is not None

    @pytest.mark.asyncio
    async def test_segment_created_by_set_null_on_user_delete(self, db_session):
        """Segment.created_by is set to NULL when user is deleted."""
        # Create separate user for this test
        user = User(email="segment-creator@example.com", password_hash="x")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        segment = Segment(
            name="User Delete Test",
            type="climb",
            polyline="test",
            start_point=ST_SetSRID(ST_MakePoint(7.4, 46.9), 4326),
            end_point=ST_SetSRID(ST_MakePoint(7.5, 47.0), 4326),
            bounds=ST_SetSRID(
                ST_MakePolygon(
                    ST_MakeLine(
                        text("ARRAY[ST_MakePoint(7.4, 46.9), ST_MakePoint(7.5, 46.9), "
                             "ST_MakePoint(7.5, 47.0), ST_MakePoint(7.4, 47.0), ST_MakePoint(7.4, 46.9)]")
                    )
                ),
                4326,
            ),
            distance_m=1000.0,
            elevation_gain_m=100.0,
            avg_grade_pct=10.0,
            max_grade_pct=15.0,
            gradient_segments=[],
            created_by=user.id,
        )
        db_session.add(segment)
        await db_session.commit()
        segment_id = segment.id

        # Delete user
        await db_session.delete(user)
        await db_session.commit()

        # Segment should still exist but created_by should be NULL
        db_session.expire_all()
        result = await db_session.execute(select(Segment).where(Segment.id == segment_id))
        segment = result.scalar_one()
        assert segment.created_by is None


class TestSegmentEffortModel:
    """Tests for SegmentEffort model."""

    @pytest.fixture
    async def sample_segment(self, db_session, seed_user):
        """Create a sample segment for effort tests."""
        segment = Segment(
            name="Effort Test Segment",
            type="climb",
            polyline="test",
            start_point=ST_SetSRID(ST_MakePoint(7.4, 46.9), 4326),
            end_point=ST_SetSRID(ST_MakePoint(7.5, 47.0), 4326),
            bounds=ST_SetSRID(
                ST_MakePolygon(
                    ST_MakeLine(
                        text("ARRAY[ST_MakePoint(7.4, 46.9), ST_MakePoint(7.5, 46.9), "
                             "ST_MakePoint(7.5, 47.0), ST_MakePoint(7.4, 47.0), ST_MakePoint(7.4, 46.9)]")
                    )
                ),
                4326,
            ),
            distance_m=1000.0,
            elevation_gain_m=100.0,
            avg_grade_pct=10.0,
            max_grade_pct=15.0,
            gradient_segments=[],
        )
        db_session.add(segment)
        await db_session.commit()
        await db_session.refresh(segment)
        return segment

    @pytest.fixture
    async def sample_activity(self, db_session, seed_user):
        """Create a sample activity for effort tests."""
        activity = Activity(
            user_id=seed_user.id,
            source="test",
            source_ref=f"effort-test-{datetime.now().timestamp()}",
            started_at=datetime(2024, 6, 15, 10, 0, 0),
        )
        db_session.add(activity)
        await db_session.commit()
        await db_session.refresh(activity)
        return activity

    @pytest.mark.asyncio
    async def test_create_effort(self, db_session, seed_user, sample_segment, sample_activity):
        """Can create a segment effort."""
        effort = SegmentEffort(
            segment_id=sample_segment.id,
            activity_id=sample_activity.id,
            user_id=seed_user.id,
            started_at=datetime(2024, 6, 15, 10, 5, 0),
            elapsed_time_seconds=300,
            moving_time_seconds=295,
            avg_power_watts=250,
            avg_hr_bpm=165,
            start_index=100,
            end_index=200,
            is_pr=True,
        )
        db_session.add(effort)
        await db_session.commit()
        await db_session.refresh(effort)

        assert effort.id is not None
        assert effort.elapsed_time_seconds == 300
        assert effort.is_pr is True

    @pytest.mark.asyncio
    async def test_effort_unique_constraint(self, db_session, seed_user, sample_segment, sample_activity):
        """Duplicate efforts (same segment, activity, start_index) are rejected."""
        effort1 = SegmentEffort(
            segment_id=sample_segment.id,
            activity_id=sample_activity.id,
            user_id=seed_user.id,
            started_at=datetime(2024, 6, 15, 10, 5, 0),
            elapsed_time_seconds=300,
            start_index=100,
            end_index=200,
        )
        db_session.add(effort1)
        await db_session.commit()

        # Try to create duplicate
        effort2 = SegmentEffort(
            segment_id=sample_segment.id,
            activity_id=sample_activity.id,
            user_id=seed_user.id,
            started_at=datetime(2024, 6, 15, 10, 5, 0),
            elapsed_time_seconds=310,  # different time
            start_index=100,  # same start_index
            end_index=200,
        )
        db_session.add(effort2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_effort_deleted_with_segment(self, db_session, seed_user, sample_activity):
        """SegmentEffort is deleted when segment is deleted (CASCADE)."""
        segment = Segment(
            name="Cascade Test Segment",
            type="climb",
            polyline="test",
            start_point=ST_SetSRID(ST_MakePoint(7.4, 46.9), 4326),
            end_point=ST_SetSRID(ST_MakePoint(7.5, 47.0), 4326),
            bounds=ST_SetSRID(
                ST_MakePolygon(
                    ST_MakeLine(
                        text("ARRAY[ST_MakePoint(7.4, 46.9), ST_MakePoint(7.5, 46.9), "
                             "ST_MakePoint(7.5, 47.0), ST_MakePoint(7.4, 47.0), ST_MakePoint(7.4, 46.9)]")
                    )
                ),
                4326,
            ),
            distance_m=1000.0,
            elevation_gain_m=100.0,
            avg_grade_pct=10.0,
            max_grade_pct=15.0,
            gradient_segments=[],
        )
        db_session.add(segment)
        await db_session.commit()
        await db_session.refresh(segment)

        effort = SegmentEffort(
            segment_id=segment.id,
            activity_id=sample_activity.id,
            user_id=seed_user.id,
            started_at=datetime(2024, 6, 15, 10, 5, 0),
            elapsed_time_seconds=300,
            start_index=100,
            end_index=200,
        )
        db_session.add(effort)
        await db_session.commit()
        effort_id = effort.id

        # Delete segment
        await db_session.delete(segment)
        await db_session.commit()

        # Effort should be gone
        result = await db_session.execute(select(SegmentEffort).where(SegmentEffort.id == effort_id))
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_effort_relationship_navigation(self, db_session, seed_user, sample_segment, sample_activity):
        """Can navigate from effort to segment and activity."""
        effort = SegmentEffort(
            segment_id=sample_segment.id,
            activity_id=sample_activity.id,
            user_id=seed_user.id,
            started_at=datetime(2024, 6, 15, 10, 5, 0),
            elapsed_time_seconds=300,
            start_index=100,
            end_index=200,
        )
        db_session.add(effort)
        await db_session.commit()
        await db_session.refresh(effort)

        assert effort.segment.name == "Effort Test Segment"


class TestSegmentSuggestionModel:
    """Tests for SegmentSuggestion model."""

    @pytest.fixture
    async def sample_segment(self, db_session):
        """Create a sample segment for suggestion tests."""
        segment = Segment(
            name="Suggestion Test Segment",
            type="climb",
            status="suggested",
            polyline="test",
            start_point=ST_SetSRID(ST_MakePoint(7.4, 46.9), 4326),
            end_point=ST_SetSRID(ST_MakePoint(7.5, 47.0), 4326),
            bounds=ST_SetSRID(
                ST_MakePolygon(
                    ST_MakeLine(
                        text("ARRAY[ST_MakePoint(7.4, 46.9), ST_MakePoint(7.5, 46.9), "
                             "ST_MakePoint(7.5, 47.0), ST_MakePoint(7.4, 47.0), ST_MakePoint(7.4, 46.9)]")
                    )
                ),
                4326,
            ),
            distance_m=1000.0,
            elevation_gain_m=100.0,
            avg_grade_pct=10.0,
            max_grade_pct=15.0,
            gradient_segments=[],
        )
        db_session.add(segment)
        await db_session.commit()
        await db_session.refresh(segment)
        return segment

    @pytest.mark.asyncio
    async def test_create_suggestion(self, db_session, seed_user, sample_segment):
        """Can create a segment suggestion."""
        now = datetime.now()
        suggestion = SegmentSuggestion(
            segment_id=sample_segment.id,
            user_id=seed_user.id,
            repetition_count=1,
            first_ridden_at=now,
            last_ridden_at=now,
            expires_at=now + timedelta(days=90),
        )
        db_session.add(suggestion)
        await db_session.commit()
        await db_session.refresh(suggestion)

        assert suggestion.id is not None
        assert suggestion.repetition_count == 1
        assert suggestion.dismissed_at is None

    @pytest.mark.asyncio
    async def test_suggestion_unique_per_user(self, db_session, seed_user, sample_segment):
        """Only one suggestion per segment per user."""
        now = datetime.now()
        suggestion1 = SegmentSuggestion(
            segment_id=sample_segment.id,
            user_id=seed_user.id,
            repetition_count=1,
            first_ridden_at=now,
            last_ridden_at=now,
            expires_at=now + timedelta(days=90),
        )
        db_session.add(suggestion1)
        await db_session.commit()

        # Try to create duplicate
        suggestion2 = SegmentSuggestion(
            segment_id=sample_segment.id,
            user_id=seed_user.id,
            repetition_count=2,
            first_ridden_at=now,
            last_ridden_at=now,
            expires_at=now + timedelta(days=90),
        )
        db_session.add(suggestion2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_suggestion_dismiss(self, db_session, seed_user, sample_segment):
        """Can dismiss a suggestion by setting dismissed_at."""
        now = datetime.now()
        suggestion = SegmentSuggestion(
            segment_id=sample_segment.id,
            user_id=seed_user.id,
            repetition_count=1,
            first_ridden_at=now,
            last_ridden_at=now,
            expires_at=now + timedelta(days=90),
        )
        db_session.add(suggestion)
        await db_session.commit()
        await db_session.refresh(suggestion)

        # Dismiss
        suggestion.dismissed_at = datetime.now()
        await db_session.commit()
        await db_session.refresh(suggestion)

        assert suggestion.dismissed_at is not None

    @pytest.mark.asyncio
    async def test_suggestion_deleted_with_segment(self, db_session, seed_user):
        """SegmentSuggestion is deleted when segment is deleted (CASCADE)."""
        segment = Segment(
            name="Cascade Suggestion Segment",
            type="climb",
            polyline="test",
            start_point=ST_SetSRID(ST_MakePoint(7.4, 46.9), 4326),
            end_point=ST_SetSRID(ST_MakePoint(7.5, 47.0), 4326),
            bounds=ST_SetSRID(
                ST_MakePolygon(
                    ST_MakeLine(
                        text("ARRAY[ST_MakePoint(7.4, 46.9), ST_MakePoint(7.5, 46.9), "
                             "ST_MakePoint(7.5, 47.0), ST_MakePoint(7.4, 47.0), ST_MakePoint(7.4, 46.9)]")
                    )
                ),
                4326,
            ),
            distance_m=1000.0,
            elevation_gain_m=100.0,
            avg_grade_pct=10.0,
            max_grade_pct=15.0,
            gradient_segments=[],
        )
        db_session.add(segment)
        await db_session.commit()
        await db_session.refresh(segment)

        now = datetime.now()
        suggestion = SegmentSuggestion(
            segment_id=segment.id,
            user_id=seed_user.id,
            repetition_count=1,
            first_ridden_at=now,
            last_ridden_at=now,
            expires_at=now + timedelta(days=90),
        )
        db_session.add(suggestion)
        await db_session.commit()
        suggestion_id = suggestion.id

        # Delete segment
        await db_session.delete(segment)
        await db_session.commit()

        # Suggestion should be gone
        result = await db_session.execute(select(SegmentSuggestion).where(SegmentSuggestion.id == suggestion_id))
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_suggestion_relationship_navigation(self, db_session, seed_user, sample_segment):
        """Can navigate from suggestion to segment."""
        now = datetime.now()
        suggestion = SegmentSuggestion(
            segment_id=sample_segment.id,
            user_id=seed_user.id,
            repetition_count=3,
            first_ridden_at=now - timedelta(days=30),
            last_ridden_at=now,
            expires_at=now + timedelta(days=90),
        )
        db_session.add(suggestion)
        await db_session.commit()
        await db_session.refresh(suggestion)

        assert suggestion.segment.name == "Suggestion Test Segment"


class TestSpatialQueries:
    """Tests for spatial index functionality."""

    @pytest.mark.asyncio
    async def test_spatial_index_query(self, db_session, seed_user):
        """Spatial query using bounds works correctly."""
        # Create a segment with known bounds
        segment = Segment(
            name="Spatial Test Segment",
            type="climb",
            polyline="test",
            start_point=ST_SetSRID(ST_MakePoint(7.45, 46.95), 4326),
            end_point=ST_SetSRID(ST_MakePoint(7.46, 46.96), 4326),
            bounds=ST_SetSRID(
                ST_MakePolygon(
                    ST_MakeLine(
                        text("ARRAY[ST_MakePoint(7.44, 46.94), ST_MakePoint(7.47, 46.94), "
                             "ST_MakePoint(7.47, 46.97), ST_MakePoint(7.44, 46.97), ST_MakePoint(7.44, 46.94)]")
                    )
                ),
                4326,
            ),
            distance_m=1000.0,
            elevation_gain_m=100.0,
            avg_grade_pct=10.0,
            max_grade_pct=15.0,
            gradient_segments=[],
        )
        db_session.add(segment)
        await db_session.commit()
        await db_session.refresh(segment)

        # Query using ST_Intersects with a point inside the bounds
        from geoalchemy2.functions import ST_Intersects

        result = await db_session.execute(
            select(Segment).where(
                ST_Intersects(Segment.bounds, ST_SetSRID(ST_MakePoint(7.455, 46.955), 4326))
            )
        )
        found = result.scalars().all()

        assert len(found) >= 1
        assert any(s.name == "Spatial Test Segment" for s in found)
