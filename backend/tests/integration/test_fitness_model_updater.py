"""
Integration tests for FitnessModelUpdater use case.

Tests CP model computation and FTP divergence notification creation,
requiring actual database operations.
"""

import json
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from trainingdash.repositories.postgres.models import (
    Activity,
    ActivityPeakPower,
    FitnessHistory,
    Notification,
)
from trainingdash.repositories.postgres.threshold_repo import PostgresThresholdRepo
from trainingdash.use_cases.fitness_model_updater import FitnessModelUpdater


def make_activity(user_id: int, started_at: datetime) -> Activity:
    """Create an activity with the given parameters."""
    return Activity(
        id=uuid4(),
        user_id=user_id,
        started_at=started_at,
        source="test",
        source_ref=f"test-{uuid4()}",
    )


def make_peak_powers(activity_id, powers: dict[int, int]) -> list[ActivityPeakPower]:
    """Create peak power records for an activity."""
    return [
        ActivityPeakPower(activity_id=activity_id, duration_seconds=dur, watts=watts)
        for dur, watts in powers.items()
    ]


class TestFitnessModelUpdater:
    """Integration tests for FitnessModelUpdater."""

    @pytest.mark.asyncio
    async def test_computes_fitness_model_and_stores_snapshot(self, db_session, seed_user):
        """Should compute CP model and store FitnessHistory row."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Create activities with peak powers that can fit the CP model
        # Need at least 2 data points in the 2-12 minute range
        activity1 = make_activity(seed_user.id, base_time - timedelta(days=2))
        db_session.add(activity1)
        await db_session.flush()

        # Typical power profile: short high power, longer lower power
        peaks1 = make_peak_powers(activity1.id, {
            5: 900,     # 5s peak power
            60: 450,    # 1 min
            120: 380,   # 2 min - in CP fitting range
            300: 320,   # 5 min - in CP fitting range
            600: 290,   # 10 min - in CP fitting range
            1200: 270,  # 20 min
        })
        for p in peaks1:
            db_session.add(p)
        await db_session.flush()

        # Run updater
        updater = FitnessModelUpdater(db_session)
        await updater.execute(seed_user.id)

        # Check FitnessHistory was created
        result = await db_session.execute(
            select(FitnessHistory).where(FitnessHistory.user_id == seed_user.id)
        )
        fitness = result.scalar_one_or_none()

        assert fitness is not None
        assert fitness.pp_watts > 0  # Peak power estimated
        assert fitness.w_prime_joules > 0  # W' calculated
        assert fitness.cp_watts > 0  # CP calculated
        assert fitness.computed_at is not None

    @pytest.mark.asyncio
    async def test_no_activities_does_nothing(self, db_session, seed_user):
        """Should handle users with no activities gracefully."""
        updater = FitnessModelUpdater(db_session)
        await updater.execute(seed_user.id)

        result = await db_session.execute(
            select(FitnessHistory).where(FitnessHistory.user_id == seed_user.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_activities_without_peaks_does_nothing(self, db_session, seed_user):
        """Should not create fitness model if no peak power data."""
        activity = make_activity(seed_user.id, datetime.now(UTC).replace(tzinfo=None))
        db_session.add(activity)
        await db_session.flush()

        updater = FitnessModelUpdater(db_session)
        await updater.execute(seed_user.id)

        result = await db_session.execute(
            select(FitnessHistory).where(FitnessHistory.user_id == seed_user.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_creates_ftp_notification_when_divergent(self, db_session, seed_user):
        """Should create notification when CP diverges >5% from FTP."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Set user's current FTP via threshold repo
        threshold_repo = PostgresThresholdRepo(db_session)
        await threshold_repo.create(
            user_id=seed_user.id,
            effective_date=date.today(),
            ftp_watts=200,  # Current FTP
            source="manual",
        )

        # Create activity with peaks suggesting higher CP (~280W)
        activity = make_activity(seed_user.id, base_time)
        db_session.add(activity)
        await db_session.flush()

        # Power profile suggesting CP around 280W (much higher than FTP of 200)
        peaks = make_peak_powers(activity.id, {
            5: 1000,
            60: 500,
            120: 400,
            300: 340,
            600: 310,
            1200: 290,
        })
        for p in peaks:
            db_session.add(p)
        await db_session.flush()

        # Run updater
        updater = FitnessModelUpdater(db_session)
        await updater.execute(seed_user.id)

        # Check notification was created
        result = await db_session.execute(
            select(Notification).where(
                Notification.user_id == seed_user.id,
                Notification.type == "ftp_suggestion",
            )
        )
        notification = result.scalar_one_or_none()

        assert notification is not None
        assert notification.status == "pending"
        assert "200W" in notification.message  # current FTP
        assert notification.payload is not None

        payload = json.loads(notification.payload)
        assert payload["current_ftp"] == 200
        assert payload["suggested_ftp"] > 200  # Should suggest higher

    @pytest.mark.asyncio
    async def test_no_notification_when_ftp_within_5_percent(self, db_session, seed_user):
        """Should not create notification when CP is within 5% of FTP."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Set FTP that matches expected CP
        threshold_repo = PostgresThresholdRepo(db_session)
        await threshold_repo.create(
            user_id=seed_user.id,
            effective_date=date.today(),
            ftp_watts=280,  # Close to expected CP
            source="manual",
        )

        activity = make_activity(seed_user.id, base_time)
        db_session.add(activity)
        await db_session.flush()

        # Power profile suggesting CP around 280W
        peaks = make_peak_powers(activity.id, {
            5: 1000,
            60: 500,
            120: 400,
            300: 340,
            600: 310,
            1200: 290,
        })
        for p in peaks:
            db_session.add(p)
        await db_session.flush()

        updater = FitnessModelUpdater(db_session)
        await updater.execute(seed_user.id)

        result = await db_session.execute(
            select(Notification).where(
                Notification.user_id == seed_user.id,
                Notification.type == "ftp_suggestion",
            )
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_no_notification_when_no_ftp_set(self, db_session, seed_user):
        """Should not create notification if user has no FTP set."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        activity = make_activity(seed_user.id, base_time)
        db_session.add(activity)
        await db_session.flush()

        peaks = make_peak_powers(activity.id, {
            5: 1000,
            120: 400,
            300: 340,
            600: 310,
        })
        for p in peaks:
            db_session.add(p)
        await db_session.flush()

        updater = FitnessModelUpdater(db_session)
        await updater.execute(seed_user.id)

        result = await db_session.execute(
            select(Notification).where(
                Notification.user_id == seed_user.id,
                Notification.type == "ftp_suggestion",
            )
        )
        # Should have no notification (no FTP to compare against)
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_batch_mode_replaces_existing_notification(self, db_session, seed_user):
        """Batch mode should replace existing pending FTP notifications."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Set low FTP
        threshold_repo = PostgresThresholdRepo(db_session)
        await threshold_repo.create(
            user_id=seed_user.id,
            effective_date=date.today(),
            ftp_watts=200,
            source="manual",
        )

        # Create existing notification
        existing = Notification(
            user_id=seed_user.id,
            type="ftp_suggestion",
            message="Old suggestion",
            payload=json.dumps({"current_ftp": 180, "suggested_ftp": 220}),
            status="pending",
        )
        db_session.add(existing)

        activity = make_activity(seed_user.id, base_time)
        db_session.add(activity)
        await db_session.flush()

        peaks = make_peak_powers(activity.id, {
            5: 1000,
            120: 400,
            300: 340,
            600: 310,
            1200: 290,
        })
        for p in peaks:
            db_session.add(p)
        await db_session.flush()

        # Run in batch mode
        updater = FitnessModelUpdater(db_session)
        await updater.execute(seed_user.id, activity_count=50)

        result = await db_session.execute(
            select(Notification).where(
                Notification.user_id == seed_user.id,
                Notification.type == "ftp_suggestion",
                Notification.status == "pending",
            )
        )
        notifications = result.scalars().all()

        # Should only have one notification (old one replaced)
        assert len(notifications) == 1
        payload = json.loads(notifications[0].payload)
        assert payload.get("batch_import") is True
        assert payload.get("activity_count") == 50

    @pytest.mark.asyncio
    async def test_single_mode_updates_existing_notification(self, db_session, seed_user):
        """Single ingest mode should update existing notification in place."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        threshold_repo = PostgresThresholdRepo(db_session)
        await threshold_repo.create(
            user_id=seed_user.id,
            effective_date=date.today(),
            ftp_watts=200,
            source="manual",
        )

        # Create existing notification
        existing = Notification(
            user_id=seed_user.id,
            type="ftp_suggestion",
            message="Old suggestion",
            payload=json.dumps({"current_ftp": 180, "suggested_ftp": 220}),
            status="pending",
        )
        db_session.add(existing)
        await db_session.flush()
        existing_id = existing.id

        activity = make_activity(seed_user.id, base_time)
        db_session.add(activity)
        await db_session.flush()

        peaks = make_peak_powers(activity.id, {
            5: 1000,
            120: 400,
            300: 340,
            600: 310,
            1200: 290,
        })
        for p in peaks:
            db_session.add(p)
        await db_session.flush()

        # Run in single mode (no activity_count)
        updater = FitnessModelUpdater(db_session)
        await updater.execute(seed_user.id)

        result = await db_session.execute(
            select(Notification).where(
                Notification.user_id == seed_user.id,
                Notification.type == "ftp_suggestion",
                Notification.status == "pending",
            )
        )
        notifications = result.scalars().all()

        # Should still only have one, same ID, updated content
        assert len(notifications) == 1
        assert notifications[0].id == existing_id
        assert "Old suggestion" not in notifications[0].message

    @pytest.mark.asyncio
    async def test_aggregates_peaks_across_multiple_activities(self, db_session, seed_user):
        """Should use best peaks across all user's activities."""
        base_time = datetime.now(UTC).replace(tzinfo=None)

        # Activity 1: better at short durations
        activity1 = make_activity(seed_user.id, base_time - timedelta(days=5))
        db_session.add(activity1)
        await db_session.flush()

        peaks1 = make_peak_powers(activity1.id, {
            5: 1100,   # Best 5s
            120: 350,
            300: 300,
        })
        for p in peaks1:
            db_session.add(p)

        # Activity 2: better at longer durations
        activity2 = make_activity(seed_user.id, base_time - timedelta(days=1))
        db_session.add(activity2)
        await db_session.flush()

        peaks2 = make_peak_powers(activity2.id, {
            5: 900,
            120: 400,   # Best 2min
            300: 340,   # Best 5min
            600: 300,   # Only 10min
        })
        for p in peaks2:
            db_session.add(p)
        await db_session.flush()

        updater = FitnessModelUpdater(db_session)
        await updater.execute(seed_user.id)

        result = await db_session.execute(
            select(FitnessHistory).where(FitnessHistory.user_id == seed_user.id)
        )
        fitness = result.scalar_one()

        # Peak power should use the best 5s from activity1
        assert fitness.pp_watts >= 1000  # Should be close to 1100

    @pytest.mark.asyncio
    async def test_user_isolation(self, db_session, seed_user):
        """Should only use activities from the specified user."""
        from trainingdash.repositories.postgres.models import User

        base_time = datetime.now(UTC).replace(tzinfo=None)

        other_user = User(email="other@example.com", password_hash="hash")
        db_session.add(other_user)
        await db_session.flush()

        # Activity for other user (should be ignored)
        other_activity = make_activity(other_user.id, base_time)
        db_session.add(other_activity)
        await db_session.flush()

        peaks = make_peak_powers(other_activity.id, {
            5: 1200,
            120: 500,
            300: 400,
        })
        for p in peaks:
            db_session.add(p)
        await db_session.flush()

        # Run for seed_user who has no activities
        updater = FitnessModelUpdater(db_session)
        await updater.execute(seed_user.id)

        result = await db_session.execute(
            select(FitnessHistory).where(FitnessHistory.user_id == seed_user.id)
        )
        # Should have no fitness history (no activities for seed_user)
        assert result.scalar_one_or_none() is None
