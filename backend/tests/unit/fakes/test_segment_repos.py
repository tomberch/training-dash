"""Unit tests for fake segment repositories."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from tests.fakes.segment_repos import (
    FakeSegmentEffortRepo,
    FakeSegmentRepo,
    FakeSegmentSuggestionRepo,
)
from trainingdash.repositories.postgres.models import (
    Segment,
    SegmentEffort,
    SegmentSuggestion,
)


def make_segment(
    *,
    name: str = "Test Climb",
    type: str = "climb",
    status: str = "approved",
    climb_category: str | None = "3",
    distance_m: float = 2000.0,
    elevation_gain_m: float = 150.0,
    effort_count: int = 0,
    athlete_count: int = 0,
) -> Segment:
    """Create a test segment with minimal required fields."""
    return Segment(
        id=uuid4(),
        name=name,
        type=type,
        status=status,
        climb_category=climb_category,
        polyline="encoded_polyline",
        start_point="POINT(7.0 46.0)",  # Simplified for fake
        end_point="POINT(7.1 46.1)",
        bounds="POLYGON((7 46, 7.1 46, 7.1 46.1, 7 46.1, 7 46))",
        distance_m=distance_m,
        elevation_gain_m=elevation_gain_m,
        avg_grade_pct=7.5,
        max_grade_pct=12.0,
        gradient_segments=[{"distance_m": 500, "grade_pct": 7.5}],
        effort_count=effort_count,
        athlete_count=athlete_count,
    )


def make_effort(
    *,
    segment_id: "uuid4",
    activity_id: "uuid4",
    user_id: int = 1,
    elapsed_time_seconds: int = 600,
    start_index: int = 100,
    end_index: int = 200,
    is_pr: bool = False,
    avg_power_watts: int | None = 250,
) -> SegmentEffort:
    """Create a test segment effort."""
    return SegmentEffort(
        id=uuid4(),
        segment_id=segment_id,
        activity_id=activity_id,
        user_id=user_id,
        started_at=datetime.now(),
        elapsed_time_seconds=elapsed_time_seconds,
        avg_power_watts=avg_power_watts,
        start_index=start_index,
        end_index=end_index,
        is_pr=is_pr,
    )


def make_suggestion(
    *,
    segment_id: "uuid4",
    user_id: int = 1,
    repetition_count: int = 3,
) -> SegmentSuggestion:
    """Create a test segment suggestion."""
    now = datetime.now()
    return SegmentSuggestion(
        id=uuid4(),
        segment_id=segment_id,
        user_id=user_id,
        repetition_count=repetition_count,
        first_ridden_at=now - timedelta(days=30),
        last_ridden_at=now,
        expires_at=now + timedelta(days=90),
    )


# =============================================================================
# FakeSegmentRepo Tests
# =============================================================================


class TestFakeSegmentRepo:
    """Tests for FakeSegmentRepo."""

    @pytest.fixture
    def repo(self) -> FakeSegmentRepo:
        return FakeSegmentRepo()

    @pytest.mark.asyncio
    async def test_save_and_get_by_id(self, repo: FakeSegmentRepo):
        segment = make_segment(name="Col du Test")
        await repo.save(segment)

        result = await repo.get_by_id(segment.id)
        assert result is not None
        assert result.name == "Col du Test"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo: FakeSegmentRepo):
        result = await repo.get_by_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_soft_deleted(self, repo: FakeSegmentRepo):
        segment = make_segment()
        await repo.save(segment)
        await repo.soft_delete(segment.id)

        result = await repo.get_by_id(segment.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_approved_excludes_suggested(self, repo: FakeSegmentRepo):
        approved = make_segment(name="Approved", status="approved")
        suggested = make_segment(name="Suggested", status="suggested")
        await repo.save(approved)
        await repo.save(suggested)

        result = await repo.list_approved()
        assert len(result) == 1
        assert result[0].name == "Approved"

    @pytest.mark.asyncio
    async def test_list_approved_filter_by_type(self, repo: FakeSegmentRepo):
        climb = make_segment(name="Climb", type="climb")
        sprint = make_segment(name="Sprint", type="sprint", climb_category=None)
        await repo.save(climb)
        await repo.save(sprint)

        result = await repo.list_approved(type="climb")
        assert len(result) == 1
        assert result[0].name == "Climb"

    @pytest.mark.asyncio
    async def test_list_approved_filter_by_category(self, repo: FakeSegmentRepo):
        cat1 = make_segment(name="Cat 1", climb_category="1")
        cat3 = make_segment(name="Cat 3", climb_category="3")
        await repo.save(cat1)
        await repo.save(cat3)

        result = await repo.list_approved(category=["1", "2"])
        assert len(result) == 1
        assert result[0].name == "Cat 1"

    @pytest.mark.asyncio
    async def test_list_approved_search(self, repo: FakeSegmentRepo):
        col = make_segment(name="Col du Galibier")
        alpe = make_segment(name="Alpe d'Huez")
        await repo.save(col)
        await repo.save(alpe)

        result = await repo.list_approved(search="galibier")
        assert len(result) == 1
        assert result[0].name == "Col du Galibier"

    @pytest.mark.asyncio
    async def test_list_approved_sorting(self, repo: FakeSegmentRepo):
        short = make_segment(name="Short", distance_m=1000)
        long = make_segment(name="Long", distance_m=5000)
        await repo.save(short)
        await repo.save(long)

        result = await repo.list_approved(sort="distance", order="desc")
        assert result[0].name == "Long"
        assert result[1].name == "Short"

    @pytest.mark.asyncio
    async def test_list_approved_pagination(self, repo: FakeSegmentRepo):
        for i in range(5):
            await repo.save(make_segment(name=f"Segment {i}", effort_count=i))

        result = await repo.list_approved(sort="popularity", order="desc", limit=2, offset=1)
        assert len(result) == 2
        assert result[0].name == "Segment 3"
        assert result[1].name == "Segment 2"

    @pytest.mark.asyncio
    async def test_count_approved(self, repo: FakeSegmentRepo):
        await repo.save(make_segment(status="approved"))
        await repo.save(make_segment(status="approved"))
        await repo.save(make_segment(status="suggested"))

        count = await repo.count_approved()
        assert count == 2

    @pytest.mark.asyncio
    async def test_soft_delete(self, repo: FakeSegmentRepo):
        segment = make_segment()
        await repo.save(segment)

        result = await repo.soft_delete(segment.id)
        assert result is True

        # Verify soft-deleted
        stored = repo._segments[segment.id]
        assert stored.deleted_at is not None

    @pytest.mark.asyncio
    async def test_soft_delete_not_found(self, repo: FakeSegmentRepo):
        result = await repo.soft_delete(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_increment_counts(self, repo: FakeSegmentRepo):
        segment = make_segment(effort_count=5, athlete_count=3)
        await repo.save(segment)

        await repo.increment_counts(segment.id, new_athlete=False)
        assert segment.effort_count == 6
        assert segment.athlete_count == 3

        await repo.increment_counts(segment.id, new_athlete=True)
        assert segment.effort_count == 7
        assert segment.athlete_count == 4

    @pytest.mark.asyncio
    async def test_find_candidates_for_matching(self, repo: FakeSegmentRepo):
        approved = make_segment(status="approved")
        suggested = make_segment(status="suggested")
        await repo.save(approved)
        await repo.save(suggested)

        # Fake impl returns all approved segments
        result = await repo.find_candidates_for_matching(bounds=None, direction_bearing=45.0)
        assert len(result) == 1
        assert result[0].id == approved.id

    def test_clear(self, repo: FakeSegmentRepo):
        repo.add(make_segment())
        repo.add(make_segment())
        assert len(repo.all()) == 2

        repo.clear()
        assert len(repo.all()) == 0


# =============================================================================
# FakeSegmentEffortRepo Tests
# =============================================================================


class TestFakeSegmentEffortRepo:
    """Tests for FakeSegmentEffortRepo."""

    @pytest.fixture
    def repo(self) -> FakeSegmentEffortRepo:
        return FakeSegmentEffortRepo()

    @pytest.mark.asyncio
    async def test_save_and_get_by_id(self, repo: FakeSegmentEffortRepo):
        segment_id = uuid4()
        activity_id = uuid4()
        effort = make_effort(segment_id=segment_id, activity_id=activity_id)
        await repo.save(effort)

        result = await repo.get_by_id(effort.id)
        assert result is not None
        assert result.segment_id == segment_id

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo: FakeSegmentEffortRepo):
        result = await repo.get_by_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_for_segment(self, repo: FakeSegmentEffortRepo):
        segment_id = uuid4()
        activity_id = uuid4()

        effort1 = make_effort(segment_id=segment_id, activity_id=activity_id, user_id=1, elapsed_time_seconds=600)
        effort2 = make_effort(segment_id=segment_id, activity_id=activity_id, user_id=1, elapsed_time_seconds=500)
        effort3 = make_effort(segment_id=segment_id, activity_id=activity_id, user_id=2, elapsed_time_seconds=550)
        await repo.save(effort1)
        await repo.save(effort2)
        await repo.save(effort3)

        # Only user 1's efforts
        result = await repo.list_for_segment(segment_id, user_id=1)
        assert len(result) == 2

        # Sorted by time ascending (default)
        assert result[0].elapsed_time_seconds == 500
        assert result[1].elapsed_time_seconds == 600

    @pytest.mark.asyncio
    async def test_list_for_segment_sort_by_power(self, repo: FakeSegmentEffortRepo):
        segment_id = uuid4()
        activity_id = uuid4()

        effort1 = make_effort(segment_id=segment_id, activity_id=activity_id, avg_power_watts=200)
        effort2 = make_effort(segment_id=segment_id, activity_id=activity_id, avg_power_watts=300)
        await repo.save(effort1)
        await repo.save(effort2)

        result = await repo.list_for_segment(segment_id, user_id=1, sort="power", order="desc")
        assert result[0].avg_power_watts == 300
        assert result[1].avg_power_watts == 200

    @pytest.mark.asyncio
    async def test_list_for_activity(self, repo: FakeSegmentEffortRepo):
        activity_id = uuid4()

        effort1 = make_effort(segment_id=uuid4(), activity_id=activity_id, start_index=200)
        effort2 = make_effort(segment_id=uuid4(), activity_id=activity_id, start_index=100)
        effort3 = make_effort(segment_id=uuid4(), activity_id=uuid4(), start_index=50)  # Different activity
        await repo.save(effort1)
        await repo.save(effort2)
        await repo.save(effort3)

        result = await repo.list_for_activity(activity_id)
        assert len(result) == 2
        # Ordered by start_index
        assert result[0].start_index == 100
        assert result[1].start_index == 200

    @pytest.mark.asyncio
    async def test_get_user_pr(self, repo: FakeSegmentEffortRepo):
        segment_id = uuid4()
        activity_id = uuid4()

        effort1 = make_effort(segment_id=segment_id, activity_id=activity_id, is_pr=False)
        effort2 = make_effort(segment_id=segment_id, activity_id=activity_id, is_pr=True)
        await repo.save(effort1)
        await repo.save(effort2)

        result = await repo.get_user_pr(segment_id, user_id=1)
        assert result is not None
        assert result.id == effort2.id

    @pytest.mark.asyncio
    async def test_get_user_pr_not_found(self, repo: FakeSegmentEffortRepo):
        result = await repo.get_user_pr(uuid4(), user_id=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_clear_user_pr(self, repo: FakeSegmentEffortRepo):
        segment_id = uuid4()
        activity_id = uuid4()

        effort = make_effort(segment_id=segment_id, activity_id=activity_id, is_pr=True)
        await repo.save(effort)

        await repo.clear_user_pr(segment_id, user_id=1)

        result = await repo.get_user_pr(segment_id, user_id=1)
        assert result is None
        assert effort.is_pr is False

    def test_clear(self, repo: FakeSegmentEffortRepo):
        repo.add(make_effort(segment_id=uuid4(), activity_id=uuid4()))
        repo.add(make_effort(segment_id=uuid4(), activity_id=uuid4()))
        assert len(repo.all()) == 2

        repo.clear()
        assert len(repo.all()) == 0


# =============================================================================
# FakeSegmentSuggestionRepo Tests
# =============================================================================


class TestFakeSegmentSuggestionRepo:
    """Tests for FakeSegmentSuggestionRepo."""

    @pytest.fixture
    def repo(self) -> FakeSegmentSuggestionRepo:
        return FakeSegmentSuggestionRepo()

    @pytest.mark.asyncio
    async def test_save_and_get_by_id(self, repo: FakeSegmentSuggestionRepo):
        segment_id = uuid4()
        suggestion = make_suggestion(segment_id=segment_id)
        await repo.save(suggestion)

        result = await repo.get_by_id(suggestion.id)
        assert result is not None
        assert result.segment_id == segment_id

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo: FakeSegmentSuggestionRepo):
        result = await repo.get_by_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_list_for_user(self, repo: FakeSegmentSuggestionRepo):
        s1 = make_suggestion(segment_id=uuid4(), user_id=1, repetition_count=5)
        s2 = make_suggestion(segment_id=uuid4(), user_id=1, repetition_count=3)
        s3 = make_suggestion(segment_id=uuid4(), user_id=2, repetition_count=10)
        await repo.save(s1)
        await repo.save(s2)
        await repo.save(s3)

        result = await repo.list_for_user(user_id=1)
        assert len(result) == 2
        # Sorted by repetition_count descending
        assert result[0].repetition_count == 5
        assert result[1].repetition_count == 3

    @pytest.mark.asyncio
    async def test_list_for_user_excludes_dismissed(self, repo: FakeSegmentSuggestionRepo):
        s1 = make_suggestion(segment_id=uuid4(), user_id=1)
        s2 = make_suggestion(segment_id=uuid4(), user_id=1)
        await repo.save(s1)
        await repo.save(s2)
        await repo.dismiss(s1.id)

        result = await repo.list_for_user(user_id=1, include_dismissed=False)
        assert len(result) == 1

        result_all = await repo.list_for_user(user_id=1, include_dismissed=True)
        assert len(result_all) == 2

    @pytest.mark.asyncio
    async def test_list_for_user_pagination(self, repo: FakeSegmentSuggestionRepo):
        for i in range(5):
            await repo.save(make_suggestion(segment_id=uuid4(), user_id=1, repetition_count=i))

        result = await repo.list_for_user(user_id=1, limit=2, offset=1)
        assert len(result) == 2
        assert result[0].repetition_count == 3
        assert result[1].repetition_count == 2

    @pytest.mark.asyncio
    async def test_count_for_user(self, repo: FakeSegmentSuggestionRepo):
        await repo.save(make_suggestion(segment_id=uuid4(), user_id=1))
        await repo.save(make_suggestion(segment_id=uuid4(), user_id=1))
        await repo.save(make_suggestion(segment_id=uuid4(), user_id=2))

        count = await repo.count_for_user(user_id=1)
        assert count == 2

    @pytest.mark.asyncio
    async def test_dismiss(self, repo: FakeSegmentSuggestionRepo):
        suggestion = make_suggestion(segment_id=uuid4())
        await repo.save(suggestion)

        result = await repo.dismiss(suggestion.id)
        assert result is True
        assert suggestion.dismissed_at is not None

    @pytest.mark.asyncio
    async def test_dismiss_not_found(self, repo: FakeSegmentSuggestionRepo):
        result = await repo.dismiss(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_dismiss_already_dismissed(self, repo: FakeSegmentSuggestionRepo):
        suggestion = make_suggestion(segment_id=uuid4())
        await repo.save(suggestion)
        await repo.dismiss(suggestion.id)

        result = await repo.dismiss(suggestion.id)
        assert result is False  # Already dismissed

    @pytest.mark.asyncio
    async def test_dismiss_all(self, repo: FakeSegmentSuggestionRepo):
        s1 = make_suggestion(segment_id=uuid4(), user_id=1)
        s2 = make_suggestion(segment_id=uuid4(), user_id=1)
        s3 = make_suggestion(segment_id=uuid4(), user_id=2)
        await repo.save(s1)
        await repo.save(s2)
        await repo.save(s3)

        count = await repo.dismiss_all(user_id=1)
        assert count == 2
        assert s1.dismissed_at is not None
        assert s2.dismissed_at is not None
        assert s3.dismissed_at is None  # Different user

    @pytest.mark.asyncio
    async def test_get_for_user_segment(self, repo: FakeSegmentSuggestionRepo):
        segment_id = uuid4()
        suggestion = make_suggestion(segment_id=segment_id, user_id=1)
        await repo.save(suggestion)

        result = await repo.get_for_user_segment(user_id=1, segment_id=segment_id)
        assert result is not None
        assert result.id == suggestion.id

    @pytest.mark.asyncio
    async def test_get_for_user_segment_not_found(self, repo: FakeSegmentSuggestionRepo):
        result = await repo.get_for_user_segment(user_id=1, segment_id=uuid4())
        assert result is None

    def test_clear(self, repo: FakeSegmentSuggestionRepo):
        repo.add(make_suggestion(segment_id=uuid4()))
        repo.add(make_suggestion(segment_id=uuid4()))
        assert len(repo.all()) == 2

        repo.clear()
        assert len(repo.all()) == 0
