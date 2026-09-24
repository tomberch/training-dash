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


class FakeRecord:
    """Fake Record row with the fields geometry computation needs."""

    def __init__(self, lat: float, lon: float, altitude_m: float, distance_m: float) -> None:
        self.lat = lat
        self.lon = lon
        self.altitude_m = altitude_m
        self.distance_m = distance_m


class FakeRecordRepo:
    """In-memory RecordRepo stand-in: 5 points straight north, ~111m apart.

    Total span ~444m, climbing from 500m to 530m elevation.
    """

    def __init__(self) -> None:
        self.activity_id = uuid4()
        self.read_count = 0
        self._records = [
            FakeRecord(46.9000, 7.4000, 500.0, 0.0),
            FakeRecord(46.9010, 7.4000, 508.0, 111.0),
            FakeRecord(46.9020, 7.4000, 516.0, 222.0),
            FakeRecord(46.9030, 7.4000, 523.0, 333.0),
            FakeRecord(46.9040, 7.4000, 530.0, 444.0),
        ]

    async def list_for_activity(self, activity_id) -> list[FakeRecord]:
        self.read_count += 1
        if activity_id == self.activity_id:
            return list(self._records)
        return []


class FakeActivity:
    """Fake Activity row for ownership checks."""

    def __init__(self, activity_id, user_id: int) -> None:
        self.id = activity_id
        self.user_id = user_id


class FakeActivityRepo:
    """In-memory ActivityRepo.get_by_id stand-in enforcing ownership."""

    def __init__(self, owner_id: int) -> None:
        self._owner_id = owner_id

    async def get_by_id(self, activity_id, user_id: int):
        if user_id == self._owner_id:
            return FakeActivity(activity_id, user_id)
        return None


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
        elevation_profile=[
            {"distance_m": 0, "elevation_m": 500, "grade_pct": 0},
            {"distance_m": 50, "elevation_m": 505, "grade_pct": 10},
        ],
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


class TestApproveWithEndpointOverrides:
    """Approving with adjusted start/end rewrites the segment geometry.

    The suggestion's detected indices can be fine-tuned by the user before
    approval; the approved segment then carries the adjusted geometry and
    matches future rides accordingly.
    """

    @pytest.mark.asyncio
    async def test_approve_with_overrides_rewrites_geometry(self):
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()
        record_repo = FakeRecordRepo()

        segment = make_segment(status="suggested")
        segment.source_activity_id = record_repo.activity_id
        segment_repo.add(segment)

        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(
            segment_repo, suggestion_repo, record_repo=record_repo, activity_repo=FakeActivityRepo(owner_id=1)
        )
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="Adjusted Climb",
            start_index=0,
            end_index=4,  # Full range — default geometry used only 2 of 5 points
        )

        assert result.success is True, result.error
        assert result.segment is not None
        # Geometry now spans the full 5-point track (~444m), not the 2-point default
        assert result.segment.distance_m == pytest.approx(444.0, abs=1.0)

    @pytest.mark.asyncio
    async def test_approve_without_overrides_keeps_geometry(self):
        """No overrides → detected geometry is preserved (current behavior)."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()
        record_repo = FakeRecordRepo()

        segment = make_segment(status="suggested")
        segment.source_activity_id = record_repo.activity_id
        original_polyline = segment.polyline
        segment_repo.add(segment)

        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(
            segment_repo, suggestion_repo, record_repo=record_repo, activity_repo=FakeActivityRepo(owner_id=1)
        )
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="Unchanged Climb",
        )

        assert result.success is True, result.error
        assert result.segment.polyline == original_polyline
        assert result.segment.distance_m == 1000.0

    @pytest.mark.asyncio
    async def test_approve_with_invalid_indices_fails(self):
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()
        record_repo = FakeRecordRepo()

        segment = make_segment(status="suggested")
        segment.source_activity_id = record_repo.activity_id
        segment_repo.add(segment)

        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(
            segment_repo, suggestion_repo, record_repo=record_repo, activity_repo=FakeActivityRepo(owner_id=1)
        )
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="Bad Indices",
            start_index=3,
            end_index=1,  # end before start
        )

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_approve_with_overrides_missing_source_activity_fails(self):
        """A suggested segment with no source activity can't be adjusted."""
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()
        record_repo = FakeRecordRepo()

        segment = make_segment(status="suggested")
        segment.source_activity_id = None
        segment_repo.add(segment)

        suggestion = make_suggestion(segment_id=segment.id, user_id=1)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(
            segment_repo, suggestion_repo, record_repo=record_repo, activity_repo=FakeActivityRepo(owner_id=1)
        )
        result = await use_case.execute(
            user_id=1,
            suggestion_id=suggestion.id,
            name="No Source",
            start_index=0,
            end_index=4,
        )

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_approve_with_overrides_rejects_unowned_source_activity(self):
        """The source activity must belong to the approving user.

        Suggested segments are global — a second user approving the same
        climb must not be able to read user A's GPS track by passing
        crafted indices. Mirrors CreateSegment's ownership check.
        """
        segment_repo = FakeSegmentRepo()
        suggestion_repo = FakeSegmentSuggestionRepo()
        record_repo = FakeRecordRepo()
        # record_repo.activity_id is owned by user 1 (fake returns records
        # regardless of user); the activity repo mediates ownership
        activity_repo = FakeActivityRepo(owner_id=1)

        segment = make_segment(status="suggested")
        segment.source_activity_id = record_repo.activity_id
        segment_repo.add(segment)

        # User 2 approves the shared suggestion
        suggestion = make_suggestion(segment_id=segment.id, user_id=2)
        suggestion_repo.add(suggestion)

        use_case = ApproveSuggestion(
            segment_repo, suggestion_repo, record_repo=record_repo, activity_repo=activity_repo
        )
        result = await use_case.execute(
            user_id=2,
            suggestion_id=suggestion.id,
            name="Stolen Track",
            start_index=0,
            end_index=4,
        )

        assert result.success is False
        assert result.error is not None
        # No records were read
        assert record_repo.read_count == 0


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
