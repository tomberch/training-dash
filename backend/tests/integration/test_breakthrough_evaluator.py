"""
Integration tests for BreakthroughEvaluator use case.

Tests the re-evaluation of is_breakthrough flags across all activities
for a user, requiring actual database operations.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from trainingdash.repositories.postgres.models import Activity, ActivityPeakPower
from trainingdash.use_cases.breakthrough_evaluator import BreakthroughEvaluator


def make_activity(user_id: int, started_at: datetime, is_breakthrough: bool = False) -> Activity:
    """Create an activity with the given parameters."""
    return Activity(
        id=uuid4(),
        user_id=user_id,
        started_at=started_at,
        source="test",
        source_ref=f"test-{uuid4()}",
        is_breakthrough=is_breakthrough,
    )


def make_peak_power(activity_id, duration_seconds: int, watts: int) -> ActivityPeakPower:
    """Create a peak power record."""
    return ActivityPeakPower(
        activity_id=activity_id,
        duration_seconds=duration_seconds,
        watts=watts,
    )


class TestBreakthroughEvaluator:
    """Integration tests for BreakthroughEvaluator."""

    @pytest.mark.asyncio
    async def test_first_activity_is_breakthrough(self, db_session, seed_user):
        """First activity with power data should be a breakthrough."""
        now = datetime.now(UTC).replace(tzinfo=None)

        # Create activity
        activity = make_activity(seed_user.id, now, is_breakthrough=False)
        db_session.add(activity)
        await db_session.flush()

        # Add peak powers at breakthrough durations (5s, 60s, 300s, 1200s)
        peaks = [
            make_peak_power(activity.id, 5, 800),
            make_peak_power(activity.id, 60, 400),
            make_peak_power(activity.id, 300, 300),
            make_peak_power(activity.id, 1200, 250),
        ]
        for p in peaks:
            db_session.add(p)
        await db_session.flush()

        # Run evaluator
        evaluator = BreakthroughEvaluator(db_session)
        await evaluator.execute(seed_user.id)

        # First activity should be a breakthrough
        await db_session.refresh(activity)
        assert activity.is_breakthrough is True

    @pytest.mark.asyncio
    async def test_second_activity_higher_power_is_breakthrough(self, db_session, seed_user):
        """Second activity that beats PRs should be a breakthrough."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # First activity
        activity1 = make_activity(seed_user.id, base_time - timedelta(days=2))
        db_session.add(activity1)
        await db_session.flush()

        peaks1 = [
            make_peak_power(activity1.id, 5, 800),
            make_peak_power(activity1.id, 60, 400),
            make_peak_power(activity1.id, 300, 300),
        ]
        for p in peaks1:
            db_session.add(p)

        # Second activity with higher power
        activity2 = make_activity(seed_user.id, base_time - timedelta(days=1))
        db_session.add(activity2)
        await db_session.flush()

        peaks2 = [
            make_peak_power(activity2.id, 5, 850),  # New PR!
            make_peak_power(activity2.id, 60, 420),  # New PR!
            make_peak_power(activity2.id, 300, 310),  # New PR!
        ]
        for p in peaks2:
            db_session.add(p)
        await db_session.flush()

        # Run evaluator
        evaluator = BreakthroughEvaluator(db_session)
        await evaluator.execute(seed_user.id)

        await db_session.refresh(activity1)
        await db_session.refresh(activity2)

        assert activity1.is_breakthrough is True  # First activity
        assert activity2.is_breakthrough is True  # Beat PRs

    @pytest.mark.asyncio
    async def test_second_activity_lower_power_not_breakthrough(self, db_session, seed_user):
        """Second activity with lower power should not be a breakthrough."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # First activity with high power
        activity1 = make_activity(seed_user.id, base_time - timedelta(days=2))
        db_session.add(activity1)
        await db_session.flush()

        peaks1 = [
            make_peak_power(activity1.id, 5, 850),
            make_peak_power(activity1.id, 60, 420),
            make_peak_power(activity1.id, 300, 310),
        ]
        for p in peaks1:
            db_session.add(p)

        # Second activity with lower power
        activity2 = make_activity(seed_user.id, base_time - timedelta(days=1))
        db_session.add(activity2)
        await db_session.flush()

        peaks2 = [
            make_peak_power(activity2.id, 5, 800),  # Below PR
            make_peak_power(activity2.id, 60, 400),  # Below PR
            make_peak_power(activity2.id, 300, 300),  # Below PR
        ]
        for p in peaks2:
            db_session.add(p)
        await db_session.flush()

        # Run evaluator
        evaluator = BreakthroughEvaluator(db_session)
        await evaluator.execute(seed_user.id)

        await db_session.refresh(activity1)
        await db_session.refresh(activity2)

        assert activity1.is_breakthrough is True  # First activity
        assert activity2.is_breakthrough is False  # Didn't beat any PRs

    @pytest.mark.asyncio
    async def test_partial_breakthrough_at_single_duration(self, db_session, seed_user):
        """Activity that beats PR at just one duration is still a breakthrough."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # First activity
        activity1 = make_activity(seed_user.id, base_time - timedelta(days=2))
        db_session.add(activity1)
        await db_session.flush()

        peaks1 = [
            make_peak_power(activity1.id, 5, 800),
            make_peak_power(activity1.id, 60, 400),
            make_peak_power(activity1.id, 300, 300),
        ]
        for p in peaks1:
            db_session.add(p)

        # Second activity - only beats 5s PR
        activity2 = make_activity(seed_user.id, base_time - timedelta(days=1))
        db_session.add(activity2)
        await db_session.flush()

        peaks2 = [
            make_peak_power(activity2.id, 5, 850),  # New PR!
            make_peak_power(activity2.id, 60, 380),  # Below PR
            make_peak_power(activity2.id, 300, 290),  # Below PR
        ]
        for p in peaks2:
            db_session.add(p)
        await db_session.flush()

        # Run evaluator
        evaluator = BreakthroughEvaluator(db_session)
        await evaluator.execute(seed_user.id)

        await db_session.refresh(activity2)
        assert activity2.is_breakthrough is True  # Beat at least one PR

    @pytest.mark.asyncio
    async def test_evaluator_corrects_wrong_flags(self, db_session, seed_user):
        """Evaluator should correct incorrectly set breakthrough flags."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # First activity marked as not breakthrough (incorrect)
        activity1 = make_activity(seed_user.id, base_time - timedelta(days=2), is_breakthrough=False)
        db_session.add(activity1)
        await db_session.flush()

        peaks1 = [make_peak_power(activity1.id, 5, 800)]
        db_session.add(peaks1[0])

        # Second activity marked as breakthrough (incorrect - lower power)
        activity2 = make_activity(seed_user.id, base_time - timedelta(days=1), is_breakthrough=True)
        db_session.add(activity2)
        await db_session.flush()

        peaks2 = [make_peak_power(activity2.id, 5, 700)]  # Lower than first
        db_session.add(peaks2[0])
        await db_session.flush()

        # Run evaluator
        evaluator = BreakthroughEvaluator(db_session)
        await evaluator.execute(seed_user.id)

        await db_session.refresh(activity1)
        await db_session.refresh(activity2)

        # Should be corrected
        assert activity1.is_breakthrough is True  # First activity IS breakthrough
        assert activity2.is_breakthrough is False  # Second is NOT

    @pytest.mark.asyncio
    async def test_activity_without_peaks_not_breakthrough(self, db_session, seed_user):
        """Activity without peak power data should not be a breakthrough."""
        now = datetime.now(UTC).replace(tzinfo=None)

        # Activity without peaks
        activity = make_activity(seed_user.id, now, is_breakthrough=True)  # incorrectly marked
        db_session.add(activity)
        await db_session.flush()

        # Run evaluator
        evaluator = BreakthroughEvaluator(db_session)
        await evaluator.execute(seed_user.id)

        await db_session.refresh(activity)
        assert activity.is_breakthrough is False

    @pytest.mark.asyncio
    async def test_no_activities_does_nothing(self, db_session, seed_user):
        """Evaluator should handle users with no activities gracefully."""
        evaluator = BreakthroughEvaluator(db_session)
        # Should not raise
        await evaluator.execute(seed_user.id)

    @pytest.mark.asyncio
    async def test_chronological_evaluation(self, db_session, seed_user):
        """Activities should be evaluated in chronological order."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Create activities in reverse chronological order in DB
        # but evaluator should process them chronologically
        activity3 = make_activity(seed_user.id, base_time)  # newest
        activity1 = make_activity(seed_user.id, base_time - timedelta(days=10))  # oldest
        activity2 = make_activity(seed_user.id, base_time - timedelta(days=5))  # middle

        db_session.add(activity3)
        db_session.add(activity1)
        db_session.add(activity2)
        await db_session.flush()

        # Powers increase over time
        db_session.add(make_peak_power(activity1.id, 300, 250))
        db_session.add(make_peak_power(activity2.id, 300, 270))
        db_session.add(make_peak_power(activity3.id, 300, 290))
        await db_session.flush()

        evaluator = BreakthroughEvaluator(db_session)
        await evaluator.execute(seed_user.id)

        await db_session.refresh(activity1)
        await db_session.refresh(activity2)
        await db_session.refresh(activity3)

        # All should be breakthroughs since power increases chronologically
        assert activity1.is_breakthrough is True
        assert activity2.is_breakthrough is True
        assert activity3.is_breakthrough is True

    @pytest.mark.asyncio
    async def test_only_breakthrough_durations_matter(self, db_session, seed_user):
        """Only 5s, 60s, 300s, 1200s durations should count for breakthrough."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # First activity with breakthrough duration
        activity1 = make_activity(seed_user.id, base_time - timedelta(days=2))
        db_session.add(activity1)
        await db_session.flush()

        db_session.add(make_peak_power(activity1.id, 300, 300))  # 5 min - counts
        db_session.add(make_peak_power(activity1.id, 120, 350))  # 2 min - doesn't count

        # Second activity beats 2 min but not 5 min
        activity2 = make_activity(seed_user.id, base_time - timedelta(days=1))
        db_session.add(activity2)
        await db_session.flush()

        db_session.add(make_peak_power(activity2.id, 300, 290))  # Below 5 min PR
        db_session.add(make_peak_power(activity2.id, 120, 380))  # Above 2 min - but doesn't count
        await db_session.flush()

        evaluator = BreakthroughEvaluator(db_session)
        await evaluator.execute(seed_user.id)

        await db_session.refresh(activity2)
        assert activity2.is_breakthrough is False  # 2 min not a breakthrough duration

    @pytest.mark.asyncio
    async def test_user_isolation(self, db_session, seed_user):
        """Evaluator should only affect activities for the specified user."""
        now = datetime.now(UTC).replace(tzinfo=None)

        # Create a second user
        from trainingdash.repositories.postgres.models import User

        other_user = User(email="other@example.com", password_hash="hash")
        db_session.add(other_user)
        await db_session.flush()

        # Activity for seed_user
        activity1 = make_activity(seed_user.id, now - timedelta(days=1))
        db_session.add(activity1)
        await db_session.flush()
        db_session.add(make_peak_power(activity1.id, 300, 300))

        # Activity for other_user marked incorrectly
        activity2 = make_activity(other_user.id, now, is_breakthrough=True)
        db_session.add(activity2)
        await db_session.flush()
        # No peaks - should be False, but we won't run evaluator for other_user
        await db_session.flush()

        # Only run for seed_user
        evaluator = BreakthroughEvaluator(db_session)
        await evaluator.execute(seed_user.id)

        await db_session.refresh(activity1)
        await db_session.refresh(activity2)

        assert activity1.is_breakthrough is True
        # other_user's activity should be unchanged (still incorrectly True)
        assert activity2.is_breakthrough is True
