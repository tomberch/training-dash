"""Unit tests for activity segments endpoint."""

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from trainingdash.repositories.postgres.models import Segment, SegmentEffort
from trainingdash.routers.activities import _compute_pr_delta, get_activity_segments
from tests.fakes.activity_repo import FakeActivityRepo
from tests.fakes.segment_repos import FakeSegmentEffortRepo


# =============================================================================
# Test Fixtures
# =============================================================================


def make_segment(
    segment_id=None,
    name: str = "Test Segment",
    type: str = "climb",
    climb_category: str | None = "4",
    distance_m: float = 1000.0,
) -> Segment:
    """Create a test segment."""
    if segment_id is None:
        segment_id = uuid4()

    segment = MagicMock(spec=Segment)
    segment.id = segment_id
    segment.name = name
    segment.type = type
    segment.climb_category = climb_category
    segment.distance_m = distance_m
    return segment


def make_effort(
    effort_id=None,
    segment: Segment = None,
    activity_id=None,
    user_id: int = 1,
    elapsed_time_seconds: int = 300,
    is_pr: bool = False,
    start_index: int = 0,
    end_index: int = 100,
) -> SegmentEffort:
    """Create a test segment effort."""
    if effort_id is None:
        effort_id = uuid4()
    if activity_id is None:
        activity_id = uuid4()
    if segment is None:
        segment = make_segment()

    effort = SegmentEffort(
        id=effort_id,
        segment_id=segment.id,
        activity_id=activity_id,
        user_id=user_id,
        started_at=datetime.now(),
        elapsed_time_seconds=elapsed_time_seconds,
        moving_time_seconds=elapsed_time_seconds - 10,
        avg_power_watts=250,
        avg_hr_bpm=160,
        start_index=start_index,
        end_index=end_index,
        is_pr=is_pr,
    )
    # Attach segment relationship for serialization
    effort.segment = segment
    return effort


# =============================================================================
# _compute_pr_delta Tests
# =============================================================================


class TestComputePrDelta:
    """Tests for _compute_pr_delta helper function."""

    @pytest.mark.asyncio
    async def test_is_pr_returns_zero(self):
        """When effort is PR, returns 0."""
        effort_repo = FakeSegmentEffortRepo()

        segment = make_segment()
        effort = make_effort(segment=segment, is_pr=True, elapsed_time_seconds=300)

        delta = await _compute_pr_delta(effort_repo, effort)

        assert delta == 0

    @pytest.mark.asyncio
    async def test_slower_than_pr_returns_positive_delta(self):
        """When effort is slower than PR, returns positive delta."""
        effort_repo = FakeSegmentEffortRepo()

        segment = make_segment()

        # PR effort (faster - 300 seconds)
        pr_effort = make_effort(
            segment=segment,
            user_id=1,
            elapsed_time_seconds=300,
            is_pr=True,
        )
        effort_repo.add(pr_effort)

        # Current effort (slower - 350 seconds)
        current_effort = make_effort(
            segment=segment,
            user_id=1,
            elapsed_time_seconds=350,
            is_pr=False,
        )
        # Need to set segment_id to match for the PR lookup
        current_effort.segment_id = segment.id

        delta = await _compute_pr_delta(effort_repo, current_effort)

        assert delta == 50  # 350 - 300 = 50 seconds slower

    @pytest.mark.asyncio
    async def test_no_pr_returns_none(self):
        """When no PR exists, returns None."""
        effort_repo = FakeSegmentEffortRepo()

        segment = make_segment()
        effort = make_effort(segment=segment, is_pr=False)

        delta = await _compute_pr_delta(effort_repo, effort)

        assert delta is None


# =============================================================================
# get_activity_segments Endpoint Tests
# =============================================================================


class TestGetActivitySegments:
    """Tests for get_activity_segments endpoint."""

    @pytest.mark.asyncio
    async def test_activity_not_found(self):
        """Returns 404 when activity doesn't exist."""
        from fastapi import HTTPException

        activity_repo = FakeActivityRepo()
        effort_repo = FakeSegmentEffortRepo()

        user = MagicMock()
        user.id = 1

        with pytest.raises(HTTPException) as exc_info:
            await get_activity_segments(
                repo=activity_repo,
                effort_repo=effort_repo,
                user=user,
                activity_id=uuid4(),
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_activity_owned_by_different_user(self):
        """Returns 404 when activity belongs to different user."""
        from fastapi import HTTPException

        from trainingdash.repositories.postgres.models import Activity

        activity_repo = FakeActivityRepo()
        effort_repo = FakeSegmentEffortRepo()

        # Activity owned by user 2
        activity = Activity(
            id=uuid4(),
            user_id=2,
            source="test",
            source_ref="test-123",
            started_at=datetime.now(),
        )
        await activity_repo.save(activity)

        # User 1 tries to access
        user = MagicMock()
        user.id = 1

        with pytest.raises(HTTPException) as exc_info:
            await get_activity_segments(
                repo=activity_repo,
                effort_repo=effort_repo,
                user=user,
                activity_id=activity.id,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_activity_with_no_segments(self):
        """Returns empty efforts list when activity has no segment efforts."""
        from trainingdash.repositories.postgres.models import Activity

        activity_repo = FakeActivityRepo()
        effort_repo = FakeSegmentEffortRepo()

        activity = Activity(
            id=uuid4(),
            user_id=1,
            source="test",
            source_ref="test-123",
            started_at=datetime.now(),
        )
        await activity_repo.save(activity)

        user = MagicMock()
        user.id = 1

        result = await get_activity_segments(
            repo=activity_repo,
            effort_repo=effort_repo,
            user=user,
            activity_id=activity.id,
        )

        assert result == {"efforts": []}

    @pytest.mark.asyncio
    async def test_activity_with_one_effort(self):
        """Returns single effort with all fields."""
        from trainingdash.repositories.postgres.models import Activity

        activity_repo = FakeActivityRepo()
        effort_repo = FakeSegmentEffortRepo()

        activity = Activity(
            id=uuid4(),
            user_id=1,
            source="test",
            source_ref="test-123",
            started_at=datetime.now(),
        )
        await activity_repo.save(activity)

        segment = make_segment(name="Test Climb", type="climb", climb_category="3")
        effort = make_effort(
            segment=segment,
            activity_id=activity.id,
            user_id=1,
            elapsed_time_seconds=600,
            is_pr=True,
            start_index=100,
            end_index=500,
        )
        effort_repo.add(effort)

        user = MagicMock()
        user.id = 1

        result = await get_activity_segments(
            repo=activity_repo,
            effort_repo=effort_repo,
            user=user,
            activity_id=activity.id,
        )

        assert len(result["efforts"]) == 1
        e = result["efforts"][0]
        assert e["id"] == str(effort.id)
        assert e["segment_id"] == str(segment.id)
        assert e["segment_name"] == "Test Climb"
        assert e["segment_type"] == "climb"
        assert e["climb_category"] == "3"
        assert e["elapsed_time_seconds"] == 600
        assert e["is_pr"] is True
        assert e["delta_to_pr_seconds"] == 0  # It's the PR
        assert e["start_index"] == 100
        assert e["end_index"] == 500

    @pytest.mark.asyncio
    async def test_activity_with_multiple_efforts_ordered_by_start_index(self):
        """Returns efforts ordered by start_index (chronologically)."""
        from trainingdash.repositories.postgres.models import Activity

        activity_repo = FakeActivityRepo()
        effort_repo = FakeSegmentEffortRepo()

        activity = Activity(
            id=uuid4(),
            user_id=1,
            source="test",
            source_ref="test-123",
            started_at=datetime.now(),
        )
        await activity_repo.save(activity)

        # Add efforts out of order
        segment1 = make_segment(name="Second Segment")
        effort1 = make_effort(
            segment=segment1,
            activity_id=activity.id,
            user_id=1,
            start_index=500,  # Later in ride
            end_index=700,
            is_pr=True,
        )

        segment2 = make_segment(name="First Segment")
        effort2 = make_effort(
            segment=segment2,
            activity_id=activity.id,
            user_id=1,
            start_index=100,  # Earlier in ride
            end_index=300,
            is_pr=True,
        )

        # Add in reverse order
        effort_repo.add(effort1)
        effort_repo.add(effort2)

        user = MagicMock()
        user.id = 1

        result = await get_activity_segments(
            repo=activity_repo,
            effort_repo=effort_repo,
            user=user,
            activity_id=activity.id,
        )

        assert len(result["efforts"]) == 2
        # Should be ordered by start_index
        assert result["efforts"][0]["start_index"] == 100
        assert result["efforts"][0]["segment_name"] == "First Segment"
        assert result["efforts"][1]["start_index"] == 500
        assert result["efforts"][1]["segment_name"] == "Second Segment"

    @pytest.mark.asyncio
    async def test_pr_delta_for_non_pr_effort(self):
        """Computes correct PR delta for effort that isn't the PR."""
        from trainingdash.repositories.postgres.models import Activity

        activity_repo = FakeActivityRepo()
        effort_repo = FakeSegmentEffortRepo()

        activity = Activity(
            id=uuid4(),
            user_id=1,
            source="test",
            source_ref="test-123",
            started_at=datetime.now(),
        )
        await activity_repo.save(activity)

        # Create segment and PR effort from a different activity
        segment = make_segment(name="Test Climb")

        pr_effort = make_effort(
            segment=segment,
            activity_id=uuid4(),  # Different activity
            user_id=1,
            elapsed_time_seconds=300,  # PR time
            is_pr=True,
            start_index=0,
            end_index=100,
        )
        effort_repo.add(pr_effort)

        # Current activity's effort (slower)
        current_effort = make_effort(
            segment=segment,
            activity_id=activity.id,
            user_id=1,
            elapsed_time_seconds=360,  # 60 seconds slower
            is_pr=False,
            start_index=100,
            end_index=200,
        )
        effort_repo.add(current_effort)

        user = MagicMock()
        user.id = 1

        result = await get_activity_segments(
            repo=activity_repo,
            effort_repo=effort_repo,
            user=user,
            activity_id=activity.id,
        )

        assert len(result["efforts"]) == 1
        assert result["efforts"][0]["is_pr"] is False
        assert result["efforts"][0]["delta_to_pr_seconds"] == 60  # 360 - 300

    @pytest.mark.asyncio
    async def test_effort_with_null_optional_fields(self):
        """Handles efforts with null power/HR."""
        from trainingdash.repositories.postgres.models import Activity

        activity_repo = FakeActivityRepo()
        effort_repo = FakeSegmentEffortRepo()

        activity = Activity(
            id=uuid4(),
            user_id=1,
            source="test",
            source_ref="test-123",
            started_at=datetime.now(),
        )
        await activity_repo.save(activity)

        segment = make_segment()
        effort = make_effort(
            segment=segment,
            activity_id=activity.id,
            user_id=1,
            is_pr=True,
        )
        # Set optional fields to None
        effort.avg_power_watts = None
        effort.avg_hr_bpm = None
        effort.moving_time_seconds = None
        effort_repo.add(effort)

        user = MagicMock()
        user.id = 1

        result = await get_activity_segments(
            repo=activity_repo,
            effort_repo=effort_repo,
            user=user,
            activity_id=activity.id,
        )

        assert len(result["efforts"]) == 1
        assert result["efforts"][0]["avg_power_watts"] is None
        assert result["efforts"][0]["avg_hr_bpm"] is None
        assert result["efforts"][0]["moving_time_seconds"] is None
