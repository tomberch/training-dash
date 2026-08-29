"""Unit tests for ApproveSuggestion use case."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from tests.fakes.segment_repos import FakeSegmentRepo, FakeSegmentSuggestionRepo
from trainingdash.domain.polyline import encode_polyline
from trainingdash.repositories.postgres.models import Segment, SegmentSuggestion
from trainingdash.use_cases.approve_suggestion import ApproveSuggestion


def make_wkt_point(lat: float, lon: float) -> str:
    """Create a WKT point string for testing."""
    return f"SRID=4326;POINT({lon} {lat})"


def make_wkt_polygon(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> str:
    """Create a WKT polygon for bounding box."""
    return (
        f"SRID=4326;POLYGON(({min_lon} {min_lat}, {max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, {min_lon} {max_lat}, {min_lon} {min_lat}))"
    )


class FakeGeometry:
    """Fake PostGIS geometry for testing."""

    def __init__(self, lat: float, lon: float) -> None:
        self.x = lon
        self.y = lat


def make_segment(
    *,
    segment_id=None,
    name: str = "Test Segment",
    status: str = "suggested",
    segment_type: str = "climb",
    start_lat: float = 46.9,
    start_lon: float = 7.4,
    end_lat: float = 46.91,
    end_lon: float = 7.41,
    polyline: str | None = None,
    created_by: int | None = None,
) -> Segment:
    """Create a test segment with fake geometry."""
    if segment_id is None:
        segment_id = uuid4()

    if polyline is None:
        # Create polyline from start to end
        points = [(start_lat, start_lon), (end_lat, end_lon)]
        polyline = encode_polyline(points)

    segment = Segment(
        id=segment_id,
        name=name,
        type=segment_type,
        status=status,
        polyline=polyline,
        distance_m=1000.0,
        elevation_gain_m=100.0,
        avg_grade_pct=10.0,
        max_grade_pct=15.0,
        gradient_segments=[{"distance_m": 50, "grade_pct": 10}],
        effort_count=0,
        athlete_count=0,
        created_by=created_by,
        created_at=datetime.now(),
    )

    # Fake geometry objects that work with to_shape()
    segment.start_point = FakeGeometry(start_lat, start_lon)
    segment.end_point = FakeGeometry(end_lat, end_lon)

    return segment


def make_suggestion(
    *,
    suggestion_id=None,
    segment_id=None,
    user_id: int = 1,
    repetition_count: int = 3,
    dismissed_at=None,
) -> SegmentSuggestion:
    """Create a test suggestion."""
    if suggestion_id is None:
        suggestion_id = uuid4()
    if segment_id is None:
        segment_id = uuid4()

    now = datetime.now()
    return SegmentSuggestion(
        id=suggestion_id,
        segment_id=segment_id,
        user_id=user_id,
        repetition_count=repetition_count,
        first_ridden_at=now - timedelta(days=30),
        last_ridden_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=60),
        dismissed_at=dismissed_at,
        created_at=now,
    )


class TestApproveSuggestionHappyPath:
    """Test successful approval scenarios."""

    @pytest.mark.asyncio
    async def test_approve_suggestion_success(self):
        """Basic approval converts suggestion to approved segment."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        # Create a suggested segment
        segment = make_segment(status="suggested", name="Auto-detected Climb")
        segment_repo.add(segment)

        # Create suggestion for user 1
        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="My Favorite Climb",
        )

        assert result.success is True
        assert result.error is None
        assert result.duplicate_segment is None
        assert result.segment is not None
        assert result.segment.name == "My Favorite Climb"
        assert result.segment.status == "approved"
        assert result.segment.created_by == 1

    @pytest.mark.asyncio
    async def test_approve_sets_created_by(self):
        """Approval sets the created_by to the approving user."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        segment = make_segment(status="suggested", created_by=None)
        segment_repo.add(segment)

        suggestion = make_suggestion(segment_id=segment.id, user_id=42)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=42,
            suggestion_id=suggestion.id,
            name="User 42's Climb",
        )

        assert result.success is True
        assert result.segment.created_by == 42

    @pytest.mark.asyncio
    async def test_approve_dismisses_suggestion(self):
        """Approval dismisses the suggestion."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        segment = make_segment(status="suggested")
        segment_repo.add(segment)

        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="Dismissed After Approval",
        )

        # Suggestion should be dismissed
        updated_suggestion = await suggestion_repo.get_by_id(suggestion.id)
        assert updated_suggestion.dismissed_at is not None

    @pytest.mark.asyncio
    async def test_approve_with_whitespace_name(self):
        """Name is trimmed of whitespace."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        segment = make_segment(status="suggested")
        segment_repo.add(segment)

        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="  Trimmed Name  ",
        )

        assert result.success is True
        assert result.segment.name == "Trimmed Name"


class TestApproveSuggestionValidation:
    """Test validation error scenarios."""

    @pytest.mark.asyncio
    async def test_name_too_short(self):
        """Name must be at least 3 characters."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        segment = make_segment(status="suggested")
        segment_repo.add(segment)

        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="AB",
        )

        assert result.success is False
        assert "at least 3 characters" in result.error

    @pytest.mark.asyncio
    async def test_name_too_short_after_trim(self):
        """Name validation happens after trimming."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        segment = make_segment(status="suggested")
        segment_repo.add(segment)

        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="  A  ",
        )

        assert result.success is False
        assert "at least 3 characters" in result.error

    @pytest.mark.asyncio
    async def test_name_too_long(self):
        """Name must be at most 100 characters."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        segment = make_segment(status="suggested")
        segment_repo.add(segment)

        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="A" * 101,
        )

        assert result.success is False
        assert "at most 100 characters" in result.error


class TestApproveSuggestionNotFound:
    """Test not-found error scenarios."""

    @pytest.mark.asyncio
    async def test_suggestion_not_found(self):
        """Error when suggestion doesn't exist."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=uuid4(),
            name="Valid Name",
        )

        assert result.success is False
        assert "Suggestion not found" in result.error

    @pytest.mark.asyncio
    async def test_segment_not_found(self):
        """Error when associated segment doesn't exist."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        # Suggestion points to non-existent segment
        suggestion = make_suggestion(segment_id=uuid4(), user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="Valid Name",
        )

        assert result.success is False
        assert "Associated segment not found" in result.error


class TestApproveSuggestionOwnership:
    """Test ownership/authorization scenarios."""

    @pytest.mark.asyncio
    async def test_wrong_user(self):
        """Error when user doesn't own the suggestion."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        segment = make_segment(status="suggested")
        segment_repo.add(segment)

        # Suggestion belongs to user 1
        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        # User 2 tries to approve
        result = await use_case.execute(
            user_id=2,
            suggestion_id=suggestion.id,
            name="Valid Name",
        )

        assert result.success is False
        assert "different user" in result.error

    @pytest.mark.asyncio
    async def test_already_dismissed(self):
        """Error when suggestion was already dismissed."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        segment = make_segment(status="suggested")
        segment_repo.add(segment)

        # Already dismissed suggestion
        suggestion = make_suggestion(
            segment_id=segment.id,
            user_id=1,
            dismissed_at=datetime.now(),
        )
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="Valid Name",
        )

        assert result.success is False
        assert "already been dismissed" in result.error

    @pytest.mark.asyncio
    async def test_segment_already_approved(self):
        """Error when segment is already approved."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        # Segment is already approved
        segment = make_segment(status="approved")
        segment_repo.add(segment)

        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="Valid Name",
        )

        assert result.success is False
        assert "already been approved" in result.error


class TestApproveSuggestionDuplicateDetection:
    """Test duplicate segment detection."""

    @pytest.mark.asyncio
    async def test_no_duplicate_when_no_approved_segments(self):
        """No duplicate when there are no approved segments."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        segment = make_segment(status="suggested")
        segment_repo.add(segment)

        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="First Segment",
        )

        assert result.success is True
        assert result.duplicate_segment is None

    @pytest.mark.asyncio
    async def test_no_duplicate_when_far_apart(self):
        """No duplicate when segments are geographically distant."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        # Existing approved segment in one location
        existing = make_segment(
            status="approved",
            name="Existing",
            start_lat=46.9,
            start_lon=7.4,
            end_lat=46.91,
            end_lon=7.41,
        )
        segment_repo.add(existing)

        # New segment far away (different city)
        new_segment = make_segment(
            status="suggested",
            start_lat=47.5,  # ~60km away
            start_lon=8.0,
            end_lat=47.51,
            end_lon=8.01,
        )
        segment_repo.add(new_segment)

        suggestion = make_suggestion(segment_id=new_segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="New Segment",
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_duplicate_detected_exact_match(self):
        """Duplicate detected when segments are identical."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        # Create a polyline for both segments
        points = [(46.9, 7.4), (46.905, 7.405), (46.91, 7.41)]
        polyline = encode_polyline(points)

        # Existing approved segment
        existing = make_segment(
            status="approved",
            name="Existing",
            start_lat=46.9,
            start_lon=7.4,
            end_lat=46.91,
            end_lon=7.41,
            polyline=polyline,
        )
        segment_repo.add(existing)

        # New segment with same geometry
        new_segment = make_segment(
            status="suggested",
            start_lat=46.9,
            start_lon=7.4,
            end_lat=46.91,
            end_lon=7.41,
            polyline=polyline,
        )
        segment_repo.add(new_segment)

        suggestion = make_suggestion(segment_id=new_segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="Duplicate Segment",
        )

        assert result.success is False
        assert "similar segment already exists" in result.error
        assert result.duplicate_segment is not None
        assert result.duplicate_segment.id == existing.id

    @pytest.mark.asyncio
    async def test_no_duplicate_start_too_far(self):
        """No duplicate when start points are > 25m apart."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        points = [(46.9, 7.4), (46.905, 7.405), (46.91, 7.41)]
        polyline = encode_polyline(points)

        # Existing approved segment
        existing = make_segment(
            status="approved",
            name="Existing",
            start_lat=46.9,
            start_lon=7.4,
            end_lat=46.91,
            end_lon=7.41,
            polyline=polyline,
        )
        segment_repo.add(existing)

        # New segment with start point 50m away (~0.00045 degrees)
        new_segment = make_segment(
            status="suggested",
            start_lat=46.9005,  # ~55m north
            start_lon=7.4,
            end_lat=46.91,  # Same end
            end_lon=7.41,
            polyline=polyline,
        )
        segment_repo.add(new_segment)

        suggestion = make_suggestion(segment_id=new_segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="Not a Duplicate",
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_no_duplicate_end_too_far(self):
        """No duplicate when end points are > 25m apart."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()

        points = [(46.9, 7.4), (46.905, 7.405), (46.91, 7.41)]
        polyline = encode_polyline(points)

        # Existing approved segment
        existing = make_segment(
            status="approved",
            name="Existing",
            start_lat=46.9,
            start_lon=7.4,
            end_lat=46.91,
            end_lon=7.41,
            polyline=polyline,
        )
        segment_repo.add(existing)

        # New segment with same start but end point 50m away
        new_segment = make_segment(
            status="suggested",
            start_lat=46.9,  # Same start
            start_lon=7.4,
            end_lat=46.9105,  # ~55m north of existing end
            end_lon=7.41,
            polyline=polyline,
        )
        segment_repo.add(new_segment)

        suggestion = make_suggestion(segment_id=new_segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(segment_repo, suggestion_repo)
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="Not a Duplicate",
        )

        assert result.success is True
